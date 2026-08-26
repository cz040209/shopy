from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .mixins import TimestampMixin
from .types import JSON_DATA


class OrchestrationRunEvent(TimestampMixin, Base):
    __tablename__ = "orchestration_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_orchestration_run_events_run_sequence"),
        Index("ix_orchestration_run_events_run_sequence", "run_id", "sequence"),
        Index("ix_orchestration_run_events_event_type", "event_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("orchestration_runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80))
    node_name: Mapped[str | None] = mapped_column(String(80))
    tool_name: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)

    run: Mapped["OrchestrationRun"] = relationship("OrchestrationRun", back_populates="events")
