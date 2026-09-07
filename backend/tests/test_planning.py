import pytest
from langchain_core.messages import AIMessage

from app.agentic.planning import PlanningAgent
from app.agentic.state import initial_shopping_state


class RoomPlanningModel:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(content=(
                '{"plan_type":"general_planning","summary":"A room plan.",'
                '"requires_catalog":true,"fulfillment_requirements":[],"steps":[], '
                '"follow_up_questions":[],"suggested_shopping_categories":[],"catalog_queries":[]}'
            ))
        return AIMessage(content=(
            '{"plan_type":"room_plan","summary":"A coordinated room update.",'
            '"requires_catalog":true,"fulfillment_requirements":['
            '{"kind":"category","value":"room seating","field":null,"quantity":1},'
            '{"kind":"category","value":"room lighting","field":null,"quantity":1}],'
            '"steps":[],"follow_up_questions":[],"suggested_shopping_categories":[],'
            '"catalog_queries":["room seating","room lighting"]}'
        ))


@pytest.mark.anyio
async def test_catalog_bound_planning_retries_for_llm_derived_retrieval_needs():
    model = RoomPlanningModel()
    state = initial_shopping_state("Help me fill and style my room.")
    state.update({"requires_catalog": True, "mission": {"goal": "Fill and style a room."}})

    result = await PlanningAgent(model, max_format_attempts=2).run(state)

    assert model.calls == 2
    assert result["requires_catalog"] is True
    assert result["required_categories"] == ["room seating", "room lighting"]
    assert result["catalog_queries"] == ["room seating", "room lighting"]


@pytest.mark.anyio
async def test_llm_planning_resolves_a_broad_setup_into_bundle_roles():
    class GamingPlanningModel:
        def __init__(self) -> None:
            self.kwargs = None

        async def ainvoke(self, messages, **kwargs):
            self.kwargs = kwargs
            return AIMessage(content=(
                '{"plan_type":"room_setup","summary":"A coordinated gaming setup.",'
                '"requires_catalog":true,"recommendation_mode":"bundle",'
                '"fulfillment_requirements":['
                '{"kind":"category","value":"desk","field":null,"quantity":1},'
                '{"kind":"category","value":"monitor","field":null,"quantity":1},'
                '{"kind":"category","value":"chair","field":null,"quantity":1},'
                '{"kind":"category","value":"keyboard","field":null,"quantity":1}],'
                '"steps":[],"follow_up_questions":[],"suggested_shopping_categories":[],'
                '"catalog_queries":["desk","monitor","chair","keyboard"]}'
            ))

    model = GamingPlanningModel()
    state = initial_shopping_state("i need a setup for my gaming room")
    state.update({
        "requires_catalog": True,
        "requires_planning": True,
        "requested_actions": ["search_products"],
        "mission": {"goal": "i need a setup for my gaming room"},
    })

    result = await PlanningAgent(model, max_format_attempts=1).run(state)

    assert result["recommendation_mode"] == "bundle"
    assert result["required_categories"] == ["desk", "monitor", "chair", "keyboard"]
    assert model.kwargs["response_mime_type"] == "application/json"
    assert model.kwargs["max_output_tokens"] >= 3000


@pytest.mark.anyio
async def test_planner_keeps_explicit_single_mode_for_multiple_retrieval_phrasings():
    class ComparisonPlanningModel:
        async def ainvoke(self, messages, **kwargs):
            return AIMessage(content=(
                '{"plan_type":"product_search","summary":"Compare matching phones.",'
                '"requires_catalog":true,"recommendation_mode":"single",'
                '"fulfillment_requirements":[{"kind":"category","value":"phone","field":null,"quantity":1}],'
                '"steps":[],"follow_up_questions":[],"suggested_shopping_categories":[],'
                '"catalog_queries":["Samsung phone","Samsung smartphone","phone"]}'
            ))

    state = initial_shopping_state("I want a Samsung phone")
    state.update({"requires_catalog": True, "requires_planning": True})

    result = await PlanningAgent(ComparisonPlanningModel(), max_format_attempts=1).run(state)

    assert result["recommendation_mode"] == "single"


@pytest.mark.anyio
async def test_bundle_planning_preserves_every_intent_product_role():
    model = RoomPlanningModel()
    state = initial_shopping_state("Build a complete setup")
    roles = ["office chair", "standing desk", "monitor", "wireless keyboard", "wireless mouse", "desk lamp"]
    state.update({
        "requires_catalog": True,
        "recommendation_mode": "bundle",
        "bundle_items": [{"query": role, "quantity": 1} for role in roles],
        "mission": {"goal": "Build a complete setup"},
    })

    result = await PlanningAgent(model, max_format_attempts=2).run(state)

    assert result["required_categories"] == roles


@pytest.mark.anyio
async def test_bundle_planning_keeps_inferred_queries_optional_instead_of_enforcing_an_umbrella():
    class TravelPlanningModel:
        async def ainvoke(self, messages, **kwargs):
            return AIMessage(content=(
                '{"plan_type":"travel_plan","summary":"A compact kit.",'
                '"requires_catalog":true,"fulfillment_requirements":['
                '{"kind":"category","value":"Travel Essentials","field":null,"quantity":1}],'
                '"steps":[],"follow_up_questions":[],"suggested_shopping_categories":[],'
                '"catalog_queries":["travel toiletry bag","compact first aid kit","portable charger"]}'
            ))

    state = initial_shopping_state("Prepare a travel kit within my budget")
    state.update({
        "requires_catalog": False,
        "recommendation_mode": "bundle",
        "mission": {"goal": "Prepare a travel kit"},
    })

    result = await PlanningAgent(TravelPlanningModel(), max_format_attempts=2).run(state)

    roles = ["travel toiletry bag", "compact first aid kit", "portable charger"]
    assert result["requires_catalog"] is True
    assert result["required_categories"] == []
    assert result["optional_categories"] == roles
    assert result.get("fulfillment_requirements", []) == []
    assert result["planning_context"]["fulfillment_requirements"] == []


@pytest.mark.anyio
async def test_planner_retries_its_own_catalog_decision_when_queries_are_missing():
    model = RoomPlanningModel()
    state = initial_shopping_state("Help me choose products for a room")
    state.update({"requires_catalog": False, "mission": {"goal": "Choose room products"}})

    result = await PlanningAgent(model, max_format_attempts=2).run(state)

    assert model.calls == 2
    assert result["requires_catalog"] is True


@pytest.mark.anyio
async def test_planner_repairs_invented_item_budgets_and_non_product_requirements():
    class ContractRepairModel:
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content=(
                    '{"plan_type":"trip","summary":"A travel kit.","requires_catalog":true,'
                    '"fulfillment_requirements":['
                    '{"kind":"budget","value":"500","field":null,"quantity":1},'
                    '{"kind":"category","value":"toiletries under 50","field":null,"quantity":1}],'
                    '"steps":[],"follow_up_questions":[],'
                    '"suggested_shopping_categories":["toiletries","portable charger"],'
                    '"catalog_queries":["toiletries under 50","portable charger under 100"]}'
                ))
            return AIMessage(content=(
                '{"plan_type":"trip","summary":"A travel kit.","requires_catalog":true,'
                '"fulfillment_requirements":['
                '{"kind":"category","value":"toiletry bottles","field":null,"quantity":1},'
                '{"kind":"category","value":"portable charger","field":null,"quantity":1}],'
                '"steps":[],"follow_up_questions":[],"suggested_shopping_categories":[],'
                '"catalog_queries":["toiletry bottles","portable charger"]}'
            ))

    model = ContractRepairModel()
    state = initial_shopping_state("Prepare a travel kit under 500")
    state.update({"recommendation_mode": "bundle", "mission": {"budget": 500}})

    result = await PlanningAgent(model, max_format_attempts=2).run(state)

    assert model.calls == 2
    assert result["required_categories"] == ["toiletry bottles", "portable charger"]
    assert {item["kind"] for item in result["fulfillment_requirements"]} == {"category"}
    assert all("50" not in query and "100" not in query for query in result["catalog_queries"])


@pytest.mark.anyio
async def test_optional_planning_format_failure_preserves_existing_catalog_mission():
    class InvalidPlanningModel:
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, messages, **kwargs):
            self.calls += 1
            return AIMessage(content="not valid planning json")

    model = InvalidPlanningModel()
    state = initial_shopping_state("Build me a travel kit for a weekend trip.")
    state.update({
        "requires_catalog": True,
        "recommendation_mode": "bundle",
        "catalog_queries": ["backpack", "packing cubes", "power adapter"],
        "bundle_items": [
            {"query": "backpack", "quantity": 1},
            {"query": "packing cubes", "quantity": 1},
            {"query": "power adapter", "quantity": 1},
        ],
        "fulfillment_requirements": [
            {"kind": "category", "value": role, "field": None, "quantity": 1}
            for role in ("backpack", "packing cubes", "power adapter")
        ],
        "mission": {"goal": "Create a weekend travel kit"},
    })

    result = await PlanningAgent(model, max_format_attempts=2).run(state)

    assert model.calls == 2
    assert result["requires_catalog"] is True
    assert result["catalog_queries"] == ["backpack", "packing cubes", "power adapter"]
    assert result["required_categories"] == ["backpack", "packing cubes", "power adapter"]
