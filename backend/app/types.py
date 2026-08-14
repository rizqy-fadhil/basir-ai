"""Custom SQLAlchemy column types used across the Basir AI backend."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator


class JsonbOrJson(TypeDecorator):
    """Stores JSON data as JSONB on PostgreSQL and as JSON on other databases.

    This allows the ORM models to be used with both PostgreSQL (production)
    and SQLite (unit tests) without changing any model code.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
