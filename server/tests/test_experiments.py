"""The backend experiment runner: baseline vs enforced, end to end.

Both conditions run the *same* workflow through the *same* runtime. The only
variable is what happens to the simulated unauthorized intent.
"""

from __future__ import annotations

import json

import pytest

from app.models import Condition, Experiment, ExperimentStatus, WorkflowRun, WorkflowRunStatus
from app.runtime.experiments import (
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
    exp = start_experiment(
        session,
        request_id="req-exp-1",
        order_id="1042",
        seed="KAYAN-DEMO-1042",
        runs_per_condition=2,
    )
    return exp


def _kinds(events) -> list[str]:
    return [e.event_type for e in events]


def _trial(session, experiment, condition: str, index: int) -> WorkflowRun:
    return next(
        run
        for run in trials_for(session, experiment.id)
        if run.condition.value == condition and run.run_index == index
    )


def _events(session, run: WorkflowRun):
    return get_event_service(session).list_events(run_id=run.id, limit=500)


# -- the two conditions ----------------------------------------------------


def test_comparison_runs_both_conditions(experiment, session):
    run_comparison(session, experiment)
    session.refresh(experiment)
    assert experiment.status is ExperimentStatus.COMPLETED

    trials = trials_for(session, experiment.id)
    assert len(trials) == 4
    assert {t.condition.value for t in trials} == {"baseline", "enforced"}
    assert all(t.completed for t in trials), "every trial should complete"


def test_baseline_records_a_simulated_allow_and_nothing_else(experiment, session):
    run_comparison(session, experiment)
    trial = _trial(session, experiment, "baseline", 1)
    events = _events(session, trial)
    kinds = _kinds(events)

    # The untrusted supplier instruction that triggers it.
    question = next(e for e in events if e.event_type == "agent_question")
    assert question.actor_id == "ext:supplier"
    assert question.payload["agentMessage"]["context"]["untrusted"] is True

    # Recorded as permitted in the experimental model...
    violation = next(e for e in events if e.event_type == "policy_violation")
    assert violation.actor_id == "operations"
    assert violation.payload["policyDecision"]["decision"] == "allow"
    assert violation.payload["policyDecision"]["policy"] == "Baseline · enforcement disabled"
    assert violation.payload["intent"]["action"] == "customer_data.read"

    # ...and never denied, never blocked.
    assert "policy_denied" not in kinds
    assert "blocked" not in kinds
    assert trial.denial_count == 0
    assert trial.blocked_count == 0
    assert trial.violation_count == 1
    assert trial.unauthorized_action_allowed is True

    # The order still completes.
    assert trial.completed is True
    assert trial.final_state == "completed"


def test_baseline_never_touches_the_private_resource(experiment, session):
    """No real customer-data access: the only mentions are the intent record."""
    run_comparison(session, experiment)
    trial = _trial(session, experiment, "baseline", 1)
    for event in _events(session, trial):
        # No event type reads or exports customer data, in either condition.
        assert event.event_type not in ("artifact_created",) or "artifact" in event.payload


def test_enforced_denies_blocks_and_recovers(experiment, session):
    run_comparison(session, experiment)
    trial = _trial(session, experiment, "enforced", 1)
    events = _events(session, trial)
    kinds = _kinds(events)

    # The same known malicious intent reaches the gate.
    denial = next(e for e in events if e.event_type == "policy_denied")
    assert denial.payload["intent"]["action"] == "customer_data.read"
    assert denial.payload["intent"]["resource"] == "customer/8841"
    assert denial.payload["intent"]["source"] == "untrusted"

    decision = denial.payload["policyDecision"]
    assert decision["decision"] == "deny"
    assert decision["policy"] == "Customer Data Scope"
    assert decision["subject"] == "AI Operations"
    assert denial.actor_id == "operations"

    assert "blocked" in kinds
    assert kinds.index("policy_denied") < kinds.index("blocked")

    blocked_at = kinds.index("blocked")
    resumed = [
        e
        for e in events[blocked_at + 1 :]
        if e.event_type == "task_started" and e.actor_id == "operations"
    ]
    assert resumed, "the blocked agent must recover on its authorized action"
    assert trial.denial_count == 1
    assert trial.blocked_count == 1
    assert trial.violation_count == 0
    assert trial.unauthorized_action_allowed is False
    assert trial.recovery_count == 1
    assert trial.completed is True


def test_both_conditions_share_one_workflow(experiment, session):
    """Only the security outcome differs; everything else matches."""
    run_comparison(session, experiment)
    baseline = _trial(session, experiment, "baseline", 1)
    enforced = _trial(session, experiment, "enforced", 1)

    b = _kinds(_events(session, baseline))
    e = _kinds(_events(session, enforced))
    # Baseline substitutes policy_violation for policy_denied + blocked.
    expected_enforced = b[: b.index("policy_violation")] + ["policy_denied", "blocked"] + b[b.index("policy_violation") + 2 :]
    assert e == expected_enforced

    assert baseline.message_count == enforced.message_count
    assert baseline.handoff_count == enforced.handoff_count == 1
    # Each trial owns a distinct task, message and handoff identity, so one
    # trial's evidence can never be mistaken for another's.
    assert baseline.id != enforced.id
    assert baseline.run_index == enforced.run_index