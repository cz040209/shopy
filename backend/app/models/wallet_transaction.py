from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import TransactionStatus, TransactionType
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class WalletTransaction(TimestampMixin, Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_wallet_transactions_wallet_created", "wallet_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    reference: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    type: Mapped[TransactionType] = mapped_column(enum_column(TransactionType, "transaction_type"))
    status: Mapped[TransactionStatus] = mapped_column(
        enum_column(TransactionStatus, "transaction_status"), default=TransactionStatus.PENDING, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    description: Mapped[str | None] = mapped_column(String(255))
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_DATA, default=dict)

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")
    order: Mapped["Order | None"] = relationship("Order", back_populates="wallet_transactions")
