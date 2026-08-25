from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .mixins import TimestampMixin
from .types import JSON_DATA


class Wallet(TimestampMixin, Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_nonnegative"),
        CheckConstraint("daily_limit >= 0 AND monthly_limit >= 0", name="limits_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("3000"))
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("12000"))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)

    user: Mapped["User"] = relationship("User", back_populates="wallet")
    transactions: Mapped[list["WalletTransaction"]] = relationship("WalletTransaction", back_populates="wallet")
