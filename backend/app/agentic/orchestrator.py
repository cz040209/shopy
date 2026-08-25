from __future__ import annotations

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
from .llm import GeminiLangChainChatModel
from .planner import NeedPlannerAgent
from .observability import OrchestrationRecorder
from .product_resolution import ProductResolutionAgent
from .product_search import ProductSearchAgent
from .review_intelligence import ReviewIntelligenceAgent
from .state import ShoppingAgentState, initial_shopping_state
from .tools import CommerceToolRegistry, ToolExecutionError
from .vision import VisionAgent


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
        vision_agent: VisionAgent | None = None,
    ) -> None:
        shared_model = model or GeminiLangChainChatModel(timeout_seconds=settings.agent_model_timeout_seconds)
        self.tool_registry = tool_registry
        self.intent_agent = IntentMissionAgent(shared_model, tools=tool_registry.tools if tool_registry else ())
        self.need_planner = NeedPlannerAgent()
        self.product_resolver = ProductResolutionAgent(shared_model)
        self.product_search_agent = ProductSearchAgent(tool_registry)
        self.review_agent = ReviewIntelligenceAgent(shared_model, tool_registry)
        self.compatibility_agent = CompatibilityAgent(shared_model)
        self.bundle_optimizer = BundleOptimizerAgent(shared_model)
        self.vision_agent = vision_agent or VisionAgent()
        self.brand_voice = BrandVoiceAgent(shared_model)
        self.auditor = auditor or ShoppingAuditor()
        self.max_repairs = max_repairs
        self.max_graph_iterations = max_graph_iterations
        self.recorder = recorder
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ShoppingAgentState)
        workflow.add_node("vision", self._vision_node)
        workflow.add_node("intent_agent", self._intent_node)
        workflow.add_node("need_planner", self._need_planner_node)
        workflow.add_node("product_search", self._product_search_node)
        workflow.add_node("review_intelligence", self._review_node)
        workflow.add_node("compatibility", self._compatibility_node)
        workflow.add_node("bundle_optimizer", self._bundle_optimizer_node)
        workflow.add_node("brand_voice", self._brand_voice_node)
        workflow.add_node("audit", self._audit_node)
        workflow.add_node("repair", self._repair_node)
        workflow.add_conditional_edges(START, self._route_start, {"vision": "vision", "intent_agent": "intent_agent"})
        workflow.add_edge("vision", "intent_agent")
        workflow.add_edge("intent_agent", "need_planner")
        workflow.add_conditional_edges(
            "need_planner",
            self._after_planner,
            {"product_search": "product_search", "brand_voice": "brand_voice"},
        )
        workflow.add_edge("product_search", "review_intelligence")
        workflow.add_edge("review_intelligence", "compatibility")
        workflow.add_edge("compatibility", "bundle_optimizer")
        workflow.add_edge("bundle_optimizer", "brand_voice")
        workflow.add_edge("brand_voice", "audit")
        workflow.add_conditional_edges("audit", self._after_audit, {"repair": "repair", "end": END})
        workflow.add_edge("repair", "brand_voice")
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
        elif node == "vision":
            inputs["mode"] = state.get("vision_input", {}).get("mode")
        elif node == "review_intelligence":
            inputs["candidate_product_ids"] = [item.get("id") for item in state.get("candidate_products", [])]
        elif node == "compatibility":
            inputs["candidate_product_ids"] = [item.get("id") for item in state.get("candidate_products", [])]
        elif node == "bundle_optimizer":
            inputs["required_categories"] = state.get("required_categories", [])
        elif node == "brand_voice":
            inputs["selected_products"] = state.get("selected_products", [])
        elif node == "audit":
            inputs["selected_products"] = state.get("selected_products", [])
        elif node == "repair":
            inputs["audit_result"] = state.get("audit_result")
        self.recorder.record("node_completed", node_name=node, input_data=inputs, output_data=output)

    def _after_planner(self, state: ShoppingAgentState) -> str:
        return "product_search" if self._requires_catalog_lookup(state) else "brand_voice"

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
        runtime_context = {"vision_context": state["vision_context"]} if state.get("vision_context") else None
        mission = await self.intent_agent.interpret(request, runtime_context=runtime_context)
        output = {
            **self._event(state, "intent_agent"),
            "mission_type": mission.mission_type, "goal": mission.goal, "catalog_query": mission.catalog_query,
            "catalog_queries": mission.catalog_queries, "requested_actions": mission.requested_actions, "budget": mission.budget,
            "bundle_items": [item.model_dump() for item in mission.bundle_items],
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
        result: dict[str, Any] = {**self._event(state, "product_search"), "next_stage": "brand_voice"}
        if self.tool_registry is None:
            self._record_node(state, "product_search", result)
            return result
        actions = self._requested_actions(state)
        search_output = await self.product_search_agent.run(state, query=self._catalog_query(state), limit=self._stock_search_limit() if "check_stock" in actions else 8, include_out_of_stock="check_stock" in actions)
        if search_output["errors"]:
            output = {**result, "errors": [*state["errors"], *search_output["errors"]]}
            self._record_node(state, "product_search", output)
            return output
        candidates = search_output["candidate_products"]
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
        action_candidates, resolution_context = await self._resolve_action_candidates(state, actions, candidates)
        tool_context = [*resolution_context, *(await self._execute_requested_actions(actions, action_candidates, state))]
        response_candidates = action_candidates if resolution_context else candidates
        output = {
            **result,
            "candidate_products": candidates,
            "selected_products": (
                self.brand_voice.select_catalog_products({**state, "candidate_products": response_candidates})
                if self._should_recommend_products(actions) else []
            ),
            "tool_results": [*state["tool_results"], *search_output["tool_results"]],
            "tool_context": tool_context,
        }
        self._record_node(state, "product_search", output)
        return output

    async def _review_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        insights = {} if state.get("stock_results") else await self.review_agent.run(state)
        output = {**self._event(state, "review_intelligence"), **insights}
        self._record_node(state, "review_intelligence", output)
        return output

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
            or self._is_stock_check(state)
            or self.brand_voice.is_shopping_mission(state.get("mission_type"))
        ):
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
            user_request=state["user_request"], actions=actions, candidates=candidates
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

    def _stock_search_limit(self) -> int:
        if self.tool_registry is None:
            return 1
        # search + one check per match + one audit check per reported match
        return max(1, min(8, (self.tool_registry.max_calls - 1) // 2))

    @staticmethod
    def _should_recommend_products(actions: list[str]) -> bool:
        """Only catalog-discovery requests produce recommendation cards/IDs."""
        return set(actions) <= {"search_products"}

    async def _brand_voice_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        output = {
            **self._event(state, "brand_voice"),
            **(await self.brand_voice.compose(state)),
            "next_stage": "audit",
        }
        self._record_node(state, "brand_voice", output)
        return output

    async def _audit_node(self, state: ShoppingAgentState) -> dict[str, Any]:
        audit = await self.auditor.audit(state, self.tool_registry)
        log_ai_event("agent.audit", request_id=state["run_id"], status=audit["status"], error_codes=[item["code"] for item in audit["errors"]])
        output = {**self._event(state, "audit"), "audit_result": dict(audit)}
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
        output = {
            **self._event(state, "repair"),
            "repair_count": attempt,
            "selected_products": [],
            "response_claims": [],
            "final_response": None,
            "next_stage": "brand_voice",
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
        if self.recorder and not defer_finish:
            self.recorder.finish(result)
        return result
