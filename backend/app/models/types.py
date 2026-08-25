import enum

from sqlalchemy import JSON, Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB


JSON_DATA = JSON().with_variant(JSONB(), "postgresql")


def enum_column(enum_class: type[enum.Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
