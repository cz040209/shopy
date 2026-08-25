from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class ShoppingAgentState(TypedDict):
    """Shared LangGraph state for every stage of a shopping mission."""

    user_request: str
    mission_type: str | None
    goal: str | None
    catalog_query: str | None
    catalog_queries: list[str]
    requested_actions: list[str]
    bundle_items: list[dict[str, Any]]
    budget: float | None
    preferences: list[str]
    constraints: list[str]
    owned_items: list[str]
    priorities: list[str]
    required_categories: list[str]
    optional_categories: list[str]
    candidate_products: list[dict[str, Any]]
    product_rankings: list[dict[str, Any]]
    review_insights: dict[str, dict[str, Any]]
    vision_context: dict[str, Any] | None
    vision_input: NotRequired[dict[str, Any]]
    stock_results: list[dict[str, Any]]
    tool_context: list[dict[str, Any]]
    selected_products: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    audit_result: dict[str, Any] | None
    repair_count: int
    final_response: str | None
    response_claims: list[dict[str, Any]]
    response_source: str | None
    attachments: list[dict[str, Any]]
    next_stage: str | None
    errors: list[str]
    graph_iterations: int
    run_id: str
    mission: NotRequired[dict[str, Any]]


def initial_shopping_state(user_request: str) -> ShoppingAgentState:
    """Create a complete state object without leaking mutable defaults."""
    return {
        "user_request": user_request.strip(),
        "mission_type": None,
        "goal": None,
        "catalog_query": None,
        "catalog_queries": [],
        "requested_actions": [],
        "bundle_items": [],
        "budget": None,
        "preferences": [],
        "constraints": [],
        "owned_items": [],
        "priorities": [],
        "required_categories": [],
        "optional_categories": [],
        "candidate_products": [],
        "product_rankings": [],
        "review_insights": {},
        "vision_context": None,
        "stock_results": [],
        "tool_context": [],
        "selected_products": [],
        "tool_results": [],
        "audit_result": None,
        "repair_count": 0,
        "final_response": None,
        "response_claims": [],
        "response_source": None,
        "attachments": [],
        "next_stage": None,
        "errors": [],
        "graph_iterations": 0,
        "run_id": "",
    }
