"""Shared test fixtures.

Tests run against a temporary SQLite file by default so the suite needs no
external service. Set ``KAYAN_TEST_DATABASE_URL`` (for example a PostgreSQL URL)
to run the same suite against real PostgreSQL.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db import session as db_session
from app.db.seed import seed_agents
from app.db.seed_roles import seed_role_templates
from app.db.session import Base
from app.main import create_app


@pytest.fixture()
def db_url() -> str:
    return os.environ.get("KAYAN_TEST_DATABASE_URL", "sqlite:///./.pytest_kayan.db")


@pytest.fixture()
def engine(db_url: str):
    """Fresh schema per test.

    PostgreSQL persists between runs (which is the point of the system), so the
    schema is dropped and recreated rather than relying on an empty database.
    """
    if db_url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
    else:
        # pool_pre_ping is a *pool* option; passing it through connect_args is
        # rejected by the psycopg driver.
        kwargs = {"pool_pre_ping": True}
    eng = create_engine(db_url, future=True, **kwargs)
    if db_url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_connection, _record):  # pragma: no cover - hook
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    db = factory()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture()
def seeded_session(session: Session) -> Session:
    """A session with the demo agents and the versioned role catalogue seeded.

    Both are seed data the application itself writes, so a test that exercises
    configuration paths should start from the same state as a running system.
    """
    seed_agents(session)
    seed_role_templates(session)
    return session


@pytest.fixture()
def client(monkeypatch, engine) -> Iterator[TestClient]:
    """TestClient wired to the temporary database.

    The app's own engine is replaced so the lifespan (create_all + seed) runs
    against the test database instead of the configured one.
    """
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr(db_session, "_engine", engine)
    monkeypatch.setattr(db_session, "_session_factory", factory)
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
    db_session.reset_engine()


@pytest.fixture()
def factory_for(engine):
    """A session factory bound to the test engine.

    Used where an assertion must observe state through a *separate* session, or
    must write something the API cannot (a lifecycle transition).
    """
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@pytest.fixture()
def configured_client(monkeypatch, engine) -> Iterator[TestClient]:
    """TestClient with the demo agents and the versioned role catalogue seeded.

    The role catalogue is seeded explicitly rather than relied upon from the app
    lifespan, so a company test does not depend on startup ordering. The lifespan
    still runs, exactly as it does in production.
    """
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr(db_session, "_engine", engine)
    monkeypatch.setattr(db_session, "_session_factory", factory)
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        session = factory()
        try:
            seed_agents(session)
            seed_role_templates(session)
        finally:
            session.close()
        yield test_client

    get_settings.cache_clear()
    db_session.reset_engine()