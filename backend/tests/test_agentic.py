import pytest
import json

from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.agentic.intent import IntentMissionAgent, StructuredOutputError, build_intent_system_prompt
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.planner import NeedPlannerAgent
from app.agentic.brand_voice import BrandVoiceAgent
from app.agentic.schemas import MissionInterpretation
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
async def test_invalid_intent_model_output_is_rejected():
    agent = IntentMissionAgent(FakeChatModel("not JSON"))
    with pytest.raises(StructuredOutputError, match="invalid JSON"):
        await agent.interpret("Build a setup")


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
