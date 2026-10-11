"""FastAPI application entrypoint.

Startup path:
1. load settings from the environment
2. open the engine
3. create tables (Alembic owns real migrations; this is the dev fast path)
4. seed the canonical agents if absent
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import text

from app.api import api_router
from app.api import ws as ws_api
from app.core.config import get_settings
from app.db.seed import seed_agents
from app.db.seed_roles import seed_role_templates
from app.db.session import create_all, get_engine, get_session_factory
from app.runtime.commands import drain_active_runs

logging.basicConfig(
    level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("kayan")


def check_database_connection() -> bool:
    """Round-trip a trivial query. Used by startup and the health/db probe."""
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("KAYAN backend starting (env=%s)", settings.app_env)
    create_all()
    session = get_session_factory()()
    try:
        inserted = seed_agents(session)
        if inserted:
            logger.info("seeded %d agent(s)", inserted)
        # The role catalogue is seed/configuration data that P0.4 contract
        # generation reads, so it must exist before the first request.
        seed_role_templates(session)
    finally:
        session.close()
    logger.info("database ready: %s", _safe_dsn(settings.database_url))
    yield
    # Let a commanded workflow finish rather than being cut off mid-run.
    await drain_active_runs()
    logger.info("KAYAN backend shutting down")


def _safe_dsn(url: str) -> str:
    """Hide credentials before logging a DSN."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://***@{rest.rsplit('@', 1)[1]}"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="KAYAN Backend",
        description=(
            "Authoritative store for KAYAN agents, tasks, messages, handoffs, "
            "events, policy decisions and experiment runs."
        ),
        version="0.7.0",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    # The event bridge sits at the root path (/ws/events), not under /api.
    app.include_router(ws_api.router)

    if settings.dev_endpoints_allowed:
        # Development only: never mounted when APP_ENV=production.
        from app.api import dev as dev_api

        app.include_router(dev_api.router)
        logger.info("development endpoints enabled (/api/dev/*)")

    @app.get("/api/health/db", tags=["health"], summary="Database connectivity probe")
    def health_db() -> dict[str, object]:
        """Prove the configured database is reachable and name the dialect."""
        try:
            check_database_connection()
        except Exception as exc:  # pragma: no cover - surfaced as 503
            return {"status": "error", "detail": type(exc).__name__}
        return {
            "status": "ok",
            "dialect": get_engine().dialect.name,
            "serverVersion": _server_version(),
        }

    return app


def _server_version() -> str | None:
    try:
        with get_engine().connect() as conn:
            return str(conn.execute(text("SELECT version()")).scalar_one())[:64]
    except Exception:  # pragma: no cover - non-PostgreSQL dialects
        return None


app = create_app()