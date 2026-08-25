from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import PaymentMethod, PaymentStatus
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_nonnegative"),
        CheckConstraint("risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)", name="risk_score_range"),
        Index("ix_payments_order_status", "order_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(enum_column(PaymentMethod, "payment_method"))
    status: Mapped[PaymentStatus] = mapped_column(enum_column(PaymentStatus, "payment_record_status"), default=PaymentStatus.PENDING)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    provider: Mapped[str | None] = mapped_column(String(80))
    provider_reference: Mapped[str | None] = mapped_column(String(160), unique=True)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    risk_details: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped["Order"] = relationship("Order", back_populates="payments")
