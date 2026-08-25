from __future__ import annotations

from pydantic import BaseModel, Field


class BundleItemPlan(BaseModel):
    query: str = Field(min_length=1, max_length=160)
    quantity: int = Field(default=1, ge=1, le=99)


class MissionInterpretation(BaseModel):
    mission_type: str = Field(min_length=1, max_length=80)
    goal: str = Field(min_length=1, max_length=300)
    catalog_query: str | None = Field(default=None, min_length=1, max_length=160)
    catalog_queries: list[str] = Field(default_factory=list, max_length=4)
    requested_actions: list[str] = Field(default_factory=list, max_length=7)
    bundle_items: list[BundleItemPlan] = Field(default_factory=list, max_length=20)
    budget: float | None = Field(default=None, ge=0)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    owned_items: list[str] = Field(default_factory=list, max_length=30)
    priorities: list[str] = Field(default_factory=list, max_length=10)


class NeedPlan(BaseModel):
    required_categories: list[str] = Field(default_factory=list, max_length=20)
    optional_categories: list[str] = Field(default_factory=list, max_length=20)
