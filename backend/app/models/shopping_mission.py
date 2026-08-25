from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import MissionMode, MissionStatus
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class ShoppingMission(TimestampMixin, Base):
    __tablename__ = "shopping_missions"
    __table_args__ = (Index("ix_missions_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    mode: Mapped[MissionMode] = mapped_column(enum_column(MissionMode, "mission_mode"))
    status: Mapped[MissionStatus] = mapped_column(enum_column(MissionStatus, "mission_status"), default=MissionStatus.DRAFT, index=True)
    title: Mapped[str | None] = mapped_column(String(220))
    prompt: Mapped[str] = mapped_column(Text)
    source_asset_url: Mapped[str | None] = mapped_column(Text)
    input_context: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User | None"] = relationship("User", back_populates="missions")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="mission")
    recommendations: Mapped[list["AIRecommendation"]] = relationship("AIRecommendation", back_populates="mission", cascade="all, delete-orphan")
