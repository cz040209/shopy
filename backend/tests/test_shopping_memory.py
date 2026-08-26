import json

import pytest
from fastapi import Response
from langchain_core.messages import AIMessage
from redis.exceptions import ConnectionError as RedisConnectionError

from app.agentic.auditor import ShoppingAuditor
from app.agentic.memory import (
    MemoryUnavailableError,
    RedisShoppingMemoryStore,
    ShoppingSessionMemory,
    memory_from_state,
)
from app.agentic.orchestrator import ShoppingOrchestrator
from app.models import User


class FakeRedis:
    def __init__(self):
        self.now = 0
        self.values: dict[str, tuple[str, int]] = {}

    async def set(self, key, value, *, ex):
        self.values[key] = (value, self.now + ex)

    async def get(self, key):
        value = self.values.get(key)
        if value is None:
            return None
        payload, expires_at = value
        if self.now >= expires_at:
            del self.values[key]
            return None
        return payload

    async def expire(self, key, seconds):
        payload = await self.get(key)
        if payload is None:
            return False
        self.values[key] = (payload, self.now + seconds)
        return True

    async def delete(self, key):
        self.values.pop(key, None)


class FailingRedis:
    async def get(self, key):
        raise RedisConnectionError("offline")


@pytest.mark.anyio
async def test_memory_isolated_by_scope_refreshes_ttl_and_expires_after_inactivity():
    redis = FakeRedis()
    store = RedisShoppingMemoryStore(redis, ttl_seconds=1800)
    await store.save("session-a", ShoppingSessionMemory(budget=4000, preferences=["wireless"]))
    await store.save("session-b", ShoppingSessionMemory(budget=200, preferences=["compact"]))

    assert (await store.load("session-a")).budget == 4000
    assert (await store.load("session-b")).preferences == ["compact"]

    redis.now = 1799
    # Reading an active session refreshes its 30-minute inactivity window.
    assert (await store.load("session-a")).budget == 4000
    redis.now = 1800
    assert (await store.load("session-a")).budget == 4000
    redis.now = 3600
    assert await store.load("session-a") is None
    assert await store.load("session-b") is None


@pytest.mark.anyio
async def test_memory_store_reports_redis_unavailability_without_returning_stale_context():
    store = RedisShoppingMemoryStore(FailingRedis(), ttl_seconds=1800)

    with pytest.raises(MemoryUnavailableError):
        await store.load("session-a")


def test_memory_state_keeps_recent_turns_preferences_and_product_decisions_bounded():
    memory = memory_from_state(
        ShoppingSessionMemory(preferences=["wireless"], recent_messages=[]),
        {
            "user_request": "Make it cheaper.",
            "final_response": "I found a lower-cost option.",
            "mission": {"goal": "gaming setup"},
            "budget": 4000,
            "preferences": ["wireless"],
            "constraints": ["under RM4000"],
            "owned_items": ["monitor"],
            "candidate_products": [{"id": "viewed-1"}],
            "selected_products": [{"id": "selected-1", "quantity": 1}],
            "excluded_product_ids": ["rejected-1"],
            "bundle": {"items": [{"product_id": "selected-1", "quantity": 1}]},
            "optimization_mode": "cheaper",
        },
    )

    assert [message.content for message in memory.recent_messages] == ["Make it cheaper.", "I found a lower-cost option."]
    assert memory.preferences == ["wireless"]
    assert memory.viewed_product_ids == ["viewed-1"]
    assert memory.selected_products == [{"id": "selected-1", "quantity": 1}]
    assert memory.rejected_product_ids == ["rejected-1"]
    assert memory.optimization_mode == "cheaper"


class FakeMemoryStore:
    def __init__(self, memory=None, *, fail=False):
        self.memory = memory
        self.fail = fail
        self.saved = []

    async def load(self, session_scope):
        if self.fail:
            raise MemoryUnavailableError("offline")
        return self.memory

    async def save(self, session_scope, memory):
        if self.fail:
            raise MemoryUnavailableError("offline")
        self.saved.append((session_scope, memory))
        self.memory = memory

    async def clear(self, session_scope):
        self.memory = None


@pytest.mark.anyio
async def test_graph_loads_previous_context_before_intent_and_updates_memory_after_audited_response():
    class MemoryAwareModel:
        intent_payload = None

        async def ainvoke(self, input, **kwargs):
            prompt = str(input[0].content)
            if "response-writing agent" in prompt:
                return AIMessage(content='{"response":"I will keep the existing budget and wireless preference.","product_ids":[],"unfulfilled_requirements":[]}')
            if "final brand-voice editor" in prompt:
                return AIMessage(content='{"response":"The RM4,000 wireless setup is now being optimized for a lower cost."}')
            self.intent_payload = json.loads(str(input[1].content))
            return AIMessage(content='{"mission_type":"information_request","goal":"gaming setup","requires_planning":false,"requires_catalog":false,"continues_context":true,"optimization_mode":"cheaper","catalog_query":null,"catalog_queries":[],"requested_actions":[],"budget":null,"bundle_items":[],"preferences":[],"constraints":[],"owned_items":[],"priorities":[],"fulfillment_requirements":[]}')

    model = MemoryAwareModel()
    memory_store = FakeMemoryStore(ShoppingSessionMemory(
        current_mission={"goal": "gaming setup", "catalog_query": "wireless gaming setup"},
        budget=4000,
        preferences=["wireless accessories"],
        recent_messages=[{"role": "user", "content": "Build me a gaming setup under RM4,000."}],
    ))
    result = await ShoppingOrchestrator(
        model,
        auditor=ShoppingAuditor(),
        memory_store=memory_store,
    ).ainvoke("Make it cheaper.", state_overrides={"memory_session_scope": "member-session"})

    assert model.intent_payload["runtime_context"]["short_term_memory"]["budget"] == 4000
    assert model.intent_payload["runtime_context"]["short_term_memory"]["preferences"] == ["wireless accessories"]
    assert result["budget"] == 4000
    assert result["preferences"] == ["wireless accessories"]
    assert result["optimization_mode"] == "cheaper"
    assert memory_store.saved[0][0] == "member-session"


@pytest.mark.anyio
async def test_graph_continues_when_memory_is_unavailable():
    class BasicModel:
        async def ainvoke(self, input, **kwargs):
            if "response-writing agent" in str(input[0].content):
                return AIMessage(content='{"response":"Hello.","product_ids":[],"unfulfilled_requirements":[]}')
            if "final brand-voice editor" in str(input[0].content):
                return AIMessage(content='{"response":"Hello."}')
            return AIMessage(content='{"mission_type":"information_request","goal":"greeting","requires_planning":false,"requires_catalog":false,"optimization_mode":null,"catalog_query":null,"catalog_queries":[],"requested_actions":[],"budget":null,"bundle_items":[],"preferences":[],"constraints":[],"owned_items":[],"priorities":[],"fulfillment_requirements":[]}')

    result = await ShoppingOrchestrator(
        BasicModel(), auditor=ShoppingAuditor(), memory_store=FakeMemoryStore(fail=True)
    ).ainvoke("Hello", state_overrides={"memory_session_scope": "offline-session"})

    assert result["audit_result"]["status"] == "pass"


@pytest.mark.anyio
async def test_new_goal_does_not_inherit_unrelated_memory_constraints():
    class NewGoalModel:
        async def ainvoke(self, input, **kwargs):
            if "response-writing agent" in str(input[0].content):
                return AIMessage(content='{"response":"Let’s plan your work wardrobe.","product_ids":[],"unfulfilled_requirements":[]}')
            if "final brand-voice editor" in str(input[0].content):
                return AIMessage(content='{"response":"Let’s plan your work wardrobe."}')
            return AIMessage(content='{"mission_type":"planning_request","goal":"work wardrobe","requires_planning":true,"requires_catalog":false,"continues_context":false,"optimization_mode":null,"catalog_query":null,"catalog_queries":[],"requested_actions":[],"budget":null,"bundle_items":[],"preferences":[],"constraints":[],"owned_items":[],"priorities":[],"fulfillment_requirements":[]}')

    store = FakeMemoryStore(ShoppingSessionMemory(
        current_mission={"goal": "desk"}, budget=200, constraints=["height about 80 cm"]
    ))
    result = await ShoppingOrchestrator(
        NewGoalModel(), auditor=ShoppingAuditor(), memory_store=store
    ).ainvoke("Help me plan a work wardrobe", state_overrides={"memory_session_scope": "member-session"})

    assert result["continues_context"] is False
    assert result["budget"] is None
    assert result["constraints"] == []


@pytest.mark.anyio
async def test_logout_clears_authenticated_session_memory(db_session, monkeypatch):
    from app.api.routes import auth as auth_route
    from app.agentic.memory import build_memory_scope

    class ClearTrackingStore:
        cleared = []

        async def clear(self, session_scope):
            self.cleared.append(session_scope)

    user = User(email="memory@example.com", full_name="Memory Member", password_hash="not-used")
    db_session.add(user)
    db_session.flush()
    token = auth_route.create_auth_session(db_session, user)
    db_session.commit()
    store = ClearTrackingStore()
    monkeypatch.setattr(auth_route, "get_shopping_memory_store", lambda: store)

    response = await auth_route.logout(Response(), session_token=token, db=db_session)

    assert response.message == "Signed out successfully."
    assert store.cleared == [build_memory_scope(
        user_id=user.id,
        auth_session_token=token,
        conversation_token="unused-for-authenticated-session",
    )]
