from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from .budgeting import recommendation_budget_limit
from .brand_voice import BrandVoiceAgent
from .product_roles import units_per_package
from .tools import ToolExecutionError


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
            return AuditResult(
                status="fail", errors=errors, warnings=[], total=None,
                audit_mode="deterministic",
            )

        total = Decimal("0")
        item_totals: list[Decimal] = []
        verified_products: dict[str, dict[str, Any]] = {}
        selected_ids: list[str] = []
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
            if str(product_id) in selected_ids:
                errors.append({"code": "duplicate_selection", "message": "A product may be selected only once."})
                continue
            selected_ids.append(str(product_id))

            try:
                product = await tools.execute("get_product", {"product_id": str(product_id)}) if tools else None
            except ToolExecutionError as error:
                # Do not misrepresent a verification/tooling failure as a
                # deleted catalog item. The repair path can then distinguish
                # actual stale products from a temporary service constraint.
                if str(error) == "Product not found.":
                    errors.append({"code": "product_not_found", "message": "A selected product no longer exists.", "product_id": str(product_id)})
                else:
                    errors.append({"code": "product_verification_failed", "message": "A selected product could not be verified against the current catalog.", "product_id": str(product_id)})
                continue
            except Exception:
                errors.append({"code": "product_verification_failed", "message": "A selected product could not be verified against the current catalog.", "product_id": str(product_id)})
                continue
            if product is None:
                errors.append({"code": "product_not_found", "message": "A selected product no longer exists.", "product_id": str(product_id)})
                continue
            verified_products[str(product_id)] = product
            stock = int(product["inventory_quantity"])
            if stock < quantity:
                errors.append({"code": "insufficient_stock", "message": "A selected product does not have enough available stock.", "product_id": str(product_id)})
                continue
            item_total = Decimal(str(product["price"])) * quantity
            total += item_total
            item_totals.append(item_total)
            self._validate_constraints(product, state, errors)

        budget = state.get("budget")
        if budget is not None:
            recommendation_mode = state.get("recommendation_mode", "single")
            budget_amount = recommendation_budget_limit(budget)
            if recommendation_mode == "bundle" and total > budget_amount:
                errors.append({"code": "budget_exceeded", "message": "The deterministic bundle total exceeds the permitted budget tolerance."})
            elif recommendation_mode == "single" and any(item_total > budget_amount for item_total in item_totals):
                errors.append({"code": "budget_exceeded", "message": "A recommended option exceeds the permitted budget tolerance."})
        self._validate_bundle_consistency(state, selected_ids, total, errors)
        self._validate_budget_disclosure(state, total, errors)
        self._validate_response_coverage(state, selected_ids, errors)
        self._validate_fulfillment(state, verified_products, errors)
        self._validate_response_claims(state, verified_products, errors)
        if BrandVoiceAgent._contains_unverified_availability_language(
            str(state.get("final_response", ""))
        ):
            errors.append({
                "code": "unsupported_availability_claim",
                "message": "A non-stock response uses unverified live availability language.",
            })
        self._validate_attachments(state, verified_products, errors)
        return AuditResult(
            status="pass" if not errors else "fail",
            errors=errors,
            warnings=[],
            total=str(total),
            audit_mode="deterministic",
        )

    async def _audit_stock_response(self, state: dict[str, Any], tools: ToolExecutor | None) -> AuditResult:
        errors: list[dict[str, str]] = []
        claims = state.get("response_claims", [])
        if tools is None:
            errors.append({"code": "tool_registry_unavailable", "message": "Current stock facts cannot be verified."})
            return AuditResult(
                status="fail", errors=errors, warnings=[], total="0",
                audit_mode="deterministic",
            )
        if not isinstance(state.get("final_response"), str) or not state["final_response"].strip():
            errors.append({"code": "missing_final_response", "message": "The response renderer did not produce a final response."})
        if not isinstance(claims, list) or not claims:
            errors.append({"code": "missing_stock_claims", "message": "The stock response contains no verified products."})
            return AuditResult(
                status="fail", errors=errors, warnings=[], total="0",
                audit_mode="deterministic",
            )
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
        return AuditResult(
            status="pass" if not errors else "fail",
            errors=errors,
            warnings=[],
            total="0",
            audit_mode="deterministic",
        )

    @staticmethod
    def _validate_fulfillment(
        state: dict[str, Any], verified_products: dict[str, dict[str, Any]], errors: list[dict[str, str]]
    ) -> None:
        """Require explicit user requirements to be covered by verified products."""
        bundle = state.get("bundle") if isinstance(state.get("bundle"), dict) else {}
        coverage = bundle.get("required_category_coverage", {}) if isinstance(bundle, dict) else {}
        verified_ids = set(verified_products)
        covered_bundle_roles = {
            str(match.get("requirement", "")).casefold().strip()
            for match in coverage.get("matches", [])
            if isinstance(match, dict)
            and str(match.get("requirement", "")).strip()
            and str(match.get("product_id", "")) in verified_ids
        } if isinstance(coverage, dict) else set()
        declared_unfulfilled = {
            str(value).casefold().strip()
            for value in state.get("unfulfilled_requirements", [])
            if isinstance(value, str) and value.strip()
        }
        bundle_missing_roles = {
            str(value).casefold().strip()
            for value in coverage.get("missing", [])
            if isinstance(value, str) and value.strip()
        } if isinstance(coverage, dict) else set()
        allowed_unfulfilled = {
            str(requirement.get("value", "")).casefold().strip()
            for requirement in state.get("fulfillment_requirements", [])
            if isinstance(requirement, dict)
            and any(str(requirement.get("value", "")).casefold().strip() in str(gap).casefold() for gap in state.get("fulfillment_gaps", []))
        }
        allowed_unfulfilled.update(bundle_missing_roles)

        def role_matches_requirement(role: str, requirement_value: str) -> bool:
            return (
                BrandVoiceAgent._terms_present(requirement_value, role)
                or BrandVoiceAgent._terms_present(role, requirement_value)
            )

        def missing_from_bundle(requirement_value: str) -> bool:
            return any(role_matches_requirement(role, requirement_value) for role in bundle_missing_roles)

        def covered_by_current_bundle(requirement_value: str) -> bool:
            return any(role_matches_requirement(role, requirement_value) for role in covered_bundle_roles)

        def declared_for_requirement(requirement_value: str) -> bool:
            return any(
                role_matches_requirement(declared, requirement_value)
                for declared in declared_unfulfilled
            )

        allowed_unfulfilled.update(
            str(requirement.get("value", "")).casefold().strip()
            for requirement in state.get("fulfillment_requirements", [])
            if isinstance(requirement, dict)
            and missing_from_bundle(str(requirement.get("value", "")).casefold().strip())
        )
        if not declared_unfulfilled.issubset(allowed_unfulfilled):
            errors.append({
                "code": "invalid_unfulfilled_requirement",
                "message": "The response declared a fulfillment gap that is not supported by catalog search results.",
            })
        selection_context = state.get("selection_context", {})
        if (
            state.get("recommendation_mode", "single") == "single"
            and declared_unfulfilled
            and isinstance(selection_context, dict)
            and int(selection_context.get("eligible_alternative_count", 0) or 0) > 0
            and selection_context.get("no_eligible_alternative") is not True
        ):
            errors.append({
                "code": "catalog_match_not_selected",
                "message": "Verified refinement alternatives exist but were not carried into the response.",
            })
        # A response may not declare a need unavailable when the search has
        # already supplied an in-stock, budget-eligible verified candidate.
        # This check uses the same typed matcher as selection, so it applies to
        # every future catalog domain without keyword-specific prose rules.
        budget = state.get("budget")
        selected_quantities: dict[str, int] = {}
        for item in state.get("selected_products", []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            try:
                selected_quantities[str(item["id"])] = max(1, int(item.get("quantity", 1) or 1))
            except (TypeError, ValueError):
                continue
        no_eligible_optimization_alternative = (
            isinstance(state.get("selection_context"), dict)
            and state["selection_context"].get("no_eligible_alternative") is True
        )
        for requirement in state.get("fulfillment_requirements", []):
            if (
                not isinstance(requirement, dict)
                or str(requirement.get("kind", "")).casefold().strip()
                not in BrandVoiceAgent._SHOPPING_REQUIREMENT_KINDS
            ):
                continue
            value = str(requirement.get("value", "")).casefold().strip()
            if value not in declared_unfulfilled:
                continue
            if missing_from_bundle(value):
                continue
            for candidate in state.get("candidate_products", []):
                if not isinstance(candidate, dict) or int(candidate.get("inventory_quantity", 0)) < 1:
                    continue
                try:
                    budget_limit = recommendation_budget_limit(budget)
                    within_budget = budget_limit is None or Decimal(str(candidate["price"])) <= budget_limit
                except Exception:
                    within_budget = False
                if within_budget and BrandVoiceAgent._matches_requirement(candidate, requirement):
                    errors.append({
                        "code": "unsupported_unavailability_claim",
                        "message": "The response declares a requirement unavailable despite a verified eligible catalog match.",
                        "requirement": value,
                    })
                    break
        for requirement in state.get("fulfillment_requirements", []):
            if (
                not isinstance(requirement, dict)
                or str(requirement.get("kind", "")).casefold().strip()
                not in BrandVoiceAgent._SHOPPING_REQUIREMENT_KINDS
            ):
                continue
            kind, value = str(requirement.get("kind", "")), str(requirement.get("value", "")).casefold().strip()
            quantity = int(requirement.get("quantity", 1) or 1)
            if not value:
                continue
            # Bundle coverage is produced from model-mapped candidate IDs and
            # then budget/stock checked deterministically by the optimizer.
            # Preserve that verified semantic mapping instead of reinterpreting
            # it later with stricter token equality.
            if kind == "category" and quantity == 1 and covered_by_current_bundle(value):
                continue
            eligible_candidates = []
            for candidate in state.get("candidate_products", []):
                if not isinstance(candidate, dict) or int(candidate.get("inventory_quantity", 0)) < 1:
                    continue
                try:
                    budget_limit = recommendation_budget_limit(budget)
                    within_budget = budget_limit is None or Decimal(str(candidate["price"])) <= budget_limit
                except Exception:
                    within_budget = False
                if within_budget and BrandVoiceAgent._matches_requirement(candidate, requirement):
                    eligible_candidates.append(candidate)
            matched_units = 0
            for product_id, product in verified_products.items():
                if BrandVoiceAgent._matches_requirement(product, requirement):
                    matched_units += (
                        selected_quantities.get(product_id, 1)
                        * units_per_package(product, value)
                    )
            eligible_units = sum(
                int(candidate.get("inventory_quantity", 0)) * units_per_package(candidate, value)
                for candidate in eligible_candidates
            )
            acknowledged_bundle_gap = (
                missing_from_bundle(value)
                and declared_for_requirement(value)
                and declared_unfulfilled.issubset(allowed_unfulfilled)
            )
            if eligible_units >= quantity and matched_units < quantity and not acknowledged_bundle_gap:
                errors.append({
                    "code": "catalog_match_not_selected",
                    "message": "Verified catalog matches were retrieved but not carried into the customer response.",
                    "requirement": value,
                })
            if matched_units < quantity:
                if no_eligible_optimization_alternative:
                    # A continuation can validly ask the customer to relax an
                    # intent-derived criterion when verified search returned
                    # no qualifying alternative. This is not an unavailable
                    # product-type claim.
                    continue
                # The writer must declare the exact unmet typed requirement.
                # This avoids fragile language-specific matching in free prose.
                # A bundle may be partly fulfilled.  A verified item for one
                # requirement must not prevent the writer from explicitly
                # disclosing another requirement that has no catalog match.
                if acknowledged_bundle_gap or (
                    value in declared_unfulfilled and value in allowed_unfulfilled and not eligible_candidates
                ):
                    continue
                errors.append({
                    "code": "fulfillment_requirement_unmet",
                    "message": f"A required {kind or 'product'} need is not covered by verified selections.",
                    "requirement": value,
                })
        # Bundle gaps are shown to the customer by the response writer. They
        # become hard failures only when represented by an explicit typed user
        # requirement above; a broad search query alone is not reliable enough
        # to claim that no matching product exists.

    @staticmethod
    def _validate_bundle_consistency(
        state: dict[str, Any], selected_ids: list[str], verified_total: Decimal,
        errors: list[dict[str, str]],
    ) -> None:
        """Reject stale bundle metadata after selections are repaired."""
        if state.get("recommendation_mode") != "bundle":
            return
        bundle = state.get("bundle")
        if not isinstance(bundle, dict):
            errors.append({
                "code": "missing_bundle_state",
                "message": "A bundle response has no verified bundle state.",
            })
            return
        bundle_ids = [
            str(item.get("product_id"))
            for item in bundle.get("selected_products", [])
            if isinstance(item, dict) and item.get("product_id")
        ]
        if len(bundle_ids) != len(set(bundle_ids)) or set(bundle_ids) != set(selected_ids):
            errors.append({
                "code": "stale_bundle_selection",
                "message": "Bundle coverage does not describe the current selected products.",
            })
        try:
            bundle_total = Decimal(str(bundle.get("total")))
        except Exception:
            bundle_total = None
        if bundle_total is None or bundle_total != verified_total:
            errors.append({
                "code": "stale_bundle_total",
                "message": "The stored bundle total does not match current verified selections.",
            })

    @classmethod
    def _validate_budget_disclosure(
        cls, state: dict[str, Any], verified_total: Decimal,
        errors: list[dict[str, str]],
    ) -> None:
        """Allow the configured tolerance only with an explicit exact warning."""
        if state.get("recommendation_mode") != "bundle" or state.get("budget") is None:
            return
        try:
            target = Decimal(str(state["budget"])).quantize(Decimal("0.01"))
            total = verified_total.quantize(Decimal("0.01"))
        except Exception:
            return
        if total <= target:
            return
        response = str(state.get("final_response", ""))
        amounts = {
            Decimal(value.replace(",", "")).quantize(Decimal("0.01"))
            for value in cls._money_pattern.findall(response)
        }
        if total - target not in amounts:
            errors.append({
                "code": "missing_over_budget_disclosure",
                "message": "An over-target bundle must state the exact amount above the customer's budget.",
            })
        total_mentions = [
            sentence for sentence in re.split(r"(?<=[.!?])\s+", response)
            if any(
                Decimal(value.replace(",", "")).quantize(Decimal("0.01")) == total
                for value in cls._money_pattern.findall(sentence)
            )
        ]
        if any(re.search(r"\b(?:within|under)\s+(?:the\s+|your\s+)?budget\b", sentence, re.IGNORECASE) for sentence in total_mentions):
            errors.append({
                "code": "incorrect_budget_disclosure",
                "message": "An over-target bundle must not be described as within or under budget.",
            })

    @staticmethod
    def _validate_response_coverage(state: dict[str, Any], selected_ids: list[str], errors: list[dict[str, str]]) -> None:
        """Defend the writer's ID checks at the last boundary as well."""
        if state.get("response_source") is None:
            return
        final_response = state.get("final_response")
        if not isinstance(final_response, str) or not final_response.strip():
            errors.append({"code": "missing_final_response", "message": "The response renderer did not produce a final response."})
        claims = state.get("response_claims", [])
        if not isinstance(claims, list):
            return
        claim_ids = [str(item.get("id")) for item in claims if isinstance(item, dict)]
        if selected_ids and (len(claim_ids) != len(set(claim_ids)) or set(claim_ids) != set(selected_ids)):
            errors.append({"code": "incomplete_response_coverage", "message": "The response must cover every selected product exactly once."})

    @staticmethod
    def _validate_response_claims(
        state: dict[str, Any],
        verified_products: dict[str, dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> None:
        """Accept only the structured writer and exact verified facts."""
        if state.get("response_source") is None:
            return
        if state.get("response_source") not in {
            "structured_llm_catalog_v1",
            "structured_llm_brand_voice_v1",
            "deterministic_catalog_renderer_v1",
        }:
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
        # A customer-supplied budget is verified mission evidence, not a
        # catalog price. It is therefore safe to repeat it in the response
        # even when no product has been selected yet.
        budget = state.get("budget")
        if budget is not None:
            try:
                budget_amount = Decimal(str(budget)).quantize(Decimal("0.01"))
                expected_amounts.add(budget_amount)
                for claim in claims:
                    if not isinstance(claim, dict) or "price" not in claim:
                        continue
                    price = Decimal(str(claim["price"])).quantize(Decimal("0.01"))
                    if price > budget_amount:
                        expected_amounts.add(price - budget_amount)
            except Exception:
                errors.append({"code": "invalid_mission_budget", "message": "The mission budget is invalid."})
        if state.get("recommendation_mode") == "bundle" and claims:
            try:
                quantities = {
                    str(item.get("id")): int(item.get("quantity", 1))
                    for item in state.get("selected_products", [])
                    if isinstance(item, dict)
                }
                bundle_total = sum(
                    (
                        Decimal(str(claim["price"])).quantize(Decimal("0.01"))
                        * quantities.get(str(claim.get("id")), 1)
                        for claim in claims if isinstance(claim, dict) and "price" in claim
                    ),
                    Decimal("0.00"),
                )
                expected_amounts.add(bundle_total)
                if budget is not None:
                    target = Decimal(str(budget)).quantize(Decimal("0.01"))
                    expected_amounts.add((target - bundle_total).quantize(Decimal("0.01")))
                    expected_amounts.add((bundle_total - target).quantize(Decimal("0.01")))
            except Exception:
                errors.append({"code": "invalid_bundle_arithmetic", "message": "The bundle arithmetic could not be verified."})
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
