"""API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    agents,
    budget,
    collaboration,
    companies,
    contracts,
    events,
    experiments,
    health,
    runs,
    setup,
    tasks,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(agents.router)
api_router.include_router(tasks.router)
api_router.include_router(collaboration.router)
api_router.include_router(events.router)
api_router.include_router(runs.router)
api_router.include_router(experiments.router)
api_router.include_router(setup.router)
api_router.include_router(budget.router)
api_router.include_router(contracts.router)
api_router.include_router(companies.router)

__all__ = ["api_router"]