from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, func
from sqlalchemy.orm import Mapped, mapped_column


class DisplayIdMixin:
    """Readable sequential identifier for administration and support tools.

    ``id`` remains the UUID primary key used by application APIs and foreign
    keys. ``display_id`` is safe to show in DBeaver and future back-office
    screens without changing those relationships.
    """

    display_id: Mapped[int | None] = mapped_column(
        BigInteger,
        Identity(start=1),
        unique=True,
        index=True,
        nullable=True,
    )


class TimestampMixin(DisplayIdMixin):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
