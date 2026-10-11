"""Application configuration.

Credentials never live in code: everything is read from the environment
(``.env`` for local development). ``DATABASE_URL`` is the single source of the
connection string.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _ensure_postgres_bin_on_path() -> None:
    """Make libpq discoverable when the driver cannot ship its own.

    On locked-down Windows hosts an application-control policy can block the
    compiled extensions inside the ``psycopg`` wheel. psycopg then falls back to
    its pure-Python implementation, which still needs libpq on the DLL search
    path. The ``pgserver`` wheel already vendors PostgreSQL binaries, so point at
    those rather than making every developer set PATH by hand.

    Best-effort and idempotent: a failure here is not fatal, since a system-wide
    libpq installation is equally valid.
    """
    if any("pgserver" in p for p in os.environ.get("PATH", "").split(os.pathsep)):
        return
    try:
        import pgserver

        bin_dir = next(pathlib.Path(pgserver.__file__).parent.glob("pginstall*")) / "bin"
    except Exception:  # pragma: no cover - pgserver is optional
        return
    if not bin_dir.exists():
        return
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    logger.debug("added bundled PostgreSQL binaries to PATH: %s", bin_dir)


_ensure_postgres_bin_on_path()


class Settings(BaseSettings):
    """Runtime settings, sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "server/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="KAYAN", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # SQLAlchemy URL. Defaults to a local SQLite file so the test suite and a
    # first `uvicorn` run work with no setup; production/dev should set
    # DATABASE_URL to a real PostgreSQL instance.
    database_url: str = Field(
        default="sqlite:///./kayan_dev.db",
        alias="DATABASE_URL",
    )

    api_default_limit: int = Field(default=100, alias="API_DEFAULT_LIMIT")
    api_max_limit: int = Field(default=500, alias="API_MAX_LIMIT")

    #: Development-only event injection, used to prove the WebSocket bridge.
    #: Never honoured when ``app_env`` is ``production``.
    enable_dev_endpoints: bool = Field(default=False, alias="ENABLE_DEV_ENDPOINTS")

    #: Multiplier applied to each workflow step's authored delay when the runtime
    #: executes an order. 0 (the default) runs the workflow at full speed: pacing
    #: is a presentation concern, not business logic. Set to e.g. ``0.05`` to make
    #: a ~20s scripted order watchable.
    runtime_pace_ms: int = Field(default=0, alias="RUNTIME_PACE_MS", ge=0, le=1000)

    #: Backend experiment execution (baseline vs enforced). This is a research
    #: capability, so it is opt-in and never enabled in production.
    enable_experiments: bool = Field(default=False, alias="ENABLE_EXPERIMENTS")

    #: Which recommendation provider to use. ``template`` is the deterministic
    #: catalogue-driven provider and the only one implemented: the backend declares
    #: no inference dependency and holds no inference credentials, so ``model``
    #: resolves to the labelled template fallback rather than to a fabricated call.
    recommendation_provider: str = Field(default="template", alias="RECOMMENDATION_PROVIDER")

    #: Bounds on a recommended workforce. The maximum matches the P0.2 workforce
    #: limit so any proposal can be submitted back as a workforce.
    recommendation_max_employees: int = Field(
        default=200, alias="RECOMMENDATION_MAX_EMPLOYEES", ge=1, le=200
    )
    recommendation_default_employees: int = Field(
        default=5, alias="RECOMMENDATION_DEFAULT_EMPLOYEES", ge=1, le=200
    )
    #: Free-text preference length, mirroring the schema bound.
    recommendation_max_notes: int = Field(
        default=2000, alias="RECOMMENDATION_MAX_NOTES", ge=1, le=8000
    )

    #: Dev-only shared secret for the budget adjustment endpoint. When set, the
    #: endpoint requires the ``X-Budget-Adjustment-Token`` header to match. When
    #: empty (the default), the endpoint is open for local development. This is
    #: NOT production authentication — KAYAN has no auth in this phase.
    budget_adjustment_token: str = Field(default="", alias="BUDGET_ADJUSTMENT_TOKEN")

    @property
    def experiments_allowed(self) -> bool:
        return self.app_env.lower() != "production" and self.enable_experiments

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def dev_endpoints_allowed(self) -> bool:
        return self.app_env.lower() != "production" and self.enable_dev_endpoints


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (import-safe; no DB access here)."""
    return Settings()