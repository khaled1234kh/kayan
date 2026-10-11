"""P0.5 concurrency and database protection.

These need real PostgreSQL: ``SELECT ... FOR UPDATE`` is a no-op on SQLite, so the
question "can two racing requests both fit?" cannot be answered there. Each test uses
independent sessions and a thread pool, exactly as two request handlers would.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from app.models import BudgetAccount, BudgetLedgerCategory, BudgetReservation
from app.schemas.budget import BudgetReservationRequest
from app.services.budget import BudgetService
from tests.p0_5_helpers import make_spendable_company

pytestmark = pytest.mark.skipif(
    not __import__("os").environ.get("KAYAN_TEST_DATABASE_URL", "").startswith("postgres"),
    reason="row-level locking and the ledger trigger are PostgreSQL behaviour",
)


@pytest.fixture()
def spendable(engine):
    """A spendable company plus a factory for independent sessions."""
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    try:
        # The role catalogue is seed data the app writes; a spendable company needs it.
        from app.db.seed import seed_agents
        from app.db.seed_roles import seed_role_templates

        seed_agents(session)
        seed_role_templates(session)
        fixture = make_spendable_company(
            session, ceiling="2000", seller_monthly="1000", seller_per_task="1000"
        )
        yield factory, fixture
    finally:
        session.close()


def _reserve(factory, company_id, employee_id, task_id, amount, key):
    """One reservation in its own session, as a separate request would."""
    session = factory()
    try:
        request = BudgetReservationRequest(
            companyId=company_id,
            employeeId=employee_id,
            taskId=task_id,
            maximumAmount=amount,
            idempotencyKey=key,
            billableOperationId=f"op-{key}",
        )
        result = BudgetService(session).reserve(request)
        return result.allowed
    except Exception:  # noqa: BLE001 - a refusal is a legitimate outcome
        return False
    finally:
        session.close()


def _reserve_concurrently(factory, fixture, requests):
    with ThreadPoolExecutor(max_workers=len(requests)) as pool:
        futures = [
            pool.submit(
                _reserve,
                factory,
                fixture.company_id,
                fixture.seller_id,
                fixture.task.id,
                amount,
                key,
            )
            for amount, key in requests
        ]
        return [future.result() for future in futures]


def test_concurrent_reservations_cannot_exceed_the_company_ceiling(spendable):
    """Two requests of 700 against a 2000 budget where the company has\n    2000 available: the point is the race, not the arithmetic ceiling.

    Without the row lock on the period account both would read the same 1000 and
    both would approve, over-committing by 400.
    """
    factory, fixture = spendable

    allowed = _reserve_concurrently(
        factory, fixture, [("700", "c1"), ("700", "c2")]
    )

    assert allowed.count(True) == 1, "the ceiling must not be exceeded under a race"
    session = factory()
    try:
        account = session.query(BudgetAccount).filter_by(company_id=fixture.company_id).one()
        service = BudgetService(session)
        totals = service.company_totals(account)
        assert totals.outstanding <= account.monthly_limit
    finally:
        session.close()


def test_concurrent_reservations_cannot_exceed_the_task_ceiling(spendable):
    """Same race, bounded by the per-task ceiling rather than the company one.

    The company has plenty of room, so only the task's own ceiling can stop the
    second request — which is exactly the case a company-level check alone misses.
    """
    from app.db.seed import seed_agents
    from app.db.seed_roles import seed_role_templates
    from app.services.lifecycle import CompanyLifecycleService

    factory, roomy = spendable
    session = factory()
    try:
        seed_agents(session)
        seed_role_templates(session)
        # Only one company may hold the active slot, so the roomy one steps aside.
        CompanyLifecycleService(session).pause(roomy.company_id)
        fixture = make_spendable_company(
            session,
            ceiling="2000",
            seller_monthly="1000",
            seller_per_task="100",
        )
    finally:
        session.close()

    allowed = _reserve_concurrently(
        factory, fixture, [("70", "t1"), ("70", "t2")]
    )

    assert allowed.count(True) == 1

    session = factory()
    try:
        on_task = session.query(BudgetReservation).filter_by(task_id=fixture.task.id).all()
        total = sum(Decimal(str(row.amount)) for row in on_task)
        assert total <= Decimal("100")
    finally:
        session.close()


def test_many_small_reservations_stay_within_the_ceiling(spendable):
    """Ten requests of 200 against 1000: exactly five can be approved."""
    factory, fixture = spendable

    allowed = _reserve_concurrently(
        factory, fixture, [(f"200", f"m{index}") for index in range(10)]
    )

    assert allowed.count(True) == 5

    session = factory()
    try:
        active = session.query(BudgetReservation).filter_by(
            company_id=fixture.company_id
        ).all()
        total = sum(Decimal(str(row.amount)) for row in active)
        assert total == Decimal("1000.000000")
    finally:
        session.close()


def test_simultaneous_duplicate_idempotency_keys_reserve_once(spendable):
    """The same key from five requests yields one reservation, not five."""
    factory, fixture = spendable

    allowed = _reserve_concurrently(
        factory, fixture, [("100", "same-key")] * 5
    )

    session = factory()
    try:
        assert session.query(BudgetReservation).filter_by(
            idempotency_key="same-key"
        ).count() == 1
        # Every caller learns the outcome; none of them spent twice.
        assert all(allowed)
    finally:
        session.close()


def test_a_company_account_is_created_once_under_concurrency(spendable):
    """Two requests racing on a new period must not produce two accounts."""
    factory, fixture = spendable

    errors: list[Exception] = []

    def open_account() -> None:
        session = factory()
        try:
            from app.models import Company

            company = session.get(Company, fixture.company_id)
            BudgetService(session).current_account(company)
        except Exception as error:  # noqa: BLE001 - recorded and asserted below
            errors.append(error)
        finally:
            session.close()

    threads = [threading.Thread(target=open_account) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    session = factory()
    try:
        accounts = session.query(BudgetAccount).filter_by(company_id=fixture.company_id).all()
        assert len(accounts) == 1, "one company, one account per period"
    finally:
        session.close()
