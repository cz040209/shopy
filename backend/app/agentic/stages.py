"""Extension contracts for future analysis stages; no commerce mutations here."""
from __future__ import annotations

from typing import Any, Protocol

from .state import ShoppingAgentState


class FutureAnalysisAgent(Protocol):
    name: str

    async def run(self, state: ShoppingAgentState) -> dict[str, Any]: ...


class ProductSearchAgent(FutureAnalysisAgent, Protocol): ...


class ReviewAgent(FutureAnalysisAgent, Protocol): ...


class SellerRiskAgent(FutureAnalysisAgent, Protocol): ...


class CompatibilityAgent(FutureAnalysisAgent, Protocol): ...


class BundleOptimizer(FutureAnalysisAgent, Protocol): ...


class VisionAgent(FutureAnalysisAgent, Protocol): ...
