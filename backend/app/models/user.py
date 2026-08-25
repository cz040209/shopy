from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import UserStatus
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[UserStatus] = mapped_column(
        enum_column(UserStatus, "user_status"), default=UserStatus.ACTIVE, index=True
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    addresses: Mapped[list["Address"]] = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user", cascade="all, delete-orphan")
    carts: Mapped[list["Cart"]] = relationship("Cart", back_populates="user", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
    missions: Mapped[list["ShoppingMission"]] = relationship("ShoppingMission", back_populates="user")
    conversations: Mapped[list["AIConversation"]] = relationship("AIConversation", back_populates="user")
    sellers: Mapped[list["Seller"]] = relationship("Seller", back_populates="owner")
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        "AuthSession", back_populates="user", cascade="all, delete-orphan"
    )
    wishlist_items: Mapped[list["WishlistItem"]] = relationship("WishlistItem", back_populates="user", cascade="all, delete-orphan")
    wallet: Mapped["Wallet | None"] = relationship("Wallet", back_populates="user", cascade="all, delete-orphan", uselist=False)
