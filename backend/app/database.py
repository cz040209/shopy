from collections.abc import Generator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_engine(database_url: str | None = None, **kwargs: object) -> Engine:
    url = database_url or settings.database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")

    defaults: dict[str, object] = {"pool_pre_ping": True}
    defaults.update(kwargs)
    return create_engine(url, **defaults)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def check_database_connection(database_engine: Engine | None = None) -> bool:
    target = database_engine or engine
    with target.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
