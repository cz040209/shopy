from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID


class ToolExecutor(Protocol):
    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class AuditResult(dict[str, Any]):
    pass


class ShoppingAuditor:
    """Deterministic last-line verification of product facts and selections."""

    _allowed_selection_fields = {"id", "quantity"}

    async def audit(self, state: dict[str, Any], tools: ToolExecutor | None) -> AuditResult:
        errors: list[dict[str, str]] = []
        selected = state.get("selected_products", [])
        if tools is None and selected:
            errors.append({"code": "tool_registry_unavailable", "message": "Current catalog facts cannot be verified."})
            return AuditResult(status="fail", errors=errors, total=None)

        total = Decimal("0")
        for selection in selected:
            if not isinstance(selection, dict) or set(selection) - self._allowed_selection_fields:
                errors.append({"code": "unsupported_product_claim", "message": "Selections may contain only product IDs and quantities."})
                continue
            try:
                product_id = UUID(str(selection.get("id")))
                quantity = int(selection.get("quantity", 1))
                if quantity < 1:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append({"code": "invalid_selection", "message": "Product selection is invalid."})
                continue

            try:
                product = await tools.execute("get_product", {"product_id": str(product_id)}) if tools else None
            except Exception:
                errors.append({"code": "product_not_found", "message": "A selected product no longer exists."})
                continue
            if product is None:
                errors.append({"code": "product_not_found", "message": "A selected product no longer exists."})
                continue
            stock = int(product["inventory_quantity"])
            if stock < quantity:
                errors.append({"code": "insufficient_stock", "message": "A selected product does not have enough available stock."})
                continue
            total += Decimal(str(product["price"])) * quantity
            self._validate_constraints(product, state, errors)

        budget = state.get("budget")
        if budget is not None and total > Decimal(str(budget)):
            errors.append({"code": "budget_exceeded", "message": "The deterministic bundle total exceeds the mission budget."})
        return AuditResult(status="pass" if not errors else "fail", errors=errors, total=str(total))

    @staticmethod
    def _validate_constraints(product: dict[str, Any], state: dict[str, Any], errors: list[dict[str, str]]) -> None:
        # Treat catalog specs/attributes as plain data, never as executable or
        # prompt content. Only explicit factual tokens are used for matching.
        facts = f"{product.get('name', '')} {product.get('specs', [])} {product.get('attributes', {})}".lower()
        requested = [*state.get("preferences", []), *state.get("constraints", [])]
        if any("wireless" in str(item).lower() for item in requested) and "wireless" not in facts:
            errors.append({"code": "constraint_unverified", "message": "Wireless preference is not verified by catalog facts."})
