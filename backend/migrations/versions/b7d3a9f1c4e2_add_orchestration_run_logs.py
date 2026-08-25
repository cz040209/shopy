"""add database-backed agent orchestration run logs

Revision ID: b7d3a9f1c4e2
Revises: 8f2d4a91b6c3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7d3a9f1c4e2"
down_revision: Union[str, None] = "8f2d4a91b6c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON_DATA = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "orchestration_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("mission_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("user_request", sa.Text(), nullable=False),
        sa.Column("initial_state", JSON_DATA, nullable=False),
        sa.Column("final_state", JSON_DATA, nullable=False),
        sa.Column("final_response", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["shopping_missions.id"], name=op.f("fk_orchestration_runs_mission_id_shopping_missions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_orchestration_runs_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orchestration_runs")),
    )
    op.create_index(op.f("ix_orchestration_runs_request_id"), "orchestration_runs", ["request_id"], unique=True)
    op.create_index(op.f("ix_orchestration_runs_user_id"), "orchestration_runs", ["user_id"], unique=False)
    op.create_index(op.f("ix_orchestration_runs_mission_id"), "orchestration_runs", ["mission_id"], unique=False)
    op.create_index(op.f("ix_orchestration_runs_status"), "orchestration_runs", ["status"], unique=False)
    op.create_index("ix_orchestration_runs_user_created", "orchestration_runs", ["user_id", "created_at"], unique=False)
    op.create_index("ix_orchestration_runs_status_created", "orchestration_runs", ["status", "created_at"], unique=False)
    op.create_table(
        "orchestration_run_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("node_name", sa.String(length=80), nullable=True),
        sa.Column("tool_name", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_data", JSON_DATA, nullable=False),
        sa.Column("output_data", JSON_DATA, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["orchestration_runs.id"], name=op.f("fk_orchestration_run_events_run_id_orchestration_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orchestration_run_events")),
        sa.UniqueConstraint("run_id", "sequence", name="uq_orchestration_run_events_run_sequence"),
    )
    op.create_index(op.f("ix_orchestration_run_events_run_id"), "orchestration_run_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_orchestration_run_events_event_type"), "orchestration_run_events", ["event_type"], unique=False)
    op.create_index("ix_orchestration_run_events_run_sequence", "orchestration_run_events", ["run_id", "sequence"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orchestration_run_events_run_sequence", table_name="orchestration_run_events")
    op.drop_index(op.f("ix_orchestration_run_events_event_type"), table_name="orchestration_run_events")
    op.drop_index(op.f("ix_orchestration_run_events_run_id"), table_name="orchestration_run_events")
    op.drop_table("orchestration_run_events")
    op.drop_index("ix_orchestration_runs_status_created", table_name="orchestration_runs")
    op.drop_index("ix_orchestration_runs_user_created", table_name="orchestration_runs")
    op.drop_index(op.f("ix_orchestration_runs_status"), table_name="orchestration_runs")
    op.drop_index(op.f("ix_orchestration_runs_mission_id"), table_name="orchestration_runs")
    op.drop_index(op.f("ix_orchestration_runs_user_id"), table_name="orchestration_runs")
    op.drop_index(op.f("ix_orchestration_runs_request_id"), table_name="orchestration_runs")
    op.drop_table("orchestration_runs")
