from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import MessageRole
from .types import JSON_DATA, enum_column


class AIMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[MessageRole] = mapped_column(enum_column(MessageRole, "message_role"))
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    token_count: Mapped[int | None] = mapped_column(Integer)
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_DATA, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["AIConversation"] = relationship("AIConversation", back_populates="messages")
