from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .mixins import TimestampMixin
from .types import JSON_DATA


class OrderItem(TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="amounts_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    seller_id: Mapped[UUID | None] = mapped_column(ForeignKey("sellers.id", ondelete="SET NULL"), index=True)
    sku: Mapped[str] = mapped_column(String(80))
    product_name: Mapped[str] = mapped_column(String(220))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    product_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product | None"] = relationship("Product", back_populates="order_items")
    seller: Mapped["Seller | None"] = relationship("Seller", back_populates="order_items")
    review: Mapped["Review | None"] = relationship("Review", back_populates="order_item", uselist=False)
