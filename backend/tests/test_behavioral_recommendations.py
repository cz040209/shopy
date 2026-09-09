import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, SystemMessage

from app.agentic.behavioral_recommendations import (
    BEHAVIORAL_RECOMMENDATION_SYSTEM_PROMPT,
    BehavioralRecommendationAgent,
)
from app.agentic.memory import ShoppingSessionMemory


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
    monkeypatch.setattr(
        "app.agentic.behavioral_recommendations.list_products",
        lambda _db, **_kwargs: candidates,
    )
    memory = ShoppingSessionMemory(
        preferences=["wireless accessories"],
        selected_products=[{"id": str(selected.id), "quantity": 1}],
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
    supplied_ids = {
        item["id"]
        for item in json.loads(messages[1].content)["eligible_catalog_candidates"]
    }
    assert supplied_ids == {str(fresh.id)}


@pytest.mark.anyio
async def test_behavioral_agent_rejects_invented_and_duplicate_model_product_ids(monkeypatch):
    fresh = product("Travel Organizer", "Travel")
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
        ShoppingSessionMemory(preferences=["travel organization"]),
    )

    assert [item.product.id for item in result.recommendations] == [fresh.id]


@pytest.mark.anyio
async def test_behavioral_agent_stays_silent_without_meaningful_session_context():
    model = BehavioralModel({"message": "", "recommendations": []})

    result = await BehavioralRecommendationAgent(model).recommend(None, ShoppingSessionMemory())

    assert result.recommendations == []
    assert model.calls == []
