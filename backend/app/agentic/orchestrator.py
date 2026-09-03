from __future__ import annotations

import json
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.ai_logging import log_ai_event
from app.config import settings

from .auditor import ShoppingAuditor
from .brand_voice import BrandVoiceAgent
from .bundle_optimizer import BundleOptimizerAgent
from .compatibility import CompatibilityAgent
from .intent import AsyncChatModel, IntentMissionAgent
from .llm import PrimaryLangChainChatModel
from .manager import WorkflowManager
from .memory import MemoryUnavailableError, ShoppingMemoryStore, ShoppingSessionMemory, memory_from_state
from .planner import NeedPlannerAgent
from .planning import PlanningAgent
from .observability import OrchestrationRecorder, active_recorder, safe_audit_data
from .product_resolution import ProductResolutionAgent
from .product_search import ProductSearchAgent
from .schemas import MissionInterpretation
from .state import ShoppingAgentState, initial_shopping_state
from .tools import CommerceToolRegistry, ToolExecutionError
from .vision import VisionAgent


class ShoppingOrchestrator:
    """Main controller for the first LangGraph shopping workflow.

    Product Search, Compatibility, Bundle,
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
        vision_agent: VisionAgent | None = None,
        memory_store: ShoppingMemoryStore | None = None,
    ) -> None:
        shared_model = model or PrimaryLangChainChatModel(timeout_seconds=settings.agent_model_timeout_seconds)
        self.tool_registry = tool_registry
        self.intent_agent = IntentMissionAgent(shared_model, tools=tool_registry.tools if tool_registry else ())
        self.need_planner = NeedPlannerAgent()
        self.planning_agent = PlanningAgent(shared_model)
        self.manager = WorkflowManager()
        self.product_resolver = ProductResolutionAgent(shared_model)
        self.product_search_agent = ProductSearchAgent(tool_registry, shared_model)
        self.compatibility_agent = CompatibilityAgent(shared_model)
        self.bundle_optimizer = BundleOptimizerAgent(shared_model)
        self.vision_agent = vision_agent or VisionAgent()
        self.memory_store = memory_store
        self.brand_voice = BrandVoiceAgent(shared_model)
        self.auditor = auditor or ShoppingAuditor(shared_model)
        self.max_repairs = max_repairs
        self.max_graph_iterations = max_graph_iterations
        self._started_at: float | None = None
        self.recorder = recorder
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ShoppingAgentState)
        def add_node(name: str, handler: Any) -> None:
            workflow.add_node(name, self._instrument_node(name, handler))

        add_node("memory_load", self._memory_load_node)
        add_node("vision", self._vision_node)
        add_node("intent_agent", self._intent_node)
        add_node("need_planner", self._need_planner_node)
        add_node("planning", self._planning_node)
        add_node("manager", self._manager_node)
        add_node("product_search", self._product_search_node)
        add_node("compatibility", self._compatibility_node)
        add_node("bundle_optimizer", self._bundle_optimizer_node)
        add_node("response_draft", self._response_draft_node)
        add_node("audit", self._audit_node)
        add_node("brand_voice", self._brand_voice_node)
        add_node("final_audit", self._final_audit_node)
        add_node("restore_audited_draft", self._restore_audited_draft_node)
        add_node("repair", self._repair_node)
        add_node("memory_update", self._memory_update_node)
        workflow.add_edge(START, "memory_load")
        workflow.add_conditional_edges("memory_load", self._route_start, {"vision": "vision", "intent_agent": "intent_agent"})
        workflow.add_edge("vision", "intent_agent")
        workflow.add_edge("intent_agent", "need_planner")
        workflow.add_conditional_edges(
            "need_planner", self._after_need_planner,
            {"planning": "planning", "manager": "manager"},
        )
        workflow.add_conditional_edges(
            "planning", self._after_planning,
            {"manager": "manager", "response_draft": "response_draft"},
        )
        workflow.add_conditional_edges(
            "manager",
            self._after_manager,
            {"product_search": "product_search", "response_draft": "response_draft"},
        )
        workflow.add_conditional_edges(
            "product_search", self._after_product_search,
            {"compatibility": "compatibility", "bundle_optimizer": "bundle_optimizer", "response_draft": "response_draft"},
        )
        workflow.add_conditional_edges(
            "compatibility", self._after_compatibility,
            {"bundle_optimizer": "bundle_optimizer", "response_draft": "response_draft"},
        )
        workflow.add_conditional_edges(
            "bundle_optimizer", self._after_bundle_optimizer,
            {"compatibility": "compatibility", "response_draft": "response_draft"},
        )
        workflow.add_edge("response_draft", "audit")
        workflow.add_conditional_edges(
            "audit",
            self._after_audit,
            {"repair": "repair", "brand_voice": "brand_voice", "memory_update": "memory_update", "end": END},
        )
        workflow.add_edge("brand_voice", "final_audit")
        workflow.add_conditional_edges(
            "final_audit", self._after_final_audit,
            {"repair": "repair", "restore_audited_draft": "restore_audited_draft", "memory_update": "memory_update", "end": END},
        )
        workflow.add_edge("restore_audited_draft", "final_audit")
        workflow.add_edge("memory_update", END)
        workflow.add_edge("repair", "response_draft")
        return workflow.compile()

    def _event(self, state: ShoppingAgentState, node: str) -> dict[str, int]:
        return {"graph_iterations": state["graph_iterations"] + 1}

    def _node_inputs(self, state: ShoppingAgentState, node: str) -> dict[str, Any]:
        inputs: dict[str, Any] = {"graph_iteration": state["graph_iterations"] + 1}
        if node == "intent_agent":
            inputs["user_request"] = state["user_request"]
        elif node == "memory_load":
            inputs["memory_session_scope"] = bool(state.get("memory_session_scope"))
        elif node == "need_planner":
            inputs["mission"] = state.get("mission", {})
        elif node == "planning":
            inputs["mission"] = state.get("mission", {})
        elif node == "manager":
            inputs["requested_actions"] = state.get("requested_actions", [])
        elif node == "product_search":
            inputs["goal"] = state.get("goal")
        elif node == "vision":
            inputs["mode"] = state.get("vision_input", {}).get("mode")
        elif node == "compatibility":
            inputs["candidate_product_ids"] = [item.get("id") for item in state.get("candidate_products", [])]
        elif node == "bundle_optimizer":
            inputs["required_categories"] = state.get("required_categories", [])
        elif node in {"response_draft", "brand_voice", "final_audit"}:
            inputs["selected_products"] = state.get("selected_products", [])
        elif node == "audit":
            inputs["selected_products"] = state.get("selected_products", [])
        elif node == "repair":
            inputs["audit_result"] = state.get("audit_result")
        elif node == "memory_update":
            inputs["memory_session_scope"] = bool(state.get("memory_session_scope"))
        return inputs

    def _instrument_node(self, node: str, handler: Any):
        """Emit safe, inspectable terminal logs around every graph node."""
        async def instrumented(state: ShoppingAgentState) -> dict[str, Any]:
            inputs = self._node_inputs(state, node)
            fields = {
                "node": node,
                "iteration": state["graph_iterations"] + 1,
                "input_payload": safe_audit_data(inputs),
            }
            if settings.ai_log_agent_node_payloads:
                log_ai_event("agent.graph.node.started", request_id=state["run_id"], **fields)
            try:
                output = await handler(state)
            except Exception as error:
                if settings.ai_log_agent_node_payloads:
                    log_ai_event(
                        "agent.graph.node.failed",
                        request_id=state["run_id"],
                        **fields,
                        error_type=type(error).__name__,
                        error_message=str(error)[:1_000],
                    )
                raise
            if settings.ai_log_agent_node_payloads:
                log_ai_event(
                    "agent.graph.node.completed",
                    request_id=state["run_id"],
                    **fields,
                    output_payload=safe_audit_data(output),
                )
            return output
        return instrumented

    def _record_node(self, state: ShoppingAgentState, node: str, output: dict[str, Any]) -> None:
        if self.recorder is None:
            return
        inputs = self._node_inputs(state, node)
        self.recorder.record("node_completed", node_name=node, input_data=inputs, output_data=output)

    def _after_manager(self, state: ShoppingAgentState) -> str:
        return "product_search" if self._requires_catalog_lookup(state) else "response_draft"

    @staticmethod
    def _after_need_planner(state: ShoppingAgentState) -> str:
        return "planning" if state.get("requires_planning") else "manager"

    @staticmethod
    def _after_planning(state: ShoppingAgentState) -> str:
        return "manager" if state.get("requires_catalog") else "response_draft"

    def _after_product_search(self, state: ShoppingAgentState) -> str:
        return self.manager.next_stage(state)

    def _after_compatibility(self, state: ShoppingAgentState) -> str:
        return self.manager.next_stage(state, "compatibility")

    def _after_bundle_optimizer(self, state: ShoppingAgentState) -> str:
        return self.manager.next_stage(state, "bundle_optimizer")

    @staticmethod
    def _route_start(state: ShoppingAgentState) -> str:
        return "vision" if state.get("vision_input") else "intent_agent"

    async def _vision_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        try:
            output = {**self._event(state, "vision"), **(await self.vision_agent.run(state))}
        except Exception as error:
            if self.recorder is not None:
                self.recorder.record(
                    "node_failed", node_name="vision", status="failed",
                    input_data={"graph_iteration": state["graph_iterations"] + 1, "mode": state.get("vision_input", {}).get("mode")},
                    error_message=f"{type(error).__name__}: {str(error)[:1000]}",
                )
            log_ai_event("agent.graph.node_failed", request_id=state["run_id"], node="vision", error_type=type(error).__name__, error_message=str(error)[:500])
            raise
        self._record_node(state, "vision", output)
        return output

    async def _memory_load_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        if self.memory_store is None or not state.get("memory_session_scope"):
            return {}
        try:
            memory = await self.memory_store.load(str(state["memory_session_scope"]))
        except MemoryUnavailableError as error:
            log_ai_event("agent.memory.load_unavailable", request_id=state["run_id"], error_type=type(error).__name__)
            return {}
        output = {
            **self._event(state, "memory_load"),
            "memory_context": memory.runtime_context() if memory is not None else None,
            # Previously rejected items remain excluded from deterministic
            # shortlisting for this active session.
            "excluded_product_ids": memory.rejected_product_ids if memory is not None else [],
        }
        self._record_node(state, "memory_load", output)
        return output

    def _requires_catalog_lookup(self, state: ShoppingAgentState) -> bool:
        """Keep catalog-fact requests on the tool-backed path.

        The model's classification is useful context, but it is not the sole
        authorization for a read-only catalog lookup. This catches a safe,
        common failure mode where a stock request is mislabeled as a generic
        information request.
        """
        return bool(self._requested_actions(state))

    async def _intent_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        request = state["user_request"]
        runtime_context: dict[str, Any] = {}
        has_vision_context = bool(state.get("vision_context"))
        if has_vision_context:
            runtime_context["vision_context"] = state["vision_context"]
        elif state.get("memory_context"):
            # A camera submission starts a new, image-grounded mission. The
            # generated camera caption has no customer-authored reference to a
            # previous mission, so prior budgets and preferences must not leak
            # into it. Text follow-ups continue to receive session memory.
            runtime_context["short_term_memory"] = state["memory_context"]
        mission = await self.intent_agent.interpret(request, runtime_context=runtime_context)
        memory_context = state.get("memory_context") or {}
        if has_vision_context:
            mission = mission.model_copy(update={"continues_context": False})
        else:
            mission = self._merge_continuation_mission(mission, memory_context)
        output = {
            **self._event(state, "intent_agent"),
            "mission_type": mission.mission_type, "recommendation_mode": mission.recommendation_mode, "goal": mission.goal,
            "requires_planning": mission.requires_planning, "requires_catalog": mission.requires_catalog,
            "continues_context": mission.continues_context,
            "optimization_mode": mission.optimization_mode,
            "catalog_query": mission.catalog_query,
            "catalog_queries": mission.catalog_queries, "requested_actions": mission.requested_actions,
            "budget": mission.budget,
            "bundle_items": [item.model_dump() for item in mission.bundle_items],
            "preferences": mission.preferences,
            "key_requirements": mission.key_requirements,
            "constraints": mission.constraints,
            "owned_items": mission.owned_items, "priorities": mission.priorities,
            "selection_criteria": [item.model_dump() for item in mission.selection_criteria],
            "fulfillment_requirements": [item.model_dump() for item in mission.fulfillment_requirements],
            "mission": mission.model_dump(),
        }
        self._record_node(state, "intent_agent", output)
        return output

    @staticmethod
    def _merge_continuation_mission(
        mission: MissionInterpretation, memory_context: object
    ) -> MissionInterpretation:
        """Build one coherent mission from a follow-up and audited session memory."""
        if not mission.continues_context or not isinstance(memory_context, dict):
            return mission
        previous = memory_context.get("current_mission")
        if not isinstance(previous, dict):
            previous = {}
        data = mission.model_dump()
        refinement = bool(mission.optimization_mode or mission.selection_criteria)
        list_fields = (
            "catalog_queries", "requested_actions", "bundle_items", "preferences",
            "key_requirements", "constraints", "owned_items", "priorities",
            "fulfillment_requirements",
        )
        for field in list_fields:
            prior_values = previous.get(field)
            if not data.get(field) and isinstance(prior_values, list):
                data[field] = prior_values
        for field in ("catalog_query",):
            if not data.get(field) and previous.get(field):
                data[field] = previous[field]
        if data.get("budget") is None and memory_context.get("budget") is not None:
            data["budget"] = memory_context["budget"]
        for field in ("preferences", "constraints", "owned_items"):
            remembered = memory_context.get(field)
            if isinstance(remembered, list):
                data[field] = list(dict.fromkeys([*remembered, *data.get(field, [])]))
        if refinement:
            # A refinement modifies the active selection; it is not a new
            # information-only mission. Preserve the prior shape unless the
            # follow-up supplied concrete replacement roles.
            if previous.get("goal"):
                data["goal"] = previous["goal"]
            if previous.get("mission_type"):
                data["mission_type"] = previous["mission_type"]
            if previous.get("recommendation_mode"):
                data["recommendation_mode"] = previous["recommendation_mode"]
            # A refinement of an existing bundle changes selection criteria,
            # not the bundle's product-role contract. Some models restate a
            # vague one-item phrase from the follow-up; use the last audited
            # role plan instead of silently dropping the other bundle roles.
            if previous.get("recommendation_mode") == "bundle":
                for field in (
                    "catalog_query", "catalog_queries", "requested_actions",
                    "bundle_items", "key_requirements", "fulfillment_requirements",
                ):
                    if previous.get(field):
                        data[field] = previous[field]
            data["requires_catalog"] = bool(
                previous.get("requires_catalog", True)
                or memory_context.get("selected_products")
                or memory_context.get("current_bundle")
            )
            data["requires_planning"] = bool(previous.get("requires_planning", False))
            if not data.get("requested_actions"):
                data["requested_actions"] = ["search_products"]
        data["optimization_mode"] = mission.optimization_mode or memory_context.get("optimization_mode")
        return MissionInterpretation.model_validate(data)

    async def _need_planner_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        plan = self.need_planner.plan(MissionInterpretation.model_validate(state["mission"]))
        output = {**self._event(state, "need_planner"), "required_categories": plan.required_categories, "optional_categories": plan.optional_categories}
        self._record_node(state, "need_planner", output)
        return output

    async def _manager_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        actions = self._requested_actions(state)
        output = {**self._event(state, "manager"), "execution_plan": self.manager.plan(state, actions)}
        self._record_node(state, "manager", output)
        return output

    async def _planning_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        output = {**self._event(state, "planning"), **(await self.planning_agent.run(state))}
        self._record_node(state, "planning", output)
        return output

    async def _product_search_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        result: dict[str, Any] = {**self._event(state, "product_search")}
        if self.tool_registry is None:
            self._record_node(state, "product_search", result)
            return result
        actions = self._requested_actions(state)
        if "check_stock" in actions:
            search_output = await self.product_search_agent.run_many(
                state,
                queries=self._catalog_queries(state),
                limit=self._stock_search_limit(),
                include_out_of_stock=True,
            )
        else:
            search_output = await self.product_search_agent.run_catalog(
                state, limit=settings.agent_catalog_context_limit
            )
        if search_output["errors"]:
            output = {**result, "errors": [*state["errors"], *search_output["errors"]]}
            self._record_node(state, "product_search", output)
            return output
        role_candidates = self._role_constrained_candidates(
            state, search_output["candidate_products"]
        )
        candidates, selection_context = self._apply_optimization_context(
            state, role_candidates
        )
        result = {**result, "product_rankings": search_output["product_rankings"]}
        if "check_stock" in actions:
            stock_results: list[dict[str, Any]] = []
            tool_results = [*state["tool_results"], *search_output["tool_results"]]
            for candidate in candidates:
                try:
                    stock = await self.tool_registry.execute("check_stock", {"product_id": str(candidate["id"])})
                except ToolExecutionError as error:
                    tool_results.append({"tool": "check_stock", "product_id": str(candidate["id"]), "error": str(error)})
                    continue
                stock_results.append({
                    "id": str(candidate["id"]), "name": str(candidate["name"]), "brand": str(candidate["brand"]),
                    "available_quantity": int(stock["available_quantity"]), "in_stock": bool(stock["in_stock"]),
                })
                tool_results.append({"tool": "check_stock", "product_id": str(candidate["id"]), "available_quantity": int(stock["available_quantity"])})
            extra_actions = [action for action in actions if action not in {"search_products", "check_stock"}]
            tool_context = await self._execute_requested_actions(extra_actions, candidates, state)
            output = {
                **result, "candidate_products": candidates, "stock_results": stock_results,
                "tool_results": tool_results, "tool_context": tool_context,
            }
            self._record_node(state, "product_search", output)
            return output
        action_candidates, resolution_context = await self._resolve_action_candidates(
            {**state, "selection_context": selection_context}, actions, candidates
        )
        tool_context = [*resolution_context, *(await self._execute_requested_actions(actions, action_candidates, state))]
        # Resolution is required for a named product/detail request, but it
        # must not collapse a recommendation into the model's first match.
        # Product discovery deliberately retains the verified shortlist so the
        # selection stage can present comparable options or build a complete,
        # outcome-driven kit.
        response_candidates = (
            candidates
            if self._should_recommend_products(actions)
            else action_candidates or candidates
        )
        selection_candidates = (
            response_candidates
            if self.brand_voice.is_shopping_mission(state.get("mission_type"))
            else action_candidates or response_candidates
        )
        no_eligible_alternative = bool(selection_context.get("no_eligible_alternative"))
        fulfillment_gaps = [] if no_eligible_alternative else self.brand_voice.fulfillment_gaps(response_candidates, state)
        output = {
            **result,
            "candidate_products": candidates,
            "selection_context": selection_context,
            # Bundle selection is resolved by the bundle optimiser. For a
            # single-product mission, the response model receives the full
            # verified candidate set and chooses its own recommendation IDs.
            "selected_products": (
                [] if (
                    state.get("recommendation_mode", "single") == "single"
                    and self.brand_voice.is_shopping_mission(state.get("mission_type"))
                )
                else self.brand_voice.select_catalog_products({**state, "candidate_products": selection_candidates})
            ) if self._should_recommend_products(actions) else [],
            "tool_results": [*state["tool_results"], *search_output["tool_results"]],
            "tool_context": tool_context,
            "fulfillment_gaps": fulfillment_gaps,
        }
        self._record_node(state, "product_search", output)
        return output

    @staticmethod
    def _role_constrained_candidates(
        state: ShoppingAgentState, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Keep single-product refinements within the active product role."""
        if state.get("recommendation_mode", "single") != "single":
            return candidates
        requirements = [
            item for item in state.get("fulfillment_requirements", [])
            if isinstance(item, dict)
            and str(item.get("kind", "")).casefold().strip()
            in BrandVoiceAgent._SHOPPING_REQUIREMENT_KINDS
        ]
        if not requirements:
            return candidates
        return [
            product for product in candidates
            if all(
                BrandVoiceAgent._matches_requirement(product, requirement)
                for requirement in requirements
            )
        ]

    @staticmethod
    def _apply_optimization_context(
        state: ShoppingAgentState, candidates: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Rank catalog facts from LLM-supplied, typed optimisation criteria.

        The intent model decides which catalog facts matter. This layer only
        resolves those field names against verified product data, compares
        reference-backed numeric criteria, and keeps the result auditable.
        """
        criteria = [
            item for item in state.get("selection_criteria", [])
            if isinstance(item, dict) and str(item.get("field", "")).strip()
        ]
        if not state.get("continues_context") or not criteria:
            return candidates, {}
        memory = state.get("memory_context")
        prior_selected = memory.get("selected_products", []) if isinstance(memory, dict) else []
        prior_ids = {
            str(item.get("id")) for item in prior_selected
            if isinstance(item, dict) and item.get("id")
        }
        reference_products = [product for product in candidates if str(product.get("id")) in prior_ids]
        filtered = list(candidates)
        applied: list[dict[str, Any]] = []
        prior_bundle = memory.get("current_bundle") if isinstance(memory, dict) else None
        bundle_total = None
        if isinstance(prior_bundle, dict):
            try:
                bundle_total = Decimal(str(prior_bundle.get("total")))
            except (InvalidOperation, TypeError, ValueError):
                bundle_total = None
        for criterion in criteria:
            operator = str(criterion.get("operator", ""))
            if operator not in {"lower_than_reference", "higher_than_reference"}:
                continue
            field = str(criterion["field"])
            # Price applied to a continuing bundle means the combined selection,
            # not "every candidate must cost less than the cheapest old item".
            # Preserve role diversity here; the bundle optimiser enforces the
            # verified prior-total comparison across candidate combinations.
            if (
                state.get("recommendation_mode") == "bundle"
                and field.casefold().strip() == "price"
                and bundle_total is not None
            ):
                applied.append({
                    "field": field, "operator": operator,
                    "reference_value": str(bundle_total), "scope": "bundle_total",
                    "eligible_count": len(filtered),
                })
                continue
            references = [
                value for product in reference_products
                if (value := ShoppingOrchestrator._numeric_catalog_fact(product, field)) is not None
            ]
            if not references:
                continue
            reference = min(references) if operator == "lower_than_reference" else max(references)
            eligible = [
                product for product in filtered
                if (value := ShoppingOrchestrator._numeric_catalog_fact(product, field)) is not None
                and (value < reference if operator == "lower_than_reference" else value > reference)
            ]
            applied.append({
                "field": field, "operator": operator, "reference_value": str(reference),
                "eligible_count": len(eligible),
            })
            filtered = eligible
        context = {
            "optimization_mode": state.get("optimization_mode"),
            "criteria": criteria,
            "reference_product_ids": sorted(prior_ids),
            "applied_comparisons": applied,
            "eligible_alternative_count": len(filtered),
            "no_eligible_alternative": bool(applied and not filtered),
        }
        if bundle_total is not None:
            context["reference_bundle_total"] = str(bundle_total)
        if context["no_eligible_alternative"]:
            return [], context
        return sorted(filtered, key=lambda product: ShoppingOrchestrator._optimization_sort_key(product, criteria)), context

    @staticmethod
    def _catalog_fact(product: dict[str, Any], field: str) -> object | None:
        """Read a top-level or structured attribute without catalog-specific mappings."""
        normalized = field.casefold().strip()
        for key, value in product.items():
            if str(key).casefold() == normalized:
                return value
        attributes = product.get("attributes")
        if isinstance(attributes, dict):
            for key, value in attributes.items():
                if str(key).casefold() == normalized:
                    return value
        return None

    @staticmethod
    def _numeric_catalog_fact(product: dict[str, Any], field: str) -> Decimal | None:
        value = ShoppingOrchestrator._catalog_fact(product, field)
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _optimization_sort_key(product: dict[str, Any], criteria: list[dict[str, Any]]) -> tuple[Any, ...]:
        """Create a stable preference ordering from verified product evidence."""
        match_score = 0
        numeric_orders: list[Decimal] = []
        evidence = json.dumps(product, ensure_ascii=False, default=str).casefold()
        for criterion in criteria:
            operator = str(criterion.get("operator", ""))
            weight = int(criterion.get("weight", 1) or 1)
            if operator == "prefer_match":
                desired = str(criterion.get("value") or criterion.get("field", "")).strip()
                if desired and BrandVoiceAgent._terms_present(desired, evidence):
                    match_score += weight
            elif operator in {"lower_than_reference", "higher_than_reference"}:
                value = ShoppingOrchestrator._numeric_catalog_fact(product, str(criterion.get("field", "")))
                if value is not None:
                    numeric_orders.append(value if operator == "lower_than_reference" else -value)
        return (-match_score, *numeric_orders, str(product.get("name", "")))

    async def _compatibility_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        output = {**self._event(state, "compatibility"), **(await self.compatibility_agent.run(state))}
        self._record_node(state, "compatibility", output)
        return output

    async def _bundle_optimizer_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        output = {**self._event(state, "bundle_optimizer"), **(await self.bundle_optimizer.run(state))}
        self._record_node(state, "bundle_optimizer", output)
        return output

    @staticmethod
    def _is_stock_check(state: ShoppingAgentState) -> bool:
        if (state.get("mission_type") or "").strip().lower() == "stock_check":
            return True
        request = state["user_request"].lower()
        return any(marker in request for marker in ("stock", "in stock", "available", "availability", "sold out", "inventory"))

    def _requested_actions(self, state: ShoppingAgentState) -> list[str]:
        """Combine the model plan with conservative deterministic fallbacks."""
        planned = [str(action) for action in state.get("requested_actions", [])]
        request = state["user_request"].lower()
        inferred: list[tuple[str, tuple[str, ...]]] = [
            ("check_stock", ("stock", "in stock", "available", "availability", "sold out", "inventory")),
            ("get_product_reviews", ("review", "rating", "feedback")),
            ("get_seller", ("seller", "vendor", "store")),
            ("compare_products", ("compare", " versus ", " vs ")),
            ("calculate_bundle_total", ("bundle total", "total cost", "cart total", "total price")),
            ("get_product", ("product details", "specification", "specs", "product info")),
            ("search_products", ("find ", "recommend", "show me", "looking for", "search")),
        ]
        for action, markers in inferred:
            if any(marker in request for marker in markers):
                planned.append(action)
        if not planned and (
            state.get("catalog_query")
            or state.get("catalog_queries")
            or state.get("fulfillment_requirements")
            or self._is_stock_check(state)
            or str(state.get("mission_type", "")).casefold() == "product_search"
        ):
            planned.append("search_products")
        if state.get("requires_catalog"):
            planned.append("search_products")
        # Search is the safe identity-resolution step for every product-specific
        # operation when the user has supplied a name rather than a UUID.
        if planned and "search_products" not in planned:
            planned.insert(0, "search_products")
        return list(dict.fromkeys(planned))

    async def _execute_requested_actions(
        self, actions: list[str], candidates: list[dict[str, Any]], state: ShoppingAgentState
    ) -> list[dict[str, Any]]:
        if self.tool_registry is None:
            return []
        context: list[dict[str, Any]] = []
        selected = candidates[:4]

        async def execute(name: str, arguments: dict[str, Any]) -> None:
            if self.tool_registry is None or self.tool_registry.remaining_calls < 1:
                return
            try:
                context.append({"tool": name, "result": await self.tool_registry.execute(name, arguments)})
            except ToolExecutionError as error:
                context.append({"tool": name, "error": str(error)})

        if "get_product" in actions and selected:
            await execute("get_product", {"product_id": str(selected[0]["id"])})
        if "get_product_reviews" in actions:
            for product in selected[:2]:
                await execute("get_product_reviews", {"product_id": str(product["id"])})
        if "get_seller" in actions:
            seller_ids = list(dict.fromkeys(str(product["seller_id"]) for product in selected))
            for seller_id in seller_ids[:2]:
                await execute("get_seller", {"seller_id": seller_id})
        if "compare_products" in actions and len(selected) >= 2:
            await execute("compare_products", {"product_ids": [str(product["id"]) for product in selected[:4]]})
        if "calculate_bundle_total" in actions:
            bundle_items = state.get("bundle_items", [])
            resolved_items: list[dict[str, Any]] = []
            for item in bundle_items:
                if self.tool_registry.remaining_calls < 2:
                    break
                try:
                    search = await self.tool_registry.execute("search_products", {"query": str(item["query"]), "limit": 8})
                except ToolExecutionError as error:
                    context.append({"tool": "search_products", "error": str(error)})
                    continue
                products = search["products"]
                if not products:
                    context.append({"tool": "search_products", "result": {"products": []}})
                    continue
                product = self._best_catalog_match(products, str(item["query"]))
                resolved_items.append({"product_id": str(product["id"]), "quantity": int(item.get("quantity", 1))})
                context.append({"tool": "search_products", "result": {"products": products}})
            if resolved_items:
                await execute("calculate_bundle_total", {"items": resolved_items})
            elif selected:
                # Preserve the previous useful fallback for an underspecified bundle.
                await execute("calculate_bundle_total", {"items": [{"product_id": str(product["id"]), "quantity": 1} for product in selected[:3]]})
        return context

    async def _resolve_action_candidates(
        self, state: ShoppingAgentState, actions: list[str], candidates: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        resolving_actions = {"get_product", "get_product_reviews", "get_seller", "compare_products"}
        # The intent model can label a factual lookup as product_search. Let the
        # grounded resolver decide from the verified candidates for every
        # search-only request, rather than depending on that label.
        search_only = set(actions) == {"search_products"}
        if not search_only and not resolving_actions.intersection(actions):
            return candidates, []
        resolved_ids = await self.product_resolver.resolve(
            user_request=state["user_request"], actions=actions, candidates=candidates,
            mission_context={
                "goal": state.get("goal"),
                "recommendation_mode": state.get("recommendation_mode"),
                "fulfillment_requirements": state.get("fulfillment_requirements", []),
                "optimization_mode": state.get("optimization_mode"),
                "selection_context": state.get("selection_context", {}),
            },
        )
        if resolved_ids:
            by_id = {str(product["id"]): product for product in candidates}
            return [by_id[product_id] for product_id in resolved_ids], [
                {"tool": "product_resolution", "result": {"product_ids": resolved_ids}}
            ]
        if len(candidates) == 1:
            return candidates, [{"tool": "product_resolution", "result": {"product_ids": [str(candidates[0]["id"])]}}]
        return [], [{"tool": "product_resolution", "result": {"product_ids": [], "status": "ambiguous"}}]

    @staticmethod
    def _best_catalog_match(products: list[dict[str, Any]], query: str) -> dict[str, Any]:
        """Resolve a named bundle item despite the catalog's broad OR search."""
        normalized_query = query.casefold().strip()
        terms = [term for term in normalized_query.replace("-", " ").split() if term]

        def score(product: dict[str, Any]) -> tuple[int, int]:
            name = str(product.get("name", "")).casefold()
            brand = str(product.get("brand", "")).casefold()
            exact = 100 if name == normalized_query else 0
            phrase = 20 if normalized_query in name or normalized_query in brand else 0
            term_matches = sum(term in name or term in brand for term in terms)
            return exact + phrase + term_matches, -len(name)

        return max(products, key=score)

    @staticmethod
    def _catalog_query(state: ShoppingAgentState) -> str:
        queries = [str(item).strip() for item in state.get("catalog_queries", []) if str(item).strip()]
        if queries:
            return " ".join(queries)
        query = (state.get("catalog_query") or "").strip()
        if query:
            return query
        preferences = [str(item).strip() for item in state.get("preferences", []) if str(item).strip()]
        if preferences:
            return " ".join(preferences)
        return state.get("goal") or state["user_request"]

    @staticmethod
    def _catalog_queries(state: ShoppingAgentState) -> list[str]:
        """Keep multi-item requests separate so catalog search stays precise."""
        items = [str(item.get("query", "")).strip() for item in state.get("bundle_items", []) if isinstance(item, dict)]
        items.extend(str(item).strip() for item in state.get("catalog_queries", []))
        if state.get("catalog_query"):
            items.append(str(state["catalog_query"]).strip())
        unique = list(dict.fromkeys(item for item in items if item))

        def terms(query: str) -> set[str]:
            return set(re.findall(r"[\w]+", query.casefold()))

        # Intent may return both a descriptive search phrase and its shorter
        # product-type form. The shorter query contributes no new retrieval
        # evidence and wastes a tool call, so retain only the more specific
        # query. Independent bundle items remain separate.
        filtered = [
            query for query in unique
            if not any(terms(query) < terms(other) for other in unique if other != query)
        ]
        return filtered or [ShoppingOrchestrator._catalog_query(state)]

    def _stock_search_limit(self) -> int:
        if self.tool_registry is None:
            return 1
        # search + check_stock + initial audit + final audit for each result.
        return max(1, min(8, (self.tool_registry.max_calls - 1) // 3))

    @staticmethod
    def _should_recommend_products(actions: list[str]) -> bool:
        """Only catalog-discovery requests produce recommendation cards/IDs."""
        return set(actions) <= {"search_products"}

    async def _response_draft_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        output = {
            **self._event(state, "response_draft"),
            **(await self.brand_voice.compose(state)),
            "next_stage": "audit",
        }
        self._record_node(state, "response_draft", output)
        return output

    async def _brand_voice_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        output = {
            **self._event(state, "brand_voice"),
            **(await self.brand_voice.polish(state)),
            "next_stage": "final_audit",
        }
        self._record_node(state, "brand_voice", output)
        return output

    async def _audit_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        audit = await self.auditor.audit(state, self.tool_registry)
        log_ai_event("agent.audit", request_id=state["run_id"], status=audit["status"], error_codes=[item["code"] for item in audit["errors"]])
        output = {**self._event(state, "audit"), "audit_result": dict(audit)}
        if audit["status"] == "pass" and isinstance(state.get("final_response"), str):
            output["audited_response"] = state["final_response"]
        self._record_node(state, "audit", output)
        return output

    def _after_audit(self, state: ShoppingAgentState) -> str:
        if state["audit_result"] and state["audit_result"].get("status") == "pass":
            if self._past_response_soft_deadline():
                log_ai_event(
                    "agent.optional_polish.skipped",
                    request_id=state["run_id"],
                    reason="response_soft_deadline",
                )
                return "memory_update" if self.memory_store is not None and state.get("memory_session_scope") else "end"
            return "brand_voice"
        return "repair" if state["repair_count"] < self.max_repairs else "end"

    def _past_response_soft_deadline(self) -> bool:
        return bool(
            self._started_at is not None
            and time.monotonic() - self._started_at >= settings.agent_response_soft_deadline_seconds
        )

    async def _final_audit_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        audit = await self.auditor.audit(state, self.tool_registry)
        log_ai_event("agent.final_audit", request_id=state["run_id"], status=audit["status"], error_codes=[item["code"] for item in audit["errors"]])
        output = {**self._event(state, "final_audit"), "audit_result": dict(audit)}
        self._record_node(state, "final_audit", output)
        return output

    def _after_final_audit(self, state: ShoppingAgentState) -> str:
        if state["audit_result"] and state["audit_result"].get("status") == "pass":
            return "memory_update" if self.memory_store is not None and state.get("memory_session_scope") else "end"
        audited = state.get("audited_response")
        if isinstance(audited, str) and audited.strip() and audited != state.get("final_response"):
            return "restore_audited_draft"
        return "repair" if state["repair_count"] < self.max_repairs else "end"

    async def _restore_audited_draft_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        """Fall back to the initial audited draft if final wording added a claim."""
        audited = state.get("audited_response")
        if not isinstance(audited, str) or not audited.strip():
            return {}
        output = {
            **self._event(state, "restore_audited_draft"),
            "final_response": audited,
            "next_stage": "final_audit",
        }
        self._record_node(state, "restore_audited_draft", output)
        return output

    async def _memory_update_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        if self.memory_store is None or not state.get("memory_session_scope"):
            return {}
        try:
            previous = ShoppingSessionMemory.model_validate(state["memory_context"]) if state.get("memory_context") else None
            await self.memory_store.save(
                str(state["memory_session_scope"]), memory_from_state(previous, state)
            )
        except (MemoryUnavailableError, ValueError, TypeError) as error:
            log_ai_event("agent.memory.update_unavailable", request_id=state["run_id"], error_type=type(error).__name__)
            return {}
        output = {**self._event(state, "memory_update")}
        self._record_node(state, "memory_update", output)
        return output

    async def _repair_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        attempt = state["repair_count"] + 1
        log_ai_event("agent.repair", request_id=state["run_id"], attempt=attempt)
        audit_errors = list((state.get("audit_result") or {}).get("errors", []))
        excluded = {
            str(item["product_id"])
            for item in audit_errors
            if isinstance(item, dict) and item.get("code") in {"product_not_found", "insufficient_stock"} and item.get("product_id")
        }
        selected = [item for item in state.get("selected_products", []) if str(item.get("id")) not in excluded]
        selection_was_lost = any(
            isinstance(item, dict) and item.get("code") in {
                "catalog_match_not_selected", "unsupported_unavailability_claim",
                "fulfillment_requirement_unmet", "requirement_not_met",
            }
            for item in audit_errors
        )
        bundle_repair_codes = {
            "catalog_match_not_selected", "fulfillment_requirement_unmet",
            "missing_requirement_coverage", "requirement_not_met",
            "stale_bundle_selection", "stale_bundle_total", "missing_bundle_state",
            "product_not_found", "insufficient_stock",
        }
        bundle_needs_rebuild = (
            state.get("recommendation_mode") == "bundle"
            and any(
                isinstance(item, dict) and item.get("code") in bundle_repair_codes
                for item in audit_errors
            )
        )
        rebuilt_bundle: dict[str, Any] = {}
        repair_state = {
            **state,
            "excluded_product_ids": [*state.get("excluded_product_ids", []), *excluded],
        }
        if bundle_needs_rebuild:
            rebuilt_bundle = await self.bundle_optimizer.run(repair_state)
            selected = list(rebuilt_bundle.get("selected_products", []))
        elif (excluded or selection_was_lost) and self._should_recommend_products(self._requested_actions(state)):
            selected = self.brand_voice.select_catalog_products({
                **repair_state,
            })
        # Preserve verified selections and give the response writer exact repair
        # feedback. This avoids replacing a useful answer with an empty one.
        output = {
            **self._event(state, "repair"),
            **rebuilt_bundle,
            "repair_count": attempt,
            "selected_products": selected,
            "excluded_product_ids": [*state.get("excluded_product_ids", []), *sorted(excluded)],
            "repair_feedback": [item for item in audit_errors if isinstance(item, dict)],
            "final_response": None,
            "next_stage": "response_draft",
        }
        self._record_node(state, "repair", output)
        return output

    async def ainvoke(
        self,
        user_request: str,
        *,
        state_overrides: dict[str, Any] | None = None,
        defer_finish: bool = False,
    ) -> ShoppingAgentState:
        if not user_request.strip():
            raise ValueError("A shopping request is required.")
        state = initial_shopping_state(user_request)
        self._started_at = time.monotonic()
        state["run_id"] = uuid4().hex[:12]
        if state_overrides:
            state.update(state_overrides)
        if self.recorder:
            state["run_id"] = self.recorder.request_id
            self.recorder.start(state)
            if self.tool_registry:
                self.tool_registry.recorder = self.recorder
        recorder_token = active_recorder.set(self.recorder)
        try:
            result = await self.graph.ainvoke(state, config={"recursion_limit": self.max_graph_iterations})
        except Exception as error:
            if self.recorder:
                self.recorder.fail(error)
            raise
        finally:
            active_recorder.reset(recorder_token)
        if self.recorder and not defer_finish:
            self.recorder.finish(result)
        return result
