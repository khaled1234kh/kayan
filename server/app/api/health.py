"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Return service liveness.

    Intentionally does not touch the database: this answers "is the process up".
    Database reachability is covered by ``GET /api/health/db``.
    """
    return HealthResponse(status="ok")