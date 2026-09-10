"""Redis-backed, expiring short-term memory for shopping sessions."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings


class MemoryUnavailableError(RuntimeError):
    """Redis could not serve short-term memory for this interaction."""


class RecentMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1200)


class ShoppingSessionMemory(BaseModel):
    """Bounded, non-sensitive context that expires with an inactive session."""

    version: int = 1
    summary: str = Field(default="", max_length=2400)
    recent_messages: list[RecentMessage] = Field(default_factory=list, max_length=16)
    current_mission: dict[str, Any] = Field(default_factory=dict)
    budget: float | None = None
    preferences: list[str] = Field(default_factory=list, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    owned_items: list[str] = Field(default_factory=list, max_length=30)
    viewed_product_ids: list[str] = Field(default_factory=list, max_length=30)
    selected_products: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    rejected_product_ids: list[str] = Field(default_factory=list, max_length=30)
    notified_product_ids: list[str] = Field(default_factory=list, max_length=30)
    current_bundle: dict[str, Any] | None = None
    optimization_mode: str | None = Field(default=None, max_length=80)

    def runtime_context(self) -> dict[str, Any]:
        """A deliberately small, data-only context supplied before intent."""
        return {
            "summary": self.summary,
            "recent_messages": [item.model_dump() for item in self.recent_messages],
            "current_mission": self.current_mission,
            "budget": self.budget,
            "preferences": self.preferences,
            "constraints": self.constraints,
            "owned_items": self.owned_items,
            "viewed_product_ids": self.viewed_product_ids,
            "selected_products": self.selected_products,
            "rejected_product_ids": self.rejected_product_ids,
            "notified_product_ids": self.notified_product_ids,
            "current_bundle": self.current_bundle,
            "optimization_mode": self.optimization_mode,
        }


class ShoppingMemoryStore(Protocol):
    async def load(self, session_scope: str) -> ShoppingSessionMemory | None: ...
    async def save(self, session_scope: str, memory: ShoppingSessionMemory) -> None: ...
    async def clear(self, session_scope: str) -> None: ...


class RedisShoppingMemoryStore:
    """JSON session memory with a sliding Redis TTL and opaque Redis keys."""

    namespace = "shopping:memory"

    def __init__(
        self,
        redis: Redis | None = None,
        *,
        redis_url: str = settings.redis_url,
        ttl_seconds: int = settings.shopping_memory_ttl_seconds,
        socket_timeout_seconds: float = settings.redis_socket_timeout_seconds,
    ) -> None:
        self.redis = redis or Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=socket_timeout_seconds,
            socket_timeout=socket_timeout_seconds,
        )
        self.ttl_seconds = max(1, ttl_seconds)

    def key_for(self, session_scope: str) -> str:
        if not session_scope.strip():
            raise ValueError("A memory session scope is required.")
        digest = hashlib.sha256(session_scope.encode("utf-8")).hexdigest()
        return f"{self.namespace}:{digest}"

    async def load(self, session_scope: str) -> ShoppingSessionMemory | None:
        key = self.key_for(session_scope)
        try:
            payload = await self.redis.get(key)
            if payload is None:
                return None
            memory = ShoppingSessionMemory.model_validate_json(payload)
            # Every successful interaction extends the inactivity window.
            await self.redis.expire(key, self.ttl_seconds)
            return memory
        except (RedisError, ValidationError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise MemoryUnavailableError("Shopping memory could not be loaded.") from error

    async def save(self, session_scope: str, memory: ShoppingSessionMemory) -> None:
        try:
            await self.redis.set(self.key_for(session_scope), memory.model_dump_json(), ex=self.ttl_seconds)
        except RedisError as error:
            raise MemoryUnavailableError("Shopping memory could not be saved.") from error

    async def clear(self, session_scope: str) -> None:
        try:
            await self.redis.delete(self.key_for(session_scope))
        except RedisError as error:
            raise MemoryUnavailableError("Shopping memory could not be cleared.") from error


_memory_store: RedisShoppingMemoryStore | None = None


def get_shopping_memory_store() -> RedisShoppingMemoryStore:
    """Reuse a Redis client connection; session data itself never lives locally."""
    global _memory_store
    if _memory_store is None:
        _memory_store = RedisShoppingMemoryStore()
    return _memory_store


def build_memory_scope(*, user_id: object | None, auth_session_token: str | None, conversation_token: str) -> str:
    """Keep authenticated sessions separate from anonymous conversation scopes."""
    if user_id is not None and auth_session_token:
        token_digest = hashlib.sha256(auth_session_token.encode("utf-8")).hexdigest()
        return f"user:{user_id}:session:{token_digest}"
    return f"conversation:{conversation_token}"


def _unique_strings(values: object, *, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _normalized_terms(value: object) -> set[str]:
    """Compare runtime-generated role text without embedding a taxonomy."""
    return {
        term for term in "".join(
            character if character.isalnum() else " "
            for character in str(value).casefold()
        ).split()
        if term
    }


def _normalized_words(value: object) -> list[str]:
    return [
        term for term in "".join(
            character if character.isalnum() else " "
            for character in str(value).casefold()
        ).split()
        if term
    ]


def _basic_role(requirement: Mapping[str, Any]) -> str:
    """Find the stable base role shared by the LLM's search variants."""
    canonical = str(requirement.get("canonical_role", "")).strip()
    raw_queries = requirement.get("search_queries", [])
    queries = [
        str(query).strip() for query in raw_queries
        if str(query).strip()
    ] if isinstance(raw_queries, list) else []
    query_terms = [_normalized_terms(query) for query in queries]
    query_terms = [terms for terms in query_terms if terms]
    if len(query_terms) < 2:
        return canonical
    shared_terms = set.intersection(*query_terms)
    shared_canonical_words = [
        word for word in _normalized_words(canonical) if word in shared_terms
    ]
    return " ".join(shared_canonical_words) or canonical


def _selected_products_with_roles(
    selected: list[dict[str, Any]], state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Persist the accepted selector role as its AI-generated base role.

    Intent already separates a broad canonical role from modifiers and emits
    dynamic search variants. This function only reconciles the selector's role
    to that runtime contract; it contains no product or category vocabulary.
    """
    reasoning_by_id = {
        str(item.get("product_id")): item
        for item in state.get("selection_reasoning", [])
        if isinstance(item, dict) and item.get("product_id")
    }
    requirements = [
        item for item in state.get("search_requirements", [])
        if isinstance(item, dict) and str(item.get("canonical_role", "")).strip()
    ]
    enriched: list[dict[str, Any]] = []
    for item in selected[:12]:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        product_id = str(item["id"])
        reasoning = reasoning_by_id.get(product_id, {})
        raw_role = str(item.get("role") or reasoning.get("role") or "").strip()
        role_terms = _normalized_terms(raw_role)
        matching: list[tuple[int, dict[str, Any]]] = []
        for requirement in requirements:
            canonical = str(requirement.get("canonical_role", "")).strip()
            canonical_terms = _normalized_terms(canonical)
            evidence_values = [
                canonical,
                str(requirement.get("original_text", "")),
                *(
                    requirement.get("search_queries", [])
                    if isinstance(requirement.get("search_queries"), list) else []
                ),
            ]
            evidence_terms = [_normalized_terms(value) for value in evidence_values]
            if not role_terms or not canonical_terms:
                continue
            if role_terms == canonical_terms:
                score = 3
            elif any(role_terms == terms for terms in evidence_terms):
                score = 2
            elif canonical_terms <= role_terms or role_terms <= canonical_terms:
                score = 1
            else:
                continue
            matching.append((score, requirement))
        matching.sort(
            key=lambda value: (
                -value[0],
                len(_normalized_terms(value[1].get("canonical_role", ""))),
            )
        )
        requirement = matching[0][1] if matching else None
        base_role = _basic_role(requirement) if requirement is not None else raw_role
        role_queries = _unique_strings(
            [
                base_role,
                *(
                    requirement.get("search_queries", [])
                    if requirement is not None
                    and isinstance(requirement.get("search_queries"), list)
                    else []
                ),
            ],
            limit=6,
        )
        stored = {
            "id": product_id,
            "quantity": max(1, int(item.get("quantity", 1))),
        }
        if base_role:
            stored["role"] = base_role
        if role_queries:
            stored["search_queries"] = role_queries
        enriched.append(stored)
    return enriched


def memory_from_state(previous: ShoppingSessionMemory | None, state: Mapping[str, Any]) -> ShoppingSessionMemory:
    """Merge only structured, bounded shopping context after an audited reply."""
    prior = previous or ShoppingSessionMemory()
    request = str(state.get("user_request", "")).strip()
    response = str(state.get("final_response", "")).strip()
    recent = [*prior.recent_messages]
    if request:
        recent.append(RecentMessage(role="user", content=request[:1200]))
    if response:
        recent.append(RecentMessage(role="assistant", content=response[:1200]))
    recent_turn_limit = max(1, settings.shopping_memory_recent_turns)
    recent = recent[-recent_turn_limit:]

    mission = state.get("mission") if isinstance(state.get("mission"), dict) else prior.current_mission
    preferences = _unique_strings([*prior.preferences, *state.get("preferences", [])], limit=20)
    constraints = _unique_strings([*prior.constraints, *state.get("constraints", [])], limit=20)
    owned_items = _unique_strings([*prior.owned_items, *state.get("owned_items", [])], limit=30)
    viewed = _unique_strings(
        [*prior.viewed_product_ids, *(str(item.get("id")) for item in state.get("candidate_products", []) if isinstance(item, dict))],
        limit=30,
    )
    rejected = _unique_strings([*prior.rejected_product_ids, *state.get("excluded_product_ids", [])], limit=30)
    current_selected = (
        state.get("selected_products")
        if isinstance(state.get("selected_products"), list)
        else None
    )
    no_eligible_refinement = bool(
        state.get("continues_context")
        and isinstance(state.get("selection_context"), dict)
        and state["selection_context"].get("no_eligible_alternative") is True
    )
    # A completed "no cheaper/better alternative" response describes the
    # comparison result; it does not discard the last audited selection. Keep
    # that reference so another refinement button can still compare against it.
    selected = (
        prior.selected_products
        if no_eligible_refinement and not current_selected
        else current_selected if current_selected is not None
        else prior.selected_products
    )
    if current_selected is not None and selected is current_selected:
        selected = _selected_products_with_roles(current_selected, state)
    bundle = state.get("bundle") if isinstance(state.get("bundle"), dict) else prior.current_bundle
    budget = state.get("budget") if state.get("budget") is not None else prior.budget
    optimization_mode = state.get("optimization_mode") or prior.optimization_mode
    summary = _build_summary(mission, budget, preferences, constraints, owned_items, selected, optimization_mode)
    return ShoppingSessionMemory(
        summary=summary,
        recent_messages=recent,
        current_mission=mission,
        budget=budget,
        preferences=preferences,
        constraints=constraints,
        owned_items=owned_items,
        viewed_product_ids=viewed,
        selected_products=selected[:12] if isinstance(selected, list) else [],
        rejected_product_ids=rejected,
        notified_product_ids=prior.notified_product_ids,
        current_bundle=bundle,
        optimization_mode=str(optimization_mode)[:80] if optimization_mode else None,
    )


def _build_summary(
    mission: Mapping[str, Any], budget: object, preferences: list[str], constraints: list[str],
    owned_items: list[str], selected: object, optimization_mode: object,
) -> str:
    """Compact deterministic summary so older raw turns do not consume context."""
    parts = [f"Goal: {str(mission.get('goal', '')).strip()}" ] if mission.get("goal") else []
    if budget is not None:
        parts.append(f"Budget: {budget}")
    if preferences:
        parts.append("Preferences: " + ", ".join(preferences[:8]))
    if constraints:
        parts.append("Constraints: " + ", ".join(constraints[:8]))
    if owned_items:
        parts.append("Already owned: " + ", ".join(owned_items[:8]))
    if isinstance(selected, list) and selected:
        parts.append("Current selections: " + ", ".join(str(item.get("id")) for item in selected[:6] if isinstance(item, dict)))
    if optimization_mode:
        parts.append(f"Optimisation: {optimization_mode}")
    return "; ".join(parts)[:2400]
