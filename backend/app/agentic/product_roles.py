"""Catalog-evidence product-role matching shared by shopping stages."""
from __future__ import annotations

import re
from typing import Any


_GENERIC_TERMS = {"item", "items", "option", "options", "product", "products"}
_ROLE_ANNOTATION_WORDS = {
    "alternative", "alternatives", "example", "examples", "optional",
}
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "pair": 2, "dozen": 12,
}


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


def role_alternatives(value: str) -> list[str]:
    """Expand a parenthetical role menu without knowing any catalog taxonomy.

    Vision and language models sometimes express one acceptable role as an
    umbrella plus examples, such as ``footwear (sneakers or boots)``. Flattening
    that phrase makes every example look mandatory. This parser understands the
    expression's grammar and leaves ordinary parenthetical qualifiers intact.
    """
    text = " ".join(str(value).split()).strip()
    match = re.fullmatch(r"([^()]+?)\s*\(([^()]+)\)", text)
    if not match:
        return [text] if text else []
    umbrella, annotation = (part.strip() for part in match.groups())
    annotated_terms = normalized_terms(annotation)
    expresses_menu = bool(
        re.search(r"\b(?:or|and/or)\b|[,;/]", annotation, flags=re.IGNORECASE)
        or _ROLE_ANNOTATION_WORDS.intersection(annotated_terms)
    )
    if not expresses_menu:
        return [text]
    choices = []
    for choice in re.split(r"\s+(?:or|and/or)\s+|[,;/]", annotation, flags=re.IGNORECASE):
        cleaned = re.sub(
            r"^(?:(?:or|and|and/or)\s+)?(?:(?:alternative|alternatives|example|examples|optional)\s+)?",
            "", choice.strip(), flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            choices.append(cleaned)
    return list(dict.fromkeys([umbrella, *choices]))


def product_identity_parts(product: dict[str, Any]) -> list[str]:
    """Use catalog type fields as role evidence, never incidental specifications."""
    attributes = product.get("attributes", {})
    typed_values = [
        str(value) for key, value in attributes.items()
        if key.casefold() in {"type", "product_type"} or key.casefold().endswith("_category")
    ] if isinstance(attributes, dict) else []
    return [str(product.get("name", "")), str(product.get("category", "")), *typed_values]


def _same_product_form(left: str, right: str) -> bool:
    return left == right


def _matches_simple_product_role(product: dict[str, Any], role: str) -> bool:
    """Match a product role against typed catalog identity evidence.

    Product-form vocabulary is supplied dynamically by the intent stage. This
    matcher therefore validates normalized catalog identity without embedding
    a product taxonomy or synonym dictionary.
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
    return set(qualifiers).issubset(available) and any(
        _same_product_form(requested_head, product_head) for product_head in heads
    )


def matches_product_role(product: dict[str, Any], role: str) -> bool:
    """Match one catalog identity against any valid expression alternative."""
    alternatives = role_alternatives(role)
    return bool(alternatives) and any(
        _matches_simple_product_role(product, alternative)
        for alternative in alternatives
    )


def has_product_role_overlap(product: dict[str, Any], role: str) -> bool:
    """Require a semantic mapping to preserve the requested product form."""
    available = normalized_terms(" ".join(product_identity_parts(product)))
    return bool(available) and any(
        requested
        and any(
            _same_product_form(requested[-1], product_term)
            for product_term in available
        )
        for alternative in role_alternatives(role)
        if (requested := normalized_terms(alternative))
    )


def units_per_package(product: dict[str, Any], role: str) -> int:
    """Read an explicit role-unit count from structured pack-size evidence.

    Counts are accepted only when the nearby noun matches the requested role,
    so dimensions and volumes such as ``50 x 80 cm`` or ``473 ml`` cannot be
    mistaken for the number of requested items.
    """
    attributes = product.get("attributes", {})
    values: list[str] = []
    if isinstance(attributes, dict):
        values.extend(
            str(value) for key, value in attributes.items()
            if key.casefold().replace("_", " ") in {
                "pack size", "package contents", "pack contents", "quantity", "count",
            }
        )
    for spec in product.get("specs", []):
        if not isinstance(spec, dict):
            continue
        label = str(spec.get("label", "")).casefold().replace("_", " ").strip()
        if label in {"pack size", "package contents", "pack contents", "quantity", "count"}:
            values.append(str(spec.get("value", "")))

    requested_heads = [
        terms[-1]
        for alternative in role_alternatives(role)
        if (terms := normalized_terms(alternative))
    ]
    if not requested_heads:
        return 1
    for value in values:
        raw_tokens = re.findall(r"[\w]+", value.casefold())
        for index, token in enumerate(raw_tokens):
            count = int(token) if token.isdigit() else _NUMBER_WORDS.get(token)
            if count is None or count < 1 or count > 99:
                continue
            nearby = normalized_terms(" ".join(raw_tokens[index + 1:index + 5]))
            if any(
                _same_product_form(requested_head, term)
                for requested_head in requested_heads for term in nearby
            ):
                return count
    return 1
