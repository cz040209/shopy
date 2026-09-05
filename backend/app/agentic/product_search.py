"""Tool-grounded, role-expanded catalog retrieval."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.config import settings

from .state import ShoppingAgentState
from .tools import CommerceToolRegistry, ToolExecutionError


class ProductSearchAgent:
    name = "product_search"
    _GENERIC_QUERY_TERMS = {
        "a", "an", "and", "buy", "find", "for", "get", "i", "item", "items",
        "me", "my", "of", "option", "options", "please", "product", "products",
        "recommend", "show", "some", "the", "to", "under", "want", "with",
    }

    def __init__(self, tools: CommerceToolRegistry | None) -> None:
        self.tools = tools

    async def run(self, state: ShoppingAgentState, *, query: str, limit: int = 8, include_out_of_stock: bool = False) -> dict[str, Any]:
        if self.tools is None:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": ["Catalog tools are unavailable."]}
        try:
            result = await self.tools.execute("search_products", {"query": query, "limit": limit})
        except ToolExecutionError as error:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": [str(error)]}
        return self._result(self._rank(result["products"], state, include_out_of_stock=include_out_of_stock), catalog_count=len(result["products"]))

    async def run_requirements(
        self, state: ShoppingAgentState, *, requirements: list[dict[str, Any]],
        per_role_limit: int = settings.agent_catalog_role_matches_per_need,
        include_out_of_stock: bool = False,
    ) -> dict[str, Any]:
        """Retrieve all roles in one tool call and keep bounded role coverage."""
        if self.tools is None:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": ["Catalog tools are unavailable."]}
        groups = []
        for requirement in requirements:
            role = str(requirement.get("canonical_role", "")).strip()
            queries = list(dict.fromkeys(
                str(query).strip() for query in requirement.get("search_queries", [])
                if str(query).strip()
            ))[:6]
            if role and queries:
                groups.append({"role": role, "queries": queries})
        if not groups:
            fallback = str(state.get("catalog_query") or state.get("goal") or state["user_request"]).strip()
            groups = [{"role": fallback[:120], "queries": [fallback[:160]]}]
        try:
            result = await self.tools.execute("search_products", {
                "query_groups": groups,
                "limit": max(1, per_role_limit),
            })
        except ToolExecutionError as error:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": [str(error)]}
        ranked = self._rank(result["products"], state, include_out_of_stock=include_out_of_stock)
        shortlist_limit = max(1, settings.agent_catalog_shortlist_limit)
        by_id = {str(item["product"]["id"]): item for item in ranked}
        role_ids = [
            str(product_id)
            for group in groups
            for product_id in result.get("query_matches", {}).get(group["role"], [])
            if str(product_id) in by_id
        ]
        memory = state.get("memory_context")
        prior = memory.get("selected_products", []) if isinstance(memory, dict) else []
        reference_ids = [
            str(item.get("id")) for item in prior
            if isinstance(item, dict) and str(item.get("id")) in by_id
        ]
        ranked_ids = [str(item["product"]["id"]) for item in ranked]
        chosen = list(dict.fromkeys([*role_ids, *reference_ids, *ranked_ids]))[:shortlist_limit]
        shortlisted = [by_id[product_id] for product_id in chosen]
        return self._result(
            shortlisted,
            catalog_count=len(result["products"]),
            retrieval_role_matches={
                str(role): [str(product_id) for product_id in product_ids]
                for role, product_ids in result.get("query_matches", {}).items()
            },
        )

    @staticmethod
    def _result(
        ranked: list[dict[str, Any]], *, catalog_count: int,
        retrieval_role_matches: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        return {
            "candidate_products": [item["product"] for item in ranked],
            "product_rankings": [
                {"product_id": item["product"]["id"], "score": item["score"], "reasons": item["reasons"]}
                for item in ranked
            ],
            "tool_results": [{"tool": "search_products", "catalog_count": catalog_count, "result_count": len(ranked)}],
            "retrieval_role_matches": retrieval_role_matches or {},
            "errors": [],
        }

    @classmethod
    def _intent_terms(cls, state: ShoppingAgentState) -> set[str]:
        vision = state.get("vision_context", {})
        values: list[Any] = [
            state.get("user_request", ""), state.get("goal", ""), state.get("catalog_query", ""),
            *state.get("catalog_queries", []), *state.get("preferences", []),
            *state.get("constraints", []), *state.get("required_categories", []),
            *(vision.get("colors", []) if isinstance(vision, dict) else []),
            *(vision.get("visual_constraints", []) if isinstance(vision, dict) else []),
        ]
        for requirement in state.get("search_requirements", []):
            if not isinstance(requirement, dict):
                continue
            values.extend([
                requirement.get("canonical_role", ""),
                *requirement.get("required_features", []),
                *requirement.get("preferred_features", []),
                *requirement.get("search_queries", []),
            ])
        values.extend(
            requirement.get("value", "") for requirement in state.get("fulfillment_requirements", [])
            if isinstance(requirement, dict)
            and str(requirement.get("kind", "")).casefold().strip()
            in {"category", "feature", "attribute"}
        )
        return {
            cls._normalize_token(token)
            for token in re.findall(r"[\w]+", " ".join(map(str, values)).casefold())
            if len(token) > 1 and token not in cls._GENERIC_QUERY_TERMS and not token.isdigit()
        }

    @staticmethod
    def _normalize_token(token: str) -> str:
        if len(token) > 4 and token.endswith("ies"):
            return f"{token[:-3]}y"
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            return token[:-1]
        return token

    @classmethod
    def _rank(cls, products: list[dict[str, Any]], state: ShoppingAgentState, *, include_out_of_stock: bool) -> list[dict[str, Any]]:
        budget = Decimal(str(state["budget"])) if state.get("budget") is not None else None
        intent_terms = cls._intent_terms(state)
        owned = " ".join(map(str, state.get("owned_items", []))).lower()
        ranked: list[dict[str, Any]] = []
        for product in products:
            if int(product.get("inventory_quantity", 0)) < 1 and not include_out_of_stock:
                continue
            facts = " ".join(map(str, [
                product.get("name", ""), product.get("brand", ""), product.get("category", ""),
                product.get("search_terms", []), product.get("seller_name", ""),
                product.get("specs", []), product.get("attributes", {}),
            ])).casefold()
            if owned and str(product.get("name", "")).casefold() in owned:
                continue
            score, reasons = (20, ["in stock"]) if int(product.get("inventory_quantity", 0)) > 0 else (0, ["stock status checked"])
            try:
                price = Decimal(str(product["price"]))
                if budget is not None:
                    if price > budget:
                        continue
                    score += 20
                    reasons.append("within budget")
            except Exception:
                continue
            fact_terms = {
                cls._normalize_token(token) for token in re.findall(r"[\w]+", facts)
            }
            matched = sorted(intent_terms.intersection(fact_terms))
            if matched:
                score += 12 * len(matched)
                reasons.append(f"matches mission terms: {', '.join(matched[:8])}")
            ranked.append({"product": product, "score": score, "reasons": reasons})
        return sorted(ranked, key=lambda item: (-item["score"], str(item["product"]["name"])))
