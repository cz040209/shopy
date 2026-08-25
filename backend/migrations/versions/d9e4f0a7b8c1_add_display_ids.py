"""add readable sequential display IDs

Revision ID: d9e4f0a7b8c1
Revises: b7d3a9f1c4e2
Create Date: 2026-08-25 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e4f0a7b8c1"
down_revision: Union[str, None] = "b7d3a9f1c4e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = (
    "users",
    "addresses",
    "auth_sessions",
    "sellers",
    "categories",
    "products",
    "product_images",
    "reviews",
    "carts",
    "cart_items",
    "wishlist_items",
    "orders",
    "order_items",
    "payments",
    "wallets",
    "wallet_transactions",
    "shopping_missions",
    "ai_conversations",
    "ai_messages",
    "ai_recommendations",
    "orchestration_runs",
    "orchestration_run_events",
)


def upgrade() -> None:
    # UUID primary keys are intentionally retained. Each table instead gains a
    # separate identity value that begins at one and is unique per table.
    is_postgresql = op.get_bind().dialect.name == "postgresql"
    for table in TABLES:
        column = (
            sa.Column("display_id", sa.BigInteger(), sa.Identity(start=1))
            if is_postgresql
            else sa.Column("display_id", sa.BigInteger(), nullable=True)
        )
        op.add_column(
            table,
            column,
        )
        if is_postgresql:
            op.execute(sa.text(f"UPDATE {table} SET display_id = DEFAULT WHERE display_id IS NULL"))
            op.alter_column(table, "display_id", nullable=False)
        op.create_index(f"ix_{table}_display_id", table, ["display_id"], unique=True)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_display_id", table_name=table)
        op.drop_column(table, "display_id")
