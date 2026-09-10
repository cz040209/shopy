import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, SystemMessage
from sqlalchemy import select

from app.agentic.behavioral_recommendations import (
    BEHAVIORAL_RECOMMENDATION_SYSTEM_PROMPT,
    BehavioralRecommendationAgent,
)
from app.agentic.memory import ShoppingSessionMemory
from app.models import Category, OrchestrationRun, Product, ProductStatus, Seller, SellerStatus, User


class BehavioralModel:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    async def ainvoke(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return AIMessage(content=json.dumps(self.payload))


def product(name: str, category: str = "Accessories"):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        brand="Shopy Test",
        description=f"A {name.lower()} for daily use.",
        category=SimpleNamespace(name=category, slug=category.lower()),
        specs=[],
        attributes={},
        price=100,
        currency="MYR",
        badge=None,
        rating_average=4.5,
        review_count=20,
        inventory_quantity=5,
        reserved_quantity=0,
    )


def test_behavioral_role_queries_cover_each_base_role_before_variants():
    memory = ShoppingSessionMemory(selected_products=[
        {"id": "chair-1", "role": "chair", "search_queries": ["chair", "office chair"]},
        {"id": "keyboard-1", "role": "keyboard", "search_queries": ["keyboard", "wireless keyboard"]},
        {"id": "mouse-1", "role": "mouse", "search_queries": ["mouse", "wireless mouse"]},
    ])

    queries = BehavioralRecommendationAgent._selected_role_queries(memory)

    assert queries[:3] == ["chair", "keyboard", "mouse"]
    assert queries[3:6] == ["office chair", "wireless keyboard", "wireless mouse"]


@pytest.mark.anyio
async def test_behavioral_agent_uses_system_prompt_and_never_repeats_memory_products(monkeypatch):
    selected = product("Wireless Keyboard")
    viewed = product("Wireless Mouse")
    rejected = product("Wireless Headset")
    notified = product("Wireless Charger")
    fresh = product("Wireless Presenter")
    candidates = [selected, viewed, rejected, notified, fresh]
    monkeypatch.setattr(
        "app.agentic.behavioral_recommendations.get_product",
        lambda _db, product_id: selected if product_id == selected.id else None,
    )
    catalog_calls = []
    def list_candidates(_db, **kwargs):
        catalog_calls.append(kwargs)
        return candidates
    monkeypatch.setattr("app.agentic.behavioral_recommendations.list_products", list_candidates)
    memory = ShoppingSessionMemory(
        preferences=["wireless accessories"],
        selected_products=[{
            "id": str(selected.id),
            "quantity": 1,
            "role": "keyboard",
            "search_queries": ["keyboard", "wireless keyboard"],
        }],
        current_bundle={"total": "450", "budget_remaining": "50"},
        viewed_product_ids=[str(viewed.id)],
        rejected_product_ids=[str(rejected.id)],
        notified_product_ids=[str(notified.id)],
    )
    model = BehavioralModel({
        "message": "We found another option that fits your wireless setup.",
        "recommendations": [
            {"product_id": str(fresh.id), "reason": "Complements your wireless setup."},
        ],
    })

    result = await BehavioralRecommendationAgent(model).recommend(None, memory, limit=3)

    assert [item.product.id for item in result.recommendations] == [fresh.id]
    assert result.message.startswith("We found")
    assert len(model.calls) == 1
    messages, kwargs = model.calls[0]
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == BEHAVIORAL_RECOMMENDATION_SYSTEM_PROMPT
    assert kwargs["enable_thinking"] is False
    supplied_memory = json.loads(messages[1].content)["short_term_memory"]
    assert supplied_memory["selected_products"][0]["role"] == "keyboard"
    assert [call.get("query") for call in catalog_calls if call.get("query")] == [
        "keyboard", "wireless keyboard", "wireless accessories",
    ]
    supplied_payload = json.loads(messages[1].content)
    supplied_ids = {
        item["id"]
        for item in supplied_payload["eligible_catalog_candidates"]
    }
    assert supplied_ids == {str(fresh.id)}
    assert supplied_payload["eligible_catalog_candidates"][0]["remaining_bundle_budget"] == "50"
    assert supplied_payload["eligible_catalog_candidates"][0]["fits_remaining_bundle_budget"] is False


@pytest.mark.anyio
async def test_behavioral_agent_rejects_invented_and_duplicate_model_product_ids(monkeypatch):
    selected = product("Carry-on Luggage", "Travel")
    fresh = product("Travel Organizer", "Travel")
    monkeypatch.setattr(
        "app.agentic.behavioral_recommendations.get_product",
        lambda _db, product_id: selected if product_id == selected.id else None,
    )
    monkeypatch.setattr(
        "app.agentic.behavioral_recommendations.list_products",
        lambda _db, **_kwargs: [fresh],
    )
    model = BehavioralModel({
        "message": "You may like these.",
        "recommendations": [
            {"product_id": "invented-id", "reason": "Invented."},
            {"product_id": str(fresh.id), "reason": "Fits your travel plans."},
            {"product_id": str(fresh.id), "reason": "Repeated."},
        ],
    })

    result = await BehavioralRecommendationAgent(model).recommend(
        None,
        ShoppingSessionMemory(
            preferences=["travel organization"],
            selected_products=[{"id": str(selected.id), "quantity": 1}],
        ),
    )

    assert [item.product.id for item in result.recommendations] == [fresh.id]


@pytest.mark.anyio
async def test_behavioral_agent_stays_silent_without_meaningful_session_context():
    model = BehavioralModel({"message": "", "recommendations": []})

    result = await BehavioralRecommendationAgent(model).recommend(None, ShoppingSessionMemory())

    assert result.recommendations == []
    assert model.calls == []


@pytest.mark.anyio
async def test_reminder_route_persists_independent_behavioral_run(db_session, monkeypatch):
    """The optional popup has a full audit trail without joining the main graph."""
    from app.api.routes import recommendations as recommendation_route

    seller = Seller(name="Behavioral Seller", slug="behavioral-seller", status=SellerStatus.ACTIVE)
    category = Category(name="Accessories", slug="accessories")
    selected = Product(
        seller=seller, category=category, sku="BEHAVIOR-SELECTED", slug="wireless-keyboard",
        name="Wireless Keyboard", brand="Shopy Test", description="A wireless keyboard.",
        price=100, status=ProductStatus.ACTIVE, inventory_quantity=5,
    )
    fresh = Product(
        seller=seller, category=category, sku="BEHAVIOR-FRESH", slug="wireless-presenter",
        name="Wireless Presenter", brand="Shopy Test", description="A wireless presenter.",
        price=100, status=ProductStatus.ACTIVE, inventory_quantity=5,
    )
    user = User(email="behavioral-log@example.com", full_name="Behavioral Logger")
    db_session.add_all([user, selected, fresh])
    db_session.commit()

    class MemoryStore:
        def __init__(self):
            self.saved = None

        async def load(self, _scope):
            return ShoppingSessionMemory(
                preferences=["wireless accessories"],
                selected_products=[{"id": str(selected.id), "quantity": 1}],
                viewed_product_ids=["already-viewed"],
            )

        async def save(self, _scope, memory):
            self.saved = memory

    store = MemoryStore()
    monkeypatch.setattr(recommendation_route, "get_shopping_memory_store", lambda: store)
    monkeypatch.setattr(
        "app.agentic.behavioral_recommendations.get_product",
        lambda _db, product_id: selected if product_id == selected.id else None,
    )
    monkeypatch.setattr(
        "app.agentic.behavioral_recommendations.list_products",
        lambda _db, **_kwargs: [fresh],
    )
    monkeypatch.setattr(
        recommendation_route,
        "PrimaryLangChainChatModel",
        lambda **_kwargs: BehavioralModel({
            "message": "We think you may also like this wireless companion.",
            "recommendations": [{
                "product_id": str(fresh.id), "reason": "Complements the wireless setup.",
            }],
        }),
    )

    response = await recommendation_route.claim_behavioral_reminder(
        user=user, db=db_session, session_token="session-secret", conversation_token="conversation",
    )

    assert [item.product.id for item in response.products] == [fresh.id]
    assert store.saved is not None
    run = db_session.scalar(select(OrchestrationRun).where(
        OrchestrationRun.run_type == "behavioral_reminder"
    ))
    assert run is not None
    assert run.user_id == user.id
    assert run.status == "completed"
    assert run.initial_state["memory_session_scope_hash"] != "session-secret"
    assert run.final_state["behavioral_reminder"]["selected_product_ids"] == [str(fresh.id)]
    assert run.final_state["behavioral_reminder"]["popup_message"] == response.message
    assert [event.event_type for event in run.events] == [
        "run_started",
        "behavioral_candidate_discovery",
        "behavioral_selection",
        "behavioral_notification_delivery",
        "run_finished",
    ]
