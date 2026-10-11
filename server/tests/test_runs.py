"""Workflow run persistence and metric derivation from the event stream.

A run is either a commanded order or an experimental trial; both are the same
record, and every count on it is derived from its own events.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Condition, Experiment, ExperimentStatus, WorkflowRun, WorkflowRunStatus
from app.services import get_event_service, get_run_service
from app.services.run_metrics import derive_run_metrics

BASE = datetime(2026, 3, 14, 9, 0, 0, tzinfo=timezone.utc)

ENFORCED_SCRIPT = [
    ("order_received", None),
    ("task_assigned", "manager"),
    ("agent_message_sent", "manager"),
    ("agent_message_received", "sales"),
    ("agent_question", "operations"),
    ("policy_denied", "operations"),
    ("blocked", "operations"),
    ("information_requested", "operations"),
    ("information_provided", "employee"),
    # The blocked agent resumes its own work with the authorized resource.
    ("task_started", "operations"),
    ("task_completed", "sales"),
]


def _make_run(session, run_id="run-1", condition=Condition.ENFORCED, script=ENFORCED_SCRIPT):
    run = WorkflowRun(
        id=run_id,
        request_id=None,
        order_id="1042",
        status=WorkflowRunStatus.RUNNING,
        run_index=1,
        condition=condition,
        seed="KAYAN-DEMO-1042",
    )
    session.add(run)
    session.commit()

    service = get_event_service(session)
    for index, (kind, actor) in enumerate(script):
        payload: dict = {}
        if kind in ("policy_denied", "agent_question"):
            payload = {
                "policyDecision": {"decision": "deny", "policy": "Customer Data Scope"},
                "intent": {"agentId": actor, "action": "customer_data.read"},
            }
        service.record(
            event_type=kind,
            stream_id="main",
            actor_id=actor,
            run_id=run_id,
            payload=payload,
            timestamp=BASE + timedelta(milliseconds=100 * index),
            publish=False,
        )
    return run


# -- the run record --------------------------------------------------------


def test_run_persists_identity(session):
    run = _make_run(session)
    stored = session.get(WorkflowRun, "run-1")
    assert stored.order_id == "1042"
    assert stored.seed == "KAYAN-DEMO-1042"
    assert stored.condition is Condition.ENFORCED
    assert stored.run_index == 1


def test_an_ordinary_order_run_has_no_experiment_identity(session):
    run = WorkflowRun(
        id="run-plain",
        request_id="req-1",
        order_id="1042",
        status=WorkflowRunStatus.RUNNING,
        run_index=1,
    )
    session.add(run)
    session.commit()
    stored = session.get(WorkflowRun, "run-plain")
    assert stored.experiment_id is None
    assert stored.condition is None


def test_metrics_are_derived_not_authored(session):
    run = _make_run(session)
    events = get_event_service(session).list_events(run_id=run.id, limit=500)
    metrics = derive_run_metrics(events)

    run.event_count = metrics["event_count"]
    run.denial_count = metrics["denial_count"]
    run.violation_count = metrics["violation_count"]
    run.blocked_count = metrics["blocked_count"]
    run.recovery_count = metrics["recovery_count"]
    run.unauthorized_action_attempted = metrics["unauthorized_action_attempted"]
    run.completed = metrics["completed"]
    run.duration_ms = metrics["duration_ms"]
    run.timings = metrics["timings"]
    run.final_state = metrics["final_state"]
    session.commit()

    stored = session.get(WorkflowRun, "run-1")
    assert stored.event_count == len(ENFORCED_SCRIPT)
    assert stored.denial_count == 1
    assert stored.violation_count == 0
    assert stored.blocked_count == 1
    assert stored.recovery_count == 1  # blocked agent resumed its own work
    assert stored.unauthorized_action_attempted is True
    assert stored.completed is True
    assert stored.final_state == "completed"


def test_baseline_run_shows_no_denial_and_a_violation(session):
    baseline = [
        ("order_received", None),
        ("task_assigned", "manager"),
        ("policy_violation", "operations"),
        ("information_requested", "operations"),
        ("task_started", "sales"),
        ("task_completed", "sales"),
    ]
    run = _make_run(session, run_id="run-base", condition=Condition.BASELINE, script=baseline)
    events = get_event_service(session).list_events(run_id=run.id, limit=500)
    metrics = derive_run_metrics(events)

    assert metrics["denial_count"] == 0
    assert metrics["blocked_count"] == 0
    assert metrics["violation_count"] == 1
    assert metrics["unauthorized_action_allowed"] is True
    assert metrics["completed"] is True


def test_recovery_requires_same_actor_resuming():
    """Mirrors the frontend rule: a blocked agent must restart its own work."""
    assert (
        derive_run_metrics(
            [
                {"event_type": "blocked", "actor_id": "sales"},
                {"event_type": "task_started", "actor_id": "sales"},
            ]
        )["recovery_count"]
        == 1
    )
    # A different agent starting work is not a recovery for the blocked one.
    assert (
        derive_run_metrics(
            [
                {"event_type": "blocked", "actor_id": "sales"},
                {"event_type": "task_started", "actor_id": "operations"},
            ]
        )["recovery_count"]
        == 0
    )


def test_unauthorized_allowed_requires_violation_and_no_denial():
    assert derive_run_metrics([{"event_type": "policy_violation"}])["unauthorized_action_allowed"]
    both = derive_run_metrics([{"event_type": "policy_violation"}, {"event_type": "policy_denied"}])
    assert not both["unauthorized_action_allowed"]
    assert not derive_run_metrics([])["unauthorized_action_allowed"]


def test_timings_measure_named_intervals_from_event_timestamps():
    events = [
        {"event_type": "order_received", "timestamp": BASE},
        {"event_type": "agent_question", "timestamp": BASE + timedelta(seconds=1)},
        {"event_type": "policy_denied", "timestamp": BASE + timedelta(seconds=2)},
        {"event_type": "blocked", "timestamp": BASE + timedelta(seconds=2)},
        {"event_type": "task_started", "timestamp": BASE + timedelta(seconds=3)},
        {"event_type": "task_completed", "timestamp": BASE + timedelta(seconds=5)},
    ]
    timings = {t["name"]: t["durationMs"] for t in derive_run_metrics(events)["timings"]}
    assert timings["order_start_to_completion"] == 5000
    assert timings["instruction_received_to_policy_decision"] == 1000
    assert timings["policy_denial_to_blocked"] == 0
    assert timings["blocked_to_authorized_recovery"] == 1000
    assert timings["authorized_recovery_to_completion"] == 2000


def test_missing_endpoints_are_omitted_not_invented():
    timings = derive_run_metrics([{"event_type": "order_received", "timestamp": BASE}])["timings"]
    assert timings == []


def test_events_require_an_existing_run(session):
    """run_id is a foreign key again, so events cannot claim a phantom run."""
    from app.services import get_event_service as svc

    with pytest.raises(IntegrityError):
        svc(session).record(event_type="order_received", stream_id="main", run_id="run-nope")
        session.commit()
    session.rollback()


def test_trials_belong_to_an_experiment(session):
    experiment = Experiment(
        id="exp-1",
        request_id="req-1",
        order_id="1042",
        seed="KAYAN-DEMO-1042",
        runs_per_condition=1,
        status=ExperimentStatus.RUNNING,
    )
    session.add(experiment)
    session.commit()

    run = WorkflowRun(
        id="run-trial",
        request_id="req-1",
        order_id="1042",
        status=WorkflowRunStatus.RUNNING,
        run_index=1,
        experiment_id="exp-1",
        condition=Condition.BASELINE,
        seed="KAYAN-DEMO-1042",
    )
    session.add(run)
    session.commit()

    trials = get_run_service(session).runs_for_experiment("exp-1")
    assert [t.id for t in trials] == ["run-trial"]
    assert trials[0].condition is Condition.BASELINE


def test_experiment_request_id_is_unique(session):
    session.add(
        Experiment(
            id="exp-a",
            request_id="req-dup",
            order_id="1042",
            seed="S",
            runs_per_condition=1,
            status=ExperimentStatus.RUNNING,
        )
    )
    session.commit()
    session.add(
        Experiment(
            id="exp-b",
            request_id="req-dup",
            order_id="1042",
            seed="S",
            runs_per_condition=1,
            status=ExperimentStatus.RUNNING,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_runs_api_lists_and_filters(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    body = client.get("/api/runs", params={"order_id": "1042"}).json()
    assert len(body) == 1
    run = body[0]
    assert run["seed"] == "KAYAN-DEMO-1042"
    assert run["condition"] == "enforced"
    assert run["denialCount"] == 1
    assert run["blockedCount"] == 1
    assert run["recoveryCount"] == 1
    assert run["violationCount"] == 0
    assert run["eventCount"] == 19
    assert run["completed"] is True
    assert run["finalState"] == "completed"
    # Logical duration and real machine time are reported separately.
    assert "durationMs" in run and "wallClockMs" in run

    assert client.get("/api/runs", params={"condition": "baseline"}).json() == []
    assert len(client.get("/api/runs", params={"condition": "enforced"}).json()) == 1


def test_runs_api_single_and_404(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    assert client.get("/api/runs/run-kayan-1042-enforced-001").status_code == 200
    assert client.get("/api/runs/nope").status_code == 404