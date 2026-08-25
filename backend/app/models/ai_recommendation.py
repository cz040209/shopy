from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from .enums import RecommendationFeedback
from .mixins import TimestampMixin
from .types import JSON_DATA, enum_column


class AIRecommendation(TimestampMixin, Base):
    __tablename__ = "ai_recommendations"
    __table_args__ = (
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="score_range"),
        CheckConstraint("rank > 0", name="rank_positive"),
        UniqueConstraint("mission_id", "rank", name="uq_recommendations_mission_rank"),
        Index("ix_recommendations_mission_score", "mission_id", "score"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    mission_id: Mapped[UUID] = mapped_column(ForeignKey("shopping_missions.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    rationale: Mapped[str] = mapped_column(Text)
    feedback: Mapped[RecommendationFeedback] = mapped_column(
        enum_column(RecommendationFeedback, "recommendation_feedback"), default=RecommendationFeedback.NONE
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_DATA, default=dict)

    mission: Mapped["ShoppingMission"] = relationship("ShoppingMission", back_populates="recommendations")
    product: Mapped["Product | None"] = relationship("Product", back_populates="recommendations")
