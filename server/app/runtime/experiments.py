"""The backend experiment runner.

Executes a baseline-versus-enforced comparison by driving the *same* runtime and
the *same* workflow definition twice. The only experimental variable is the
treatment of the simulated unauthorized intent:

    enforced -> authorize_intent() -> DENY -> policy_denied -> blocked -> recovery
    baseline -> simulated_allow()  -> policy_violation              -> continues

Everything else — participants, message chain, handoff structure, ordering — is
identical, which is what makes the comparison meaningful.

Safety: baseline records that an unauthorized action *would have been* permitted.
No customer record is read, no authorization is disabled anywhere else, and the
mode is unreachable from an ordinary ``request_order``.

Aggregation is derived on read, never stored as independent truth.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Condition, Experiment, ExperimentStatus, WorkflowRun
from app.services.events import EventService

logger = logging.getLogger(__name__)

#: The two conditions, in the order the comparison runs them.
CONDITIONS = (Condition.BASELINE, Condition.ENFORCED)

#: Guard rail for a research command; the UI default is 10.
MAX_RUNS_PER_CONDITION = 50


class ExperimentDisabled(RuntimeError):
    """Raised when experiments are not enabled in this configuration."""


def new_experiment_id() -> str:
    return f"exp_{uuid.uuid4().hex[:12]}"


def start_experiment(
    session: Session,
    *,
    request_id: str,
    order_id: str,
    seed: str,
    runs_per_condition: int,
) -> Experiment:
    """Create the comparison record. It stores configuration, not results."""
    experiment = Experiment(
        id=new_experiment_id(),
        request_id=request_id,
        order_id=order_id,
        seed=seed,
        runs_per_condition=runs_per_condition,
        status=ExperimentStatus.RUNNING,
    )
    session.add(experiment)
    session.commit()
    logger.info(
        "experiment %s started: order=%s seed=%s runs/condition=%d",
        experiment.id,
        order_id,
        seed,
        runs_per_condition,
    )
    return experiment


def run_comparison(session: Session, experiment: Experiment) -> Experiment:
    """Run every trial of a comparison, then finalise its status.

    A trial that raises is recorded as failed and the comparison continues, so a
    partial result is preserved and reported as partial rather than discarded.
    """
    from app.runtime.runtime import KayanRuntime

    service = EventService(session)
    completed = 0
    failed = 0

    for condition in CONDITIONS:
        for index in range(1, experiment.runs_per_condition + 1):
            try:
                run = KayanRuntime(mode=condition.value).request_order(
                    session,
                    order_id=experiment.order_id,
                    request_id=experiment.request_id,
                    condition=condition.value,
                    experiment_id=experiment.id,
                    seed=experiment.seed,
                )
            except Exception:  # noqa: BLE001 - recorded per trial, never swallowed
                logger.exception(
                    "experiment %s trial %s #%d failed", experiment.id, condition.value, index
                )
                failed += 1
                continue
            if run.status.value == "completed":
                completed += 1
            else:
                failed += 1

    experiment.completed_at = datetime.now(timezone.utc)
    total = len(CONDITIONS) * experiment.runs_per_condition
    if failed == 0 and completed == total:
        experiment.status = ExperimentStatus.COMPLETED
    elif completed == 0:
        experiment.status = ExperimentStatus.FAILED
    else:
        experiment.status = ExperimentStatus.PARTIALLY_FAILED
    if failed:
        experiment.error = f"{failed} of {total} trial(s) did not complete"
    session.commit()

    events = service.count_events()
    logger.info(
        "experiment %s finished: status=%s completed=%d failed=%d stream events=%d",
        experiment.id,
        experiment.status.value,
        completed,
        failed,
        events,
    )
    return experiment


# -- reading results -------------------------------------------------------


def trials_for(session: Session, experiment_id: str) -> list[WorkflowRun]:
    """Every trial of a comparison, ordered by condition then index."""
    return list(
        session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.experiment_id == experiment_id)
            .order_by(WorkflowRun.condition, WorkflowRun.run_index)
        ).scalars()
    )


def _average(values: list[int]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def summarise_condition(condition: str, runs: list[WorkflowRun]) -> dict[str, Any]:
    """Descriptive aggregate for one condition, derived from its trials."""
    durations = [r.duration_ms for r in runs]
    return {
        "condition": condition,
        "runs": len(runs),
        "completedRuns": sum(1 for r in runs if r.completed),
        "failedRuns": sum(1 for r in runs if r.status.value == "failed"),
        "averageDurationMs": _average(durations),
        "minDurationMs": min(durations) if durations else 0,
        "maxDurationMs": max(durations) if durations else 0,
        "averageEventCount": _average([r.event_count for r in runs]),
        "averageMessageCount": _average([r.message_count for r in runs]),
        "averageHandoffCount": _average([r.handoff_count for r in runs]),
        "totalPolicyDecisions": sum(r.policy_decision_count for r in runs),
        "totalDenials": sum(r.denial_count for r in runs),
        "totalViolations": sum(r.violation_count for r in runs),
        "totalBlocked": sum(r.blocked_count for r in runs),
        "totalRecoveries": sum(r.recovery_count for r in runs),
        "unauthorizedActionsAttempted": sum(1 for r in runs if r.unauthorized_action_attempted),
        "unauthorizedActionsAllowed": sum(1 for r in runs if r.unauthorized_action_allowed),
    }


def build_comparison(session: Session, experiment: Experiment) -> dict[str, Any]:
    """The comparison summary, computed from the persisted trials.

    Nothing here is stored: the trial rows are the record, and this is a view.
    """
    trials = trials_for(session, experiment.id)
    by_condition = {c.value: [t for t in trials if (t.condition.value if t.condition else None) == c.value] for c in CONDITIONS}
    return {
        "seed": experiment.seed,
        "runsPerCondition": experiment.runs_per_condition,
        "baseline": summarise_condition("baseline", by_condition.get("baseline", [])),
        "enforced": summarise_condition("enforced", by_condition.get("enforced", [])),
    }


# -- export ----------------------------------------------------------------

#: Documents how timings were produced, so a reader cannot mistake them for
#: wall-clock or statistical measurements.
TIMING_METHOD = (
    "logical - measured from recorded event timestamps of the shared workflow. "
    "No step sleeps to inflate a duration, and machine execution time is reported "
    "separately as wallClockMs. These are deterministic reproducible measurements, "
    "not a model-performance benchmark."
)

CSV_COLUMNS = (
    "run_id",
    "experiment_id",
    "condition",
    "seed",
    "run_index",
    "duration_ms",
    "wall_clock_ms",
    "completed",
    "status",
    "event_count",
    "message_count",
    "handoff_count",
    "policy_decision_count",
    "denial_count",
    "violation_count",
    "blocked_count",
    "recovery_count",
    "unauthorized_action_attempted",
    "unauthorized_action_allowed",
    "final_state",
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def run_to_dict(run: WorkflowRun) -> dict[str, Any]:
    """One trial record, in the shape the export and API use."""
    return {
        "runId": run.id,
        "experimentId": run.experiment_id,
        "orderId": run.order_id,
        "condition": run.condition.value if run.condition else None,
        "seed": run.seed,
        "runIndex": run.run_index,
        "startedAt": _iso(run.started_at),
        "completedAt": _iso(run.completed_at),
        "durationMs": run.duration_ms,
        "wallClockMs": run.wall_clock_ms,
        "completed": run.completed,
        "status": run.status.value,
        "eventCount": run.event_count,
        "messageCount": run.message_count,
        "handoffCount": run.handoff_count,
        "policyDecisionCount": run.policy_decision_count,
        "denialCount": run.denial_count,
        "violationCount": run.violation_count,
        "blockedCount": run.blocked_count,
        "recoveryCount": run.recovery_count,
        "unauthorizedActionAttempted": run.unauthorized_action_attempted,
        "unauthorizedActionAllowed": run.unauthorized_action_allowed,
        "finalState": run.final_state,
        "error": run.error,
        "timings": run.timings or [],
    }


def build_export(session: Session, experiment: Experiment, generated_at: str) -> dict[str, Any]:
    """The full persisted experiment: configuration, summaries and every trial."""
    trials = trials_for(session, experiment.id)
    return {
        "experiment": experiment.id,
        "configuration": {
            "orderId": experiment.order_id,
            "seed": experiment.seed,
            "runsPerCondition": experiment.runs_per_condition,
            "conditions": [c.value for c in CONDITIONS],
            "status": experiment.status.value,
            "startedAt": _iso(experiment.started_at),
            "completedAt": _iso(experiment.completed_at),
            "error": experiment.error,
            "timingMethod": TIMING_METHOD,
        },
        "generatedAt": generated_at,
        "summary": build_comparison(session, experiment),
        "runs": [run_to_dict(run) for run in trials],
        "note": (
            "Event-level evidence is not duplicated here; inspect a trial's events "
            "through /api/runs/workflow/{runId}/events or the audit view."
        ),
    }


def _cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if any(ch in text for ch in ',"\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def build_csv(session: Session, experiment: Experiment) -> str:
    """One row per persisted trial. Missing metrics stay empty, never invented."""
    lines = [",".join(CSV_COLUMNS)]
    for run in trials_for(session, experiment.id):
        record = run_to_dict(run)
        lines.append(
            ",".join(
                _cell(
                    {
                        "run_id": record["runId"],
                        "experiment_id": record["experimentId"],
                        "condition": record["condition"],
                        "seed": record["seed"],
                        "run_index": record["runIndex"],
                        "duration_ms": record["durationMs"],
                        "wall_clock_ms": record["wallClockMs"],
                        "completed": record["completed"],
                        "status": record["status"],
                        "event_count": record["eventCount"],
                        "message_count": record["messageCount"],
                        "handoff_count": record["handoffCount"],
                        "policy_decision_count": record["policyDecisionCount"],
                        "denial_count": record["denialCount"],
                        "violation_count": record["violationCount"],
                        "blocked_count": record["blockedCount"],
                        "recovery_count": record["recoveryCount"],
                        "unauthorized_action_attempted": record["unauthorizedActionAttempted"],
                        "unauthorized_action_allowed": record["unauthorizedActionAllowed"],
                        "final_state": record["finalState"],
                    }[column]
                )
                for column in CSV_COLUMNS
            )
        )
    return "\n".join(lines)