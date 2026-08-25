from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import OrderStatus, PaymentStatus
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND handling_amount >= 0 AND discount_amount >= 0 AND total_amount >= 0", name="amounts_nonnegative"),
        CheckConstraint("total_amount = subtotal + tax_amount + handling_amount - discount_amount", name="total_matches_components"),
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    cart_id: Mapped[UUID | None] = mapped_column(ForeignKey("carts.id", ondelete="SET NULL"), unique=True)
    shipping_address_id: Mapped[UUID | None] = mapped_column(ForeignKey("addresses.id", ondelete="SET NULL"))
    status: Mapped[OrderStatus] = mapped_column(enum_column(OrderStatus, "order_status"), default=OrderStatus.PENDING)
    payment_status: Mapped[PaymentStatus] = mapped_column(enum_column(PaymentStatus, "payment_status"), default=PaymentStatus.PENDING)
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    handling_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_address_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_DATA)
    notes: Mapped[str | None] = mapped_column(Text)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User | None"] = relationship("User", back_populates="orders")
    cart: Mapped["Cart | None"] = relationship("Cart", back_populates="order")
    shipping_address: Mapped["Address | None"] = relationship("Address", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="order")
    wallet_transactions: Mapped[list["WalletTransaction"]] = relationship("WalletTransaction", back_populates="order")
