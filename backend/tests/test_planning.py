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
