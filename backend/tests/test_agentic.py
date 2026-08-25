import pytest
from langchain_core.messages import AIMessage

from app.agentic.intent import IntentMissionAgent, StructuredOutputError
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.planner import NeedPlannerAgent
from app.agentic.schemas import MissionInterpretation
from app.agentic.state import initial_shopping_state


class FakeChatModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[object] = []

    async def ainvoke(self, input: object, **kwargs: object) -> AIMessage:
        self.calls.append(input)
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

    assert result.required_categories == ["gaming laptop or desktop", "keyboard", "mouse", "headset"]
    assert "mousepad" in result.optional_categories


def test_initial_state_is_complete_and_mutable_fields_are_not_shared():
    first = initial_shopping_state("Find a gaming setup")
    second = initial_shopping_state("Find a travel kit")
    first["preferences"].append("wireless")

    assert first["repair_count"] == 0
    assert second["preferences"] == []
    assert first["candidate_products"] == []


@pytest.mark.anyio
async def test_invalid_intent_model_output_is_rejected():
    agent = IntentMissionAgent(FakeChatModel("not JSON"))
    with pytest.raises(StructuredOutputError, match="invalid JSON"):
        await agent.interpret("Build a setup")


@pytest.mark.anyio
async def test_orchestrator_routes_intent_to_planner_and_audit():
    orchestrator = ShoppingOrchestrator(FakeChatModel(MISSION_JSON))
    result = await orchestrator.ainvoke("Build me a gaming setup under RM4,000.")

    assert result["goal"] == "gaming setup"
    assert result["required_categories"]
    assert result["next_stage"] == "audit"
    assert result["audit_result"]["status"] == "pass"
    assert result["final_response"] is not None
