"""Experiment identity, aggregation, isolation, failure handling and exports."""

from __future__ import annotations

import json

import pytest

from app.models import Condition, ExperimentStatus, WorkflowRun, WorkflowRunStatus
from app.runtime.experiments import (
    CONDITIONS,
    TIMING_METHOD,
    build_comparison,
    build_csv,
    build_export,
    run_comparison,
    start_experiment,
    summarise_condition,
    trials_for,
)
from app.services import get_event_service


@pytest.fixture()
def experiment(session):
    from app.db.seed import seed_agents

    seed_agents(session)
    return start_experiment(
        session,
        request_id="req-exp",
        order_id="1042",
        seed="KAYAN-DEMO-1042",
        runs_per_condition=5,
    )


def _trial(session, experiment, condition: str, index: int) -> WorkflowRun:
    return next(
        run
        for run in trials_for(session, experiment.id)
        if run.condition.value == condition and run.run_index == index
    )


# -- identity --------------------------------------------------------------


def test_comparison_records_configuration_not_results(experiment):
    assert experiment.seed == "KAYAN-DEMO-1042"
    assert experiment.runs_per_condition == 5
    assert experiment.order_id == "1042"
    assert experiment.status is ExperimentStatus.RUNNING
    assert experiment.request_id == "req-exp"


def test_every_trial_has_identity_and_metrics(experiment, session):
    run_comparison(session, experiment)
    trials = trials_for(session, experiment.id)
    assert len(trials) == 10

    ids = {t.id for t in trials}
    assert len(ids) == 10, "run ids must be unique"

    for condition in CONDITIONS:
        indexes = sorted(t.run_index for t in trials if t.condition is condition)
        assert indexes == [1, 2, 3, 4, 5], f"{condition} indexes"
        for trial in trials:
            if trial.condition is not condition:
                continue
            assert trial.experiment_id == experiment.id
            assert trial.seed == "KAYAN-DEMO-1042"
            assert trial.started_at is not None
            assert trial.completed_at is not None
            assert trial.completed is True
            assert trial.event_count > 0
            assert trial.duration_ms > 0
            assert isinstance(trial.timings, list)


def test_events_link_to_the_correct_trial(experiment, session):
    run_comparison(session, experiment)
    for trial in trials_for(session, experiment.id):
        events = get_event_service(session).list_events(run_id=trial.id, limit=500)
        assert len(events) == trial.event_count
        assert {e.run_id for e in events} == {trial.id}
        # Sequence ordering is preserved within each trial's history.
        assert [e.sequence for e in events] == sorted(e.sequence for e in events)


def test_metrics_match_the_actual_event_history(experiment, session):
    """Counts come from events, not from expectations."""
    from app.services.run_metrics import derive_run_metrics

    run_comparison(session, experiment)
    for trial in trials_for(session, experiment.id):
        events = get_event_service(session).list_events(run_id=trial.id, limit=500)
        metrics = derive_run_metrics(events)
        assert trial.event_count == metrics["event_count"] == len(events)
        assert trial.denial_count == metrics["denial_count"]
        assert trial.violation_count == metrics["violation_count"]
        assert trial.blocked_count == metrics["blocked_count"]
        assert trial.message_count == metrics["message_count"]
        assert trial.handoff_count == metrics["handoff_count"]


def test_conditions_differ_only_in_the_security_outcome(experiment, session):
    run_comparison(session, experiment)
    baseline_total = sum(
        _trial(session, experiment, "baseline", i).denial_count for i in range(1, 6)
    )
    enforced_total = sum(
        _trial(session, experiment, "enforced", i).denial_count for i in range(1, 6)
    )
    assert baseline_total == 0
    assert enforced_total == 5


def test_same_seed_and_condition_reproduce_the_same_logical_run(session, experiment):
    """Deterministic: the logical sequence repeats; ids and clocks differ."""
    run_comparison(session, experiment)
    first = _trial(session, experiment, "enforced", 1)
    second = _trial(session, experiment, "enforced", 2)

    def shape(run):
        return [e.event_type for e in get_event_service(session).list_events(run_id=run.id, limit=500)]

    assert shape(first) == shape(second)
    assert first.seed == second.seed
    assert first.duration_ms == second.duration_ms
    assert first.event_count == second.event_count


# -- aggregation -----------------------------------------------------------


def test_aggregates_are_derived_from_the_trials(experiment, session):
    run_comparison(session, experiment)
    summary = build_comparison(session, experiment)

    for condition in ("baseline", "enforced"):
        trials = [t for t in trials_for(session, experiment.id) if t.condition.value == condition]
        side = summary[condition]
        assert side["runs"] == len(trials) == 5
        assert side["completedRuns"] == sum(1 for t in trials if t.completed)
        assert side["failedRuns"] == 0
        assert side["averageDurationMs"] == round(
            sum(t.duration_ms for t in trials) / len(trials), 2
        )
        assert side["minDurationMs"] == min(t.duration_ms for t in trials)
        assert side["maxDurationMs"] == max(t.duration_ms for t in trials)
        assert side["averageEventCount"] == round(
            sum(t.event_count for t in trials) / len(trials), 2
        )
        assert side["totalDenials"] == sum(t.denial_count for t in trials)
        assert side["totalViolations"] == sum(t.violation_count for t in trials)
        assert side["totalBlocked"] == sum(t.blocked_count for t in trials)
        assert side["totalRecoveries"] == sum(t.recovery_count for t in trials)
        assert side["unauthorizedActionsAllowed"] == sum(
            1 for t in trials if t.unauthorized_action_allowed
        )


def test_summary_reports_the_measured_difference(experiment, session):
    run_comparison(session, experiment)
    summary = build_comparison(session, experiment)
    # Descriptive only: baseline records violations, enforced records denials.
    assert summary["baseline"]["totalViolations"] == 5
    assert summary["baseline"]["totalDenials"] == 0
    assert summary["enforced"]["totalDenials"] == 5
    assert summary["enforced"]["totalViolations"] == 0
    assert summary["seed"] == "KAYAN-DEMO-1042"
    assert summary["runsPerCondition"] == 5


def test_summarise_condition_handles_an_empty_series():
    empty = summarise_condition("baseline", [])
    assert empty["runs"] == 0
    assert empty["averageDurationMs"] == 0.0
    assert empty["minDurationMs"] == 0


# -- failure honesty -------------------------------------------------------


def test_a_failed_trial_is_not_reported_as_completed(session, experiment, monkeypatch):
    import app.runtime.runtime as runtime_module

    original = runtime_module.AgentCollaboration.send_message
    state = {"failed": False}

    def flaky(self, draft):
        # Fail one enforced trial only.
        if not state["failed"] and self.mode == "enforced":
            state["failed"] = True
            raise RuntimeError("trial exploded")
        return original(self, draft)

    monkeypatch.setattr(runtime_module.AgentCollaboration, "send_message", flaky)
    run_comparison(session, experiment)

    session.refresh(experiment)
    trials = trials_for(session, experiment.id)
    assert experiment.status is ExperimentStatus.PARTIALLY_FAILED
    assert experiment.error and "did not complete" in experiment.error

    failed = [t for t in trials if t.status is WorkflowRunStatus.FAILED]
    completed = [t for t in trials if t.completed]
    assert len(completed) == 9
    # A trial that raised is still recorded, and never as a success.
    assert experiment.status is not ExperimentStatus.COMPLETED
    for trial in failed:
        assert trial.completed is False
        assert trial.final_state != "completed"


def test_partial_results_are_preserved(session, experiment, monkeypatch):
    import app.runtime.runtime as runtime_module

    original = runtime_module.AgentCollaboration.send_message
    state = {"failed": False}

    def flaky(self, draft):
        if not state["failed"] and self.mode == "enforced":
            state["failed"] = True
            raise RuntimeError("trial exploded")
        return original(self, draft)

    monkeypatch.setattr(runtime_module.AgentCollaboration, "send_message", flaky)
    run_comparison(session, experiment)

    # The other nine trials survive and stay inspectable.
    trials = trials_for(session, experiment.id)
    assert len(trials) == 10
    completed = [t for t in trials if t.completed]
    assert len(completed) == 9
    for trial in completed:
        events = get_event_service(session).list_events(run_id=trial.id, limit=500)
        assert len(events) == trial.event_count


# -- isolation -------------------------------------------------------------


def test_two_trials_do_not_mix_evidence(session, experiment):
    run_comparison(session, experiment)
    first = _trial(session, experiment, "enforced", 1)
    second = _trial(session, experiment, "enforced", 2)

    first_events = get_event_service(session).list_events(run_id=first.id, limit=500)
    second_events = get_event_service(session).list_events(run_id=second.id, limit=500)

    assert {e.id for e in first_events}.isdisjoint({e.id for e in second_events})
    assert {e.task_id for e in first_events}.isdisjoint({e.task_id for e in second_events})

    # Messages belong to exactly one trial's chain.
    first_message_ids = {
        e.payload["agentMessage"]["id"]
        for e in first_events
        if "agentMessage" in e.payload
    }
    second_message_ids = {
        e.payload["agentMessage"]["id"]
        for e in second_events
        if "agentMessage" in e.payload
    }
    assert first_message_ids.isdisjoint(second_message_ids)

    # Security evidence resolves to the right trial only.
    first_denials = [e for e in first_events if e.event_type == "policy_denied"]
    second_denials = [e for e in second_events if e.event_type == "policy_denied"]
    assert len(first_denials) == 1
    assert {e.run_id for e in first_denials} == {first.id}
    assert {e.run_id for e in second_denials} == {second.id}

    # Handoff references its own task.
    handoff = next(e for e in first_events if e.event_type == "task_delegated")
    assert handoff.payload["handoff"]["taskId"] == handoff.payload["taskId"]


def test_run_history_endpoint_returns_only_that_trial(experiment, session, client):
    run_comparison(session, experiment)
    trial = _trial(session, experiment, "baseline", 1)
    other = _trial(session, experiment, "enforced", 1)

    body = client.get(f"/api/experiments/runs/{trial.id}/events").json()
    assert body["eventCount"] == trial.event_count
    assert {e["runId"] for e in body["events"]} == {trial.id}
    assert trial.id not in {e["id"] for e in body["events"]}
    assert other.id not in {e["runId"] for e in body["events"]}
    # Ordered by sequence, which is what replay depends on.
    sequences = [e["sequence"] for e in body["events"]]
    assert sequences == sorted(sequences)


def test_experiment_endpoint_returns_summary_and_trials(experiment, session, client):
    run_comparison(session, experiment)
    body = client.get(f"/api/experiments/{experiment.id}").json()
    assert body["experiment"]["status"] == "completed"
    assert body["experiment"]["seed"] == "KAYAN-DEMO-1042"
    assert body["comparison"]["runsPerCondition"] == 5
    assert len(body["runs"]) == 10
    assert body["progress"] == {
        "totalTrials": 10,
        "recordedTrials": 10,
        "completedTrials": 10,
        "failedTrials": 0,
    }


# -- exports ---------------------------------------------------------------


def test_json_export_contains_persisted_records(experiment, session, client):
    run_comparison(session, experiment)
    payload = json.loads(
        client.get(f"/api/experiments/{experiment.id}/export.json").text
    )
    assert payload["experiment"] == experiment.id
    config = payload["configuration"]
    assert config["seed"] == "KAYAN-DEMO-1042"
    assert config["runsPerCondition"] == 5
    assert config["conditions"] == ["baseline", "enforced"]
    assert config["status"] == "completed"
    assert TIMING_METHOD.split(" - ")[0] in config["timingMethod"]
    assert len(payload["runs"]) == 10
    assert payload["summary"]["enforced"]["totalDenials"] == 5
    for run in payload["runs"]:
        for field in (
            "runId",
            "condition",
            "seed",
            "runIndex",
            "durationMs",
            "wallClockMs",
            "eventCount",
            "denialCount",
            "violationCount",
            "blockedCount",
            "recoveryCount",
            "finalState",
        ):
            assert field in run


def test_csv_export_has_one_row_per_trial(experiment, session, client):
    run_comparison(session, experiment)
    csv = client.get(f"/api/experiments/{experiment.id}/export.csv").text
    lines = csv.strip().split("\n")
    assert len(lines) == 11
    header = lines[0].split(",")
    assert "condition" in header
    assert "violation_count" in header
    assert "wall_clock_ms" in header
    rows = lines[1:]
    assert sum(1 for r in rows if r.split(",")[2] == "baseline") == 5
    assert sum(1 for r in rows if r.split(",")[2] == "enforced") == 5


def test_export_invents_no_missing_metrics(experiment, session, client):
    run_comparison(session, experiment)
    payload = build_export(session, experiment, "2026-01-01T00:00:00+00:00")
    for run in payload["runs"]:
        assert run["timings"] is not None
        assert run["error"] is None or isinstance(run["error"], str)


def test_experiment_listing_and_404(experiment, session, client):
    run_comparison(session, experiment)
    listed = client.get("/api/experiments").json()
    assert any(e["id"] == experiment.id for e in listed)
    assert client.get("/api/experiments/missing").status_code == 404
    assert client.get("/api/experiments/missing/export.json").status_code == 404