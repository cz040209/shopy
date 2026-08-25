from __future__ import annotations

import re
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
    _money_pattern = re.compile(r"\b(?:RM|MYR)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b", re.IGNORECASE)

    async def audit(self, state: dict[str, Any], tools: ToolExecutor | None) -> AuditResult:
        errors: list[dict[str, str]] = []
        selected = state.get("selected_products", [])
        if state.get("response_source") in {"structured_llm_stock_v1", "structured_llm_brand_voice_stock_v1"}:
            return await self._audit_stock_response(state, tools)
        if tools is None and selected:
            errors.append({"code": "tool_registry_unavailable", "message": "Current catalog facts cannot be verified."})
            return AuditResult(status="fail", errors=errors, total=None)

        total = Decimal("0")
        verified_products: dict[str, dict[str, Any]] = {}
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
            verified_products[str(product_id)] = product
            stock = int(product["inventory_quantity"])
            if stock < quantity:
                errors.append({"code": "insufficient_stock", "message": "A selected product does not have enough available stock."})
                continue
            total += Decimal(str(product["price"])) * quantity
            self._validate_constraints(product, state, errors)

        budget = state.get("budget")
        if budget is not None and total > Decimal(str(budget)):
            errors.append({"code": "budget_exceeded", "message": "The deterministic bundle total exceeds the mission budget."})
        self._validate_response_claims(state, verified_products, errors)
        self._validate_attachments(state, verified_products, errors)
        return AuditResult(status="pass" if not errors else "fail", errors=errors, total=str(total))

    async def _audit_stock_response(self, state: dict[str, Any], tools: ToolExecutor | None) -> AuditResult:
        errors: list[dict[str, str]] = []
        claims = state.get("response_claims", [])
        if tools is None:
            errors.append({"code": "tool_registry_unavailable", "message": "Current stock facts cannot be verified."})
            return AuditResult(status="fail", errors=errors, total="0")
        if not isinstance(state.get("final_response"), str) or not state["final_response"].strip():
            errors.append({"code": "missing_final_response", "message": "The response renderer did not produce a final response."})
        if not isinstance(claims, list) or not claims:
            errors.append({"code": "missing_stock_claims", "message": "The stock response contains no verified products."})
            return AuditResult(status="fail", errors=errors, total="0")
        for claim in claims:
            try:
                product_id = UUID(str(claim["id"]))
                stock = await tools.execute("check_stock", {"product_id": str(product_id)})
            except Exception:
                errors.append({"code": "stock_not_verified", "message": "A stock result could not be verified."})
                continue
            expected = {"available_quantity": int(stock["available_quantity"]), "in_stock": bool(stock["in_stock"])}
            if any(claim.get(key) != value for key, value in expected.items()):
                errors.append({"code": "unsupported_stock_claim", "message": "A response stock claim differs from current catalog facts."})
            name = str(claim.get("name", ""))
            expected_line = (
                f"{name}: {'in stock' if expected['in_stock'] else 'out of stock'} "
                f"({expected['available_quantity']} available)"
            )
            if expected_line not in state["final_response"]:
                errors.append({"code": "missing_response_product_reference", "message": "A verified product is missing from the response text."})
        return AuditResult(status="pass" if not errors else "fail", errors=errors, total="0")

    @staticmethod
    def _validate_response_claims(
        state: dict[str, Any],
        verified_products: dict[str, dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> None:
        """Accept only the structured writer and exact verified facts."""
        if state.get("response_source") is None:
            return
        if state.get("response_source") not in {"structured_llm_catalog_v1", "structured_llm_brand_voice_v1"}:
            errors.append({"code": "untrusted_response_source", "message": "The response was not created by the verified renderer."})
            return
        if not isinstance(state.get("final_response"), str) or not state["final_response"].strip():
            errors.append({"code": "missing_final_response", "message": "The response renderer did not produce a final response."})
        claims = state.get("response_claims", [])
        if not isinstance(claims, list):
            errors.append({"code": "invalid_response_claims", "message": "Response claims are invalid."})
            return
        for claim in claims:
            if not isinstance(claim, dict):
                errors.append({"code": "invalid_response_claim", "message": "A response claim is invalid."})
                continue
            product = verified_products.get(str(claim.get("id")))
            if product is None:
                errors.append({"code": "unverified_response_product", "message": "A response names a product that was not verified."})
                continue
            expected = {
                "name": str(product["name"]),
                "brand": str(product["brand"]),
                "price": str(product["price"]),
                "currency": str(product["currency"]),
                "in_stock": True,
            }
            if any(claim.get(key) != value for key, value in expected.items()):
                errors.append({"code": "unsupported_response_claim", "message": "A response product claim differs from current catalog facts."})
                continue
            if expected["name"] not in state["final_response"]:
                errors.append({"code": "missing_response_product_reference", "message": "A verified product is missing from the response text."})

        expected_amounts = {
            Decimal(str(claim["price"])).quantize(Decimal("0.01"))
            for claim in claims
            if isinstance(claim, dict) and "price" in claim
        }
        for item in state.get("tool_context", []):
            if not isinstance(item, dict) or item.get("tool") != "calculate_bundle_total":
                continue
            result = item.get("result")
            if isinstance(result, dict) and "subtotal" in result:
                expected_amounts.add(Decimal(str(result["subtotal"])).quantize(Decimal("0.01")))
        for amount in ShoppingAuditor._money_pattern.findall(state.get("final_response", "")):
            try:
                parsed = Decimal(amount.replace(",", "")).quantize(Decimal("0.01"))
            except Exception:
                errors.append({"code": "invalid_response_price", "message": "The response contains an invalid price."})
                continue
            if parsed not in expected_amounts:
                errors.append({"code": "unsupported_response_price", "message": "The response contains a price not verified by the catalog."})

    @staticmethod
    def _validate_attachments(
        state: dict[str, Any],
        verified_products: dict[str, dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> None:
        attachments = state.get("attachments", [])
        if not isinstance(attachments, list):
            errors.append({"code": "invalid_attachments", "message": "Response attachments are invalid."})
            return
        for attachment in attachments:
            if not isinstance(attachment, dict):
                errors.append({"code": "invalid_attachment", "message": "A response attachment is invalid."})
                continue
            product = verified_products.get(str(attachment.get("product_id")))
            if product is None:
                errors.append({"code": "unverified_attachment_product", "message": "An attachment product was not verified."})
                continue
            expected = {
                "product_slug": str(product["slug"]),
                "name": str(product["name"]),
                "price": str(product["price"]),
                "currency": str(product["currency"]),
                "image_url": product.get("image_url"),
            }
            if any(attachment.get(key) != value for key, value in expected.items()):
                errors.append({"code": "unsupported_attachment_claim", "message": "An attachment differs from verified catalog facts."})

    @staticmethod
    def _validate_constraints(product: dict[str, Any], state: dict[str, Any], errors: list[dict[str, str]]) -> None:
        # Treat catalog specs/attributes as plain data, never as executable or
        # prompt content. Only explicit factual tokens are used for matching.
        facts = f"{product.get('name', '')} {product.get('specs', [])} {product.get('attributes', {})}".lower()
        requested = [*state.get("preferences", []), *state.get("constraints", [])]
        if any("wireless" in str(item).lower() for item in requested) and "wireless" not in facts:
            errors.append({"code": "constraint_unverified", "message": "Wireless preference is not verified by catalog facts."})
