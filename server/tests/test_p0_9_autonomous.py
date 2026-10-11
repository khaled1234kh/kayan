"""P0.9: Manager agent + autonomous runtime loop.

Covers the six required behaviours plus the human-escalation pause, the
per-role artifact shapes, and the ``run_autonomous`` command:

1. Manager picks the correct (oldest actionable) task.
2. Manager blocks a task no contract can staff, with ``no_eligible_worker``.
3. The loop stops with ``target_reached`` when the board is fully worked.
4. The loop stops with ``budget_exhausted`` when the ceiling is gone.
5. A TrustGate denial is recorded and the loop continues with the next task.
6. Determinism: same board + contracts + budget gives the same assignment.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import (
    BudgetLedgerCategory,
    BudgetLedgerEntry,
    Company,
    CompanyTask,
    Event,
    TaskStatus,
)
from app.runtime.autonomous import (
    artifact_for_task,
    is_budget_exhausted,
    is_target_reached,
    run_cycle,
    run_until_target_or_budget,
)
from app.runtime.manager import (
    HUMAN_CLARIFICATION_REQUIRED,
    NO_ELIGIBLE_WORKER,
    Manager,
)
from app.schemas.commands import ProtocolError, parse_command
from app.security.trustgate import PolicyDecision
from app.services.budget import BudgetService

from tests.p0_5_helpers import make_spendable_company, reserve_request

BASE_TIME = datetime(2026, 1, 5, 9, 0, 0, tzinfo=timezone.utc)


def _order_oldest_first(session, first: CompanyTask, second: CompanyTask) -> None:
    """Pin creation order so the board order is exact, not clock-dependent."""
    first.created_at = BASE_TIME
    second.created_at = BASE_TIME + timedelta(seconds=1)
    session.commit()


def _events_for(session, task_id: str, event_type: str) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.task_id == task_id, Event.event_type == event_type)
        .order_by(Event.sequence)
    )
    return list(session.execute(stmt).scalars())


# -- 1. Manager picks the correct task -------------------------------------


def test_manager_picks_oldest_actionable_task(seeded_session):
    fix = make_spendable_company(seeded_session)
    _order_oldest_first(seeded_session, fix.task, fix.other_task)

    outcome = Manager(seeded_session).pick_and_assign(fix.company_id)

    assert outcome.action == "assigned"
    assert outcome.task_id == fix.task.id
    assert outcome.employee_id == fix.seller_id
    assert outcome.contract_id is not None


def test_manager_skips_non_actionable_tasks(seeded_session):
    fix = make_spendable_company(seeded_session)
    fix.task.status = TaskStatus.COMPLETED
    seeded_session.commit()
    _order_oldest_first(seeded_session, fix.task, fix.other_task)

    outcome = Manager(seeded_session).pick_and_assign(fix.company_id)

    assert outcome.action == "assigned"
    assert outcome.task_id == fix.other_task.id


# -- 2. No eligible worker --------------------------------------------------


def test_manager_blocks_task_with_no_eligible_worker(seeded_session):
    fix = make_spendable_company(seeded_session)
    lonely = fix.make_task(fix.seller_id, "support", title="Support backlog")
    _order_oldest_first(seeded_session, lonely, fix.task)

    outcome = Manager(seeded_session).pick_and_assign(fix.company_id)

    assert outcome.action == "blocked_no_worker"
    assert outcome.task_id == lonely.id
    assert outcome.reason_code == NO_ELIGIBLE_WORKER
    seeded_session.refresh(lonely)
    assert lonely.status is TaskStatus.BLOCKED
    blocked = _events_for(seeded_session, lonely.id, "blocked")
    assert len(blocked) == 1
    assert blocked[0].payload["reasonCode"] == NO_ELIGIBLE_WORKER


# -- 3. Loop stops when the target is reached -------------------------------


def test_loop_stops_when_target_reached(seeded_session):
    fix = make_spendable_company(seeded_session)
    _order_oldest_first(seeded_session, fix.task, fix.other_task)

    result = run_until_target_or_budget(seeded_session, fix.company_id)

    assert result.stop_reason == "target_reached"
    assert result.completed == 2
    assert result.cycles == 2
    seeded_session.refresh(fix.task)
    seeded_session.refresh(fix.other_task)
    assert fix.task.status is TaskStatus.COMPLETED
    assert fix.other_task.status is TaskStatus.COMPLETED
    assert is_target_reached(seeded_session, fix.company_id)

    artifacts = _events_for(seeded_session, fix.task.id, "artifact_created")
    assert len(artifacts) == 1
    artifact = artifacts[0].payload["artifact"]
    assert artifact["kind"] == "quotation"
    assert artifact["companyId"] == fix.company_id
    assert artifact["companyName"] == fix.company.name
    assert artifact["templateKey"] == fix.company.template_key
    assert artifact["source"] == "mock"

    charges = seeded_session.execute(
        select(BudgetLedgerEntry).where(
            BudgetLedgerEntry.company_id == fix.company_id,
            BudgetLedgerEntry.category == BudgetLedgerCategory.ACTUAL_COST_CHARGED,
        )
    ).scalars().all()
    assert len(charges) == 2


# -- 4. Loop stops when the budget is exhausted ------------------------------


def test_loop_stops_when_budget_exhausted(seeded_session):
    fix = make_spendable_company(
        seeded_session,
        ceiling="110",
        seller_monthly="100",
        seller_per_task="100",
        owner_monthly="10",
    )
    owner_task = fix.make_task(fix.owner.id, "review", title="Owner review")
    budget = BudgetService(seeded_session)
    assert budget.reserve(
        reserve_request(fix.company_id, fix.seller_id, fix.task.id, "100", "p09-exh-1")
    ).allowed
    assert budget.reserve(
        reserve_request(fix.company_id, fix.owner.id, owner_task.id, "10", "p09-exh-2")
    ).allowed
    assert is_budget_exhausted(seeded_session, fix.company_id)

    result = run_until_target_or_budget(seeded_session, fix.company_id)

    assert result.stop_reason == "budget_exhausted"
    assert result.completed == 0
    seeded_session.refresh(fix.task)
    assert fix.task.status is TaskStatus.OPEN


# -- 5. TrustGate denial is recorded and the loop continues ------------------


def test_trustgate_denial_recorded_and_loop_continues(seeded_session, monkeypatch):
    import app.runtime.autonomous as autonomous

    fix = make_spendable_company(seeded_session)
    _order_oldest_first(seeded_session, fix.task, fix.other_task)
    real_authorize = autonomous.authorize_intent
    calls = {"count": 0}

    def deny_first(intent):
        calls["count"] += 1
        if calls["count"] == 1:
            return PolicyDecision(
                decision="deny",
                policy="Test policy",
                subject="test",
                action=intent.action,
                resource=intent.resource,
                reason="test denial",
            )
        return real_authorize(intent)

    monkeypatch.setattr(autonomous, "authorize_intent", deny_first)

    result = run_until_target_or_budget(seeded_session, fix.company_id)

    seeded_session.refresh(fix.task)
    seeded_session.refresh(fix.other_task)
    assert fix.task.status is TaskStatus.BLOCKED
    assert fix.other_task.status is TaskStatus.COMPLETED
    denials = _events_for(seeded_session, fix.task.id, "policy_denied")
    assert len(denials) == 1
    assert denials[0].payload["policyDecision"]["decision"] == "deny"
    blocked = _events_for(seeded_session, fix.task.id, "blocked")
    assert blocked and blocked[0].payload["reasonCode"] == "trustgate_denied"
    # The blocked task can never be staffed again, so the loop reports the
    # honest reason rather than pretending the target was reached.
    assert result.stop_reason == "no_actionable_tasks"
    assert result.completed == 1


# -- 6. Determinism ----------------------------------------------------------


def test_same_inputs_give_same_assignment(seeded_session):
    fix = make_spendable_company(seeded_session)
    _order_oldest_first(seeded_session, fix.task, fix.other_task)
    manager = Manager(seeded_session)

    first_candidates = manager.eligible_candidates(fix.company_id, fix.task)
    second_candidates = manager.eligible_candidates(fix.company_id, fix.task)
    assert first_candidates == second_candidates
    assert first_candidates and first_candidates[0].employee_id == fix.seller_id

    first = manager.pick_and_assign(fix.company_id)
    assert first.action == "assigned"
    # Restore the exact input state and pick again.
    task = seeded_session.get(CompanyTask, fix.task.id)
    assert task is not None
    task.employee_id = fix.seller_id
    seeded_session.commit()
    second = Manager(seeded_session).pick_and_assign(fix.company_id)

    assert (second.action, second.task_id, second.employee_id) == (
        first.action,
        first.task_id,
        first.employee_id,
    )


# -- human escalation pauses instead of executing ----------------------------


def test_human_seat_pauses_for_clarification(seeded_session):
    fix = make_spendable_company(seeded_session)
    review = fix.make_task(fix.owner.id, "review", title="Needs a human call")
    _order_oldest_first(seeded_session, review, fix.task)

    outcome = Manager(seeded_session).pick_and_assign(fix.company_id)

    assert outcome.action == "awaiting_human"
    assert outcome.reason_code == HUMAN_CLARIFICATION_REQUIRED
    seeded_session.refresh(review)
    assert review.status is TaskStatus.AWAITING_APPROVAL
    waiting = _events_for(seeded_session, review.id, "awaiting_info")
    assert len(waiting) == 1
    assert waiting[0].payload["reasonCode"] == HUMAN_CLARIFICATION_REQUIRED
    # No money moved for work that will not run.
    summary = BudgetService(seeded_session).summary(fix.company_id)
    assert summary.actual_spend == 0
    assert summary.outstanding_reservations == 0


def test_run_cycle_surfaces_human_pause(seeded_session):
    fix = make_spendable_company(seeded_session)
    review = fix.make_task(fix.owner.id, "review", title="Needs a human call")
    _order_oldest_first(seeded_session, review, fix.task)

    cycle = run_cycle(seeded_session, fix.company_id)

    assert cycle.action == "awaiting_human"
    assert cycle.reason_code == HUMAN_CLARIFICATION_REQUIRED


# -- per-role artifact shapes --------------------------------------------------


def test_artifacts_carry_real_company_fields(seeded_session):
    fix = make_spendable_company(seeded_session)
    company = seeded_session.get(Company, fix.company_id)
    assert company is not None

    quotation = artifact_for_task(company, fix.task, fix.seller_id, "sales")
    assert quotation["kind"] == "quotation"
    assert quotation["companyName"] == company.name
    assert quotation["templateKey"] == company.template_key
    assert quotation["currency"] == company.currency
    assert quotation["taskId"] == fix.task.id

    stock_task = fix.make_task(fix.seller_id, "inventory", title="Count stock")
    evidence = artifact_for_task(company, stock_task, fix.seller_id, "operations")
    assert evidence["kind"] == "stock_evidence"
    assert evidence["companyId"] == fix.company_id
    assert evidence["required"] == 50

    plan_task = fix.make_task(fix.owner.id, "review", title="Review board")
    plan = artifact_for_task(company, plan_task, fix.owner.id, "manager")
    assert plan["kind"] == "review"
    assert plan["taskId"] == plan_task.id

    # Deterministic: the same task always yields the same artifact.
    assert artifact_for_task(company, fix.task, fix.seller_id, "sales") == quotation


# -- run_autonomous command ----------------------------------------------------


def test_run_autonomous_command_parses_with_defaults():
    command = parse_command(
        {"kind": "command", "command": "run_autonomous", "requestId": "auto-1"}
    )
    assert not isinstance(command, ProtocolError)
    assert command.command == "run_autonomous"
    assert command.company_id is None
    assert command.max_iterations == 50


def test_run_autonomous_command_rejects_bad_iterations():
    result = parse_command(
        {
            "kind": "command",
            "command": "run_autonomous",
            "requestId": "auto-bad",
            "maxIterations": 0,
        }
    )
    assert isinstance(result, ProtocolError)
    assert result.code == "invalid_command"


def test_run_autonomous_refused_with_no_active_company(client):
    with client.websocket_connect("/ws/events?stream=auto-none") as websocket:
        websocket.send_json(
            {"kind": "command", "command": "run_autonomous", "requestId": "auto-no-company"}
        )
        ack = websocket.receive_json()
    assert ack["kind"] == "command_ack"
    assert ack["accepted"] is False
    assert ack["reason"] == "no_active_company"


def test_run_autonomous_works_board_end_to_end(client, seeded_session):
    fix = make_spendable_company(seeded_session)
    _order_oldest_first(seeded_session, fix.task, fix.other_task)

    with client.websocket_connect("/ws/events?stream=auto-e2e") as websocket:
        websocket.send_json(
            {"kind": "command", "command": "run_autonomous", "requestId": "auto-e2e-1"}
        )
        ack = websocket.receive_json()
        assert ack["accepted"] is True
        deadline = time.time() + 20.0
        while time.time() < deadline:
            seeded_session.expire_all()
            first = seeded_session.get(CompanyTask, fix.task.id)
            second = seeded_session.get(CompanyTask, fix.other_task.id)
            assert first is not None and second is not None
            if (
                first.status is TaskStatus.COMPLETED
                and second.status is TaskStatus.COMPLETED
            ):
                break
            time.sleep(0.05)
        else:
            pytest.fail("autonomous loop did not complete the board in 20s")
