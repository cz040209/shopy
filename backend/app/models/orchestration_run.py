from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .mixins import TimestampMixin
from .types import JSON_DATA


class OrchestrationRun(TimestampMixin, Base):
    __tablename__ = "orchestration_runs"
    __table_args__ = (
        Index("ix_orchestration_runs_user_created", "user_id", "created_at"),
        Index("ix_orchestration_runs_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    mission_id: Mapped[UUID | None] = mapped_column(ForeignKey("shopping_missions.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    user_request: Mapped[str] = mapped_column(Text)
    initial_state: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    final_state: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    final_response: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User | None"] = relationship("User", back_populates="orchestration_runs")
    events: Mapped[list["OrchestrationRunEvent"]] = relationship(
        "OrchestrationRunEvent", back_populates="run", cascade="all, delete-orphan", order_by="OrchestrationRunEvent.sequence"
    )
