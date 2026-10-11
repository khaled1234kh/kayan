"""Event and ExperimentRun API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, Field

from app.schemas.common import ApiSchema


class EventOut(ApiSchema):
    """Persisted event, shaped like the frontend ``KayanEvent``.

    ``sequence`` is the ordering key; ``timestamp`` is not used for ordering.
    """

    id: str
    #: camelCase to match the existing frontend contract. The ORM column is
    #: ``event_type``, hence the explicit validation alias.
    type: str = Field(
        validation_alias=AliasChoices("event_type", "type"),
        serialization_alias="type",
    )
    sequence: int
    stream_id: str
    timestamp: datetime
    actor_id: str | None = None
    target_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    #: Reproducible logical position within a run, when the event has one. Real
    #: ``timestamp`` and this offset are separate on purpose; ``null`` for
    #: configuration events, which belong to no run.
    clock_offset_ms: int | None = None
    payload: dict = {}


class ExperimentRunOut(ApiSchema):
    """Run metadata. Counts are derived from the event stream, not authored."""

    id: str
    experiment_id: str
    seed: str
    mode: str
    run_index: int
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int
    completed: bool
    event_count: int
    message_count: int
    handoff_count: int
    policy_decision_count: int
    denial_count: int
    blocked_count: int
    recovery_count: int
    unauthorized_action_attempted: bool
    unauthorized_action_allowed: bool
    timings: list = []
    final_state: str | None = None

class WorkflowRunOut(ApiSchema):
    """One commanded execution of the KAYAN workflow."""

    id: str
    request_id: str | None = None
    order_id: str
    status: str
    run_index: int
    event_count: int
    denial_count: int
    blocked_count: int
    recovery_count: int
    final_state: str | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ExperimentOut(ApiSchema):
    """One baseline-vs-enforced comparison. Configuration and lifecycle only."""

    id: str
    request_id: str | None = None
    order_id: str
    seed: str
    runs_per_condition: int
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
