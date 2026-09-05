"""LangGraph-powered shopping-agent backbone.

This package intentionally contains no HTTP route or database mutation. It is
the reusable workflow layer that future API, voice, and vision entry points use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .brand_voice import BrandVoiceAgent
    from .orchestrator import ShoppingOrchestrator
    from .state import ShoppingAgentState

__all__ = ["BrandVoiceAgent", "ShoppingAgentState", "ShoppingOrchestrator", "initial_shopping_state"]


def __getattr__(name: str) -> Any:
    """Load public agent types lazily to avoid provider/orchestrator cycles."""
    if name == "BrandVoiceAgent":
        from .brand_voice import BrandVoiceAgent
        return BrandVoiceAgent
    if name == "ShoppingOrchestrator":
        from .orchestrator import ShoppingOrchestrator
        return ShoppingOrchestrator
    if name in {"ShoppingAgentState", "initial_shopping_state"}:
        from .state import ShoppingAgentState, initial_shopping_state
        return {
            "ShoppingAgentState": ShoppingAgentState,
            "initial_shopping_state": initial_shopping_state,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
