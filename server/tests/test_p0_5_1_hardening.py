"""P0.5.1 budget hardening: exhaustion events and an injectable accounting clock.

Two gaps in P0.5, closed here.

``budget_limit_reached`` existed in the catalogue but nothing emitted it. The
distinction it draws is the whole point: a reservation that is merely *larger* than
what remains leaves funds available and says nothing about a ceiling being empty,
while a ceiling whose available amount reaches zero has genuinely stopped accepting
money.

The accounting clock was not injectable, so month rollover could only be tested by
arithmetic rather than by standing on a boundary. It is now a constructor argument,
defaulting to the real UTC clock.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.events.bus import get_event_bus
from app.events.types import EVENT_CATALOGUE, EventCategory, EventType
from app.models import BudgetAccount, BudgetLedgerCategory, BudgetReservation
from app.schemas.budget import BudgetAdjustmentRequest
from app.services.budget import BudgetService
from app.services.events import EventService
from tests.p0_5_helpers import make_spendable_company, reserve_request, settle_request

FRONTEND_EVENTS_TS = (
    Path(__file__).resolve().parents[2] / "kayan-3d" / "src" / "types" / "events.ts"
)

JAN_31_LAST_INSTANT = datetime(2026, 1, 31, 23, 59, 59, 999_999, tzinfo=timezone.utc)
FEB_1_FIRST_INSTANT = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
JAN_1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
#: Future dates, for the rule that reads the *most recent* recorded ceiling.
NEXT_YEAR_JAN_31 = datetime(2027, 1, 31, 23, 59, 59, 999_999, tzinfo=timezone.utc)
NEXT_YEAR_FEB_1 = datetime(2027, 2, 1, 0, 0, 0, tzinfo=timezone.utc)


def events_of(session, event_type):
    return [
        event
        for event in EventService(session).list_events(stream_id="main", limit=1000)
        if event.event_type == event_type
    ]


def exhaustion_events(session, level=None):
    found = events_of(session, "budget_limit_reached")
    if level is None:
        return found
    return [event for event in found if event.payload["level"] == level]


def fixed_clock(moment: datetime):
    return lambda: moment


def accounts_in(session, company_id, period_start):
    return (
        session.query(BudgetAccount)
        .filter_by(company_id=company_id, period_start=period_start)
        .count()
    )


def reachable_ceilings(session):
    """A company whose allocations exactly fill its ceiling.

    Contract generation refuses allocations above the company ceiling, so the only
    way a *reservation* can empty the company ceiling is when the allocated total
    equals it and every allocation is committed. That is what this fixture sets up.
    """
    return make_spendable_company(
        session,
        ceiling="50",
        seller_monthly="40",
        seller_per_task="40",
        owner_monthly="10",
    )


def commit_everything(live, budget):
    """Commit the whole company allocation and return the three reservations.

    The seller's 40 is split across two tasks of 40 each, so neither task ceiling is
    emptied; the company and employee ceilings are.
    """
    first = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "20", "k1")
    )
    second = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.other_task.id, "20", "k2")
    )
    owner_contract = live.contract_for(live.owner.id)
    owner_task = live.make_task(live.owner.id, owner_contract.task_scope[0])
    third = budget.reserve(
        reserve_request(live.company_id, live.owner.id, owner_task.id, "10", "k3")
    )
    return first, second, third, owner_task


# -- semantics: exhaustion is not the same as a refusal ------------------------


def test_refused_with_money_remaining_reports_no_exhaustion(seeded_session):
    """A request bigger than the remainder leaves funds available. No ceiling is empty."""
    live = make_spendable_company(
        seeded_session, ceiling="1000", seller_monthly="100", seller_per_task="100"
    )
    budget = BudgetService(seeded_session)

    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "500", "k1")
    )

    assert result.allowed is False
    assert result.denied.available == Decimal("100")
    assert result.denied.available > Decimal("0")
    assert events_of(seeded_session, "budget_reservation_denied")
    assert events_of(seeded_session, "budget_limit_reached") == []


def test_a_reservation_that_empties_a_ceiling_reports_exhaustion(seeded_session):
    """The ceiling reaches zero available, so it can no longer accept money."""
    live = reachable_ceilings(seeded_session)
    budget = BudgetService(seeded_session)

    budget.reserve(reserve_request(live.company_id, live.seller_id, live.task.id, "20", "k1"))
    assert events_of(seeded_session, "budget_limit_reached") == []

    commit_everything(live, budget)

    company = exhaustion_events(seeded_session, "company")
    assert len(company) == 1
    assert company[0].payload["availableAmount"] == "0"
    assert company[0].payload["trigger"] == "reservation_consumed_remaining_budget"
    assert budget.summary(live.company_id).available == Decimal("0")
    # Splitting the seller's work across two tasks of 40 each left both task
    # ceilings open; only the owner's smaller task ceiling emptied.
    assert not any(
        event.payload["taskId"] in (live.task.id, live.other_task.id)
        for event in exhaustion_events(seeded_session, "task")
    )
    assert exhaustion_events(seeded_session, "task")


def test_adjusting_the_ceiling_onto_committed_spend_reports_exhaustion(seeded_session):
    """Lowering the ceiling onto the money already committed empties it.

    The adjustment is the transition that takes available to zero, so it reports the
    exhaustion itself: there is no reason to wait for the next refusal to discover a
    state the system already knows. A later refusal at the now-empty ceiling is silent,
    because nothing about the state changed in between.
    """
    live = make_spendable_company(
        seeded_session,
        ceiling="1000",
        seller_monthly="40",
        seller_per_task="40",
        owner_monthly="10",
    )
    budget = BudgetService(seeded_session)

    held = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, held.reservation_id, "40", "s1"))

    owner_contract = live.contract_for(live.owner.id)
    owner_task = live.make_task(live.owner.id, owner_contract.task_scope[0])
    owner_held = budget.reserve(
        reserve_request(live.company_id, live.owner.id, owner_task.id, "10", "k2")
    )
    budget.settle(settle_request(live.company_id, owner_held.reservation_id, "10", "s2"))

    # Every allocated unit is now spent, so the ceiling can be set exactly there.
    budget.adjust_monthly_limit(
        live.company_id,
        BudgetAdjustmentRequest(
            newMonthlyLimit="50",
            currency="USD",
            reason="match committed spend",
            idempotencyKey="adj-1",
        ),
    )
    assert budget.summary(live.company_id).available == Decimal("0")
    reported = exhaustion_events(seeded_session, "company")
    assert len(reported) == 1
    assert reported[0].payload["trigger"] == "budget_adjusted"

    refused = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "5", "k3")
    )

    assert refused.allowed is False
    assert refused.denied.available == Decimal("0")
    # The empty ceiling was already announced by the adjustment; the refusal adds
    # nothing, because the state it observed is the state that was already reported.
    assert len(exhaustion_events(seeded_session, "company")) == 1


def test_lowering_the_ceiling_with_funds_available_reports_no_exhaustion(seeded_session):
    """A reduction that leaves funds available does not empty the ceiling."""
    live = make_spendable_company(
        seeded_session, ceiling="1000", seller_monthly="400", seller_per_task="100"
    )
    budget = BudgetService(seeded_session)
    budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "100", "k1")
    )

    budget.adjust_monthly_limit(
        live.company_id,
        BudgetAdjustmentRequest(
            newMonthlyLimit="500",
            currency="USD",
            reason="trim the ceiling",
            idempotencyKey="adj-1",
        ),
    )

    assert budget.summary(live.company_id).available == Decimal("400")
    assert exhaustion_events(seeded_session, "company") == []


def test_repeated_refusals_at_an_empty_ceiling_are_reported_once(seeded_session):
    """Nothing about the state changed, so the state is not re-announced."""
    live = reachable_ceilings(seeded_session)
    budget = BudgetService(seeded_session)

    commit_everything(live, budget)
    assert len(exhaustion_events(seeded_session, "company")) == 1

    for key in ("k4", "k5", "k6"):
        result = budget.reserve(
            reserve_request(live.company_id, live.seller_id, live.task.id, "1", key)
        )
        assert result.allowed is False
        assert result.denied.available == Decimal("0")

    assert len(exhaustion_events(seeded_session, "company")) == 1
    assert len(events_of(seeded_session, "budget_reservation_denied")) == 3


def test_restoring_capacity_then_emptying_again_is_a_new_transition(seeded_session):
    live = reachable_ceilings(seeded_session)
    budget = BudgetService(seeded_session)

    _, _, third, owner_task = commit_everything(live, budget)
    assert len(exhaustion_events(seeded_session, "company")) == 1

    # Returning the commitment empties nothing, so it stays unreported.
    budget.release(third.reservation_id, idempotency_key="r1")
    assert budget.summary(live.company_id).available == Decimal("10")
    assert len(exhaustion_events(seeded_session, "company")) == 1

    second_owner_task = live.make_task(live.owner.id, owner_task.category)
    budget.reserve(
        reserve_request(live.company_id, live.owner.id, second_owner_task.id, "10", "k4")
    )

    assert len(exhaustion_events(seeded_session, "company")) == 2
    assert budget.summary(live.company_id).available == Decimal("0")


def test_the_ledger_records_the_exhaustion_without_changing_any_balance(seeded_session):
    live = reachable_ceilings(seeded_session)
    budget = BudgetService(seeded_session)

    commit_everything(live, budget)

    markers = [
        entry
        for entry in budget.ledger(live.company_id, limit=100)
        if entry.category is BudgetLedgerCategory.BUDGET_LIMIT_REACHED
    ]
    reported = events_of(seeded_session, "budget_limit_reached")
    assert len(markers) == len(reported)
    assert markers
    # History, not money: a marker must never move a balance.
    assert all(Decimal(marker.amount) == Decimal("0") for marker in markers)
    assert all(marker.currency == "USD" for marker in markers)
    assert budget.summary(live.company_id).actual_spend == Decimal("0")


# -- payload and ordering -----------------------------------------------------


def test_the_event_names_the_company_level_and_currency(seeded_session):
    live = reachable_ceilings(seeded_session)
    budget = BudgetService(seeded_session)

    commit_everything(live, budget)

    payload = exhaustion_events(seeded_session, "company")[0].payload
    assert payload["companyId"] == live.company_id
    assert payload["currency"] == "USD"
    assert payload["limitAmount"] == "50.000000"
    assert payload["availableAmount"] == "0"
    assert payload["accountId"].startswith("bac_")
    assert payload["periodStart"][:7] == "2026-10"


def test_an_employee_exhaustion_names_the_employee(seeded_session):
    # Two tasks, so the employee's allocation empties while both tasks still have room.
    live = make_spendable_company(
        seeded_session, ceiling="1000", seller_monthly="40", seller_per_task="40"
    )
    budget = BudgetService(seeded_session)

    budget.reserve(reserve_request(live.company_id, live.seller_id, live.task.id, "20", "k1"))
    budget.reserve(reserve_request(live.company_id, live.seller_id, live.other_task.id, "20", "k2"))

    reported = exhaustion_events(seeded_session, "employee")
    assert len(reported) == 1
    assert reported[0].payload["employeeId"] == live.seller_id
    assert reported[0].payload["limitAmount"] == "40.000000"
    assert exhaustion_events(seeded_session, "task") == []


def test_a_task_exhaustion_names_the_task(seeded_session):
    live = make_spendable_company(
        seeded_session,
        ceiling="1000",
        seller_monthly="500",
        seller_per_task="40",
    )
    budget = BudgetService(seeded_session)

    budget.reserve(reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1"))

    reported = exhaustion_events(seeded_session, "task")
    assert len(reported) == 1
    assert reported[0].payload["taskId"] == live.task.id
    assert reported[0].payload["employeeId"] == live.seller_id
    assert reported[0].payload["limitAmount"] == "40.000000"
    assert exhaustion_events(seeded_session, "company") == []


def test_the_reservation_is_recorded_before_the_exhaustion(seeded_session):
    """Ordering follows the sequence assigned inside the one transaction."""
    live = reachable_ceilings(seeded_session)
    budget = BudgetService(seeded_session)

    commit_everything(live, budget)

    stream = EventService(seeded_session).list_events(stream_id="main", limit=1000)
    reserved = [e for e in stream if e.event_type == "budget_reserved"][-1]
    exhausted = [
        e
        for e in stream
        if e.event_type == "budget_limit_reached"
        and e.payload["billableOperationId"] == "op-k3"
    ]
    assert exhausted
    assert all(event.sequence > reserved.sequence for event in exhausted)


def test_the_ceiling_adjustment_is_recorded_before_the_exhaustion_it_establishes(
    seeded_session,
):
    """The adjustment is the fact; the exhaustion it causes follows it in the stream."""
    live = make_spendable_company(
        seeded_session,
        ceiling="1000",
        seller_monthly="40",
        seller_per_task="40",
        owner_monthly="10",
    )
    budget = BudgetService(seeded_session)
    held = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, held.reservation_id, "40", "s1"))
    owner_contract = live.contract_for(live.owner.id)
    owner_task = live.make_task(live.owner.id, owner_contract.task_scope[0])
    owner_held = budget.reserve(
        reserve_request(live.company_id, live.owner.id, owner_task.id, "10", "k2")
    )
    budget.settle(settle_request(live.company_id, owner_held.reservation_id, "10", "s2"))
    budget.adjust_monthly_limit(
        live.company_id,
        BudgetAdjustmentRequest(
            newMonthlyLimit="50",
            currency="USD",
            reason="match committed spend",
            idempotencyKey="adj-1",
        ),
    )

    stream = EventService(seeded_session).list_events(stream_id="main", limit=1000)
    adjusted = [e for e in stream if e.event_type == "budget_adjusted"][-1]
    exhausted = [e for e in stream if e.event_type == "budget_limit_reached"][-1]
    assert adjusted.sequence < exhausted.sequence


def test_nothing_is_published_when_the_transaction_fails(seeded_session, monkeypatch):
    """A failure after the reservation is staged must publish nothing at all."""
    live = reachable_ceilings(seeded_session)
    budget = BudgetService(seeded_session)

    # The first 20 leaves the employee's allocation half full; the second empties it,
    # so this reserve is the one that stages budget_reserved and then the exhaustion.
    budget.reserve(reserve_request(live.company_id, live.seller_id, live.task.id, "20", "k1"))

    published: list[dict] = []
    unsubscribe = get_event_bus().subscribe(published.append)

    real_stage = budget._events.stage
    calls = {"n": 0}

    def exploding_stage(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # the exhaustion event, staged after budget_reserved
            raise RuntimeError("storage failed mid-reservation")
        return real_stage(**kwargs)

    monkeypatch.setattr(budget._events, "stage", exploding_stage)

    try:
        with pytest.raises(RuntimeError):
            budget.reserve(
                reserve_request(live.company_id, live.seller_id, live.other_task.id, "20", "k2")
            )
        seeded_session.rollback()

        def for_operation(event_type):
            return [
                event
                for event in events_of(seeded_session, event_type)
                if event.payload.get("billableOperationId") == "op-k2"
            ]

        assert for_operation("budget_limit_reached") == []
        assert for_operation("budget_reserved") == []
        assert seeded_session.query(BudgetReservation).filter_by(
            billable_operation_id="op-k2"
        ).count() == 0
        assert published == []
    finally:
        unsubscribe()


def test_a_replayed_request_publishes_nothing_new(seeded_session):
    live = make_spendable_company(
        seeded_session, ceiling="1000", seller_monthly="40", seller_per_task="40"
    )
    budget = BudgetService(seeded_session)
    budget.reserve(reserve_request(live.company_id, live.seller_id, live.task.id, "20", "k1"))
    request = reserve_request(live.company_id, live.seller_id, live.other_task.id, "20", "k2")

    budget.reserve(request)
    before = len(events_of(seeded_session, "budget_limit_reached"))
    assert before == 1  # the employee's allocation emptied

    published: list[dict] = []
    unsubscribe = get_event_bus().subscribe(published.append)
    try:
        replay = budget.reserve(request)
    finally:
        unsubscribe()

    assert replay.replayed is True
    assert len(events_of(seeded_session, "budget_limit_reached")) == before
    assert published == []


# -- catalogue parity ---------------------------------------------------------


def test_the_backend_catalogue_keeps_budget_limit_reached_in_governance():
    assert EventType("budget_limit_reached") is EventType.BUDGET_LIMIT_REACHED
    assert EVENT_CATALOGUE[EventType.BUDGET_LIMIT_REACHED] is EventCategory.GOVERNANCE


def test_the_frontend_catalogue_agrees_with_the_backend():
    if not FRONTEND_EVENTS_TS.exists():
        pytest.skip("frontend catalogue not present in this checkout")
    source = FRONTEND_EVENTS_TS.read_text(encoding="utf-8")

    union = source.split("export type KayanEventType =", 1)[1].split(";", 1)[0]
    assert "budget_limit_reached" in set(re.findall(r"'([a-z_]+)'", union))

    definitions = source.split("export const EVENT_DEFS", 1)[1]
    frontend_defs = dict(
        re.findall(r"(\w+):\s*\{[^}]*?category:\s*'(\w+)'", definitions, re.S)
    )
    backend = {event.value: category.value for event, category in EVENT_CATALOGUE.items()}
    assert backend == frontend_defs
    assert frontend_defs["budget_limit_reached"] == "governance"


# -- the accounting clock -----------------------------------------------------


def test_the_last_instant_of_a_month_still_belongs_to_that_month(seeded_session):
    live = make_spendable_company(seeded_session)
    budget = BudgetService(seeded_session, clock=fixed_clock(JAN_31_LAST_INSTANT))
    company = budget._companies.get_company(live.company_id)

    account = budget.current_account(company)

    assert account.period_start.replace(tzinfo=timezone.utc) == JAN_1
    assert account.period_end.replace(tzinfo=timezone.utc) == FEB_1_FIRST_INSTANT


def test_the_first_instant_of_the_next_month_opens_a_new_period(seeded_session):
    live = make_spendable_company(seeded_session)
    company = live.company

    january = BudgetService(
        seeded_session, clock=fixed_clock(JAN_31_LAST_INSTANT)
    ).current_account(company)
    february = BudgetService(
        seeded_session, clock=fixed_clock(FEB_1_FIRST_INSTANT)
    ).current_account(company)

    assert january.id != february.id
    assert february.period_start.replace(tzinfo=timezone.utc) == FEB_1_FIRST_INSTANT
    assert february.period_end.replace(tzinfo=timezone.utc) == datetime(
        2026, 3, 1, tzinfo=timezone.utc
    )


def test_lookup_and_creation_are_idempotent_within_one_period(seeded_session):
    live = make_spendable_company(seeded_session)
    budget = BudgetService(seeded_session, clock=fixed_clock(FEB_1_FIRST_INSTANT))
    company = budget._companies.get_company(live.company_id)

    first = budget.current_account(company)
    second = budget.current_account(company)

    assert first.id == second.id
    # One account for February. The real-time account opened when the company was
    # created belongs to a different period and is untouched.
    assert accounts_in(seeded_session, live.company_id, FEB_1_FIRST_INSTANT) == 1


def test_opening_a_new_period_leaves_the_previous_period_untouched(seeded_session):
    live = make_spendable_company(
        seeded_session, ceiling="1000", seller_monthly="100", seller_per_task="100"
    )
    january = BudgetService(seeded_session, clock=fixed_clock(JAN_31_LAST_INSTANT))
    held = january.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "60", "k1")
    )
    january.settle(settle_request(live.company_id, held.reservation_id, "60", "s1"))
    january_account = january.current_account(
        january._companies.get_company(live.company_id)
    )
    january_ledger = [
        (entry.id, entry.category, str(entry.amount))
        for entry in january.ledger(live.company_id, limit=100)
    ]

    february = BudgetService(seeded_session, clock=fixed_clock(FEB_1_FIRST_INSTANT))
    february_account = february.current_account(
        february._companies.get_company(live.company_id)
    )

    assert february_account.id != january_account.id
    # February starts clean: spend belongs to the month it happened.
    assert february._spend_for_account(february_account) == Decimal("0")
    assert february._outstanding(account_id=february_account.id) == Decimal("0")
    # January is neither reset nor rewritten.
    assert january._spend_for_account(january_account) == Decimal("60")
    assert [
        (entry.id, entry.category, str(entry.amount))
        for entry in january.ledger(live.company_id, limit=100)
    ] == january_ledger


def test_a_new_period_carries_the_configured_ceiling_forward(seeded_session):
    """Documented rule: a new month starts from the most recent ceiling.

    The clock is set in the future, because the rule reads the account with the
    latest period start: a January date would be *older* than the account opened when
    the company was created, so it would not be the most recent one.
    """
    live = make_spendable_company(seeded_session, ceiling="1000")
    january = BudgetService(seeded_session, clock=fixed_clock(NEXT_YEAR_JAN_31))
    january.adjust_monthly_limit(
        live.company_id,
        BudgetAdjustmentRequest(
            newMonthlyLimit="777",
            currency="USD",
            reason="quarterly plan",
            idempotencyKey="adj-1",
        ),
    )
    assert january.summary(live.company_id).monthly_limit == Decimal("777")

    february = BudgetService(seeded_session, clock=fixed_clock(NEXT_YEAR_FEB_1))
    carried = february.current_account(
        february._companies.get_company(live.company_id)
    )

    assert carried.monthly_limit == Decimal("777")
    assert carried.currency == "USD"
    assert february.summary(live.company_id).monthly_limit == Decimal("777")


def test_a_reservation_stays_with_the_period_that_approved_it(seeded_session):
    live = make_spendable_company(
        seeded_session, ceiling="1000", seller_monthly="100", seller_per_task="100"
    )
    january = BudgetService(seeded_session, clock=fixed_clock(JAN_31_LAST_INSTANT))
    result = january.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "60", "k1")
    )
    january_account = january.current_account(
        january._companies.get_company(live.company_id)
    )

    february = BudgetService(seeded_session, clock=fixed_clock(FEB_1_FIRST_INSTANT))
    february_account = february.current_account(
        february._companies.get_company(live.company_id)
    )

    stored = seeded_session.get(BudgetReservation, result.reservation_id)
    assert stored.account_id == january_account.id
    assert stored.account_id != february_account.id
    # February is unaffected by January's outstanding commitment.
    assert february._outstanding(account_id=february_account.id) == Decimal("0")


def test_an_explicit_instant_overrides_the_service_clock(seeded_session):
    live = make_spendable_company(seeded_session)
    budget = BudgetService(seeded_session, clock=fixed_clock(FEB_1_FIRST_INSTANT))
    company = budget._companies.get_company(live.company_id)

    account = budget.current_account(company, now=JAN_31_LAST_INSTANT)

    assert account.period_start.replace(tzinfo=timezone.utc) == JAN_1


def test_production_defaults_to_the_real_utc_clock(seeded_session):
    from app.services.companies import current_period

    live = make_spendable_company(seeded_session)
    budget = BudgetService(seeded_session)

    account = budget.current_account(budget._companies.get_company(live.company_id))
    start, end = current_period()

    assert account.period_start.replace(tzinfo=timezone.utc) == start
    assert account.period_end.replace(tzinfo=timezone.utc) == end


def test_a_naive_instant_is_refused_rather_than_guessed(seeded_session):
    live = make_spendable_company(seeded_session)
    budget = BudgetService(seeded_session)
    company = budget._companies.get_company(live.company_id)

    with pytest.raises(ValueError) as caught:
        budget.current_account(company, now=datetime(2026, 1, 31, 23, 59, 59))

    assert "timezone-aware" in str(caught.value)