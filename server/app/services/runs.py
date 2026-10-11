"""Workflow run queries.

One run record serves both a commanded order and an experimental trial, so there
is a single place that reads runs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkflowRun


class RunService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_runs(
        self,
        *,
        experiment_id: str | None = None,
        condition: str | None = None,
        order_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkflowRun]:
        stmt = select(WorkflowRun).order_by(WorkflowRun.started_at, WorkflowRun.id)
        if experiment_id is not None:
            stmt = stmt.where(WorkflowRun.experiment_id == experiment_id)
        if condition is not None:
            stmt = stmt.where(WorkflowRun.condition == condition)
        if order_id is not None:
            stmt = stmt.where(WorkflowRun.order_id == order_id)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self._session.get(WorkflowRun, run_id)

    def add_run(self, run: WorkflowRun) -> WorkflowRun:
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def new_run_id(self) -> str:
        return f"run_{uuid.uuid4().hex[:12]}"

    def runs_for_experiment(self, experiment_id: str) -> list[WorkflowRun]:
        stmt = (
            select(WorkflowRun)
            .where(WorkflowRun.experiment_id == experiment_id)
            .order_by(WorkflowRun.condition, WorkflowRun.run_index)
        )
        return list(self._session.execute(stmt).scalars())


def get_run_service(session: Session) -> RunService:
    return RunService(session)