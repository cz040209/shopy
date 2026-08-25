from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .mixins import TimestampMixin


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        UniqueConstraint("user_id", "product_id", name="uq_reviews_user_product"),
        Index("ix_reviews_product_created", "product_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("order_items.id", ondelete="SET NULL"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(180))
    body: Mapped[str | None] = mapped_column(Text)
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    product: Mapped["Product"] = relationship("Product", back_populates="reviews")
    order_item: Mapped["OrderItem | None"] = relationship("OrderItem", back_populates="review")
