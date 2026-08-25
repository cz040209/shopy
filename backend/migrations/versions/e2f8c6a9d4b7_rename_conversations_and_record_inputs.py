"""rename conversations and retain multimodal input audit data

Revision ID: e2f8c6a9d4b7
Revises: d9e4f0a7b8c1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e2f8c6a9d4b7"
down_revision: Union[str, None] = "d9e4f0a7b8c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_DATA = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.rename_table("ai_conversations", "conversations")
    op.drop_index("ix_ai_conversations_user_updated", table_name="conversations")
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"], unique=False)

    op.add_column("ai_messages", sa.Column("input_type", sa.String(length=24), nullable=True))
    op.add_column("ai_messages", sa.Column("input_payload", JSON_DATA, nullable=False, server_default=sa.text("'{}'")))
    op.add_column("ai_messages", sa.Column("processing_metadata", JSON_DATA, nullable=False, server_default=sa.text("'{}'")))
    op.create_index(op.f("ix_ai_messages_input_type"), "ai_messages", ["input_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_messages_input_type"), table_name="ai_messages")
    op.drop_column("ai_messages", "processing_metadata")
    op.drop_column("ai_messages", "input_payload")
    op.drop_column("ai_messages", "input_type")
    op.drop_index("ix_conversations_user_updated", table_name="conversations")
    op.create_index("ix_ai_conversations_user_updated", "conversations", ["user_id", "updated_at"], unique=False)
    op.rename_table("conversations", "ai_conversations")
