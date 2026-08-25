from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import ProductBadge, ProductStatus
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_nonnegative"),
        CheckConstraint("compare_at_price IS NULL OR compare_at_price >= price", name="compare_price_valid"),
        CheckConstraint("inventory_quantity >= 0", name="inventory_nonnegative"),
        CheckConstraint("reserved_quantity >= 0 AND reserved_quantity <= inventory_quantity", name="reserved_inventory_valid"),
        Index("ix_products_catalog", "status", "category_id", "seller_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    seller_id: Mapped[UUID] = mapped_column(ForeignKey("sellers.id", ondelete="RESTRICT"), index=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    sku: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    brand: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    status: Mapped[ProductStatus] = mapped_column(
        enum_column(ProductStatus, "product_status"), default=ProductStatus.DRAFT, index=True
    )
    badge: Mapped[ProductBadge | None] = mapped_column(enum_column(ProductBadge, "product_badge"))
    inventory_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    emoji: Mapped[str | None] = mapped_column(String(16))
    specs: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DATA, default=list)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    rating_average: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0"))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    seller: Mapped["Seller"] = relationship("Seller", back_populates="products")
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="product", cascade="all, delete-orphan")
    cart_items: Mapped[list["CartItem"]] = relationship("CartItem", back_populates="product")
    order_items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="product")
    recommendations: Mapped[list["AIRecommendation"]] = relationship("AIRecommendation", back_populates="product")
    wishlist_items: Mapped[list["WishlistItem"]] = relationship("WishlistItem", back_populates="product", cascade="all, delete-orphan")
