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
    selected = state.get("selected_products") if isinstance(state.get("selected_products"), list) else prior.selected_products
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
