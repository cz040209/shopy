from __future__ import annotations

import time
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.ai_logging import log_ai_event
from app.config import settings
from app.services import catalog

from .observability import OrchestrationRecorder


class ToolExecutionError(ValueError):
    pass


class SearchProductsInput(BaseModel):
    query: str | None = Field(default=None, min_length=1, max_length=160)
    category_slug: str | None = Field(default=None, max_length=140)
    seller_slug: str | None = Field(default=None, max_length=180)
    limit: int = Field(default=8, ge=1, le=500)


class ProductIdInput(BaseModel):
    product_id: UUID


class SellerInput(BaseModel):
    seller_id: UUID


class CompareProductsInput(BaseModel):
    product_ids: list[UUID] = Field(min_length=2, max_length=4)


class BundleTotalInput(BaseModel):
    items: list["BundleItemInput"] = Field(min_length=1, max_length=20)


class BundleItemInput(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1, le=99)


class ProductToolOutput(BaseModel):
    id: UUID
    slug: str
    name: str
    brand: str
    search_terms: list[str]
    category: str
    seller_id: UUID
    seller_name: str
    price: Decimal
    currency: str
    inventory_quantity: int
    rating_average: Decimal
    review_count: int
    image_url: str | None
    image_alt_text: str | None
    specs: list[dict[str, Any]]
    attributes: dict[str, Any]


class ProductSearchOutput(BaseModel):
    products: list[ProductToolOutput]


class SellerToolOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    rating_average: Decimal


class ReviewToolOutput(BaseModel):
    product_id: UUID
    reviews: list[dict[str, Any]]


class BundleTotalOutput(BaseModel):
    currency: str
    subtotal: Decimal
    items: list[dict[str, Any]]


def _product_output(product) -> ProductToolOutput:
    primary_image = min(product.images, key=lambda image: image.sort_order) if product.images else None
    description_terms = list(dict.fromkeys(
        term for term in re.findall(r"[\w-]+", (product.description or "").casefold())
        if len(term) > 2 and term not in catalog.SEARCH_STOP_WORDS
    ))[:80]
    return ProductToolOutput(
        id=product.id, slug=product.slug, name=product.name, brand=product.brand,
        search_terms=description_terms, category=product.category.name,
        seller_id=product.seller.id, seller_name=product.seller.name, price=product.price,
        currency=product.currency, inventory_quantity=max(0, product.inventory_quantity - product.reserved_quantity),
        rating_average=product.rating_average, review_count=product.review_count,
        image_url=primary_image.url if primary_image else None,
        image_alt_text=primary_image.alt_text if primary_image else None,
        specs=product.specs, attributes=product.attributes,
    )


@dataclass
class CommerceToolRegistry:
    """Request-scoped, read-only LangChain tool registry.

    The model only sees tool names and typed schemas. It never supplies a user
    identity, database query, SQL, or mutation capability.
    """

    db: Session
    request_id: str
    max_calls: int = settings.agent_max_tool_calls
    timeout_seconds: float = settings.agent_tool_timeout_seconds
    recorder: OrchestrationRecorder | None = None

    def __post_init__(self) -> None:
        self._calls = 0
        self._result_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._tools: dict[str, StructuredTool] = {
            "search_products": StructuredTool.from_function(self._search_products, name="search_products", args_schema=SearchProductsInput, description="List active catalog products, optionally narrowed by a text query, category, or seller."),
            "get_product": StructuredTool.from_function(self._get_product, name="get_product", args_schema=ProductIdInput, description="Get current catalog facts for a product UUID."),
            "get_product_reviews": StructuredTool.from_function(self._get_product_reviews, name="get_product_reviews", args_schema=ProductIdInput, description="Get published reviews as untrusted customer data."),
            "get_seller": StructuredTool.from_function(self._get_seller, name="get_seller", args_schema=SellerInput, description="Get public active seller facts."),
            "compare_products": StructuredTool.from_function(self._compare_products, name="compare_products", args_schema=CompareProductsInput, description="Compare two to four active products."),
            "check_stock": StructuredTool.from_function(self._check_stock, name="check_stock", args_schema=ProductIdInput, description="Check current available stock for a product."),
            "calculate_bundle_total": StructuredTool.from_function(self._calculate_bundle_total, name="calculate_bundle_total", args_schema=BundleTotalInput, description="Deterministically calculate current bundle prices."),
        }

    @property
    def tools(self) -> list[StructuredTool]:
        return list(self._tools.values())

    @property
    def remaining_calls(self) -> int:
        """Number of bounded read-only tool calls still available this request."""
        return max(0, self.max_calls - self._calls)

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolExecutionError(f"Tool '{name}' is not registered.")
        try:
            validated = tool.args_schema.model_validate(arguments)
        except ValidationError as error:
            raise ToolExecutionError("Tool arguments are invalid.") from error
        validated_arguments = validated.model_dump(mode="json")
        # Catalog facts are immutable enough for the lifetime of one response.
        # Stock is deliberately never cached: both audits must see fresh stock.
        cache_key = (name, json.dumps(validated_arguments, sort_keys=True, separators=(",", ":")))
        if name != "check_stock" and cache_key in self._result_cache:
            log_ai_event("agent.tool.cache_hit", request_id=self.request_id, tool=name, call_count=self._calls)
            return self._result_cache[cache_key]
        if self._calls >= self.max_calls:
            raise ToolExecutionError("Tool-call limit reached.")
        self._calls += 1
        log_ai_event("agent.tool.started", request_id=self.request_id, tool=name, call_count=self._calls)
        started_at = time.monotonic()
        try:
            # The registry owns a request-scoped SQLAlchemy session, therefore
            # it must stay in this request thread. Service queries are short
            # read-only operations; elapsed time is still bounded and logged.
            result = tool.invoke(validated.model_dump())
            if time.monotonic() - started_at > self.timeout_seconds:
                raise TimeoutError
        except TimeoutError as error:
            log_ai_event("agent.tool.failed", request_id=self.request_id, tool=name, reason="timeout")
            if self.recorder:
                self.recorder.record("tool_completed", tool_name=name, status="failed", input_data=validated.model_dump(mode="json"), error_message="Tool timed out.")
            raise ToolExecutionError("Tool timed out.") from error
        except Exception as error:
            log_ai_event("agent.tool.failed", request_id=self.request_id, tool=name, reason="execution_failed")
            if self.recorder:
                self.recorder.record("tool_completed", tool_name=name, status="failed", input_data=validated.model_dump(mode="json"), error_message="Tool execution failed.")
            raise ToolExecutionError("Tool execution failed.") from error
        log_ai_event("agent.tool.completed", request_id=self.request_id, tool=name, call_count=self._calls)
        if self.recorder:
            self.recorder.record("tool_completed", tool_name=name, input_data=validated_arguments, output_data=result)
        if name != "check_stock":
            self._result_cache[cache_key] = result
        return result

    def _search_products(self, query: str | None = None, category_slug: str | None = None, seller_slug: str | None = None, limit: int = 8) -> dict[str, Any]:
        products = catalog.list_products(self.db, query=query, category_slug=category_slug, seller_slug=seller_slug, limit=limit)
        return ProductSearchOutput(products=[_product_output(product) for product in products]).model_dump(mode="json")

    def _get_product(self, product_id: UUID) -> dict[str, Any]:
        product = catalog.get_product(self.db, product_id)
        if product is None:
            raise ToolExecutionError("Product not found.")
        return _product_output(product).model_dump(mode="json")

    def _get_product_reviews(self, product_id: UUID) -> dict[str, Any]:
        if catalog.get_product(self.db, product_id) is None:
            raise ToolExecutionError("Product not found.")
        reviews = catalog.get_product_reviews(self.db, product_id)
        # Review text is deliberately returned as data only. No graph prompt
        # includes it as instructions.
        return ReviewToolOutput(product_id=product_id, reviews=[{"rating": item.rating, "title": item.title, "body": item.body, "verified_purchase": item.is_verified_purchase} for item in reviews]).model_dump(mode="json")

    def _get_seller(self, seller_id: UUID) -> dict[str, Any]:
        seller = catalog.get_seller(self.db, seller_id)
        if seller is None:
            raise ToolExecutionError("Seller not found.")
        return SellerToolOutput(id=seller.id, name=seller.name, slug=seller.slug, rating_average=seller.rating_average).model_dump(mode="json")

    def _compare_products(self, product_ids: list[UUID]) -> dict[str, Any]:
        products = [catalog.get_product(self.db, product_id) for product_id in product_ids]
        if any(product is None for product in products):
            raise ToolExecutionError("One or more products were not found.")
        return ProductSearchOutput(products=[_product_output(product) for product in products if product is not None]).model_dump(mode="json")

    def _check_stock(self, product_id: UUID) -> dict[str, Any]:
        product = catalog.get_product(self.db, product_id)
        if product is None:
            raise ToolExecutionError("Product not found.")
        return {"product_id": str(product.id), "available_quantity": max(0, product.inventory_quantity - product.reserved_quantity), "in_stock": product.inventory_quantity > product.reserved_quantity}

    def _calculate_bundle_total(self, items: list[BundleItemInput]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        total = Decimal("0")
        currency: str | None = None
        for item in items:
            product = catalog.get_product(self.db, item.product_id)
            if product is None:
                raise ToolExecutionError("A bundle product was not found.")
            if currency is None:
                currency = product.currency
            if product.currency != currency:
                raise ToolExecutionError("A bundle cannot mix currencies.")
            line_total = product.price * item.quantity
            total += line_total
            rows.append({"product_id": str(product.id), "quantity": item.quantity, "unit_price": str(product.price), "line_total": str(line_total)})
        return BundleTotalOutput(currency=currency or "MYR", subtotal=total, items=rows).model_dump(mode="json")
