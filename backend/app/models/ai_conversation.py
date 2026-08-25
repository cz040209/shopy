from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .mixins import TimestampMixin
from .types import JSON_DATA


class Conversation(TimestampMixin, Base):
    """A customer session containing text, voice, and image shopping inputs."""

    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_updated", "user_id", "updated_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    mission_id: Mapped[UUID | None] = mapped_column(ForeignKey("shopping_missions.id", ondelete="SET NULL"), index=True)
    session_token: Mapped[str | None] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(220))
    model: Mapped[str | None] = mapped_column(String(120))
    context: Mapped[dict[str, Any]] = mapped_column(JSON_DATA, default=dict)

    user: Mapped["User | None"] = relationship("User", back_populates="conversations")
    mission: Mapped["ShoppingMission | None"] = relationship("ShoppingMission", back_populates="conversations")
    messages: Mapped[list["AIMessage"]] = relationship(
        "AIMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="AIMessage.created_at"
    )


# Temporary Python-level compatibility for callers while the database table has
# the clearer public name, ``conversations``.
AIConversation = Conversation
