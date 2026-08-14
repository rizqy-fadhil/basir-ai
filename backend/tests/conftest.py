"""Shared pytest fixtures for the backend test suite.

Uses a temporary SQLite file (via pytest tmp_path) as the test database.
Each test gets its own DB file so tests are fully isolated.

The JsonbOrJson TypeDecorator falls back to JSON under SQLite so JSONB
columns work transparently.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

# ---------------------------------------------------------------------------
# Patch env vars BEFORE any app module is imported.
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["BACKEND_API_KEY"] = "test-secret-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Cafe, Meja, Snapshot, StatusMeja  # noqa: F401


# ---------------------------------------------------------------------------
# Engine / schema per test
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_url(tmp_path: Path) -> str:
    """Return a unique SQLite file URL for this test."""
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture()
def db_engine(db_url: str):
    """Create the engine, create schema, yield, teardown."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def SessionFactory(db_engine):
    """Return a sessionmaker bound to the test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture()
def db(SessionFactory) -> Generator[Session, None, None]:
    """Yield a session for use in test body (for inserting seed data)."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_url: str, db_engine) -> Generator[TestClient, None, None]:
    """TestClient whose requests open their own connection to the same DB file.

    Each HTTP request gets a fresh session from the test engine so that
    committed data from the test body is always visible — regardless of which
    thread handles the request.
    """
    RequestSessionFactory = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )

    def override_get_db():
        s = RequestSessionFactory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cafe(db: Session) -> Cafe:
    c = Cafe(id=1, nama="Test Cafe", slug="test-cafe")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def meja(db: Session, cafe: Cafe) -> Meja:
    m = Meja(cafe_id=cafe.id, nomor_meja=1, kapasitas=2)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture()
def meja_with_status(db: Session, meja: Meja) -> tuple[Meja, StatusMeja]:
    from datetime import datetime, timezone

    sm = StatusMeja(
        meja_id=meja.id,
        terisi=1,
        status="partial",
        updated_at=datetime(2026, 8, 14, 6, 0, 0, tzinfo=timezone.utc),
    )
    db.add(sm)
    db.commit()
    db.refresh(sm)
    return meja, sm
