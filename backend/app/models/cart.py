from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import CartStatus
from .mixins import TimestampMixin
from .types import enum_column


class Cart(TimestampMixin, Base):
    __tablename__ = "carts"
    __table_args__ = (
        Index(
            "uq_carts_active_user", "user_id", unique=True,
            postgresql_where=text("status = 'active'"), sqlite_where=text("status = 'active'"),
        ),
        Index("ix_carts_status_updated", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_token: Mapped[str | None] = mapped_column(String(128), unique=True)
    status: Mapped[CartStatus] = mapped_column(enum_column(CartStatus, "cart_status"), default=CartStatus.ACTIVE)
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped["User | None"] = relationship("User", back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    order: Mapped["Order | None"] = relationship("Order", back_populates="cart", uselist=False)
