import pytest
import json
from decimal import Decimal

from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.agentic.intent import IntentMissionAgent, StructuredOutputError, build_intent_system_prompt
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.planner import NeedPlannerAgent
from app.agentic.brand_voice import BrandVoiceAgent
from app.agentic.auditor import AuditFinding, ShoppingAuditor
from app.agentic.bundle_optimizer import BundleOptimizerAgent
from app.agentic.schemas import MissionInterpretation
from app.agentic.manager import WorkflowManager
from app.agentic.state import initial_shopping_state


class FakeChatModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[object] = []

    async def ainvoke(self, input: object, **kwargs: object) -> AIMessage:
        self.calls.append(input)
        if "response-writing agent" in str(input[0].content):
            payload = json.loads(str(input[1].content))
            products = payload["verified_catalog_products"]
            response = "I can help with this request." if not products else "\n".join(
                f"{product['name']} — RM {product['price']}" for product in products
            )
            return AIMessage(content=json.dumps({"response": response, "product_ids": [product["id"] for product in products]}))
        return AIMessage(content=self.response)


MISSION_JSON = """{
  "mission_type": "build_setup",
  "goal": "gaming setup",
  "budget": 4000,
  "owned_items": ["monitor"],
  "preferences": ["wireless accessories"],
  "constraints": [],
  "priorities": ["gaming_performance", "value"]
}"""


@pytest.mark.anyio
async def test_intent_agent_extracts_structured_mission():
    agent = IntentMissionAgent(FakeChatModel(MISSION_JSON))
    result = await agent.interpret("Build me a gaming setup under RM4,000. I already have a monitor and prefer wireless accessories.")

    assert result.mission_type == "build_setup"
    assert result.budget == 4000
    assert result.owned_items == ["monitor"]
    assert result.preferences == ["wireless accessories"]


def test_need_planner_returns_required_and_optional_categories():
    mission = MissionInterpretation.model_validate_json(MISSION_JSON)
    result = NeedPlannerAgent().plan(mission)

    assert result.required_categories == ["gaming setup"]
    assert result.optional_categories == []


def test_need_planner_does_not_rebuy_a_more_specific_owned_item():
    mission = MissionInterpretation(
        mission_type="product_search", recommendation_mode="bundle",
        goal="complete the look", owned_items=["beige t-shirt with navy trim"],
        bundle_items=[{"query": "beige shirt", "quantity": 1}, {"query": "white sneakers", "quantity": 1}],
    )

    result = NeedPlannerAgent().plan(mission)

    assert result.required_categories == ["white sneakers"]


def test_intent_normalization_reconciles_vision_and_malformed_duplicate_requirements():
    mission = MissionInterpretation(
        mission_type="product_search", recommendation_mode="bundle", goal="complete the look",
        requires_catalog=True, requested_actions=["search_products"],
        owned_items=["red beaded necklace"],
        bundle_items=[{"query": "beige shirt"}, {"query": "red necklace"}],
        catalog_queries=["beige shirt", "red necklace"],
        fulfillment_requirements=[
            {"kind": "category", "field": "category", "value": "shirt"},
            {"kind": "category", "field": None, "value": "necklace"},
        ],
    )

    normalized = IntentMissionAgent._normalize_mission(mission, {"vision_context": {
        "existing_items": ["beige t-shirt with navy trim", "red beaded necklace"],
        "possible_shopping_needs": ["white sneakers", "navy trousers"],
    }})

    assert [item.query for item in normalized.bundle_items] == ["white sneakers", "navy trousers"]
    assert [item.value for item in normalized.fulfillment_requirements] == ["white sneakers", "navy trousers"]
    assert "beige t-shirt with navy trim" in normalized.owned_items


def test_intent_normalization_removes_feature_duplicates_embedded_in_bundle_roles():
    mission = MissionInterpretation(
        mission_type="product_search", recommendation_mode="bundle", goal="WFH setup",
        bundle_items=[{"query": "ergonomic chair"}, {"query": "standing desk"}],
        fulfillment_requirements=[
            {"kind": "category", "field": "category", "value": "chair"},
            {"kind": "category", "field": "category", "value": "desk"},
            {"kind": "feature", "field": "features", "value": "ergonomic"},
            {"kind": "feature", "field": "features", "value": "standing desk"},
        ],
    )

    normalized = IntentMissionAgent._normalize_mission(mission, None)

    assert [item.model_dump() for item in normalized.fulfillment_requirements] == [
        {"kind": "category", "value": "chair", "field": None, "quantity": 1},
        {"kind": "category", "value": "desk", "field": None, "quantity": 1},
    ]


def test_initial_state_is_complete_and_mutable_fields_are_not_shared():
    first = initial_shopping_state("Find a gaming setup")
    second = initial_shopping_state("Find a travel kit")
    first["preferences"].append("wireless")

    assert first["repair_count"] == 0
    assert second["preferences"] == []
    assert first["candidate_products"] == []


def test_intent_prompt_uses_the_runtime_tool_registry():
    class RuntimeToolArgs(BaseModel):
        query: str

    class RuntimeTool:
        name = "runtime_catalog_lookup"
        description = "Look up a product in a runtime-provided catalog."
        args_schema = RuntimeToolArgs

    prompt = build_intent_system_prompt([RuntimeTool()])

    assert "runtime_catalog_lookup" in prompt
    assert "Look up a product in a runtime-provided catalog." in prompt
    assert '"query"' in prompt
    assert "search_products" not in prompt


@pytest.mark.anyio
async def test_invalid_intent_model_output_uses_a_safe_fallback():
    agent = IntentMissionAgent(FakeChatModel("not JSON"))
    result = await agent.interpret("Build a setup")

    assert result.mission_type == "information_request"
    assert result.goal == "Build a setup"
    assert result.requested_actions == []


@pytest.mark.anyio
async def test_intent_agent_retries_a_schema_failure():
    class RetryIntentModel:
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, input, **kwargs):
            self.calls += 1
            return AIMessage(content="not JSON" if self.calls == 1 else MISSION_JSON)

    model = RetryIntentModel()
    result = await IntentMissionAgent(model).interpret("Build a setup")

    assert model.calls == 2
    assert result.goal == "gaming setup"


@pytest.mark.anyio
async def test_intent_agent_retries_an_unverifiable_optimization_continuation():
    class SearchArgs(BaseModel):
        query: str

    class SearchTool:
        name = "search_products"
        description = "Search verified catalog products."
        args_schema = SearchArgs

    class RetryComparisonModel:
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, input, **kwargs):
            self.calls += 1
            payload = {
                "mission_type": "product_search",
                "recommendation_mode": "bundle",
                "goal": "refine the current setup",
                "requires_catalog": True,
                "continues_context": True,
                "optimization_mode": "lower total cost",
                "requested_actions": ["search_products"],
                "selection_criteria": [] if self.calls == 1 else [{
                    "field": "price", "operator": "lower_than_reference",
                    "value": None, "weight": 3,
                }],
            }
            return AIMessage(content=json.dumps(payload))

    model = RetryComparisonModel()
    result = await IntentMissionAgent(model, tools=[SearchTool()]).interpret(
        "Refine the current bundle",
        runtime_context={"short_term_memory": {
            "selected_products": [{"id": "prior-product"}],
            "current_bundle": {"total": "500.00"},
        }},
    )

    assert model.calls == 2
    assert result.selection_criteria[0].field == "price"
    assert result.selection_criteria[0].operator == "lower_than_reference"


@pytest.mark.anyio
async def test_brand_voice_retries_invalid_structured_output():
    class RetryModel:
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, input, **kwargs):
            self.calls += 1
            return AIMessage(content="not JSON" if self.calls == 1 else '{"response":"What product category are you interested in?","product_ids":[]}')

    model = RetryModel()
    result = await BrandVoiceAgent(model, max_format_attempts=2).compose(initial_shopping_state("I want to buy something"))

    assert model.calls == 2
    assert result["final_response"] == "What product category are you interested in?"
    assert result["response_claims"] == []


@pytest.mark.anyio
async def test_brand_voice_retries_a_valid_draft_that_omits_a_verified_product_id():
    product_id = "11111111-1111-1111-1111-111111111111"

    class CoverageRetryModel:
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, input, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='{"response":"Here is an option.","product_ids":[],"unfulfilled_requirements":[]}')
            return AIMessage(content=json.dumps({
                "response": "Verified option: Compact Desk.",
                "product_ids": [product_id],
                "unfulfilled_requirements": [],
            }))

    state = initial_shopping_state("Recommend a compact desk")
    state.update({
        "candidate_products": [{
            "id": product_id, "slug": "compact-desk", "name": "Compact Desk", "brand": "Shopy",
            "price": "199.00", "currency": "MYR", "inventory_quantity": 3,
            "category": "Office Furniture", "specs": [], "attributes": {}, "image_url": None,
        }],
        "selected_products": [{"id": product_id, "quantity": 1}],
    })
    model = CoverageRetryModel()

    result = await BrandVoiceAgent(model, max_format_attempts=2).compose(state)

    assert model.calls == 2
    assert result["response_claims"][0]["id"] == product_id


@pytest.mark.anyio
async def test_brand_voice_uses_verified_renderer_when_model_keeps_renaming_product():
    product_id = "22222222-2222-2222-2222-222222222222"

    class RenamingModel:
        async def ainvoke(self, input, **kwargs):
            return AIMessage(content=json.dumps({
                "response": "A shortened product name for RM 49.00.",
                "product_ids": [product_id],
                "unfulfilled_requirements": [],
            }))

    state = initial_shopping_state("Recommend an item")
    state.update({
        "candidate_products": [{
            "id": product_id, "slug": "exact-product", "name": "Exact Verified Product Name",
            "brand": "Shopy", "price": "49.00", "currency": "MYR",
            "inventory_quantity": 3, "category": "Accessories", "specs": [],
            "attributes": {}, "image_url": None,
        }],
        "selected_products": [{"id": product_id, "quantity": 1}],
    })

    result = await BrandVoiceAgent(RenamingModel(), max_format_attempts=2).compose(state)

    assert "Exact Verified Product Name" in result["final_response"]
    assert result["selected_products"] == [{"id": product_id, "quantity": 1}]
    assert result["response_source"] == "deterministic_catalog_renderer_v1"


@pytest.mark.anyio
async def test_optional_brand_polish_preserves_audited_response_during_model_outage():
    class UnavailableModel:
        async def ainvoke(self, input, **kwargs):
            raise RuntimeError("temporary provider failure")

    state = initial_shopping_state("Recommend an item")
    state["final_response"] = "Exact audited response."

    result = await BrandVoiceAgent(UnavailableModel()).polish(state)

    assert result == {"final_response": "Exact audited response."}


@pytest.mark.anyio
async def test_brand_voice_replaces_hidden_gap_response_with_visible_verified_disclosure():
    missing_role = "portable charger"

    class HiddenGapModel:
        async def ainvoke(self, input, **kwargs):
            return AIMessage(content=json.dumps({
                "response": "I can prepare the requested kit.",
                "product_ids": [],
                "unfulfilled_requirements": [missing_role],
            }))

    state = initial_shopping_state("Prepare a kit")
    state.update({
        "recommendation_mode": "bundle",
        "bundle": {
            "required_category_coverage": {"covered": [], "missing": [missing_role], "matches": []},
            "selected_products": [], "total": "0",
        },
        "fulfillment_gaps": [f"No verified candidate covered: {missing_role}"],
        "fulfillment_requirements": [
            {"kind": "category", "value": missing_role, "field": None, "quantity": 1},
        ],
    })

    result = await BrandVoiceAgent(HiddenGapModel(), max_format_attempts=1).compose(state)

    assert BrandVoiceAgent._gap_disclosure(missing_role) in result["final_response"]
    assert result["response_source"] == "deterministic_catalog_renderer_v1"


def test_non_product_planning_requirement_does_not_select_a_false_catalog_match():
    state = initial_shopping_state("Prepare a kit under 500")
    state.update({
        "recommendation_mode": "bundle",
        "budget": 500,
        "fulfillment_requirements": [
            {"kind": "budget", "value": "500", "field": None, "quantity": 1},
        ],
        "candidate_products": [{
            "id": "cleaner", "name": "Interior Cleaner", "brand": "Test",
            "category": "Automotive", "price": "40", "inventory_quantity": 2,
            "specs": [{"label": "Size", "value": "500 ml"}], "attributes": {},
        }],
    })

    assert BrandVoiceAgent.fulfillment_gaps(state["candidate_products"], state) == []


@pytest.mark.anyio
async def test_auditor_delivers_transparent_no_match_bundle_and_ignores_planning_metadata():
    missing_role = "portable charger"
    state = initial_shopping_state("Prepare a kit under 500")
    state.update({
        "budget": 500,
        "recommendation_mode": "bundle",
        "selected_products": [],
        "bundle": {
            "selected_products": [], "total": "0", "currency": "MYR",
            "required_category_coverage": {
                "covered": [], "missing": [missing_role], "matches": [],
            },
        },
        "fulfillment_requirements": [
            {"kind": "budget", "value": "500", "field": None, "quantity": 1},
            {"kind": "category", "value": missing_role, "field": None, "quantity": 1},
        ],
        "fulfillment_gaps": [f"No verified candidate covered: {missing_role}"],
        "unfulfilled_requirements": [missing_role],
        "final_response": f"I could not verify a matching item for: {missing_role}.",
        "response_claims": [],
        "response_source": "deterministic_catalog_renderer_v1",
        "attachments": [],
    })

    result = await ShoppingAuditor().audit(state, tools=None)

    assert result["status"] == "pass"


def test_catalog_selection_covers_each_dynamic_requirement_with_a_different_product():
    state = initial_shopping_state("Build a work outfit")
    state.update({
        "recommendation_mode": "bundle",
        "fulfillment_requirements": [
            {"kind": "category", "value": "shirt", "field": None, "quantity": 1},
            {"kind": "category", "value": "pants", "field": None, "quantity": 1},
        ],
        "candidate_products": [
            {"id": "shirt", "name": "Formal Shirt", "brand": "Shopy", "category": "Formal Wear", "price": "109", "inventory_quantity": 4, "specs": [], "attributes": {"department": "apparel"}},
            {"id": "pants", "name": "Flex Taper Chinos", "brand": "Shopy", "category": "Pants", "price": "139", "inventory_quantity": 4, "specs": [], "attributes": {"department": "apparel"}},
            {"id": "bag", "name": "Work Bag", "brand": "Shopy", "category": "Accessories", "price": "89", "inventory_quantity": 4, "specs": [], "attributes": {"department": "apparel"}},
        ],
    })

    assert BrandVoiceAgent.select_catalog_products(state) == [
        {"id": "shirt", "quantity": 1}, {"id": "pants", "quantity": 1},
    ]


def test_catalog_selection_does_not_invent_product_family_aliases():
    state = initial_shopping_state("Build a weekend travel kit")
    state.update({
        "recommendation_mode": "bundle",
        "fulfillment_requirements": [
            {"kind": "category", "value": "Travel Bag", "field": None, "quantity": 1},
            {"kind": "category", "value": "Toiletries", "field": None, "quantity": 1},
        ],
        "candidate_products": [
            {"id": "pack", "name": "Thule Aion 28L", "brand": "Thule", "category": "Travel Backpack", "price": "699", "inventory_quantity": 4, "specs": [], "attributes": {"department": "travel"}},
            {"id": "toiletry", "name": "BAGSMART Hanging Toiletry Bag", "brand": "BAGSMART", "category": "Toiletry Organiser", "price": "89", "inventory_quantity": 4, "specs": [], "attributes": {"department": "travel"}},
        ],
    })

    # The deterministic fallback uses only catalog text. Semantic family
    # mapping belongs to the bundle model and its verified coverage record.
    assert BrandVoiceAgent.select_catalog_products(state) == [
        {"id": "toiletry", "quantity": 1},
    ]


def test_product_role_matching_rejects_accessories_that_only_mention_the_role():
    monitor_arm = {
        "name": "Arc Single Monitor Arm", "category": "Desk Accessories",
        "specs": [{"label": "Compatibility", "value": "17-32 inch monitors"}],
        "attributes": {"compatibility": "VESA monitors"},
    }
    desk_mat = {
        "name": "Orbit XL Desk Mat", "category": "Desk Accessories",
        "specs": [], "attributes": {"compatibility": "keyboard and mouse"},
    }

    assert not BundleOptimizerAgent._matches(monitor_arm, "monitor")
    assert not BundleOptimizerAgent._matches(desk_mat, "mouse")
    assert not BrandVoiceAgent._matches_requirement(
        monitor_arm, {"kind": "category", "value": "monitor", "field": None}
    )
    assert BundleOptimizerAgent._matches(monitor_arm, "monitor arm")


def test_auditor_allows_llm_objection_that_only_repeats_a_verified_disclosed_gap():
    finding = AuditFinding(
        code="missing_requirement_coverage",
        message="The standing desk was not included.",
        excerpt="A standing desk could not be included in this selection.",
    )
    state = {
        "unfulfilled_requirements": ["standing desk"],
        "fulfillment_gaps": ["No verified candidate covered: standing desk"],
    }

    assert ShoppingAuditor._is_transparent_verified_gap(finding, state)


def test_auditor_recognizes_verified_gap_named_in_finding_message_not_excerpt():
    finding = AuditFinding(
        code="missing_requirement_coverage",
        message="The portable charger requirement is not covered.",
        excerpt="I can help with your request.",
    )
    state = {
        "unfulfilled_requirements": ["portable charger"],
        "fulfillment_gaps": ["No verified candidate covered: portable charger"],
    }

    assert ShoppingAuditor._is_transparent_verified_gap(finding, state)


def test_auditor_allows_exact_writer_disclosure_when_review_mislabels_it_as_unsupported():
    missing_role = "travel toiletries kit"
    finding = AuditFinding(
        code="unsupported_prose_claim",
        message="The response says the item was not found, but the bundle only marks it missing.",
        excerpt=BrandVoiceAgent._gap_disclosure(missing_role),
    )
    state = {
        "unfulfilled_requirements": [missing_role],
        "fulfillment_gaps": [f"No verified candidate covered: {missing_role}"],
    }

    assert ShoppingAuditor._is_transparent_verified_gap(finding, state)


def test_auditor_keeps_a_different_unsupported_claim_about_a_missing_role():
    missing_role = "travel toiletries kit"
    finding = AuditFinding(
        code="unsupported_prose_claim",
        message="The waterproof claim is not in verified evidence.",
        excerpt="The travel toiletries kit is completely waterproof.",
    )
    state = {
        "unfulfilled_requirements": [missing_role],
        "fulfillment_gaps": [f"No verified candidate covered: {missing_role}"],
    }

    assert not ShoppingAuditor._is_transparent_verified_gap(finding, state)


def test_auditor_allows_exact_verified_over_budget_disclosure():
    finding = AuditFinding(
        code="unsupported_prose_claim",
        message="The overage is within the configured recommendation tolerance.",
        excerpt="The total is RM 417.00, which is RM 17.00 over your budget of RM 400.00.",
    )
    state = {
        "budget": 400,
        "recommendation_mode": "bundle",
        "bundle": {"total": "417.00"},
    }

    assert ShoppingAuditor._is_verified_budget_disclosure(finding, state)


def test_semantic_audit_arithmetic_keeps_single_recommendations_as_alternatives():
    state = {
        "recommendation_mode": "single",
        "budget": 3800,
        "selected_products": [
            {"id": "pixel", "quantity": 1},
            {"id": "xiaomi", "quantity": 1},
            {"id": "nova", "quantity": 1},
        ],
    }
    products = {
        "pixel": {"id": "pixel", "price": "3799.00"},
        "xiaomi": {"id": "xiaomi", "price": "3499.00"},
        "nova": {"id": "nova", "price": "2190.00"},
    }

    arithmetic = ShoppingAuditor._verified_arithmetic(
        state, products, Decimal("9488.00")
    )

    assert arithmetic["budget_scope"] == "per_option"
    assert arithmetic["selected_total"] is None
    assert [item["option_total"] for item in arithmetic["option_totals"]] == [
        "3799.00", "3499.00", "2190.00",
    ]
    assert all(item["within_target"] for item in arithmetic["option_totals"])


def test_semantic_audit_arithmetic_combines_products_only_for_bundles():
    arithmetic = ShoppingAuditor._verified_arithmetic(
        {"recommendation_mode": "bundle", "budget": 400},
        {},
        Decimal("417.00"),
    )

    assert arithmetic["budget_scope"] == "combined_bundle"
    assert arithmetic["selected_total"] == "417.00"
    assert arithmetic["over_target_by"] == "17.00"


def test_response_writer_rejects_unverified_availability_language_dynamically():
    assert BrandVoiceAgent._contains_unverified_availability_language(
        "The verified option is available for RM 3499.00."
    )
    assert not BrandVoiceAgent._contains_unverified_availability_language(
        "The verified option costs RM 3499.00."
    )
    assert not BrandVoiceAgent._contains_unverified_availability_language(
        "The verified color is available in Black and Silver."
    )


@pytest.mark.anyio
async def test_auditor_blocks_price_based_availability_outside_stock_flow():
    state = initial_shopping_state("Show me an option")
    state.update({
        "final_response": "The verified option is available for RM 3499.00.",
        "response_source": "structured_llm_brand_voice_v1",
        "response_claims": [],
    })

    audit = await ShoppingAuditor().audit(state, tools=None)

    assert any(
        error["code"] == "unsupported_availability_claim"
        for error in audit["errors"]
    )


def test_feature_requirement_requires_value_and_product_role():
    mouse = {
        "name": "Glide Wireless Mouse", "brand": "Glide", "category": "Mice",
        "specs": [], "attributes": {"connectivity": "wireless"},
    }

    assert BrandVoiceAgent._matches_requirement(
        mouse, {"kind": "feature", "field": "mouse", "value": "wireless"}
    )
    assert not BrandVoiceAgent._matches_requirement(
        mouse, {"kind": "feature", "field": "keyboard", "value": "wireless"}
    )


def test_auditor_rejects_bundle_metadata_for_a_previous_selection():
    errors: list[dict[str, str]] = []
    state = {
        "recommendation_mode": "bundle",
        "bundle": {
            "selected_products": [{"product_id": "old-product", "quantity": 1}],
            "total": "100",
        },
    }

    ShoppingAuditor._validate_bundle_consistency(state, ["new-product"], Decimal("120"), errors)

    assert {error["code"] for error in errors} == {"stale_bundle_selection", "stale_bundle_total"}


def test_auditor_accepts_a_transparent_bundle_gap_with_a_more_specific_role_name():
    headphone = {
        "id": "headphones", "name": "Quiet Headphones", "brand": "Test",
        "category": "Headphones", "price": "500", "inventory_quantity": 1,
        "specs": [{"label": "Feature", "value": "Noise cancelling"}], "attributes": {},
    }
    state = initial_shopping_state("Build a setup")
    state.update({
        "recommendation_mode": "bundle",
        "budget": 1000,
        "candidate_products": [headphone],
        "fulfillment_requirements": [
            {"kind": "feature", "field": "feature", "value": "noise cancelling", "quantity": 1},
        ],
        "fulfillment_gaps": ["No verified candidate covered: noise cancelling headphones"],
        "unfulfilled_requirements": ["noise cancelling headphones"],
        "bundle": {"required_category_coverage": {
            "covered": [], "missing": ["noise cancelling headphones"], "matches": [],
        }},
    })
    errors: list[dict[str, str]] = []

    ShoppingAuditor._validate_fulfillment(state, {}, errors)

    assert errors == []


def test_single_recommendation_mode_returns_two_comparable_choices_when_available():
    state = initial_shopping_state("Recommend a dining chair")
    state.update({
        "recommendation_mode": "single",
        "fulfillment_requirements": [{"kind": "category", "value": "chair", "field": None, "quantity": 1}],
        "candidate_products": [
            {"id": "cane", "name": "Cane Dining Chair", "brand": "Shopy", "category": "Dining Chairs", "price": "249", "inventory_quantity": 4, "specs": [], "attributes": {}},
            {"id": "oak", "name": "Oak Dining Chair", "brand": "Shopy", "category": "Dining Chairs", "price": "299", "inventory_quantity": 4, "specs": [], "attributes": {}},
            {"id": "lamp", "name": "Dining Lamp", "brand": "Shopy", "category": "Lighting", "price": "159", "inventory_quantity": 4, "specs": [], "attributes": {}},
        ],
    })

    assert BrandVoiceAgent.select_catalog_products(state) == [
        {"id": "cane", "quantity": 1}, {"id": "oak", "quantity": 1},
    ]


def test_single_phone_request_keeps_multiple_llm_resolved_comparables():
    state = initial_shopping_state("I want to buy a phone under RM 5,000")
    state.update({
        "recommendation_mode": "single",
        "budget": 5_000,
        "fulfillment_requirements": [{"kind": "category", "value": "phone", "field": None, "quantity": 1}],
        # These are the same kind of post-resolution candidates shown in the
        # supplied log: all are verified phones within the stated budget.
        "candidate_products": [
            {"id": "iphone-16", "name": "Apple iPhone 16", "brand": "Apple", "category": "Phones", "price": "3999", "inventory_quantity": 42, "specs": [], "attributes": {}},
            {"id": "iphone-16-pro", "name": "Apple iPhone 16 Pro", "brand": "Apple", "category": "Phones", "price": "4999", "inventory_quantity": 24, "specs": [], "attributes": {}},
            {"id": "galaxy-s25", "name": "Samsung Galaxy S25", "brand": "Samsung", "category": "Phones", "price": "3999", "inventory_quantity": 38, "specs": [], "attributes": {}},
        ],
    })

    assert BrandVoiceAgent.select_catalog_products(state) == [
        {"id": "iphone-16", "quantity": 1}, {"id": "iphone-16-pro", "quantity": 1},
    ]


def test_single_recommendation_allows_a_configured_near_budget_option_but_not_a_larger_overrun():
    state = initial_shopping_state("Recommend a phone under RM 5,000")
    state.update({
        "recommendation_mode": "single",
        "budget": 5_000,
        "fulfillment_requirements": [{"kind": "category", "value": "phone", "field": None, "quantity": 1}],
        "candidate_products": [
            {"id": "near-budget", "name": "Near Budget Phone", "category": "Phones", "price": "6500", "inventory_quantity": 4, "specs": [], "attributes": {}},
            {"id": "too-far", "name": "Too Far Phone", "category": "Phones", "price": "6500.01", "inventory_quantity": 4, "specs": [], "attributes": {}},
        ],
    })

    assert BrandVoiceAgent.select_catalog_products(state) == [{"id": "near-budget", "quantity": 1}]


@pytest.mark.anyio
async def test_llm_selected_bundle_mode_receives_a_multi_product_bundle():
    state = initial_shopping_state("Build me a dining furniture collection")
    state.update({
        "mission_type": "product_search",
        "recommendation_mode": "bundle",
        "budget": 1_000,
        "required_categories": ["chair", "table", "lamp"],
        "candidate_products": [
            {"id": "chair", "name": "Cane Dining Chair", "category": "Dining Furniture", "price": "249", "inventory_quantity": 4},
            {"id": "table", "name": "Round Dining Table", "category": "Dining Tables", "price": "499", "inventory_quantity": 3},
            {"id": "lamp", "name": "Warm Dining Lamp", "category": "Lighting", "price": "159", "inventory_quantity": 7},
        ],
    })

    result = await BundleOptimizerAgent().run(state)

    assert result["bundle"]["product_count"] == 3
    assert {item["id"] for item in result["selected_products"]} == {"chair", "table", "lamp"}


def test_auditor_allows_a_declared_gap_in_a_partially_fulfilled_bundle():
    travel_bag = {
        "id": "pack", "name": "Thule Aion 28L", "brand": "Thule", "category": "Travel Backpack",
        "price": "699", "inventory_quantity": 4, "specs": [], "attributes": {"department": "travel"},
    }
    state = initial_shopping_state("Build a weekend travel kit")
    state.update({
        "candidate_products": [travel_bag],
        "fulfillment_requirements": [
            {"kind": "category", "value": "Travel Bag", "field": None, "quantity": 1},
            {"kind": "category", "value": "Clothing", "field": None, "quantity": 1},
        ],
        "fulfillment_gaps": ["No verified catalog match for: Clothing"],
        "unfulfilled_requirements": ["clothing"],
        "bundle": {
                "required_category_coverage": {
                    "covered": ["Travel Bag"],
                    "missing": ["Clothing"],
                    "matches": [{"requirement": "Travel Bag", "product_id": "pack"}],
                },
        },
    })
    errors: list[dict[str, str]] = []

    ShoppingAuditor._validate_fulfillment(state, {"pack": travel_bag}, errors)

    assert errors == []


def test_catalog_selection_normalizes_product_type_across_category_fields():
    """A singular intent requirement must match plural/domain catalog labels."""
    state = initial_shopping_state("I want to buy a cheap laptop")
    state.update({
        # Mirrors a malformed-but-recoverable intent field from a live run.
        "fulfillment_requirements": [{"kind": "attribute", "field": "category", "value": "laptop", "quantity": 1}],
        "candidate_products": [{
            "id": "laptop", "name": "Acer Swift Go 14", "brand": "Acer", "category": "Laptops",
            "price": "3699", "inventory_quantity": 5, "specs": [],
            "attributes": {"department": "electronics", "device_category": "laptops"},
        }],
    })

    assert BrandVoiceAgent.fulfillment_gaps(state["candidate_products"], state) == []
    assert BrandVoiceAgent.select_catalog_products(state) == [{"id": "laptop", "quantity": 1}]


@pytest.mark.anyio
async def test_bundle_resolves_generic_product_form_terms_from_catalog_evidence():
    """Customer phrasing should not create a gap for an equivalent catalog type."""
    shampoo = {
        "id": "shampoo", "name": "Gold Class Car Wash Shampoo", "brand": "Meguiar's",
        "category": "Car Shampoo", "price": "49", "inventory_quantity": 8,
        "specs": [], "attributes": {"department": "automotive", "car_care_category": "Car Shampoo"},
    }
    mitt = {
        "id": "mitt", "name": "Chenille Premium Car Wash Mitt", "brand": "Chemical Guys",
        "category": "Wash Mitt", "price": "29", "inventory_quantity": 8,
        "specs": [], "attributes": {"department": "automotive", "car_care_category": "Wash Mitt"},
    }
    state = initial_shopping_state("Build a weekly wash kit")
    state.update({
        "recommendation_mode": "bundle", "budget": 300,
        "required_categories": ["car wash soap"],
        "fulfillment_requirements": [{"kind": "category", "value": "car wash soap", "field": None, "quantity": 1}],
        "candidate_products": [shampoo, mitt],
    })

    assert BrandVoiceAgent.fulfillment_gaps(state["candidate_products"], state) == []
    assert BrandVoiceAgent._matches_requirement(
        shampoo, {"kind": "category", "value": "car wash soap", "field": None}
    )
    assert not BrandVoiceAgent._matches_requirement(
        mitt, {"kind": "category", "value": "car wash soap", "field": None}
    )

    result = await BundleOptimizerAgent().run(state)

    assert result["selected_products"] == [{"id": "shampoo", "quantity": 1}]
    assert result["bundle"]["required_category_coverage"]["missing"] == []


def test_catalog_queries_remove_only_redundant_subqueries():
    state = initial_shopping_state("Find a cheap laptop")
    state.update({"catalog_queries": ["cheap laptop", "toner"], "catalog_query": "laptop"})

    assert ShoppingOrchestrator._catalog_queries(state) == ["cheap laptop", "toner"]


def test_optimisation_continuation_uses_llm_criteria_and_a_prior_catalog_fact():
    state = initial_shopping_state("This is too expensive for me")
    state.update({
        "continues_context": True,
        "optimization_mode": "cheaper",
        "selection_criteria": [{
            "field": "price", "operator": "lower_than_reference", "value": None, "weight": 3,
        }],
        "memory_context": {"selected_products": [{"id": "current-phone", "quantity": 1}]},
    })
    candidates = [
        {"id": "current-phone", "name": "Current Phone", "price": "3999.00"},
        {"id": "lower-phone", "name": "Lower-Priced Phone", "price": "3499.00"},
        {"id": "higher-phone", "name": "Higher-Priced Phone", "price": "4599.00"},
    ]

    alternatives, context = ShoppingOrchestrator._apply_optimization_context(state, candidates)

    assert [item["id"] for item in alternatives] == ["lower-phone"]
    assert context["reference_product_ids"] == ["current-phone"]
    assert context["eligible_alternative_count"] == 1
    assert context["no_eligible_alternative"] is False
    assert context["applied_comparisons"] == [{
        "field": "price", "operator": "lower_than_reference",
        "reference_value": "3999.00", "eligible_count": 1,
    }]


def test_single_refinement_filters_by_dynamic_product_role_before_comparison():
    state = initial_shopping_state("Make it cheaper")
    state.update({
        "recommendation_mode": "single",
        "continues_context": True,
        "fulfillment_requirements": [
            {"kind": "category", "field": None, "value": "phone", "quantity": 1},
        ],
        "selection_criteria": [{
            "field": "price", "operator": "lower_than_reference", "value": None, "weight": 3,
        }],
        "memory_context": {"selected_products": [{"id": "current-phone", "quantity": 1}]},
    })
    candidates = [
        {"id": "current-phone", "name": "Current Phone", "category": "Phones", "price": "3499"},
        {"id": "value-phone", "name": "Value Phone", "category": "Phones", "price": "2190"},
        {"id": "cable", "name": "Phone Charging Cable", "category": "Cables", "price": "49"},
        {"id": "holder", "name": "Magnetic Phone Holder", "category": "Car Accessories", "price": "59"},
    ]

    role_candidates = ShoppingOrchestrator._role_constrained_candidates(state, candidates)
    alternatives, context = ShoppingOrchestrator._apply_optimization_context(
        state, role_candidates
    )

    assert [item["id"] for item in role_candidates] == ["current-phone", "value-phone"]
    assert [item["id"] for item in alternatives] == ["value-phone"]
    assert context["eligible_alternative_count"] == 1


def test_auditor_rejects_a_false_gap_when_refinement_alternatives_exist():
    state = initial_shopping_state("Make it cheaper")
    state.update({
        "recommendation_mode": "single",
        "fulfillment_requirements": [
            {"kind": "category", "field": None, "value": "phone", "quantity": 1},
        ],
        "fulfillment_gaps": ["No verified catalog match for: phone"],
        "unfulfilled_requirements": ["phone"],
        "selection_context": {
            "eligible_alternative_count": 2,
            "no_eligible_alternative": False,
        },
    })
    errors: list[dict[str, str]] = []

    ShoppingAuditor._validate_fulfillment(state, {}, errors)

    assert any(error["code"] == "catalog_match_not_selected" for error in errors)


def test_bundle_refinement_inherits_the_complete_prior_mission_contract():
    follow_up = MissionInterpretation(
        mission_type="product_search", recommendation_mode="single",
        goal="a cheaper setup", continues_context=True, optimization_mode="cheaper",
        requires_catalog=True, requested_actions=["search_products"],
        bundle_items=[{"query": "cheaper setup"}],
        fulfillment_requirements=[{"kind": "category", "value": "setup"}],
        selection_criteria=[{
            "field": "price", "operator": "lower_than_reference", "value": None, "weight": 3,
        }],
    )
    memory = {
        "budget": 1000,
        "preferences": ["lightweight"],
        "current_mission": {
            "mission_type": "product_search", "recommendation_mode": "bundle",
            "goal": "travel setup", "requires_catalog": True,
            "catalog_queries": ["carry-on", "travel pillow", "travel adapter"],
            "requested_actions": ["search_products"],
            "bundle_items": [{"query": "carry-on"}, {"query": "travel pillow"}, {"query": "travel adapter"}],
            "fulfillment_requirements": [
                {"kind": "category", "value": "carry-on", "quantity": 1},
                {"kind": "category", "value": "travel pillow", "quantity": 1},
                {"kind": "category", "value": "travel adapter", "quantity": 1},
            ],
        },
    }

    merged = ShoppingOrchestrator._merge_continuation_mission(follow_up, memory)

    assert merged.goal == "travel setup"
    assert merged.recommendation_mode == "bundle"
    assert merged.budget == 1000
    assert [item.query for item in merged.bundle_items] == ["carry-on", "travel pillow", "travel adapter"]
    assert [item.value for item in merged.fulfillment_requirements] == ["carry-on", "travel pillow", "travel adapter"]
    assert merged.selection_criteria == follow_up.selection_criteria


def test_manager_always_runs_optimizer_for_bundle_mode_even_with_one_planned_role():
    plan = WorkflowManager().plan({
        "mission_type": "product_search", "recommendation_mode": "bundle",
        "required_categories": ["travel setup"], "owned_items": [],
    }, ["search_products"])

    assert plan["stages"] == ["bundle_optimizer"]


def test_manager_does_not_schedule_review_intelligence_for_aggregate_ratings():
    plan = WorkflowManager().plan({
        "mission_type": "product_search", "recommendation_mode": "single",
        "required_categories": ["headphones"], "owned_items": [],
    }, ["search_products", "get_product_reviews"])

    assert plan["stages"] == []


def test_bundle_price_refinement_uses_prior_total_without_filtering_product_roles():
    state = initial_shopping_state("Make the setup cheaper")
    state.update({
        "continues_context": True, "recommendation_mode": "bundle", "optimization_mode": "cheaper",
        "selection_criteria": [{
            "field": "price", "operator": "lower_than_reference", "value": None, "weight": 3,
        }],
        "memory_context": {
            "selected_products": [{"id": "old-chair"}, {"id": "old-lamp"}],
            "current_bundle": {"total": "500.00"},
        },
    })
    candidates = [
        {"id": "old-chair", "name": "Old Chair", "price": "350"},
        {"id": "new-chair", "name": "New Chair", "price": "220"},
        {"id": "old-lamp", "name": "Old Lamp", "price": "150"},
        {"id": "new-lamp", "name": "New Lamp", "price": "80"},
    ]

    alternatives, context = ShoppingOrchestrator._apply_optimization_context(state, candidates)

    assert {item["id"] for item in alternatives} == {item["id"] for item in candidates}
    assert context["reference_bundle_total"] == "500.00"
    assert context["applied_comparisons"] == [{
        "field": "price", "operator": "lower_than_reference", "reference_value": "500.00",
        "scope": "bundle_total", "eligible_count": 4,
    }]


@pytest.mark.anyio
async def test_bundle_price_refinement_selects_a_lower_total_for_the_same_roles():
    state = initial_shopping_state("Make the setup cheaper")
    state.update({
        "recommendation_mode": "bundle", "budget": 1000,
        "required_categories": ["chair", "lamp"],
        "selection_context": {"applied_comparisons": [{
            "field": "price", "operator": "lower_than_reference",
            "reference_value": "500.00", "scope": "bundle_total",
        }]},
        "candidate_products": [
            {"id": "premium-chair", "name": "Premium Chair", "category": "Chairs", "price": "420", "currency": "MYR", "inventory_quantity": 2},
            {"id": "value-chair", "name": "Value Chair", "category": "Chairs", "price": "220", "currency": "MYR", "inventory_quantity": 2},
            {"id": "premium-lamp", "name": "Premium Lamp", "category": "Lamps", "price": "190", "currency": "MYR", "inventory_quantity": 2},
            {"id": "value-lamp", "name": "Value Lamp", "category": "Lamps", "price": "80", "currency": "MYR", "inventory_quantity": 2},
        ],
    })

    result = await BundleOptimizerAgent().run(state)

    assert result["bundle"]["total"] == "300"
    assert {item["id"] for item in result["selected_products"]} == {"value-chair", "value-lamp"}
    assert result["bundle"]["required_category_coverage"]["missing"] == []


def test_optimisation_can_rank_by_dynamic_qualitative_catalog_evidence():
    state = initial_shopping_state("Make it more comfortable")
    state.update({
        "continues_context": True,
        "optimization_mode": "comfort",
        "selection_criteria": [{
            "field": "comfort", "operator": "prefer_match", "value": "ergonomic lumbar support", "weight": 5,
        }],
    })
    candidates = [
        {"id": "basic", "name": "Basic Chair", "price": "200", "attributes": {}, "specs": [{"text": "fixed seat"}]},
        {"id": "ergonomic", "name": "Ergonomic Chair", "price": "400", "attributes": {"support": "adjustable lumbar support"}, "specs": []},
    ]

    alternatives, context = ShoppingOrchestrator._apply_optimization_context(state, candidates)

    assert [item["id"] for item in alternatives] == ["ergonomic", "basic"]
    assert context["no_eligible_alternative"] is False


@pytest.mark.anyio
async def test_brand_voice_polishes_an_audited_draft_with_a_run_specific_strategy():
    class PolishModel:
        async def ainvoke(self, input, **kwargs):
            assert "final brand-voice editor" in str(input[0].content)
            payload = json.loads(str(input[1].content))
            assert payload["variation"]["variation_token"] == "un-token"
            return AIMessage(content='{"response":"Here is the same verified answer in fresher wording."}')

    state = initial_shopping_state("Find a desk lamp")
    state.update({"run_id": "example-run-token", "final_response": "Verified answer.", "response_claims": []})

    result = await BrandVoiceAgent(PolishModel()).polish(state)

    assert result["final_response"] == "Here is the same verified answer in fresher wording."


@pytest.mark.anyio
async def test_orchestrator_routes_intent_to_planner_and_audit():
    orchestrator = ShoppingOrchestrator(FakeChatModel(MISSION_JSON))
    result = await orchestrator.ainvoke("Build me a gaming setup under RM4,000.")

    assert result["goal"] == "gaming setup"
    assert result["required_categories"]
    assert result["next_stage"] == "final_audit"
    assert result["audit_result"]["status"] == "pass"
    assert result["final_response"] is not None


@pytest.mark.anyio
async def test_orchestrator_routes_general_planning_requests_to_planning_agent():
    class PlanningModel:
        async def ainvoke(self, input, **kwargs):
            prompt = str(input[0].content)
            if "general planning agent" in prompt:
                return AIMessage(content=json.dumps({
                    "plan_type": "move_in", "summary": "Start with essentials.",
                    "steps": ["Set up utilities.", "Prepare one room at a time."],
                    "follow_up_questions": ["Which room comes first?"],
                    "suggested_shopping_categories": ["cleaning essentials"],
                }))
            if "response-writing agent" in prompt:
                return AIMessage(content='{"response":"Start with utilities, then set up one room at a time.","product_ids":[],"unfulfilled_requirements":[]}')
            return AIMessage(content='{"mission_type":"planning_request","goal":"prepare a new home","requires_planning":true,"requires_catalog":false,"catalog_query":null,"catalog_queries":[],"requested_actions":[],"budget":null,"bundle_items":[],"preferences":[],"constraints":[],"owned_items":[],"priorities":[],"fulfillment_requirements":[]}')

    result = await ShoppingOrchestrator(PlanningModel()).ainvoke("I am moving into a new house. What should I prepare?")

    assert result["planning_context"]["plan_type"] == "move_in"
    assert result["audit_result"]["status"] == "pass"
