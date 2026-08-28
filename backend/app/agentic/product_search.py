"""Deterministic, tool-grounded catalog search and ranking."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.config import settings

from .state import ShoppingAgentState
from .tools import CommerceToolRegistry, ToolExecutionError


class ProductSearchAgent:
    name = "product_search"

    def __init__(self, tools: CommerceToolRegistry | None) -> None:
        self.tools = tools

    async def run(self, state: ShoppingAgentState, *, query: str, limit: int = 8, include_out_of_stock: bool = False) -> dict[str, Any]:
        if self.tools is None:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": ["Catalog tools are unavailable."]}
        try:
            result = await self.tools.execute("search_products", {"query": query, "limit": limit})
        except ToolExecutionError as error:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": [str(error)]}
        ranked = self._rank(result["products"], state, include_out_of_stock=include_out_of_stock)
        return {
            "candidate_products": [item["product"] for item in ranked],
            "product_rankings": [{"product_id": item["product"]["id"], "score": item["score"], "reasons": item["reasons"]} for item in ranked],
            "tool_results": [{"tool": "search_products", "result_count": len(ranked)}],
            "errors": [],
        }

    async def run_many(
        self, state: ShoppingAgentState, *, queries: list[str], limit: int = 8, include_out_of_stock: bool = False
    ) -> dict[str, Any]:
        """Search each requested item independently, then merge stable results."""
        merged: dict[str, dict[str, Any]] = {}
        rankings: dict[str, dict[str, Any]] = {}
        tool_results: list[dict[str, Any]] = []
        errors: list[str] = []
        for query in list(dict.fromkeys(item.strip() for item in queries if item.strip())):
            result = await self.run(state, query=query, limit=limit, include_out_of_stock=include_out_of_stock)
            errors.extend(result["errors"])
            tool_results.extend(result["tool_results"])
            for product in result["candidate_products"]:
                merged.setdefault(str(product["id"]), product)
            for ranking in result["product_rankings"]:
                previous = rankings.get(str(ranking["product_id"]))
                if previous is None or ranking["score"] > previous["score"]:
                    rankings[str(ranking["product_id"])] = ranking
        ordered = sorted(
            merged.values(),
            key=lambda product: (-float(rankings.get(str(product["id"]), {}).get("score", 0)), str(product["name"])),
        )
        return {"candidate_products": ordered, "product_rankings": list(rankings.values()), "tool_results": tool_results, "errors": errors}

    async def run_catalog(
        self, state: ShoppingAgentState, *, limit: int = settings.agent_catalog_context_limit,
        include_out_of_stock: bool = False,
    ) -> dict[str, Any]:
        """Load verified catalog facts before the model chooses recommendations.

        The query intent remains available as ranking context, but it never
        decides which catalog rows the model is allowed to consider.
        """
        if self.tools is None:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": ["Catalog tools are unavailable."]}
        try:
            result = await self.tools.execute("search_products", {"limit": limit})
        except ToolExecutionError as error:
            return {"candidate_products": [], "product_rankings": [], "tool_results": [], "errors": [str(error)]}
        ranked = self._rank(result["products"], state, include_out_of_stock=include_out_of_stock)
        return {
            "candidate_products": [item["product"] for item in ranked],
            "product_rankings": [{"product_id": item["product"]["id"], "score": item["score"], "reasons": item["reasons"]} for item in ranked],
            "tool_results": [{"tool": "search_products", "result_count": len(ranked)}],
            "errors": [],
        }

    @staticmethod
    def _rank(products: list[dict[str, Any]], state: ShoppingAgentState, *, include_out_of_stock: bool) -> list[dict[str, Any]]:
        budget = Decimal(str(state["budget"])) if state.get("budget") is not None else None
        vision = state.get("vision_context", {})
        requested = [
            *state.get("preferences", []), *state.get("constraints", []), *state.get("required_categories", []),
            *(vision.get("colors", []) if isinstance(vision, dict) else []),
            *(vision.get("visual_constraints", []) if isinstance(vision, dict) else []),
        ]
        owned = " ".join(map(str, state.get("owned_items", []))).lower()
        ranked: list[dict[str, Any]] = []
        for product in products:
            if int(product.get("inventory_quantity", 0)) < 1 and not include_out_of_stock:
                continue
            facts = " ".join(map(str, [product.get("name", ""), product.get("brand", ""), product.get("category", ""), product.get("specs", []), product.get("attributes", {})])).lower()
            if owned and str(product.get("name", "")).lower() in owned:
                continue
            score, reasons = (20, ["in stock"]) if int(product.get("inventory_quantity", 0)) > 0 else (0, ["stock status checked"])
            try:
                price = Decimal(str(product["price"]))
                if budget is not None:
                    if price > budget:
                        continue
                    score += 20; reasons.append("within budget")
            except Exception:
                continue
            for item in requested:
                tokens = [token for token in str(item).lower().split() if len(token) > 2]
                if tokens and any(token in facts for token in tokens):
                    score += 10; reasons.append(f"matches {item}")
            ranked.append({"product": product, "score": score, "reasons": reasons})
        return sorted(ranked, key=lambda item: (-item["score"], str(item["product"]["name"])))
