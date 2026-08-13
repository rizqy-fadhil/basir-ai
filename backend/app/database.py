"""Database engine, session factory, and declarative base for Basir AI."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# psycopg v3 driver requires the +psycopg dialect suffix.
# Fall back to a local dev URL if DATABASE_URL is not set.
_raw_url: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://basirai:basirai-local-only@localhost:5432/basirai",
)

# Ensure the psycopg v3 dialect is specified.
# Accept both bare "postgresql://" (from older configs) and the explicit form.
if _raw_url.startswith("postgresql://") and "+psycopg" not in _raw_url:
    DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = _raw_url

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db():
    """FastAPI dependency that yields a database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
