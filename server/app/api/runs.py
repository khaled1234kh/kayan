"""Workflow run read endpoints.

A run is either a commanded order or an experimental trial; the query parameters
say which. Trials of a comparison are also reachable through
``/api/experiments/{experiment_id}``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, not_found
from app.runtime import experiments as exp
from app.services import get_run_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", summary="List workflow runs")
def list_runs(
    session: DbSession,
    experiment_id: str | None = None,
    condition: str | None = None,
    order_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    runs = get_run_service(session).list_runs(
        experiment_id=experiment_id,
        condition=condition,
        order_id=order_id,
        limit=limit,
        offset=offset,
    )
    return [exp.run_to_dict(run) for run in runs]


@router.get("/{run_id}", summary="Get one workflow run")
def get_run(run_id: str, session: DbSession) -> dict:
    run = get_run_service(session).get_run(run_id)
    if run is None:
        raise not_found("WorkflowRun", run_id)
    return exp.run_to_dict(run)


@router.get("/workflow/orders/{order_id}", summary="Runs for one order")
def list_workflow_runs(order_id: str, session: DbSession) -> list[dict]:
    runs = get_run_service(session).list_runs(order_id=order_id)
    return [exp.run_to_dict(run) for run in runs]