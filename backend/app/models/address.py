from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import AddressKind
from .mixins import TimestampMixin
from .types import enum_column


class Address(TimestampMixin, Base):
    __tablename__ = "addresses"
    __table_args__ = (Index("ix_addresses_user_default", "user_id", "is_default"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[AddressKind] = mapped_column(enum_column(AddressKind, "address_kind"), default=AddressKind.SHIPPING)
    label: Mapped[str | None] = mapped_column(String(80))
    recipient_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(32))
    line1: Mapped[str] = mapped_column(String(255))
    line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(120))
    postal_code: Mapped[str] = mapped_column(String(24))
    country_code: Mapped[str] = mapped_column(String(2), default="MY")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship("User", back_populates="addresses")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="shipping_address")
