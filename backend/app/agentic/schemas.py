from __future__ import annotations

from pydantic import BaseModel, Field


class BundleItemPlan(BaseModel):
    query: str = Field(min_length=1, max_length=160)
    quantity: int = Field(default=1, ge=1, le=99)


class FulfillmentRequirement(BaseModel):
    """A user-stated need that can be tested against verified catalog facts."""

    # Planning requests may use domains beyond the product catalog (for
    # example room, task, or style). The auditor only enforces known shopping
    # kinds; unknown kinds remain planning context rather than invalid input.
    kind: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=160)
    field: str | None = Field(default=None, max_length=120)
    quantity: int = Field(default=1, ge=1, le=99)


class MissionInterpretation(BaseModel):
    mission_type: str = Field(min_length=1, max_length=80)
    goal: str = Field(min_length=1, max_length=300)
    requires_planning: bool = False
    requires_catalog: bool = False
    catalog_query: str | None = Field(default=None, min_length=1, max_length=160)
    catalog_queries: list[str] = Field(default_factory=list, max_length=4)
    requested_actions: list[str] = Field(default_factory=list, max_length=7)
    bundle_items: list[BundleItemPlan] = Field(default_factory=list, max_length=20)
    budget: float | None = Field(default=None, ge=0)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    owned_items: list[str] = Field(default_factory=list, max_length=30)
    priorities: list[str] = Field(default_factory=list, max_length=10)
    fulfillment_requirements: list[FulfillmentRequirement] = Field(default_factory=list, max_length=30)


class NeedPlan(BaseModel):
    required_categories: list[str] = Field(default_factory=list, max_length=20)
    optional_categories: list[str] = Field(default_factory=list, max_length=20)
