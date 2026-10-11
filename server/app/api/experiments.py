"""Experiment API: status, results, run history and exports.

Read-only, plus the two export formats. Everything is derived from the persisted
trials; nothing is computed by the client and nothing is stored as an aggregate.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, not_found
from app.models import Experiment, WorkflowRun
from app.runtime import experiments as exp
from app.schemas import ExperimentOut

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentOut], summary="List comparisons")
def list_experiments(session: DbSession, limit: int = 50, offset: int = 0) -> list[ExperimentOut]:
    rows = session.execute(
        select(Experiment).order_by(Experiment.started_at.desc()).limit(limit).offset(offset)
    ).scalars()
    return [ExperimentOut.model_validate(row) for row in rows]


@router.get("/{experiment_id}", summary="One comparison with its derived results")
def get_experiment(experiment_id: str, session: DbSession) -> dict:
    """Status plus the comparison summary and every trial record.

    Polling this is how a client recovers after a page reload: the experiment's
    lifecycle is persisted, not held in the socket.
    """
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise not_found("Experiment", experiment_id)

    trials = exp.trials_for(session, experiment_id)
    return {
        "experiment": ExperimentOut.model_validate(experiment).model_dump(by_alias=True),
        "comparison": exp.build_comparison(session, experiment),
        "runs": [exp.run_to_dict(run) for run in trials],
        "progress": {
            "totalTrials": len(exp.CONDITIONS) * experiment.runs_per_condition,
            "recordedTrials": len(trials),
            "completedTrials": sum(1 for run in trials if run.completed),
            "failedTrials": sum(1 for run in trials if run.status.value == "failed"),
        },
    }


@router.get("/{experiment_id}/export.json", summary="Persisted experiment as JSON")
def export_experiment_json(experiment_id: str, session: DbSession) -> Response:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise not_found("Experiment", experiment_id)
    payload = exp.build_export(session, experiment, datetime.now(timezone.utc).isoformat())
    import json

    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{experiment_id}.json"'},
    )


@router.get("/{experiment_id}/export.csv", summary="Persisted trials as CSV")
def export_experiment_csv(experiment_id: str, session: DbSession) -> PlainTextResponse:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise not_found("Experiment", experiment_id)
    return PlainTextResponse(
        content=exp.build_csv(session, experiment),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{experiment_id}.csv"'},
    )


# -- run-scoped history, for isolated audit evidence ------------------------


@router.get(
    "/runs/{workflow_run_id}",
    summary="One workflow run (trial or commanded order) with its metrics",
)
def get_run(workflow_run_id: str, session: DbSession) -> dict:
    run = session.get(WorkflowRun, workflow_run_id)
    if run is None:
        raise not_found("WorkflowRun", workflow_run_id)
    return exp.run_to_dict(run)


@router.get(
    "/runs/{workflow_run_id}/events",
    summary="One run's persisted events, in sequence order",
)
def get_run_events(
    workflow_run_id: str,
    session: DbSession,
    stream_id: str | None = None,
) -> dict:
    """The recorded history of exactly one run.

    This is what makes a trial's evidence isolable: events are selected by their
    owning run and returned in stream order, so audit derivation for one trial can
    never mix in another. It is a read of recorded history, not a rerun.
    """
    from app.services.events import EventService

    run = session.get(WorkflowRun, workflow_run_id)
    if run is None:
        raise not_found("WorkflowRun", workflow_run_id)

    service = EventService(session)
    events = service.list_events(run_id=workflow_run_id, stream_id=stream_id, limit=5000)
    return {
        "run": exp.run_to_dict(run),
        "eventCount": len(events),
        # runId is included here because this endpoint is already run-scoped,
        # which makes the evidence's owner explicit without widening the
        # live event contract.
        "events": [
            {**EventService.to_client_event(event), "runId": event.run_id} for event in events
        ],
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Not allowed: experiments start through the command channel",
)
def create_experiment() -> None:
    """Experiments are started by ``run_comparison`` on the WebSocket.

    There is deliberately no HTTP write path: the same protocol that the client
    already uses is the only way to ask the backend for work.
    """
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Use the run_comparison command on /ws/events",
    )