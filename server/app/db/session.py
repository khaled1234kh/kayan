"""Declarative base and engine/session management.

There is exactly one engine per process and one session factory. Application code
never builds its own engines and never writes ad-hoc SQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _engine_kwargs(url: str) -> dict[str, Any]:
    """Engine options appropriate to the dialect."""
    if url.startswith("sqlite"):
        # Foreign keys are off by default in SQLite; enable them so relationship
        # behaviour matches PostgreSQL.
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Process-wide engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            future=True,
            **_engine_kwargs(settings.database_url),
        )
        if settings.database_url.startswith("sqlite"):
            # SQLite ignores foreign keys unless asked. Tests run on SQLite, and
            # without this a bogus run_id would silently insert instead of
            # failing the way PostgreSQL does.
            @event.listens_for(_engine, "connect")
            def _enable_foreign_keys(dbapi_connection, _record):  # pragma: no cover - hook
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Process-wide session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _session_factory


def new_session() -> Session:
    """Open a single session.

    ``get_session_factory()`` returns the factory itself, so this is the
    unambiguous "give me a session" helper and the one callers should pass when
    they need a zero-argument session callable.
    """
    return get_session_factory()()


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session.

    Rolls back on error; the caller decides when to commit.
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose the engine (used by tests that swap the database URL)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def create_all() -> None:
    """Create tables for the configured database.

    Alembic owns real migrations; this is the fast path for local development
    and tests.
    """
    from app import models  # noqa: F401  (ensure models are imported)

    Base.metadata.create_all(bind=get_engine())