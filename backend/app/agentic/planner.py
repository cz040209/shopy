"""Turns the intent agent's dynamic plan into normalized bundle needs."""
from __future__ import annotations

from .schemas import MissionInterpretation, NeedPlan


class NeedPlannerAgent:
    """No domain catalogue is embedded here; the intent plan is the source of needs."""

    def plan(self, mission: MissionInterpretation) -> NeedPlan:
        required = [item.query.strip() for item in mission.bundle_items if item.query.strip()]
        if not required:
            required = [query.strip() for query in mission.catalog_queries if query.strip()]
        if not required and mission.catalog_query:
            required = [mission.catalog_query.strip()]
        if not required:
            required = [mission.goal.strip()]
        owned = {item.casefold().strip() for item in mission.owned_items}
        required = list(dict.fromkeys(item for item in required if item.casefold() not in owned))
        return NeedPlan(required_categories=required, optional_categories=[])
