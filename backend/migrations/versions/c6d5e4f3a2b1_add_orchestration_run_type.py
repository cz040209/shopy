"""add orchestration run type

Revision ID: c6d5e4f3a2b1
Revises: a1c7e9f3b2d4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6d5e4f3a2b1"
down_revision: Union[str, None] = "a1c7e9f3b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orchestration_runs",
        sa.Column("run_type", sa.String(length=40), server_default="shopping", nullable=False),
    )
    op.create_index(
        "ix_orchestration_runs_run_type_created",
        "orchestration_runs",
        ["run_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orchestration_runs_run_type_created", table_name="orchestration_runs")
    op.drop_column("orchestration_runs", "run_type")
