"""P0.5 monthly periods and the metering abstraction.

Periods are where accounting quietly goes wrong: a rollover must not reset spend,
must not move an in-flight reservation into a later month, and must not leave two
accounts for one company-period.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models import BudgetAccount, BudgetReservation
from app.schemas.budget import BudgetReservationRequest
from app.services.budget import BudgetService, money
from app.services.companies import current_period
from app.services.metering import MeteredUsage, MockCostMeter, get_meter
from app.models import CostCategory, MeterSource
from tests.p0_5_helpers import make_spendable_company, reserve_request, settle_request


@pytest.fixture()
def live(seeded_session):
    return make_spendable_company(seeded_session)


@pytest.fixture()
def budget(seeded_session, live):
    return BudgetService(seeded_session)


# -- periods ----------------------------------------------------------------


def test_the_account_covers_one_utc_month(seeded_session, live, budget):
    account = budget.current_account(budget._companies.get_company(live.company_id))

    start, end = current_period()
    stored_start = _aware(account.period_start)
    stored_end = _aware(account.period_end)
    assert stored_start == start
    assert stored_end == end
    assert start < end
    assert account.period_start.day == 1
    assert (account.period_end - account.period_start) >= timedelta(days=28)


def _aware(value):
    """SQLite returns naive datetimes; the domain works in UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def test_the_account_is_created_once_per_period(seeded_session, live, budget):
    company = budget._companies.get_company(live.company_id)
    first = budget.current_account(company)
    second = budget.current_account(company)

    assert first.id == second.id
    assert seeded_session.query(BudgetAccount).filter_by(company_id=live.company_id).count() == 1


def test_a_new_period_carries_the_configured_ceiling_forward(seeded_session):
    """Documented rule: a new month starts from the most recent ceiling."""
    company = make_spendable_company(seeded_session, ceiling="1000")
    service = BudgetService(seeded_session)

    account = service.current_account(service._companies.get_company(company.company_id))
    assert account.monthly_limit == Decimal("1000")

    next_start = account.period_start + timedelta(days=32)
    next_end = next_start + timedelta(days=31)
    carried = BudgetAccount(
        id="bac_future",
        company_id=company.company_id,
        currency=account.currency,
        monthly_limit=Decimal("1000"),
        period_start=next_start,
        period_end=next_end,
    )
    seeded_session.add(carried)
    seeded_session.commit()

    latest = seeded_session.query(BudgetAccount).filter_by(
        company_id=company.company_id
    ).order_by(BudgetAccount.period_start.desc()).first()
    assert latest.period_start == next_start


def test_an_earlier_period_is_never_reset_or_deleted(seeded_session):
    company = make_spendable_company(seeded_session, ceiling="1000")
    service = BudgetService(seeded_session)
    account = service.current_account(service._companies.get_company(company.company_id))

    earlier = BudgetAccount(
        id="bac_earlier",
        company_id=company.company_id,
        currency="USD",
        monthly_limit=Decimal("800"),
        period_start=account.period_start - timedelta(days=32),
        period_end=account.period_start - timedelta(days=1),
    )
    seeded_session.add(earlier)
    seeded_session.commit()

    BudgetService(seeded_session).reserve(
        reserve_request(company.company_id, company.seller_id, company.task.id, "100", "k1")
    )

    stored = seeded_session.get(BudgetAccount, "bac_earlier")
    assert stored is not None
    assert stored.monthly_limit == Decimal("800")


def test_a_reservation_stays_linked_to_the_period_it_was_approved_in(seeded_session):
    """An in-flight commitment is not silently reassigned to a later month."""
    live = make_spendable_company(seeded_session, ceiling="1000")
    budget = BudgetService(seeded_session)
    result = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    account = budget.current_account(budget._companies.get_company(live.company_id))

    reservation = seeded_session.get(BudgetReservation, result.reservation_id)
    assert reservation.account_id == account.id

    # A later period appearing does not move it.
    later = BudgetAccount(
        id="bac_later",
        company_id=live.company_id,
        currency="USD",
        monthly_limit=Decimal("1000"),
        period_start=account.period_start + timedelta(days=32),
        period_end=account.period_start + timedelta(days=63),
    )
    seeded_session.add(later)
    seeded_session.commit()

    assert seeded_session.get(BudgetReservation, result.reservation_id).account_id == account.id
    # The later period starts clean, because spend belongs to the month it happened.
    assert budget.current_account(budget._companies.get_company(live.company_id)).id == account.id


def test_spend_is_counted_against_the_period_that_incurred_it(seeded_session):
    live = make_spendable_company(seeded_session, ceiling="1000")
    budget = BudgetService(seeded_session)
    reserved = budget.reserve(
        reserve_request(live.company_id, live.seller_id, live.task.id, "40", "k1")
    )
    budget.settle(settle_request(live.company_id, reserved.reservation_id, "12", "s1"))
    account = budget.current_account(budget._companies.get_company(live.company_id))

    assert budget._spend_for_account(account) == Decimal("12.000000")

    earlier = BudgetAccount(
        id="bac_earlier",
        company_id=live.company_id,
        currency="USD",
        monthly_limit=Decimal("1000"),
        period_start=account.period_start - timedelta(days=32),
        period_end=account.period_start - timedelta(days=1),
    )
    seeded_session.add(earlier)
    seeded_session.commit()

    assert budget._spend_for_account(earlier) == Decimal("0")


def test_period_boundaries_are_utc(seeded_session):
    start, end = current_period(datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc))
    assert start == datetime(2026, 3, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 4, 1, tzinfo=timezone.utc)


def test_money_is_normalised_to_the_stored_scale():
    assert money("40") == Decimal("40.000000")
    assert money(Decimal("12.5")) == Decimal("12.500000")
    assert str(money("1.234567")) == "1.234567"


# -- metering ---------------------------------------------------------------


def test_the_mock_meter_identifies_itself_as_mock():
    meter = get_meter()
    assert meter.source is MeterSource.MOCK

    record = meter.measure(
        [MeteredUsage(category=CostCategory.TOOL_CALL, units=1, billable_operation_id="op-1")],
        currency="USD",
    )
    assert record.source is MeterSource.MOCK
    assert record.currency == "USD"


def test_the_mock_meter_is_deterministic():
    meter = MockCostMeter()
    usage = [MeteredUsage(category=CostCategory.LLM_INPUT_TOKENS, units=100, billable_operation_id="op")]
    assert meter.measure(usage, currency="USD") == meter.measure(usage, currency="USD")


def test_no_provider_meter_is_configured():
    """This deployment has no inference provider, and does not pretend otherwise."""
    with pytest.raises(ValueError) as caught:
        get_meter("openai")
    assert "no inference provider" in str(caught.value)


def test_estimate_is_at_least_the_measured_cost():
    meter = MockCostMeter()
    usage = [MeteredUsage(category=CostCategory.LLM_OUTPUT_TOKENS, units=50, billable_operation_id="op")]

    estimated = meter.estimate_maximum(usage, currency="USD")
    measured = meter.measure(usage, currency="USD")

    assert estimated >= measured.total


def test_metering_requires_one_billable_operation_per_record():
    meter = MockCostMeter()
    with pytest.raises(ValueError) as caught:
        meter.measure(
            [
                MeteredUsage(category=CostCategory.TOOL_CALL, units=1, billable_operation_id="op-a"),
                MeteredUsage(category=CostCategory.TOOL_CALL, units=1, billable_operation_id="op-b"),
            ],
            currency="USD",
        )
    assert "one billable operation id" in str(caught.value)


def test_a_reservation_uses_the_estimator_and_settlement_uses_the_meter(seeded_session, live, budget):
    """The lifecycle the meter exists for, end to end."""
    from app.services.execution import BudgetedExecutor

    meter = MockCostMeter()
    estimated = meter.estimate_maximum(
        [MeteredUsage(category=CostCategory.LLM_INPUT_TOKENS, units=2000, billable_operation_id="op-1")],
        currency="USD",
    )
    assert estimated > 0

    outcome = BudgetedExecutor(budget, meter).run(
        reservation=reserve_request(
            live.company_id, live.seller_id, live.task.id, str(estimated), "k1", operation="op-1"
        ),
        work=lambda: (
            "done",
            [MeteredUsage(category=CostCategory.LLM_INPUT_TOKENS, units=1500, billable_operation_id="op-1")],
        ),
    )

    assert outcome.executed is True
    assert outcome.settlement.charged_amount == Decimal("0.001500")
    assert outcome.settlement.released_amount == Decimal("0.000500")


def test_a_failed_reservation_leaves_the_operation_uninvoked_and_releasable(
    seeded_session, live, budget
):
    from app.services.execution import BudgetedExecutor

    calls = {"count": 0}

    def work():
        calls["count"] += 1
        return ("nope", [])

    outcome = BudgetedExecutor(budget, MockCostMeter()).run(
        reservation=reserve_request(
            live.company_id, live.seller_id, live.task.id, "999999", "k1"
        ),
        work=work,
    )

    assert outcome.executed is False
    assert calls["count"] == 0
    # Nothing is held: a refused operation commits no money.
    assert budget.summary(live.company_id).outstanding_reservations == Decimal("0")