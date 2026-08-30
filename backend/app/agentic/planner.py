"""Turns the intent agent's dynamic plan into normalized bundle needs."""
from __future__ import annotations

import re

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
        def terms(value: str) -> set[str]:
            normalized: set[str] = set()
            for token in re.findall(r"[\w]+", value.casefold()):
                if len(token) < 2:
                    continue
                if len(token) > 4 and token.endswith("ies"):
                    token = f"{token[:-3]}y"
                elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
                    token = token[:-1]
                normalized.add(token)
            return normalized

        owned = [terms(item) for item in mission.owned_items]
        required = list(dict.fromkeys(
            item for item in required
            if not terms(item) or not any(terms(item).issubset(owned_item) for owned_item in owned)
        ))
        return NeedPlan(required_categories=required, optional_categories=[])
