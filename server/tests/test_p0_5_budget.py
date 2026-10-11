"""P0.5 reservation, settlement and release.

The invariants under test are the ones that decide whether the system can be trusted
with money: every ceiling is enforced, nothing is trusted from the caller, a repeated
request cannot spend twice, and a refusal leaves evidence without leaving a charge.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.company.errors import ConfigurationError, ConflictError, NotFoundError
from app.models import (
    BudgetLedgerCategory,
    BudgetReservation,
    BudgetReservationStatus,
    CompanyEmployee,
    CompanyStatus,
    ContractStatus,
    MeterSource,
)
from app.schemas.budget import BudgetReservationRequest, BudgetSettlementRequest
from app.services.budget import BudgetService
from app.services.events import EventService
from app.services.execution import BudgetedExecutor, PolicyDenied
from app.services.metering import MeteredUsage, MockCostMeter
from app.models import CostCategory
from tests.p0_5_helpers import make_spendable_company, reserve_request, settle_request


@pytest.fixture()
def live(seeded_session):
    return make_spendable_company(seeded_session)


@pytest.fixture()
def budget(seeded_session, live):
    return BudgetService(seeded_session)


def events_of(session, event_type):
    return [
        event
        for event in EventService(session).list_events(stream_id="main", limit=1000)
        if event.event_type == event_type
    ]


# -- reservation ------------------------------------------------------------


def test_sufficient_funds_permit_a_reservation(seeded_session, live, budget):
    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    assert result.allowed is True
    assert result.reserved_amount == Decimal("40")
    assert result.reservation_id
    assert result.available_after == Decimal("960")

    reservation = seeded_session.get(BudgetReservation, result.reservation_id)
    assert reservation.status is BudgetReservationStatus.ACTIVE
    assert reservation.billable_operation_id == "op-k1"


def test_insufficient_company_funds_deny_the_reservation(seeded_session, live, budget):
    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "5000", "k1")
    )

    assert result.allowed is False
    assert "company period" in result.denied.scope
    assert result.reservation_id is None
    assert seeded_session.query(BudgetReservation).count() == 0


def test_insufficient_employee_funds_deny_the_reservation(seeded_session, live, budget):
    """The company has plenty; the employee's contract allocation does not."""
    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "450", "k1")
    )

    assert result.allowed is False
    assert "employee monthly" in result.denied.scope


def test_insufficient_task_funds_deny_the_reservation(seeded_session, live, budget):
    """Aggregated across operations on that task, not per call."""
    assert budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "70", "k1")
    ).allowed

    second = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k2")
    )

    assert second.allowed is False
    assert "task" in second.denied.scope


def test_the_tightest_ceiling_decides(seeded_session, live, budget):
    """Fits the company, fails the employee: refused."""
    budget.adjust_monthly_limit(
        live.company_id,
        __import__(
            "app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]
        ).BudgetAdjustmentRequest(
            newMonthlyLimit="9000", currency="USD", reason="room", idempotencyKey="adj"
        ),
    )
    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "450", "k1")
    )

    assert result.allowed is False
    assert "employee monthly" in result.denied.scope


def test_a_draft_company_cannot_reserve(seeded_session, budget):
    draft = make_spendable_company(seeded_session, activate=False)

    with pytest.raises(ConflictError) as caught:
        budget.reserve(
            reserve_request(draft.company_id, draft.seller_id, draft.task.id, "1", "k1")
        )
    assert "draft" in str(caught.value)


def test_a_paused_company_cannot_reserve(seeded_session, live, budget):
    from app.services.lifecycle import CompanyLifecycleService

    CompanyLifecycleService(seeded_session).pause(live.company_id)

    with pytest.raises(ConflictError) as caught:
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, live.task.id, "1", "k1")
        )
    assert "paused" in str(caught.value)


def test_an_employee_without_an_active_contract_is_refused(seeded_session, live, budget):
    """Configuration alone does not authorise spending."""
    employee = seeded_session.get(CompanyEmployee, live.seller_id)
    employee.active_contract_id = None
    seeded_session.commit()

    with pytest.raises(ConflictError) as caught:
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, live.task.id, "1", "k1")
        )
    assert "no active contract" in str(caught.value)


def test_a_superseded_contract_cannot_authorise_spending(seeded_session, live, budget):
    contract = live.contract_for(live.seller_id)
    contract.status = ContractStatus.SUPERSEDED
    seeded_session.commit()

    with pytest.raises(ConflictError):
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, live.task.id, "1", "k1")
        )


def test_a_contract_whose_terms_were_tampered_cannot_authorise_spending(
    seeded_session, live, budget
):
    contract = live.contract_for(live.seller_id)
    contract.budget_per_month = Decimal("999999")  # hash no longer matches
    seeded_session.commit()

    with pytest.raises(ConflictError) as caught:
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, live.task.id, "1", "k1")
        )
    assert "integrity check" in str(caught.value)


def test_a_caller_cannot_supply_the_limits(seeded_session, live, budget):
    """Extra fields are refused rather than ignored: no caller-supplied budget."""
    with pytest.raises(Exception):
        BudgetReservationRequest(
            companyId=live.company_id,
            employeeId=live.seller_id,
            taskId=live.task.id,
            maximumAmount="1",
            idempotencyKey="k1",
            billableOperationId="op",
            budgetPerMonth="999999",
        )


def test_an_unknown_employee_is_refused(seeded_session, live, budget):
    with pytest.raises(NotFoundError):
        budget.reserve(
            reserve_request(live.company_id, "emp_nobody", live.task.id, "1", "k1")
        )


def test_an_employee_of_another_company_is_refused(seeded_session, live, budget):
    other = make_spendable_company(seeded_session, ceiling="5000", activate=False)

    with pytest.raises(NotFoundError):
        budget.reserve(
            reserve_request(live.company_id, other.seller_id, live.task.id, "1", "k1")
        )


def test_a_missing_task_is_refused(seeded_session, live, budget):
    with pytest.raises(ConfigurationError) as caught:
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, None, "1", "k1")
        )
    assert "taskId is required" in str(caught.value)


def test_a_task_belonging_to_another_employee_is_refused(seeded_session, live, budget):
    stranger_task = live.make_task(live.owner.id, "quotation")

    with pytest.raises(ConfigurationError) as caught:
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, stranger_task.id, "1", "k1")
        )
    assert "not assigned" in str(caught.value)


def test_a_task_outside_the_contract_category_is_refused(seeded_session, live, budget):
    out_of_scope = live.make_task(live.seller_id, "teleportation")

    with pytest.raises(ConfigurationError) as caught:
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, out_of_scope.id, "1", "k1")
        )
    assert "does not permit" in str(caught.value)


def test_a_duplicate_reservation_does_not_double_reserve(seeded_session, live, budget):
    first = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    second = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    assert second.reservation_id == first.reservation_id
    assert second.replayed is True
    assert seeded_session.query(BudgetReservation).count() == 1
    assert budget.summary(live.company_id).outstanding_reservations == Decimal("40")


def test_reusing_a_key_with_different_parameters_is_a_conflict(seeded_session, live, budget):
    budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    with pytest.raises(ConflictError) as caught:
        budget.reserve(
            reserve_request(live.company_id, live.seller_id, live.task.id, "60", "k1")
        )
    assert "different reservation" in str(caught.value)


def test_a_denied_reservation_is_recorded_but_creates_no_reservation(
    seeded_session, live, budget
):
    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "9999", "k1")
    )

    assert result.allowed is False
    assert seeded_session.query(BudgetReservation).count() == 0
    denials = [
        entry
        for entry in budget.ledger(live.company_id, limit=50)
        if entry.category is BudgetLedgerCategory.RESERVATION_DENIED
    ]
    assert len(denials) == 1
    assert events_of(seeded_session, "budget_reservation_denied")
    assert not events_of(seeded_session, "budget_reserved")


def test_a_repeated_denial_replays_the_recorded_refusal(seeded_session, live, budget):
    request = reserve_request(
        live.company_id, live.seller_id, live.task.id, "9999", "k1"
    )
    first = budget.reserve(request)
    second = budget.reserve(request)

    assert second.replayed is True
    assert second.denied.reason == first.denied.reason
    assert len(events_of(seeded_session, "budget_reservation_denied")) == 1


def test_reservation_emits_budget_reserved(seeded_session, live, budget):
    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    events = events_of(seeded_session, "budget_reserved")
    assert len(events) == 1
    payload = events[0].payload
    assert payload["reservationId"] == result.reservation_id
    assert payload["amount"] == "40.000000"
    assert payload["companyId"] == live.company_id
    assert events[0].run_id is None
    assert events[0].clock_offset_ms is None


# -- settlement -------------------------------------------------------------


def test_settlement_records_the_actual_charge(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    settled = budget.settle(
        settle_request(live.company_id, reserved.reservation_id, "12.50", "s1")
    )

    assert settled.charged_amount == Decimal("12.50")
    assert settled.released_amount == Decimal("27.50")
    summary = budget.summary(live.company_id)
    assert summary.actual_spend == Decimal("12.50")
    assert summary.outstanding_reservations == ZERO
    assert summary.available == summary.monthly_limit - Decimal("12.50")


ZERO = Decimal("0")


def test_settlement_releases_the_unused_remainder(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "9", "s1"))

    categories = {
        entry.category: entry.amount
        for entry in budget.ledger(live.company_id, limit=50)
    }
    assert categories[BudgetLedgerCategory.ACTUAL_COST_CHARGED] == Decimal("9")
    assert categories[BudgetLedgerCategory.RESERVATION_RELEASED] == Decimal("-31")


def test_an_identical_settlement_retry_does_not_charge_twice(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    request = settle_request(live.company_id, reserved.reservation_id, "12", "s1")

    first = budget.settle(request)
    second = budget.settle(request)

    assert second.replayed is True
    assert second.charged_amount == first.charged_amount
    assert budget.summary(live.company_id).actual_spend == Decimal("12")


def test_a_conflicting_settlement_retry_is_rejected(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "12", "s1"))

    with pytest.raises(ConflictError) as caught:
        budget.settle(settle_request(live.company_id, reserved.reservation_id, "20", "s1"))
    assert "already used" in str(caught.value)


def test_a_negative_settlement_is_refused(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    with pytest.raises(ConfigurationError):
        budget.settle(settle_request(live.company_id, reserved.reservation_id, "-1", "s1"))


def test_settling_more_than_reserved_is_an_explicit_reconciliation_failure(
    seeded_session, live, budget
):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    with pytest.raises(ConflictError) as caught:
        budget.settle(settle_request(live.company_id, reserved.reservation_id, "50", "s1"))

    assert "exceeds the reserved maximum" in str(caught.value)
    assert caught.value.details["difference"] == "10.000000"
    # The money stays committed, so the discrepancy cannot be bypassed by spending on.
    reservation = seeded_session.get(BudgetReservation, reserved.reservation_id)
    assert reservation.status is BudgetReservationStatus.ACTIVE
    assert budget.summary(live.company_id).actual_spend == ZERO


def test_settling_twice_is_refused(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "12", "s1"))

    with pytest.raises(ConflictError) as caught:
        budget.settle(settle_request(live.company_id, reserved.reservation_id, "12", "other"))
    assert "is settled" in str(caught.value)


# -- release ----------------------------------------------------------------


def test_release_returns_uncommitted_money(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    released = budget.release(reserved.reservation_id, idempotency_key="r1")

    assert released.released_amount == Decimal("40")
    assert budget.summary(live.company_id).outstanding_reservations == ZERO
    assert events_of(seeded_session, "budget_released")


def test_a_duplicate_release_does_not_release_twice(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )

    first = budget.release(reserved.reservation_id, idempotency_key="r1")
    second = budget.release(reserved.reservation_id, idempotency_key="r1")

    assert second.replayed is True
    assert second.released_amount == first.released_amount
    releases = [
        entry
        for entry in budget.ledger(live.company_id, limit=50)
        if entry.category is BudgetLedgerCategory.RESERVATION_RELEASED
    ]
    assert len(releases) == 1


def test_a_settled_reservation_cannot_be_released(seeded_session, live, budget):
    """The money was spent; releasing it would erase a real cost."""
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "25", "s1"))

    with pytest.raises(ConflictError) as caught:
        budget.release(reserved.reservation_id, idempotency_key="r1")
    assert "refund or adjustment" in str(caught.value)
    assert budget.summary(live.company_id).actual_spend == Decimal("25")


def test_releasing_an_unknown_reservation_is_not_found(seeded_session, budget):
    with pytest.raises(NotFoundError):
        budget.release("res_nope", idempotency_key="r1")


# -- summary and ledger -----------------------------------------------------


def test_summary_is_derived_not_stored(seeded_session, live, budget):
    budget.reserve(reserve_request(live.company_id, live.seller_id, live.task.id, "30", "k1"))
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.other_task.id, "20", "k2")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "5", "s1"))

    summary = budget.summary(live.company_id)

    assert summary.monthly_limit == Decimal("1000")
    assert summary.actual_spend == Decimal("5")
    assert summary.outstanding_reservations == Decimal("30")
    assert summary.available == Decimal("965")
    assert summary.currency == "USD"

    allocation = next(
        row for row in summary.employee_allocations if row.employee_id == live.seller_id
    )
    assert allocation.monthly_limit == Decimal("400")
    assert allocation.monthly_outstanding == Decimal("30")
    assert allocation.per_task_limit == Decimal("100")


def test_ledger_is_paginated_and_ordered(seeded_session, live, budget):
    for index in range(6):
        budget.reserve(
            reserve_request(
                live.company_id, live.seller_id, live.task.id, "5", f"k{index}", operation=f"op{index}"
            )
        )

    page = budget.ledger(live.company_id, limit=4, offset=0)
    assert len(page) == 4
    # Newest first. Ids are random, so ordering is by time and only breaks ties by id.
    stamps = [entry.created_at for entry in page]
    assert stamps == sorted(stamps, reverse=True)

    following = budget.ledger(live.company_id, limit=4, offset=4)
    assert not {entry.id for entry in page} & {entry.id for entry in following}


def test_ledger_can_be_filtered(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "10", "s1"))

    charged = budget.ledger(
        live.company_id, limit=50, category=BudgetLedgerCategory.ACTUAL_COST_CHARGED
    )
    assert len(charged) == 1
    assert charged[0].amount == Decimal("10")


def test_reservations_are_not_counted_as_spend(seeded_session, live, budget):
    """The classic double-count: a commitment is not a cost."""
    budget.reserve(reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1"))

    summary = budget.summary(live.company_id)

    assert summary.actual_spend == ZERO
    assert summary.outstanding_reservations == Decimal("40")
    assert summary.available == Decimal("960")


def test_balances_reconcile_after_mixed_operations(seeded_session, live, budget):
    a = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "30", "k1")
    )
    b = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.other_task.id, "20", "k2")
    )
    c = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.other_task.id, "10", "k3")
    )
    budget.settle(settle_request(live.company_id, a.reservation_id, "25", "s1"))
    budget.settle(settle_request(live.company_id, b.reservation_id, "18", "s2"))
    budget.release(c.reservation_id, idempotency_key="r1")

    summary = budget.summary(live.company_id)
    assert summary.actual_spend == Decimal("43")
    assert summary.outstanding_reservations == ZERO
    assert summary.available == Decimal("957")

    # The ledger tells the same story.
    spend = budget._spend_for_account(
        seeded_session.get(type(None) or None, None) if False else _account(budget, live)
    )
    assert spend == Decimal("43")


def _account(budget, live):
    company = seeded_get(budget, live)
    return budget.current_account(company)


def seeded_get(budget, live):
    from app.models import Company

    return budget._session.get(Company, live.company_id)


# -- adjustments -----------------------------------------------------------


def test_an_adjustment_raises_the_ceiling_and_is_audited(seeded_session, live, budget):
    result = budget.adjust_monthly_limit(
        live.company_id,
        __import__(
            "app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]
        ).BudgetAdjustmentRequest(
            newMonthlyLimit="2500", currency="USD", reason="won a contract", idempotencyKey="a1"
        ),
    )

    assert result.monthly_limit == Decimal("2500")
    assert result.account_version == 2
    entries = [
        entry
        for entry in budget.ledger(live.company_id, limit=50)
        if entry.category is BudgetLedgerCategory.BUDGET_INCREASED
    ]
    assert len(entries) == 1
    assert entries[0].amount == Decimal("1500")
    assert events_of(seeded_session, "budget_adjusted")


def test_a_repeated_adjustment_is_idempotent(seeded_session, live, budget):
    request = __import__(
        "app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]
    ).BudgetAdjustmentRequest(
        newMonthlyLimit="2500", currency="USD", reason="won", idempotencyKey="a1"
    )
    budget.adjust_monthly_limit(live.company_id, request)
    second = budget.adjust_monthly_limit(live.company_id, request)

    assert second.monthly_limit == Decimal("2500")
    assert second.account_version == 2
    assert len([e for e in budget.ledger(live.company_id, limit=50)
                if e.category is BudgetLedgerCategory.BUDGET_INCREASED]) == 1


def test_a_reused_adjustment_key_with_a_different_ceiling_conflicts(seeded_session, live, budget):
    __import__("app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]).BudgetAdjustmentRequest(
        newMonthlyLimit="2500", currency="USD", reason="a", idempotencyKey="a1"
    )
    budget.adjust_monthly_limit(
        live.company_id,
        __import__("app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]).BudgetAdjustmentRequest(
            newMonthlyLimit="2500", currency="USD", reason="a", idempotencyKey="a1"
        ),
    )

    with pytest.raises(ConflictError):
        budget.adjust_monthly_limit(
            live.company_id,
            __import__("app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]).BudgetAdjustmentRequest(
                newMonthlyLimit="3000", currency="USD", reason="b", idempotencyKey="a1"
            ),
        )


def test_a_ceiling_cannot_fall_below_committed_money(seeded_session, live, budget):
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "30", "s1"))

    with pytest.raises(ConflictError) as caught:
        budget.adjust_monthly_limit(
            live.company_id,
            __import__("app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]).BudgetAdjustmentRequest(
                newMonthlyLimit="10", currency="USD", reason="cut", idempotencyKey="a1"
            ),
        )
    assert "below the" in str(caught.value)


def test_a_currency_mismatch_is_refused(seeded_session, live, budget):
    with pytest.raises(ConfigurationError):
        budget.adjust_monthly_limit(
            live.company_id,
            __import__("app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]).BudgetAdjustmentRequest(
                newMonthlyLimit="2000", currency="EUR", reason="x", idempotencyKey="a1"
            ),
        )


def test_a_ceiling_below_active_contract_allocations_is_refused(seeded_session, live, budget):
    with pytest.raises(ConflictError) as caught:
        budget.adjust_monthly_limit(
            live.company_id,
            __import__("app.schemas.budget", fromlist=["BudgetAdjustmentRequest"]).BudgetAdjustmentRequest(
                newMonthlyLimit="450", currency="USD", reason="squeeze", idempotencyKey="a1"
            ),
        )
    assert "contract allocations" in str(caught.value)


# -- the pre-execution seam -------------------------------------------------


def test_a_successful_metered_operation_reserves_executes_and_settles(
    seeded_session, live, budget
):
    meter = MockCostMeter()
    executor = BudgetedExecutor(budget, meter)
    usage = [
        MeteredUsage(category=CostCategory.LLM_INPUT_TOKENS, units=1000, billable_operation_id="op-1"),
        MeteredUsage(category=CostCategory.LLM_OUTPUT_TOKENS, units=500, billable_operation_id="op-1"),
    ]

    outcome = executor.run(
        reservation=reserve_request(
            live.company_id, live.seller_id, live.task.id, "10", "k1", operation="op-1"
        ),
        work=lambda: ("quotation drafted", usage),
    )

    assert outcome.executed is True
    assert outcome.result == "quotation drafted"
    assert outcome.settlement.charged_amount == Decimal("0.002000")
    assert outcome.settlement.released_amount == Decimal("9.998000")
    assert events_of(seeded_session, "budget_charged")


def test_mock_costs_are_labelled_as_simulated(seeded_session, live, budget):
    meter = MockCostMeter()
    executor = BudgetedExecutor(budget, meter)
    outcome = executor.run(
        reservation=reserve_request(
            live.company_id, live.seller_id, live.task.id, "10", "k1", operation="op-1"
        ),
        work=lambda: (
            "done",
            [MeteredUsage(category=CostCategory.TOOL_CALL, units=1, billable_operation_id="op-1")],
        ),
    )
    charge = next(
        event
        for event in events_of(seeded_session, "budget_charged")
    )

    assert charge.payload["meterSource"] == "mock"
    assert outcome.settlement is not None


def test_a_message_is_recorded_but_not_charged_twice(seeded_session, live, budget):
    """A message and the model call behind it are one billable operation."""
    meter = MockCostMeter()
    tool_only = meter.measure(
        [MeteredUsage(category=CostCategory.TOOL_CALL, units=1, billable_operation_id="op-1")],
        currency="USD",
    )
    with_message = meter.measure(
        [
            MeteredUsage(category=CostCategory.TOOL_CALL, units=1, billable_operation_id="op-1"),
            MeteredUsage(category=CostCategory.AGENT_MESSAGE, units=1, billable_operation_id="op-1"),
        ],
        currency="USD",
    )

    assert with_message.total == tool_only.total
    assert with_message.operation_count == 1


def test_an_insufficient_budget_never_invokes_the_work(seeded_session, live, budget):
    calls = {"count": 0}

    def work():
        calls["count"] += 1
        return ("should not happen", [])

    outcome = BudgetedExecutor(budget, MockCostMeter()).run(
        reservation=reserve_request(
            live.company_id, live.seller_id, live.task.id, "99999", "k1", operation="op-1"
        ),
        work=work,
    )

    assert outcome.executed is False
    assert calls["count"] == 0, "the callable must never be reached when money is refused"
    assert outcome.denial_reason


def test_a_policy_denial_stops_before_any_reservation(seeded_session, live, budget):
    executor = BudgetedExecutor(budget, MockCostMeter(), policy=lambda: False)

    with pytest.raises(PolicyDenied):
        executor.run(
            reservation=reserve_request(
                live.company_id, live.seller_id, live.task.id, "1", "k1"
            ),
            work=lambda: ("nope", []),
        )

    assert seeded_session.query(BudgetReservation).count() == 0
    assert events_of(seeded_session, "budget_reserved") == []


def test_budget_availability_never_overrides_a_policy_denial(seeded_session, live, budget):
    """Plenty of money, still denied: security comes first."""
    executor = BudgetedExecutor(budget, MockCostMeter(), policy=lambda: False)

    with pytest.raises(PolicyDenied):
        executor.run(
            reservation=reserve_request(
                live.company_id, live.seller_id, live.task.id, "1", "k1"
            ),
            work=lambda: ("nope", []),
        )
    assert budget.summary(live.company_id).available == Decimal("1000")