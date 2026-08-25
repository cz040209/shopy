from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import SellerStatus
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class Seller(TimestampMixin, Base):
    __tablename__ = "sellers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SellerStatus] = mapped_column(
        enum_column(SellerStatus, "seller_status"), default=SellerStatus.PENDING, index=True
    )
    rating_average: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0"))
    settings: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="seller")
    owner: Mapped["User | None"] = relationship("User", back_populates="sellers")
    order_items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="seller")
