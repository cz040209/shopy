from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import Base, build_engine, check_database_connection


EXPECTED_TABLES = {
    "addresses",
    "conversations",
    "ai_messages",
    "ai_recommendations",
    "auth_sessions",
    "cart_items",
    "carts",
    "categories",
    "order_items",
    "orders",
    "orchestration_run_events",
    "orchestration_runs",
    "payments",
    "product_images",
    "products",
    "reviews",
    "sellers",
    "shopping_missions",
    "users",
    "wallet_transactions",
    "wallets",
    "wishlist_items",
}


def test_database_connectivity(db_engine):
    assert check_database_connection(db_engine) is True


def test_metadata_contains_expected_tables():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_initial_migration_upgrades_and_downgrades(tmp_path):
    database_path = tmp_path / "migration.sqlite3"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")

    command.upgrade(config, "head")
    engine = build_engine(f"sqlite+pysqlite:///{database_path}")
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES | {"alembic_version"}

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
