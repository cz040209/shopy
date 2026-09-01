"""Catalog-evidence product-role matching shared by shopping stages."""
from __future__ import annotations

import re
from typing import Any


# These are product-form words, rather than catalog or department aliases.  They
# let the matcher understand ordinary customer language (for example, soap vs
# shampoo) without encoding any domain-specific category mapping.
_ROLE_TERM_FAMILIES = (
    frozenset({"cleaner", "cleanser", "detergent", "shampoo", "soap", "wash"}),
)
_GENERIC_TERMS = {"item", "items", "option", "options", "product", "products"}


def normalized_terms(value: str) -> list[str]:
    """Return stable, singularized meaningful terms from user or catalog text."""
    terms: list[str] = []
    for token in re.findall(r"[\w]+", value.casefold()):
        if len(token) < 2:
            continue
        if len(token) > 4 and token.endswith("ies"):
            token = f"{token[:-3]}y"
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if token not in _GENERIC_TERMS:
            terms.append(token)
    return terms


def product_identity_parts(product: dict[str, Any]) -> list[str]:
    """Use catalog type fields as role evidence, never incidental specifications."""
    attributes = product.get("attributes", {})
    typed_values = [
        str(value) for key, value in attributes.items()
        if key.casefold() in {"type", "product_type"} or key.casefold().endswith("_category")
    ] if isinstance(attributes, dict) else []
    return [str(product.get("name", "")), str(product.get("category", "")), *typed_values]


def _same_product_form(left: str, right: str) -> bool:
    if left == right:
        return True
    return any(left in family and right in family for family in _ROLE_TERM_FAMILIES)


def matches_product_role(product: dict[str, Any], role: str) -> bool:
    """Match a product role against typed catalog identity evidence.

    Exact normalized matching remains the normal path.  The fallback permits a
    generic product-form equivalent only when every requested qualifier is
    present in the catalog identity.  That prevents an unrelated cleaner from
    matching a request such as ``wheel cleaner`` while allowing catalog-native
    labels like ``car shampoo`` to satisfy ``car wash soap``.
    """
    requested = normalized_terms(role)
    if not requested:
        return True
    identity_parts = product_identity_parts(product)
    available = set(normalized_terms(" ".join(identity_parts)))
    attributes = product.get("attributes", {})
    # Department can corroborate a matching product role (for example, a bag
    # sold in the travel department), but it never supplies the role head.
    if isinstance(attributes, dict):
        available.update(normalized_terms(str(attributes.get("department", ""))))
    heads = {
        terms[-1] for part in identity_parts
        if (terms := normalized_terms(part))
    }
    if set(requested).issubset(available) and requested[-1] in heads:
        return True

    qualifiers, requested_head = requested[:-1], requested[-1]
    return bool(qualifiers) and set(qualifiers).issubset(available) and any(
        _same_product_form(requested_head, product_head) for product_head in heads
    )
