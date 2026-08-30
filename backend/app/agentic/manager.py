"""Deterministic stage selection for the shopping workflow."""
from __future__ import annotations

from typing import Any


class WorkflowManager:
    """Choose only the analysis stages needed for the interpreted mission.

    Routing is deterministic because it controls tool use and latency. The LLM
    may describe requested actions, but cannot cause an unknown stage to run.
    """

    _VALID_STAGES = ("compatibility", "bundle_optimizer")

    def plan(self, state: dict[str, Any], actions: list[str]) -> dict[str, Any]:
        mission_type = str(state.get("mission_type", "")).casefold()
        stages: list[str] = []
        if (
            state.get("recommendation_mode") == "bundle"
            or mission_type in {"build_setup", "bundle"}
            or len(state.get("required_categories", [])) > 1
        ):
            stages.append("bundle_optimizer")
        # Compatibility is meaningful only after a tentative bundle exists.
        if state.get("owned_items") or mission_type in {"build_setup", "bundle"}:
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
