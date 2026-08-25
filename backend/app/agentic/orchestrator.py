from __future__ import annotations

from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.ai_logging import log_ai_event
from app.config import settings

from .auditor import ShoppingAuditor
from .intent import AsyncChatModel, IntentMissionAgent
from .llm import GeminiLangChainChatModel
from .planner import NeedPlannerAgent
from .observability import OrchestrationRecorder
from .state import ShoppingAgentState, initial_shopping_state
from .tools import CommerceToolRegistry, ToolExecutionError


class ShoppingOrchestrator:
    """Main controller for the first LangGraph shopping workflow.

    Future Product Search, Review, Seller Risk, Compatibility, Bundle,
    Auditor, Repair, and Vision nodes attach after ``next_stage``.
    """

    def __init__(
        self,
        model: AsyncChatModel | None = None,
        *,
        tool_registry: CommerceToolRegistry | None = None,
        auditor: ShoppingAuditor | None = None,
        max_repairs: int = settings.agent_max_repair_attempts,
        max_graph_iterations: int = settings.agent_max_graph_iterations,
        recorder: OrchestrationRecorder | None = None,
    ) -> None:
        self.intent_agent = IntentMissionAgent(model or GeminiLangChainChatModel(timeout_seconds=settings.agent_model_timeout_seconds))
        self.need_planner = NeedPlannerAgent()
        self.tool_registry = tool_registry
        self.auditor = auditor or ShoppingAuditor()
        self.max_repairs = max_repairs
        self.max_graph_iterations = max_graph_iterations
        self.recorder = recorder
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ShoppingAgentState)
        workflow.add_node("intent_agent", self._intent_node)
        workflow.add_node("need_planner", self._need_planner_node)
        workflow.add_node("product_search", self._product_search_node)
        workflow.add_node("audit", self._audit_node)
        workflow.add_node("repair", self._repair_node)
        workflow.add_edge(START, "intent_agent")
        workflow.add_edge("intent_agent", "need_planner")
        workflow.add_edge("need_planner", "product_search")
        workflow.add_edge("product_search", "audit")
        workflow.add_conditional_edges("audit", self._after_audit, {"repair": "repair", "end": END})
        workflow.add_edge("repair", "audit")
        return workflow.compile()

    def _event(self, state: ShoppingAgentState, node: str) -> dict[str, int]:
        log_ai_event("agent.graph.node", request_id=state["run_id"], node=node, iteration=state["graph_iterations"] + 1)
        return {"graph_iterations": state["graph_iterations"] + 1}

    def _record_node(self, state: ShoppingAgentState, node: str, output: dict[str, Any]) -> None:
        if self.recorder is None:
            return
        inputs: dict[str, Any] = {"graph_iteration": state["graph_iterations"] + 1}
        if node == "intent_agent":
            inputs["user_request"] = state["user_request"]
        elif node == "need_planner":
            inputs["mission"] = state.get("mission", {})
        elif node == "product_search":
            inputs["goal"] = state.get("goal")
        elif node == "audit":
            inputs["selected_products"] = state.get("selected_products", [])
        elif node == "repair":
            inputs["audit_result"] = state.get("audit_result")
        self.recorder.record("node_completed", node_name=node, input_data=inputs, output_data=output)

    async def _intent_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        mission = await self.intent_agent.interpret(state["user_request"])
        output = {
            **self._event(state, "intent_agent"),
            "mission_type": mission.mission_type, "goal": mission.goal, "budget": mission.budget,
            "preferences": mission.preferences, "constraints": mission.constraints,
            "owned_items": mission.owned_items, "priorities": mission.priorities,
            "mission": mission.model_dump(),
        }
        self._record_node(state, "intent_agent", output)
        return output

    async def _need_planner_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        from .schemas import MissionInterpretation
        plan = self.need_planner.plan(MissionInterpretation.model_validate(state["mission"]))
        output = {**self._event(state, "need_planner"), "required_categories": plan.required_categories, "optional_categories": plan.optional_categories}
        self._record_node(state, "need_planner", output)
        return output

    async def _product_search_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        result: dict[str, Any] = {**self._event(state, "product_search"), "next_stage": "audit"}
        if self.tool_registry is None:
            self._record_node(state, "product_search", result)
            return result
        try:
            search = await self.tool_registry.execute("search_products", {"query": state["goal"] or state["user_request"], "limit": 8})
        except ToolExecutionError as error:
            output = {**result, "errors": [*state["errors"], str(error)]}
            self._record_node(state, "product_search", output)
            return output
        output = {**result, "candidate_products": search["products"], "tool_results": [*state["tool_results"], {"tool": "search_products", "result_count": len(search["products"])}]}
        self._record_node(state, "product_search", output)
        return output

    async def _audit_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        audit = await self.auditor.audit(state, self.tool_registry)
        log_ai_event("agent.audit", request_id=state["run_id"], status=audit["status"], error_codes=[item["code"] for item in audit["errors"]])
        response = "Shopping recommendations passed factual verification." if audit["status"] == "pass" else "Recommendations need repair before they can be shown."
        output = {**self._event(state, "audit"), "audit_result": dict(audit), "final_response": response}
        self._record_node(state, "audit", output)
        return output

    def _after_audit(self, state: ShoppingAgentState) -> str:
        if state["audit_result"] and state["audit_result"].get("status") == "pass":
            return "end"
        return "repair" if state["repair_count"] < self.max_repairs else "end"

    async def _repair_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        attempt = state["repair_count"] + 1
        log_ai_event("agent.repair", request_id=state["run_id"], attempt=attempt)
        # Conservative foundation: remove unverifiable selections. Future
        # Bundle Optimizer/Repair agents can replace this deterministic step.
        output = {**self._event(state, "repair"), "repair_count": attempt, "selected_products": [], "next_stage": "audit"}
        self._record_node(state, "repair", output)
        return output

    async def ainvoke(self, user_request: str, *, state_overrides: dict[str, Any] | None = None) -> ShoppingAgentState:
        if not user_request.strip():
            raise ValueError("A shopping request is required.")
        state = initial_shopping_state(user_request)
        state["run_id"] = uuid4().hex[:12]
        if state_overrides:
            state.update(state_overrides)
        if self.recorder:
            state["run_id"] = self.recorder.request_id
            self.recorder.start(state)
            if self.tool_registry:
                self.tool_registry.recorder = self.recorder
        try:
            result = await self.graph.ainvoke(state, config={"recursion_limit": self.max_graph_iterations})
        except Exception as error:
            if self.recorder:
                self.recorder.fail(error)
            raise
        if self.recorder:
            self.recorder.finish(result)
        return result
