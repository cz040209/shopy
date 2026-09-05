import json
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.brand_voice import BrandVoiceAgent
from app.agentic.bundle_optimizer import BundleOptimizerAgent
from app.agentic.compatibility import CompatibilityAgent
from app.agentic.intent import IntentMissionAgent
from app.agentic.product_search import ProductSearchAgent
from app.agentic.product_selector import ProductSelectorAgent
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


@pytest.mark.anyio
async def test_broad_product_role_keeps_real_recommendations_and_rejects_accessories(db_session):
    mouse = add_product(
        db_session, sku="ADV-MOUSE", name="Glide Wireless Mouse",
        price="189", inventory=8,
    )
    mouse.description = "Quiet ergonomic mouse with multi-device switching."
    accessory = add_product(
        db_session, sku="ADV-MAT", name="Large Mouse Desk Mat",
        price="79", inventory=8,
    )
    accessory.description = "A protective desk surface for a keyboard and mouse."
    db_session.commit()
    state = initial_shopping_state("Shop this shop object image.")
    state.update({
        "recommendation_mode": "single",
        "search_requirements": [{
            "original_text": "wireless computer mouse",
            "canonical_role": "mouse",
            "required_features": [],
            "preferred_features": ["wireless", "ergonomic"],
            "search_queries": ["mouse", "wireless computer mouse", "ergonomic mouse"],
        }],
        "fulfillment_requirements": [
            {"kind": "category", "value": "mouse", "field": None, "quantity": 1},
        ],
    })

    result = await ProductSearchAgent(
        CommerceToolRegistry(db_session, "mouse-recommendations")
    ).run_requirements(state, requirements=state["search_requirements"], per_role_limit=6)
    candidates = ShoppingOrchestrator._role_constrained_candidates(
        state, result["candidate_products"],
    )
    selected = BrandVoiceAgent.select_catalog_products({
        **state, "candidate_products": candidates,
    })

    assert [item["id"] for item in candidates] == [str(mouse.id)]
    assert selected == [{"id": str(mouse.id), "quantity": 1}]


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
async def test_generic_recommendation_keeps_grounded_candidates_without_entity_resolution():
    class ResolverMustNotRun:
        async def resolve(self, **kwargs):
            raise AssertionError("A generic recommendation is not named-product resolution")

    orchestrator = ShoppingOrchestrator(GraphModel())
    orchestrator.product_resolver = ResolverMustNotRun()
    candidates = [
        {"id": "mouse-a", "name": "Mouse A"},
        {"id": "mouse-b", "name": "Mouse B"},
    ]
    state = initial_shopping_state("Recommend a mouse")
    state.update({"mission_type": "product_search", "recommendation_mode": "single"})

    resolved, context = await orchestrator._resolve_action_candidates(
        state, ["search_products"], candidates,
    )

    assert resolved == candidates
    assert context == [{
        "tool": "product_resolution",
        "result": {
            "product_ids": ["mouse-a", "mouse-b"],
            "status": "recommendation_candidates",
        },
    }]


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
async def test_bundle_optimizer_uses_role_bound_runtime_vocabulary_when_catalog_labels_differ():
    products = [
        {
            "id": "soap", "name": "Gold Class Car Wash Shampoo",
            "category": "Car Shampoo", "price": "49", "inventory_quantity": 8,
            "attributes": {"department": "automotive", "car_care_category": "Car Shampoo"},
        },
        {
            "id": "mitt", "name": "Chenille Premium Car Wash Mitt",
            "category": "Wash Mitt", "price": "29", "inventory_quantity": 8,
            "attributes": {"department": "automotive", "car_care_category": "Wash Mitt"},
        },
        {
            "id": "wheel", "name": "Wheel Cleaner Plus",
            "category": "Wheel Cleaner", "price": "65", "inventory_quantity": 8,
            "attributes": {"department": "automotive", "car_care_category": "Wheel Cleaner"},
        },
        {
            "id": "cargo", "name": "Utility Cargo Pants",
            "category": "Cargo Pants", "price": "179", "inventory_quantity": 8,
            "attributes": {"department": "apparel"},
        },
    ]
    roles = ["car wash soap", "microfiber car wash mitt", "wheel and tire cleaner"]
    state = initial_shopping_state("Build a weekly care kit")
    state.update({
        "recommendation_mode": "bundle",
        "required_categories": roles,
        "candidate_products": products,
        "search_requirements": [
            {
                "original_text": roles[0], "canonical_role": roles[0],
                "search_queries": [roles[0], "vehicle cleaning soap", "auto wash liquid"],
            },
            {
                "original_text": roles[1], "canonical_role": roles[1],
                "search_queries": [roles[1], "wash mitt for cars", "automotive microfiber mitt"],
            },
            {
                "original_text": roles[2], "canonical_role": roles[2],
                "search_queries": [roles[2], "tire shine product", "rims and tires cleaning solution"],
            },
        ],
        "retrieval_role_matches": {
            role: [product["id"] for product in products] for role in roles
        },
    })

    result = await BundleOptimizerAgent().run(state)

    assert {item["id"] for item in result["selected_products"]} == {
        "soap", "mitt", "wheel",
    }
    assert result["bundle"]["product_count"] == 3
    assert result["bundle"]["required_category_coverage"]["missing"] == []


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


@pytest.mark.anyio
async def test_product_selector_sees_complete_bundle_shortlist_and_repairs_rejected_choice():
    class SelectorModel:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, messages, **kwargs):
            self.calls += 1
            payload = json.loads(str(messages[1].content))
            assert {item["id"] for item in payload["verified_catalog_products"]} == {
                "soap", "mitt", "wheel", "cloth",
            }
            assert payload["verified_catalog_products"][0]["description"] == "Paint-safe wash concentrate"
            assert kwargs["enable_thinking"] is False
            assert kwargs["response_mime_type"] == "application/json"
            assert kwargs["max_output_tokens"] == 3000
            if self.calls == 1:
                return AIMessage(content=json.dumps({
                    "mode": "bundle",
                    "related_candidate_count": 4,
                    "choices": [
                            {"product_id": "soap", "role": "wash soap", "reason": "Cleans paint", "quantity": 1},
                            {"product_id": "mitt", "role": "wash mitt", "reason": "Applies wash", "quantity": 1},
                    ],
                    "unfulfilled_roles": [],
                }))
            assert "Bundle mode must select 3" in str(messages[0].content)
            return AIMessage(content=json.dumps({
                "mode": "bundle",
                "related_candidate_count": 4,
                "choices": [
                    {"product_id": "soap", "role": "wash soap", "reason": "Cleans paint", "quantity": 1},
                    {"product_id": "mitt", "role": "wash mitt", "reason": "Applies wash", "quantity": 1},
                    {"product_id": "wheel", "role": "wheel cleaner", "reason": "Cleans wheels", "quantity": 1},
                ],
                "unfulfilled_roles": [],
            }))

    products = [
        {"id": "soap", "name": "Wash Soap", "brand": "A", "description": "Paint-safe wash concentrate", "category": "Wash", "price": "40", "currency": "MYR", "inventory_quantity": 5},
        {"id": "mitt", "name": "Wash Mitt", "brand": "B", "category": "Tools", "price": "20", "currency": "MYR", "inventory_quantity": 5},
        {"id": "wheel", "name": "Wheel Cleaner", "brand": "C", "category": "Wheel", "price": "30", "currency": "MYR", "inventory_quantity": 5},
        {"id": "cloth", "name": "Drying Cloth", "brand": "D", "category": "Drying", "price": "15", "currency": "MYR", "inventory_quantity": 5},
    ]
    state = initial_shopping_state("Build a weekly wash kit")
    state.update({"recommendation_mode": "bundle", "candidate_products": products})
    model = SelectorModel()

    result = await ProductSelectorAgent(model, max_attempts=2).run(state)

    assert model.calls == 2
    assert result["selection_source"] == "llm_product_selector_v1"
    assert [item["id"] for item in result["selected_products"]] == ["soap", "mitt", "wheel"]
    assert result["bundle"]["product_count"] == 3
    assert result["bundle"]["total"] == "90"


@pytest.mark.anyio
async def test_product_selector_uses_llm_for_single_comparable_choices():
    class SelectorModel:
        async def ainvoke(self, messages, **kwargs):
            payload = json.loads(str(messages[1].content))
            assert len(payload["verified_catalog_products"]) == 3
            return AIMessage(content=json.dumps({
                "mode": "single",
                "related_candidate_count": 3,
                "choices": [
                    {"product_id": "one", "role": "headphones", "reason": "Portable option", "quantity": 1},
                    {"product_id": "two", "role": "headphones", "reason": "Comfort option", "quantity": 1},
                ],
                "unfulfilled_roles": [],
            }))

    state = initial_shopping_state("Recommend headphones")
    state.update({
        "recommendation_mode": "single",
        "candidate_products": [
            {"id": value, "name": value.title(), "brand": "Test", "category": "Headphones", "price": "100", "currency": "MYR", "inventory_quantity": 5}
            for value in ("one", "two", "three")
        ],
    })

    result = await ProductSelectorAgent(SelectorModel()).run(state)

    assert result["selection_source"] == "llm_product_selector_v1"
    assert [item["id"] for item in result["selected_products"]] == ["one", "two"]
    assert result["bundle"] is None


@pytest.mark.anyio
async def test_product_selector_failure_never_chooses_products_deterministically():
    class InvalidModel:
        async def ainvoke(self, messages, **kwargs):
            return AIMessage(content="not json")

    state = initial_shopping_state("Recommend a keyboard")
    state.update({
        "recommendation_mode": "single",
        "candidate_products": [
            {"id": "one", "name": "One", "price": "100", "inventory_quantity": 5},
            {"id": "two", "name": "Two", "price": "120", "inventory_quantity": 5},
        ],
    })

    result = await ProductSelectorAgent(InvalidModel(), max_attempts=2).run(state)

    assert result["selected_products"] == []
    assert result["selection_source"] == "llm_product_selector_failed"
    assert result["selection_errors"]


def test_product_selector_accepts_json_wrapped_by_model_explanation():
    value = ProductSelectorAgent._selection_object(
        'I considered every candidate.\n{"mode":"single","related_candidate_count":0,"choices":[],"unfulfilled_roles":[]}\nDone.'
    )

    assert value["mode"] == "single"


@pytest.mark.anyio
async def test_product_selector_rejects_cross_domain_lexical_false_positive():
    class SelectorModel:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, messages, **kwargs):
            self.calls += 1
            selected = ["car", "hair"] if self.calls == 1 else ["car", "ceramic"]
            return AIMessage(content=json.dumps({
                "mode": "single",
                "related_candidate_count": 2,
                "choices": [
                    {
                        "product_id": product_id, "role": "car wash shampoo",
                        "reason": "Candidate comparison", "quantity": 1,
                    }
                    for product_id in selected
                ],
                "unfulfilled_roles": [],
            }))

    state = initial_shopping_state("Recommend car wash shampoo")
    state.update({
        "recommendation_mode": "single",
        "required_categories": ["car wash shampoo"],
        "search_requirements": [{
            "original_text": "car wash shampoo", "canonical_role": "car wash shampoo",
            "search_queries": ["car wash shampoo", "automotive shampoo", "car cleaning wash"],
        }],
        "candidate_products": [
            {"id": "car", "name": "Car Wash Shampoo", "category": "Car Care", "price": "40", "inventory_quantity": 5},
            {"id": "ceramic", "name": "Ceramic Vehicle Wash", "category": "Car Shampoo", "price": "60", "inventory_quantity": 5},
            {"id": "hair", "name": "Creamy Shampoo", "category": "Hair Care", "price": "20", "inventory_quantity": 5},
        ],
    })
    model = SelectorModel()

    result = await ProductSelectorAgent(model, max_attempts=2).run(state)

    assert model.calls == 2
    assert [item["id"] for item in result["selected_products"]] == ["car", "ceramic"]
    assert result["selection_source"] == "llm_product_selector_v1"
