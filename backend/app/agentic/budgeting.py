"""Shared, configurable budget policy for catalog recommendations."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.config import settings


def recommendation_budget_limit(budget: Any) -> Decimal | None:
    """Return the highest price/total eligible for a recommendation.

    The customer's stated budget remains the target.  A small, configurable
    allowance permits clearly disclosed near-budget alternatives.
    """
    if budget is None:
        return None
    amount = Decimal(str(budget))
    tolerance = Decimal(str(settings.agent_recommendation_budget_tolerance_percent)) / Decimal("100")
    return amount * (Decimal("1") + tolerance)
