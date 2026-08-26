"""add provider-reported token usage to orchestration logs

Revision ID: a1c7e9f3b2d4
Revises: f3a7b2c8e5d1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c7e9f3b2d4"
down_revision: Union[str, None] = "f3a7b2c8e5d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orchestration_runs", sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("orchestration_runs", sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("orchestration_runs", sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("orchestration_run_events", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("orchestration_run_events", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("orchestration_run_events", sa.Column("total_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orchestration_run_events", "total_tokens")
    op.drop_column("orchestration_run_events", "output_tokens")
    op.drop_column("orchestration_run_events", "input_tokens")
    op.drop_column("orchestration_runs", "total_tokens")
    op.drop_column("orchestration_runs", "output_tokens")
    op.drop_column("orchestration_runs", "input_tokens")
