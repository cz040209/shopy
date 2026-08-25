"""link orchestration runs to conversations

Revision ID: f3a7b2c8e5d1
Revises: e2f8c6a9d4b7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a7b2c8e5d1"
down_revision: Union[str, None] = "e2f8c6a9d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orchestration_runs") as batch:
        batch.add_column(sa.Column("conversation_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_orchestration_runs_conversation_id_conversations"),
            "conversations", ["conversation_id"], ["id"], ondelete="SET NULL",
        )
    op.create_index(op.f("ix_orchestration_runs_conversation_id"), "orchestration_runs", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orchestration_runs_conversation_id"), table_name="orchestration_runs")
    with op.batch_alter_table("orchestration_runs") as batch:
        batch.drop_constraint(op.f("fk_orchestration_runs_conversation_id_conversations"), type_="foreignkey")
        batch.drop_column("conversation_id")
