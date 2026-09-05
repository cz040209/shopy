import json
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.bundle_optimizer import BundleOptimizerAgent
from app.agentic.compatibility import CompatibilityAgent
from app.agentic.intent import IntentMissionAgent
from app.agentic.product_search import ProductSearchAgent
from app.agentic.schemas import BundleItemPlan, MissionInterpretation, SearchRequirement
from app.agentic.state import initial_shopping_state
from app.agentic.tools import CommerceToolRegistry
from app.agentic.vision import VISION_PROMPT, VisionAgent
from app.models import Category, Product, ProductStatus, Seller, SellerStatus


def add_product(db, *, sku: str, name: str, price: str, inventory: int) -> Product:
    seller = db.scalar(select(Seller).where(Seller.slug == "advanced-seller"))
    if seller is None:
        seller = Seller(name="Advanced Seller", slug="advanced-seller", status=SellerStatus.ACTIVE)
        db.add(seller)
    category = db.scalar(select(Category).where(Category.slug == "advanced-category"))
    if category is None:
        category = Category(name="Advanced Category", slug="advanced-category")
        db.add(category)
    product = Product(seller=seller, category=category, sku=sku, slug=sku.lower(), name=name, brand="Advanced", description="wireless meeting headset", price=Decimal(price), status=ProductStatus.ACTIVE, inventory_quantity=inventory, specs=[{"label": "Use", "value": "Meeting calls"}])
    db.add(product); db.commit()
    return product


@pytest.mark.anyio
async def test_product_search_filters_stock_budget_and_never_invents_ids(db_session):
    affordable = add_product(db_session, sku="ADV-001", name="Affordable Headset", price="90", inventory=3)
    add_product(db_session, sku="ADV-002", name="Sold Out Headset", price="80", inventory=0)
    add_product(db_session, sku="ADV-003", name="Premium Headset", price="900", inventory=3)
    state = initial_shopping_state("Need a wireless meeting headset")
    state.update({"budget": 200, "preferences": ["wireless"], "constraints": ["meeting"], "required_categories": ["headset"]})

    result = await ProductSearchAgent(CommerceToolRegistry(db_session, "search-filter")).run(state, query="headset")

    assert [item["id"] for item in result["candidate_products"]] == [str(affordable.id)]
    assert result["product_rankings"][0]["product_id"] == str(affordable.id)


def test_product_ranking_uses_whole_terms_not_substrings():
    state = initial_shopping_state("car cleaner")
    products = [
        {"id": "skin", "name": "Skincare Cleanser", "brand": "Test", "category": "Beauty", "price": "20", "inventory_quantity": 1},
        {"id": "car", "name": "Car Cleaner", "brand": "Test", "category": "Car Care", "price": "20", "inventory_quantity": 1},
    ]

    ranked = ProductSearchAgent._rank(products, state, include_out_of_stock=False)

    assert ranked[0]["product"]["id"] == "car"
    assert ranked[1]["reasons"] == ["in stock"]


def test_search_requirement_keeps_dynamic_aliases_for_lexical_role_variant():
    requirement = SearchRequirement(
        original_text="light",
        canonical_role="lighting",
        preferred_features=["RGB", "ambient"],
        search_queries=["lighting", "desk light", "ambient lighting", "RGB light", "LED light"],
    )

    result = IntentMissionAgent._normalized_search_requirements([requirement], ["light"])

    assert result[0].canonical_role == "lighting"
    assert result[0].search_queries == [
        "lighting", "light", "desk light", "ambient lighting", "RGB light", "LED light",
    ]


def test_required_search_feature_becomes_auditable_for_the_same_role():
    mission = MissionInterpretation(
        mission_type="product_search",
        recommendation_mode="bundle",
        goal="Add an RGB light",
        requires_catalog=True,
        catalog_query="lighting",
        requested_actions=["search_products"],
        bundle_items=[BundleItemPlan(query="lighting", quantity=1)],
        search_requirements=[SearchRequirement(
            original_text="RGB lights",
            canonical_role="lighting",
            required_features=["RGB"],
            search_queries=["lighting", "RGB light", "LED light"],
        )],
    )

    normalized = IntentMissionAgent._normalize_mission(
        mission, None, user_request="I need an RGB light",
    )

    assert any(
        requirement.kind == "feature"
        and requirement.value == "RGB"
        and requirement.field == "lighting"
        and requirement.quantity == 1
        for requirement in normalized.fulfillment_requirements
    )


@pytest.mark.anyio
async def test_role_expanded_search_uses_one_tool_call_and_json_catalog_evidence(db_session):
    matching = add_product(
        db_session, sku="ADV-RGB", name="Ambient Bar", price="90", inventory=3,
    )
    matching.description = "soft room illumination"
    matching.attributes = {"lighting_mode": "RGB ambient"}
    db_session.commit()
    registry = CommerceToolRegistry(db_session, "expanded-search")
    state = initial_shopping_state("Add ambient lighting")
    state["search_requirements"] = [{
        "original_text": "ambient lighting",
        "canonical_role": "lighting",
        "required_features": [],
        "preferred_features": ["RGB", "ambient"],
        "search_queries": ["lighting", "ambient lighting", "RGB light"],
    }]

    result = await ProductSearchAgent(registry).run_requirements(
        state, requirements=state["search_requirements"], per_role_limit=6,
    )

    assert str(matching.id) in [item["id"] for item in result["candidate_products"]]
    assert registry.remaining_calls == registry.max_calls - 1


class VisionGenerator:
    last_kwargs = None

    async def generate(self, **kwargs):
        self.last_kwargs = kwargs
        return '{"detected_objects":["sofa","window"],"category":["living room"],"colors":["beige"],"style":["minimal"],"existing_items":["sofa"],"possible_shopping_needs":["floor lamp"],"visual_constraints":["keep walkway clear"]}'


@pytest.mark.anyio
async def test_vision_agent_returns_structured_context_and_rejects_missing_image():
    generator = VisionGenerator()
    agent = VisionAgent(generator)
    context = await agent.analyze(image_bytes=b"image", mime_type="image/png", mode="shop_room")
    assert context.possible_shopping_needs == ["floor lamp"]
    assert generator.last_kwargs["qwen_model"] == "qwen3.5-omni-plus"
    assert generator.last_kwargs["enable_thinking"] is False
    state = initial_shopping_state("Shop this room")
    state["vision_input"] = {"image_bytes": b"image", "mime_type": "image/png", "mode": "shop_room"}
    assert (await agent.run(state))["vision_context"]["mode"] == "shop_room"
    with pytest.raises(ValueError, match="image is required"):
        await agent.analyze(image_bytes=b"", mime_type="image/png", mode="shop_room")
    with pytest.raises(ValueError, match="Unsupported"):
        await agent.analyze(image_bytes=b"image", mime_type="image/png", mode="bad-mode")


def test_vision_prompt_applies_evidence_and_crop_rules_to_every_mode():
    assert "Evidence and outcome policy for every mode" in VISION_PROMPT
    assert "not automatically something the customer wants to buy" in VISION_PROMPT
    assert "framing, occlusion, and image quality" in VISION_PROMPT
    assert "do not apply a predefined room checklist" in VISION_PROMPT
    assert "cropped image is incomplete evidence" in VISION_PROMPT
    assert "anatomy, facial features, hair, and grooming" in VISION_PROMPT
    assert "do not assume a fixed outfit template" in VISION_PROMPT.casefold()


class GraphVisionAgent:
    async def run(self, state):
        return {"vision_context": {"detected_objects": ["desk"], "possible_shopping_needs": ["task lamp"], "visual_constraints": []}}


class GraphModel:
    async def ainvoke(self, messages, **kwargs):
        if "response-writing agent" in str(messages[0].content):
            return AIMessage(content='{"response":"I can help with the room.","product_ids":[]}')
        return AIMessage(content='{"mission_type":"information_request","goal":"room context","catalog_query":null,"catalog_queries":[],"requested_actions":[],"budget":null,"preferences":[],"constraints":[],"owned_items":[],"priorities":[]}')


@pytest.mark.anyio
async def test_image_mode_routes_vision_before_intent():
    result = await ShoppingOrchestrator(GraphModel(), vision_agent=GraphVisionAgent()).ainvoke("Shop this room", state_overrides={"vision_input": {"image_bytes": b"x", "mime_type": "image/png", "mode": "shop_room"}})
    assert result["vision_context"]["detected_objects"] == ["desk"]
    assert result["graph_iterations"] == 8


@pytest.mark.anyio
async def test_image_intent_is_isolated_from_previous_session_memory():
    class CapturingIntentAgent:
        def __init__(self):
            self.runtime_context = None

        async def interpret(self, user_request, runtime_context=None):
            self.runtime_context = runtime_context
            return MissionInterpretation(
                mission_type="product_search", goal="Shop the photographed room",
                continues_context=True,
            )

    intent_agent = CapturingIntentAgent()
    orchestrator = ShoppingOrchestrator(GraphModel())
    orchestrator.intent_agent = intent_agent
    state = initial_shopping_state("Shop this shop room image.")
    state.update({
        "vision_context": {"mode": "shop_room", "detected_objects": ["chair"]},
        "memory_context": {
            "budget": 2000,
            "preferences": ["comfortable"],
            "current_mission": {"goal": "Build a WFH setup", "budget": 2000},
        },
    })

    result = await orchestrator._intent_node(state)

    assert intent_agent.runtime_context == {"vision_context": state["vision_context"]}
    assert result["continues_context"] is False
    assert result["budget"] is None


@pytest.mark.anyio
async def test_compatibility_reports_conflicting_verified_model_facts():
    class CompatibilityModel:
        async def ainvoke(self, messages, **kwargs):
            return AIMessage(content='{"fields":[{"field":"compatible_models","rule":"must_overlap"}]}')

    state = initial_shopping_state("Build a compatible setup")
    state["candidate_products"] = [
        {"id": "a", "name": "Case A", "category": "accessory", "inventory_quantity": 2, "attributes": {"compatible_models": ["alpha"]}, "specs": []},
        {"id": "b", "name": "Device B", "category": "device", "inventory_quantity": 2, "attributes": {"compatible_models": ["beta"]}, "specs": []},
    ]
    result = await CompatibilityAgent(CompatibilityModel()).run(state)
    assert result["compatibility_results"][0]["status"] == "incompatible"
    assert result["compatibility_results"][0]["affected_product_ids"] == ["a", "b"]


@pytest.mark.anyio
async def test_bundle_optimizer_enforces_budget_and_reports_coverage():
    state = initial_shopping_state("Build a gaming setup under RM 3000")
    state.update({
        "budget": 3000, "required_categories": ["laptop", "keyboard"], "optional_categories": ["mouse"],
        "recommendation_mode": "bundle",
        "candidate_products": [
            {"id": "laptop", "name": "Gaming Laptop", "category": "laptop", "price": "2500", "currency": "MYR", "inventory_quantity": 1, "specs": [], "attributes": {}},
            {"id": "keyboard", "name": "Gaming Keyboard", "category": "keyboard", "price": "400", "currency": "MYR", "inventory_quantity": 1, "specs": [], "attributes": {}},
            {"id": "mouse", "name": "Gaming Mouse", "category": "mouse", "price": "200", "currency": "MYR", "inventory_quantity": 1, "specs": [], "attributes": {}},
        ],
        "product_rankings": [{"product_id": "laptop", "score": 90}, {"product_id": "keyboard", "score": 60}, {"product_id": "mouse", "score": 50}],
    })
    result = await BundleOptimizerAgent().run(state)
    assert result["bundle"]["total"] == "3100"
    assert result["bundle"]["budget_remaining"] == "-100"
    assert result["bundle"]["required_category_coverage"]["missing"] == []
    assert {item["id"] for item in result["selected_products"]} == {"laptop", "keyboard", "mouse"}


@pytest.mark.anyio
async def test_bundle_optimizer_fulfills_model_generated_role_menus_without_empty_result():
    roles = [
        "bottoms (jeans or chinos)",
        "footwear (sneakers or boots)",
        "outerwear layer (optional jacket)",
        "accessories (watch, cap, or bag)",
    ]
    state = initial_shopping_state("Complete this look")
    state.update({
        "recommendation_mode": "bundle",
        "required_categories": roles,
        "fulfillment_requirements": [
            {"kind": "category", "value": role, "quantity": 1}
            for role in roles
        ],
        "candidate_products": [
            {"id": "jeans", "name": "Relaxed Carpenter Jeans", "category": "Jeans", "price": "199", "currency": "MYR", "inventory_quantity": 10, "specs": [], "attributes": {}},
            {"id": "boots", "name": "Trail Grip Hiking Boot", "category": "Shoes", "price": "359", "currency": "MYR", "inventory_quantity": 10, "specs": [], "attributes": {}},
            {"id": "jacket", "name": "Lightweight Bomber Jacket", "category": "Outerwear", "price": "239", "currency": "MYR", "inventory_quantity": 10, "specs": [], "attributes": {}},
            {"id": "watch", "name": "Minimal Steel Watch", "category": "Accessories", "price": "229", "currency": "MYR", "inventory_quantity": 10, "specs": [], "attributes": {}},
        ],
    })

    result = await BundleOptimizerAgent().run(state)

    assert {item["id"] for item in result["selected_products"]} == {
        "jeans", "boots", "jacket", "watch",
    }
    assert result["bundle"]["required_category_coverage"]["missing"] == []
    assert result["fulfillment_gaps"] == []


@pytest.mark.anyio
async def test_bundle_optimizer_does_not_use_mousepad_as_mouse_or_gaming_product_as_laptop():
    state = initial_shopping_state("Build a gaming setup under RM 1000")
    state.update({
        "budget": 1000, "required_categories": ["gaming laptop or desktop", "mouse"],
        "recommendation_mode": "bundle",
        "candidate_products": [
            {"id": "pad", "name": "Gaming Mousepad", "category": "Gaming", "price": "40", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
            {"id": "desk", "name": "Gaming Desk", "category": "Gaming", "price": "400", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
            {"id": "mouse", "name": "Wireless Mouse", "category": "Workspace", "price": "120", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
        ],
        "product_rankings": [],
    })
    result = await BundleOptimizerAgent().run(state)
    assert result["bundle"]["required_category_coverage"]["covered"] == ["mouse"]
    assert result["bundle"]["required_category_coverage"]["missing"] == ["gaming laptop or desktop"]
    assert result["bundle"]["selected_products"] == [{"product_id": "mouse", "quantity": 1}]


@pytest.mark.anyio
async def test_exact_catalog_role_overrides_an_incorrect_semantic_mapping():
    class WrongMappingModel:
        async def ainvoke(self, messages, **kwargs):
            return AIMessage(content=json.dumps({
                "mode": "best_value", "rankings": [],
                "need_matches": [{"need": "monitor arm", "product_ids": ["desk"]}],
            }))

    state = initial_shopping_state("Add a monitor arm")
    state.update({
        "recommendation_mode": "bundle", "required_categories": ["monitor arm"],
        "candidate_products": [
            {"id": "desk", "name": "Studio Work Desk", "brand": "Test", "category": "Desks", "price": "700", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
            {"id": "arm", "name": "Arc Monitor Arm", "brand": "Test", "category": "Monitor Arms", "price": "200", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
        ],
    })

    result = await BundleOptimizerAgent(WrongMappingModel()).run(state)

    assert result["selected_products"] == [{"id": "arm", "quantity": 1}]


@pytest.mark.anyio
async def test_semantic_mapping_cannot_assign_an_unrelated_product_type_to_a_role():
    class MixedMappingModel:
        async def ainvoke(self, messages, **kwargs):
            return AIMessage(content=json.dumps({
                "mode": "quality", "rankings": [
                    {"product_id": "laptop", "score": 100, "reason": "performance"},
                    {"product_id": "chair", "score": 1, "reason": "correct product type"},
                ],
                "need_matches": [{
                    "need": "gaming chair", "product_ids": ["laptop", "chair"],
                }],
            }))

    state = initial_shopping_state("Build a gaming setup")
    state.update({
        "recommendation_mode": "bundle", "required_categories": ["gaming chair"],
        "candidate_products": [
            {"id": "laptop", "name": "Lenovo Gaming Laptop", "brand": "Lenovo", "category": "Laptops", "price": "3000", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
            {"id": "chair", "name": "Posture Pro Ergonomic Chair", "brand": "Test", "category": "Office Furniture", "price": "999", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
        ],
    })

    result = await BundleOptimizerAgent(MixedMappingModel()).run(state)

    assert result["selected_products"] == [{"id": "chair", "quantity": 1}]


@pytest.mark.anyio
async def test_bundle_optimizer_skips_optional_model_when_catalog_roles_are_verified():
    class FailingIfCalledModel:
        async def ainvoke(self, messages, **kwargs):
            raise AssertionError("verified catalog roles must not invoke semantic planning")

    state = initial_shopping_state("Build a formal work outfit")
    state.update({
        "recommendation_mode": "bundle",
        "required_categories": ["blazer", "dress shirt", "dress shoes"],
        "candidate_products": [
            {"id": "blazer", "name": "Tailored Blazer", "brand": "Test", "category": "Blazers", "price": "349", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
            {"id": "shirt", "name": "Formal Dress Shirt", "brand": "Test", "category": "Shirts", "price": "109", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
            {"id": "shoes", "name": "Leather Dress Shoes", "brand": "Test", "category": "Shoes", "price": "239", "currency": "MYR", "inventory_quantity": 2, "specs": [], "attributes": {}},
        ],
    })

    result = await BundleOptimizerAgent(FailingIfCalledModel()).run(state)

    assert result["bundle"]["required_category_coverage"]["missing"] == []
    assert {item["id"] for item in result["selected_products"]} == {"blazer", "shirt", "shoes"}


@pytest.mark.anyio
async def test_bundle_optimizer_falls_back_when_optional_semantic_plan_fails():
    class UnavailableModel:
        async def ainvoke(self, messages, **kwargs):
            raise RuntimeError("provider unavailable")

    state = initial_shopping_state("Build a specialist kit")
    state.update({
        "recommendation_mode": "bundle",
        "required_categories": ["specialist device"],
        "candidate_products": [{
            "id": "candidate", "name": "General Device", "brand": "Test",
            "category": "Equipment", "price": "100", "currency": "MYR",
            "inventory_quantity": 2, "specs": [], "attributes": {},
        }],
    })

    result = await BundleOptimizerAgent(UnavailableModel()).run(state)

    assert result["selected_products"] == []
    assert result["bundle"]["required_category_coverage"]["missing"] == ["specialist device"]


@pytest.mark.anyio
async def test_bundle_optimizer_does_not_fallback_to_an_unrelated_affordable_product():
    state = initial_shopping_state("Build a kit within my budget")
    state.update({
        "budget": 500,
        "recommendation_mode": "bundle",
        "required_categories": ["compact first aid kit"],
        "candidate_products": [{
            "id": "unrelated", "name": "Decorative Desk Tray", "brand": "Test",
            "category": "Office Decor", "price": "49", "currency": "MYR",
            "inventory_quantity": 2, "specs": [], "attributes": {},
        }],
    })

    result = await BundleOptimizerAgent().run(state)

    assert result["selected_products"] == []
    assert result["bundle"]["required_category_coverage"]["missing"] == ["compact first aid kit"]
