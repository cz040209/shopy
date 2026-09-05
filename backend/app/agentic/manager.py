"""Deterministic stage selection for the shopping workflow."""
from __future__ import annotations

from typing import Any


class WorkflowManager:
    """Choose only the analysis stages needed for the interpreted mission.

    Routing is deterministic because it controls tool use and latency. The LLM
    may describe requested actions, but cannot cause an unknown stage to run.
    """

    _VALID_STAGES = ("product_selector", "compatibility")

    def plan(self, state: dict[str, Any], actions: list[str]) -> dict[str, Any]:
        mission_type = str(state.get("mission_type", "")).casefold()
        stages: list[str] = []
        is_recommendation = (
            "search_products" in actions
            and mission_type in {"product_search", "build_setup", "bundle"}
            and set(actions) <= {"search_products"}
        )
        if is_recommendation:
            # Both single and bundle recommendations pass through the same
            # mandatory LLM selector after catalog retrieval.
            stages.append("product_selector")
        # Compatibility checks operate on the LLM-selected products.
        if is_recommendation and (
            state.get("owned_items") or mission_type in {"build_setup", "bundle"}
        ):
            stages.append("compatibility")
        return {
            "stages": [stage for stage in stages if stage in self._VALID_STAGES],
            "requested_actions": actions,
        }

    @staticmethod
    def next_stage(state: dict[str, Any], completed: str | None = None) -> str:
        stages = [str(stage) for stage in state.get("execution_plan", {}).get("stages", [])]
        if completed in stages:
            stages = stages[stages.index(completed) + 1:]
        return stages[0] if stages else "response_draft"
