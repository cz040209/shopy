from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .mixins import TimestampMixin


class ProductImage(TimestampMixin, Base):
    __tablename__ = "product_images"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        UniqueConstraint("product_id", "sort_order", name="uq_product_images_product_sort"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship("Product", back_populates="images")
