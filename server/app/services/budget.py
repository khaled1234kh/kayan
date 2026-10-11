"""Budget enforcement.

Money may not be spent on a company's authority without passing through here. The
rules, in one place:

**The hard ceiling.** For a company period, and separately for each employee's month
and each task, ``available = limit - spend - outstanding``. An operation may begin
only if its **maximum** cost fits all three. The tightest one decides.

**Reserve before execution.** No billable work starts without a successful
reservation. A denial is a result, not an exception: it is recorded and committed so
the refusal is auditable, and it creates no active reservation.

**Nothing is trusted from the caller.** Limits, contract state, remaining balances
and contract hashes are all resolved from persisted records. A request may carry a
contract id or a claimed balance; neither is believed.

**Idempotency is enforced by the database.** Reservation, settlement, release and
adjustment keys are unique columns, so a redelivered request cannot double-spend. A
key reused with different parameters is a conflict, not a silent overwrite.

**Concurrency.** Reservations serialise on the company period's ``BudgetAccount``,
which is locked ``FOR UPDATE`` on PostgreSQL. Two requests that each fit the ceiling
alone but not together cannot both be approved: the second waits, then sees the
first's reservation.

**The ledger is history.** Entries are appended, never edited or deleted. A
correction is a new ``refund_or_adjustment`` row.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.company.budgeting import (
    SPEND_CATEGORIES,
    Denied,
    ScopeTotals,
    check_request,
)
from app.company.contract_terms import verify_content_hash
from app.company.errors import ConflictError, ConfigurationError, NotFoundError
from app.models import (
    BudgetAccount,
    BudgetLedgerCategory,
    BudgetLedgerEntry,
    BudgetReservation,
    BudgetReservationStatus,
    Company,
    CompanyEmployee,
    CompanyStatus,
    CompanyTask,
    Contract,
    ContractStatus,
    MeterSource,
    new_ledger_entry_id,
    new_reservation_id,
)
from app.schemas.budget import (
    BudgetAdjustmentRequest,
    BudgetReservationRequest,
    BudgetSettlementRequest,
    ReserveResult,
    SettlementResult,
)
from app.services.companies import STREAM_ID, CompanyService, current_period
from app.services.events import EventService

logger = logging.getLogger(__name__)

ZERO = Decimal("0")

#: The storage scale of every monetary column. Amounts are normalised to it at the
#: service boundary so a stored amount, an event payload and a response body all
#: render the same figure instead of 40, 40.0 and 40.000000 depending on the path.
MONEY_SCALE = Decimal("0.000001")

#: Supplies the current instant. Production uses the real UTC clock; a test injects
#: a fixed callable so month boundaries can be exercised exactly, without sleeping or
#: moving the machine clock.
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """The real UTC clock, timezone-aware."""
    return datetime.now(timezone.utc)


def money(value) -> Decimal:
    """Normalise an amount to the stored scale."""
    return Decimal(value).quantize(MONEY_SCALE)


@dataclass(frozen=True)
class PeriodContext:
    """The accounting period a company is spending in right now."""

    account: BudgetAccount
    period_start: datetime
    period_end: datetime


#: The three ceilings a reservation is measured against, in the order they decide.
LEVEL_COMPANY = "company"
LEVEL_EMPLOYEE = "employee"
LEVEL_TASK = "task"


@dataclass(frozen=True)
class Exhaustion:
    """A ceiling that has just been emptied.

    ``available`` being zero is the whole definition: the scope can no longer commit
    anything until capacity is restored.
    """

    level: str
    limit: Decimal
    available: Decimal
    scope_key: str


@dataclass(frozen=True)
class _Denial:
    """A refused request, plus which ceiling decided it."""

    level: str
    denial: Denied
    scope_key: str


class BudgetService:
    def __init__(
        self,
        session: Session,
        events: EventService | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._events = events or EventService(session)
        self._companies = CompanyService(session, self._events)
        #: Injectable so period arithmetic can be tested at an exact instant. The
        #: default is the real UTC clock, so production behaviour is unchanged.
        self._clock: Clock = clock or utc_now

    def _now(self, now: datetime | None = None) -> datetime:
        """The instant to account against: an explicit one, else the clock's.

        A naive datetime is rejected rather than silently assumed to be UTC, because
        a period boundary computed from a naive value is wrong by the viewer's
        offset and nothing downstream would reveal it.
        """
        moment = now if now is not None else self._clock()
        if moment.tzinfo is None:
            raise ValueError(
                "budget accounting requires a timezone-aware UTC instant, got a naive "
                f"datetime: {moment!r}"
            )
        return moment

    # -- periods -----------------------------------------------------------

    def current_account(
        self, company: Company, *, create: bool = True, now: datetime | None = None
    ) -> BudgetAccount:
        """The company's budget account for the UTC month containing ``now``.

        Defaults to the service's clock, which is the real UTC clock unless a test
        injected one. Created idempotently, keyed by ``(company_id, period_start)``,
        carrying the company's currently configured ceiling and currency forward.
        Earlier periods are never touched, and nothing accumulated is reset.
        """
        moment = self._now(now)
        period_start, period_end = current_period(moment)
        stmt = (
            select(BudgetAccount)
            .where(
                BudgetAccount.company_id == company.id,
                BudgetAccount.period_start == period_start,
            )
            .with_for_update()
        )
        account = self._session.execute(stmt).scalar_one_or_none()
        if account is not None:
            return account
        if not create:
            return None

        account = BudgetAccount(
            id=f"bac_{company.id.removeprefix('cmp_')}_{period_start:%Y%m}",
            company_id=company.id,
            currency=company.currency,
            monthly_limit=self._configured_ceiling(company),
            period_start=period_start,
            period_end=period_end,
        )
        self._session.add(account)
        # Flush so a concurrent transaction either waits on this row or fails on the
        # unique key; either way two accounts for one period cannot both survive.
        self._session.flush()
        logger.info("opened budget account %s for %s", account.id, company.id)
        return account

    def _configured_ceiling(self, company: Company) -> Decimal:
        """Carry the company's configured ceiling forward into a new period.

        P0.2 keeps the live ceiling on the *account* for the current month, so a new
        period starts from whatever the most recent account recorded. Falling back to
        the company row keeps the rule defined even before any account exists.
        """
        stmt = (
            select(BudgetAccount)
            .where(BudgetAccount.company_id == company.id)
            .order_by(BudgetAccount.period_start.desc())
            .limit(1)
        )
        previous = self._session.execute(stmt).scalar_one_or_none()
        return Decimal(previous.monthly_limit) if previous else Decimal("0")

    # -- reserve -----------------------------------------------------------

    def reserve(self, request: BudgetReservationRequest) -> ReserveResult:
        """Commit the maximum cost of work that is about to run.

        Returns an explicit allowed/denied result. A denial is committed as audit
        evidence and leaves no active reservation.
        """
        company = self._companies.get_company(request.company_id)
        if company.status is not CompanyStatus.ACTIVE:
            raise ConflictError(
                f"Company '{company.id}' is {company.status.value}; billable work requires "
                "an active company",
                field="status",
            )

        # One instant for the whole operation, so the period chosen, the event
        # timestamps and the settlement cannot straddle a month boundary.
        moment = self._now()

        existing = self._reservation_by_key(request.idempotency_key)
        if existing is not None:
            return self._replayed_reservation(existing, request)

        contract = self._active_contract(company, request.employee_id)
        task = self._billable_task(contract, request.task_id)

        # Serialise on the period account. Everything below reads committed state.
        account = self.current_account(company, now=moment)
        amount = money(request.maximum_amount)

        denial = self._evaluate(account, contract, task, amount)
        if denial is not None:
            return self._record_denial(
                company, contract, task, request, account, denial, moment
            )

        reservation = BudgetReservation(
            id=new_reservation_id(),
            account_id=account.id,
            company_id=company.id,
            employee_id=contract.employee_id,
            task_id=task.id if task else None,
            run_id=request.run_id,
            amount=amount,
            currency=account.currency,
            status=BudgetReservationStatus.ACTIVE,
            idempotency_key=request.idempotency_key,
            billable_operation_id=request.billable_operation_id,
        )
        self._session.add(reservation)
        try:
            self._session.flush()
        except IntegrityError:
            # Two requests carried the same idempotency key. The unique constraint is
            # the arbiter, so the loser must not surface an error to the caller — it
            # replays the winner's reservation, exactly like a sequential retry.
            self._session.rollback()
            winner = self._reservation_by_key(request.idempotency_key)
            if winner is None:  # pragma: no cover - the constraint named another column
                raise
            logger.info(
                "reservation %s raced on key %s; replayed the winner",
                winner.id,
                request.idempotency_key,
            )
            return self._replayed_reservation(winner, request)

        self._append_ledger(
            account=account,
            category=BudgetLedgerCategory.RESERVATION_CREATED,
            amount=amount,
            reservation=reservation,
            task=task,
            idempotency_key=f"{request.idempotency_key}:created",
            billable_operation_id=request.billable_operation_id,
            note=request.description,
        )

        staged = [
            self._events.stage(
                event_type="budget_reserved",
                stream_id=STREAM_ID,
                target_id=reservation.id,
                timestamp=moment,
                payload={
                    "companyId": company.id,
                    "reservationId": reservation.id,
                    "employeeId": contract.employee_id,
                    "taskId": reservation.task_id,
                    "amount": str(amount),
                    "currency": account.currency,
                    "billableOperationId": request.billable_operation_id,
                },
            )
        ]
        # A reservation that consumes the last available money empties that ceiling.
        # The state change is a fact about the ceiling, not about the request, so it
        # is reported alongside the reservation and committed with it.
        staged.extend(
            self._stage_exhaustions(
                account,
                contract,
                task,
                request.idempotency_key,
                request.billable_operation_id,
                company,
                moment,
                levels=(LEVEL_COMPANY, LEVEL_EMPLOYEE, LEVEL_TASK),
            )
        )
        self._events.commit_and_publish(staged)
        self._session.refresh(reservation)
        logger.info(
            "reserved %s %s for company %s (operation %s)",
            amount,
            account.currency,
            company.id,
            request.billable_operation_id,
        )
        return ReserveResult(
            allowed=True,
            reservation_id=reservation.id,
            reserved_amount=amount,
            currency=account.currency,
            available_after=self.available_for_company(account),
        )

    def _evaluate(
        self,
        account: BudgetAccount,
        contract: Contract,
        task: CompanyTask | None,
        amount: Decimal,
    ) -> _Denial | None:
        """Check the request against all three ceilings. The tightest denial wins."""
        company_totals = self.company_totals(account)
        denial = check_request(
            scope=f"company period ({account.period_start:%Y-%m})",
            limit=company_totals.limit,
            spend=company_totals.spend,
            outstanding=company_totals.outstanding,
            amount=amount,
        )
        if denial is not None:
            return _Denial(
                level=LEVEL_COMPANY,
                denial=denial,
                scope_key=f"company:{account.id}",
            )

        employee_totals = self.employee_totals(account, contract)
        denial = check_request(
            scope="employee monthly allocation",
            limit=employee_totals.limit,
            spend=employee_totals.spend,
            outstanding=employee_totals.outstanding,
            amount=amount,
        )
        if denial is not None:
            return _Denial(
                level=LEVEL_EMPLOYEE,
                denial=denial,
                scope_key=f"employee:{account.id}:{contract.employee_id}",
            )

        if task is not None:
            task_totals = self.task_totals(account, contract, task)
            denial = check_request(
                scope=f"task {task.id}",
                limit=task_totals.limit,
                spend=task_totals.spend,
                outstanding=task_totals.outstanding,
                amount=amount,
            )
            if denial is not None:
                return _Denial(
                    level=LEVEL_TASK,
                    denial=denial,
                    scope_key=f"task:{account.id}:{contract.employee_id}:{task.id}",
                )
        return None

    def _record_denial(
        self,
        company: Company,
        contract: Contract,
        task: CompanyTask | None,
        request: BudgetReservationRequest,
        account: BudgetAccount,
        denial: _Denial,
        moment: datetime,
    ) -> ReserveResult:
        """Persist the refusal, then return it.

        The evidence commits in its own transaction. Raising instead would roll back
        the very record that explains why nothing happened.

        A repeated identical request replays the recorded denial rather than writing
        a second one: the refusal is a fact about the request, and asking again does
        not produce a different fact.
        """
        recorded = self._ledger_by_key(f"{request.idempotency_key}:denied")
        if recorded is not None:
            return ReserveResult(
                allowed=False,
                denied=_denial_from_note(recorded.note, denial.denial),
                currency=account.currency,
                available_after=self.available_for_company(account),
                replayed=True,
            )

        self._append_ledger(
            account=account,
            category=BudgetLedgerCategory.RESERVATION_DENIED,
            amount=ZERO,
            reservation=None,
            task=task,
            idempotency_key=f"{request.idempotency_key}:denied",
            billable_operation_id=request.billable_operation_id,
            note=_denial_to_note(denial.denial),
            employee_id=contract.employee_id,
        )
        staged = [
            self._events.stage(
                event_type="budget_reservation_denied",
                stream_id=STREAM_ID,
                target_id=company.id,
                timestamp=moment,
                payload={
                    "companyId": company.id,
                    "employeeId": contract.employee_id,
                    "taskId": task.id if task else None,
                    "requestedAmount": str(denial.denial.requested),
                    "availableAmount": str(denial.denial.available),
                    "limitAmount": str(denial.denial.limit),
                    "currency": account.currency,
                    "scope": denial.denial.scope,
                    "reason": denial.denial.reason,
                    "billableOperationId": request.billable_operation_id,
                },
            )
        ]
        # Only the ceiling that decided the refusal is reported. Another level may
        # also be empty, but saying so here would claim more than this request
        # established.
        staged.extend(
            self._stage_exhaustions(
                account,
                contract,
                task,
                request.idempotency_key,
                request.billable_operation_id,
                company,
                moment,
                levels=(denial.level,),
                seeded={denial.level: (denial.scope_key, denial.denial)},
            )
        )
        self._events.commit_and_publish(staged)
        logger.info(
            "denied reservation for company %s: %s", company.id, denial.denial.reason
        )
        return ReserveResult(
            allowed=False,
            denied=denial.denial,
            currency=account.currency,
            available_after=self.available_for_company(account),
        )

    # -- exhaustion --------------------------------------------------------

    def _scope_totals_for(
        self,
        account: BudgetAccount,
        contract: Contract,
        task: CompanyTask | None,
        level: str,
    ) -> ScopeTotals:
        if level == LEVEL_EMPLOYEE:
            return self.employee_totals(account, contract)
        if level == LEVEL_TASK and task is not None:
            return self.task_totals(account, contract, task)
        return self.company_totals(account)

    def _scope_key_for(
        self, account: BudgetAccount, contract: Contract, task: CompanyTask | None, level: str
    ) -> str:
        if level == LEVEL_EMPLOYEE:
            return f"employee:{account.id}:{contract.employee_id}"
        if level == LEVEL_TASK and task is not None:
            return f"task:{account.id}:{contract.employee_id}:{task.id}"
        return f"company:{account.id}"

    def _stage_exhaustions(
        self,
        account: BudgetAccount,
        contract: Contract | None,
        task: CompanyTask | None,
        idempotency_key: str,
        billable_operation_id: str | None,
        company: Company,
        moment: datetime,
        *,
        levels: tuple[str, ...],
        seeded: dict[str, tuple[str, Denied]] | None = None,
        trigger: str | None = None,
    ) -> list:
        """Stage a ``budget_limit_reached`` event for each ceiling just emptied.

        A ceiling counts as exhausted only when its available amount is exactly zero.
        A request that is merely larger than what remains is refused with funds still
        available, and that refusal says nothing about the ceiling being empty.

        Each level is reported once per exhaustion. Later denials at the same empty
        ceiling are silent until capacity returns — a release, a refund or a raised
        ceiling — because nothing about the state has changed in between.

        ``contract`` and ``task`` are ``None`` for a company-only exhaustion caused by
        a ceiling adjustment, which has no reservation behind it.
        """
        staged = []
        for level in levels:
            totals = self._scope_totals_for(account, contract, task, level)
            # Zero, or below it. Committed never exceeds the ceiling by construction,
            # so this is normally exactly zero; a negative figure would mean the
            # invariant broke elsewhere, and the ceiling is still unfillable.
            if money(totals.available) > ZERO:
                continue
            scope_key = self._scope_key_for(account, contract, task, level)
            if self._exhaustion_already_reported(account, level, contract, task, scope_key):
                continue

            self._append_ledger(
                account=account,
                category=BudgetLedgerCategory.BUDGET_LIMIT_REACHED,
                amount=ZERO,
                reservation=None,
                task=task if level == LEVEL_TASK else None,
                idempotency_key=f"{idempotency_key}:limit-reached:{level}",
                billable_operation_id=billable_operation_id,
                note=json.dumps(
                    {
                        "level": level,
                        "scopeKey": scope_key,
                        "limit": str(money(totals.limit)),
                        "available": "0",
                    },
                    sort_keys=True,
                ),
                employee_id=contract.employee_id if contract else None,
            )
            payload = {
                "companyId": company.id,
                "level": level,
                "scopeKey": scope_key,
                "limitAmount": str(money(totals.limit)),
                "availableAmount": "0",
                "currency": account.currency,
                "accountId": account.id,
                "periodStart": account.period_start.isoformat(),
                "billableOperationId": billable_operation_id,
            }
            if level in (LEVEL_EMPLOYEE, LEVEL_TASK):
                payload["employeeId"] = contract.employee_id if contract else None
            if level == LEVEL_TASK and task is not None:
                payload["taskId"] = task.id
            if trigger is not None:
                payload["trigger"] = trigger
            elif seeded and level in seeded:
                payload["trigger"] = "denied_reservation"
                payload["deniedScope"] = seeded[level][1].scope
            else:
                payload["trigger"] = "reservation_consumed_remaining_budget"
            staged.append(
                self._events.stage(
                    event_type="budget_limit_reached",
                    stream_id=STREAM_ID,
                    target_id=company.id,
                    timestamp=moment,
                    payload=payload,
                )
            )
            logger.info(
                "%s budget ceiling exhausted for company %s (limit %s %s)",
                level,
                company.id,
                money(totals.limit),
                account.currency,
            )
        return staged

    def _exhaustion_already_reported(
        self,
        account: BudgetAccount,
        level: str,
        contract: Contract | None,
        task: CompanyTask | None,
        scope_key: str,
    ) -> bool:
        """Whether this ceiling is still in the state that was already reported.

        The ledger is the state machine: it is append-only, so walking it backwards
        finds the newest exhaustion marker and, separately, the newest entry that
        handed capacity back. If the restore came later, the ceiling was emptied again
        and this is a new transition worth reporting.
        """
        stmt = select(BudgetLedgerEntry).where(
            BudgetLedgerEntry.account_id == account.id
        )
        if level == LEVEL_EMPLOYEE:
            stmt = stmt.where(BudgetLedgerEntry.employee_id == contract.employee_id)
        elif level == LEVEL_TASK and task is not None:
            stmt = stmt.where(
                BudgetLedgerEntry.employee_id == contract.employee_id,
                BudgetLedgerEntry.task_id == task.id,
            )
        entries = list(
            self._session.execute(
                stmt.order_by(
                    BudgetLedgerEntry.created_at.desc(), BudgetLedgerEntry.id.desc()
                )
            ).scalars()
        )

        marker_at = None
        restored_at = None
        for position, entry in enumerate(entries):
            if marker_at is None and entry.category is BudgetLedgerCategory.BUDGET_LIMIT_REACHED:
                if _markers_scope_key(entry) == scope_key:
                    marker_at = position
            elif marker_at is None and restored_at is None and _restores_capacity(entry):
                restored_at = position
            if marker_at is not None and restored_at is not None:
                break

        if marker_at is None:
            return False
        return restored_at is None or marker_at < restored_at

    def _replayed_reservation(
        self, existing: BudgetReservation, request: BudgetReservationRequest
    ) -> ReserveResult:
        """A repeated reservation returns the original result, or conflicts."""
        if (
            existing.company_id != request.company_id
            or existing.employee_id != request.employee_id
            or existing.task_id != request.task_id
            or Decimal(existing.amount) != request.maximum_amount
            or existing.billable_operation_id != request.billable_operation_id
        ):
            raise ConflictError(
                f"Idempotency key '{request.idempotency_key}' was already used for a "
                "different reservation",
                field="idempotencyKey",
            )
        account = self._session.get(BudgetAccount, existing.account_id)
        return ReserveResult(
            allowed=True,
            reservation_id=existing.id,
            reserved_amount=Decimal(existing.amount),
            currency=existing.currency,
            available_after=self.available_for_company(account) if account else None,
            replayed=True,
        )

    # -- settle ------------------------------------------------------------

    def settle(self, request: BudgetSettlementRequest) -> SettlementResult:
        """Reconcile a reservation against what was actually metered."""
        company = self._companies.get_company(request.company_id)
        reservation = self._get_reservation(company.id, request.reservation_id)

        # The charge entry is keyed by "<key>:charged", which is what makes a
        # repeated settlement recognisable. Looking up the bare key would miss it
        # and fall through to "already settled", turning a retry into a conflict.
        replay = self._ledger_by_key(f"{request.idempotency_key}:charged")
        if replay is not None:
            return self._replayed_settlement(reservation, replay, request)

        if reservation.status is not BudgetReservationStatus.ACTIVE:
            raise ConflictError(
                f"Reservation '{reservation.id}' is {reservation.status.value}; only an "
                "active reservation can be settled",
                field="reservationId",
            )

        moment = self._now()
        actual = money(request.actual_amount)
        reserved = money(reservation.amount)
        if actual < ZERO:
            raise ConfigurationError(
                "actualAmount must not be negative", field="actualAmount"
            )
        if actual > reserved:
            # Do not silently charge more than was authorised, and do not pretend the
            # operation reconciled. The reservation stays ACTIVE, so the full
            # committed amount still blocks further spending while this is resolved.
            raise ConflictError(
                f"Actual cost {actual} exceeds the reserved maximum {reserved} for "
                f"reservation '{reservation.id}'. The reservation remains active and the "
                "difference must be reconciled before more work is committed.",
                field="actualAmount",
                details={
                    "reservationId": reservation.id,
                    "reservedAmount": str(reserved),
                    "actualAmount": str(actual),
                    "difference": str(actual - reserved),
                },
            )

        account = self._session.get(BudgetAccount, reservation.account_id)
        released = reserved - actual

        if actual > ZERO:
            self._append_ledger(
                account=account,
                category=BudgetLedgerCategory.ACTUAL_COST_CHARGED,
                amount=actual,
                reservation=reservation,
                task=None,
                idempotency_key=f"{request.idempotency_key}:charged",
                billable_operation_id=reservation.billable_operation_id,
                note=request.usage_metadata,
                employee_id=reservation.employee_id,
            )
        if released > ZERO:
            self._append_ledger(
                account=account,
                category=BudgetLedgerCategory.RESERVATION_RELEASED,
                amount=-released,
                reservation=reservation,
                task=None,
                idempotency_key=f"{request.idempotency_key}:released",
                billable_operation_id=reservation.billable_operation_id,
                note="unused reservation released on settlement",
                employee_id=reservation.employee_id,
            )

        reservation.status = BudgetReservationStatus.SETTLED
        reservation.settled_at = moment
        self._session.flush()

        totals = self.company_totals(account)
        staged = [
            self._events.stage(
                event_type="budget_charged",
                stream_id=STREAM_ID,
                target_id=reservation.id,
                timestamp=moment,
                payload={
                    "companyId": company.id,
                    "reservationId": reservation.id,
                    "employeeId": reservation.employee_id,
                    "taskId": reservation.task_id,
                    "reservedAmount": str(reserved),
                    "chargedAmount": str(actual),
                    "releasedAmount": str(released),
                    "currency": reservation.currency,
                    "meterSource": request.meter_source.value,
                    "billableOperationId": reservation.billable_operation_id,
                    "availableAfter": str(totals.available),
                },
            )
        ]
        if released > ZERO:
            staged.append(
                self._events.stage(
                    event_type="budget_released",
                    stream_id=STREAM_ID,
                    target_id=reservation.id,
                    timestamp=moment,
                    payload={
                        "companyId": company.id,
                        "reservationId": reservation.id,
                        "releasedAmount": str(released),
                        "currency": reservation.currency,
                        "reason": "settlement",
                    },
                )
            )
        self._events.commit_and_publish(staged)
        self._session.refresh(reservation)
        logger.info(
            "settled reservation %s: charged %s, released %s",
            reservation.id,
            actual,
            released,
        )
        return SettlementResult(
            reservation_id=reservation.id,
            charged_amount=actual,
            released_amount=released,
            currency=reservation.currency,
            available_after=totals.available,
        )

    def _replayed_settlement(
        self,
        reservation: BudgetReservation,
        replay: BudgetLedgerEntry,
        request: BudgetSettlementRequest,
    ) -> SettlementResult:
        """Same key, same amount: the original result. Different amount: conflict."""
        charged = self._ledger_by_key(f"{request.idempotency_key}:charged")
        released = self._ledger_by_key(f"{request.idempotency_key}:released")
        original = Decimal(charged.amount) if charged else ZERO
        if original != request.actual_amount:
            raise ConflictError(
                f"Idempotency key '{request.idempotency_key}' was already used to settle "
                f"{original}, not {request.actual_amount}",
                field="idempotencyKey",
            )
        account = self._session.get(BudgetAccount, reservation.account_id)
        totals = self.company_totals(account)
        return SettlementResult(
            reservation_id=reservation.id,
            charged_amount=original,
            released_amount=Decimal(released.amount) * -1 if released else ZERO,
            currency=reservation.currency,
            available_after=totals.available,
            replayed=True,
        )

    # -- release -----------------------------------------------------------

    def release(self, reservation_id: str, *, idempotency_key: str) -> SettlementResult:
        """Return an unused commitment. Work that never ran."""
        reservation = self._session.get(BudgetReservation, reservation_id)
        if reservation is None:
            raise NotFoundError(
                f"Reservation '{reservation_id}' not found", field="reservationId"
            )

        replay = self._ledger_by_key(f"{idempotency_key}:released")
        if replay is not None:
            account = self._session.get(BudgetAccount, reservation.account_id)
            return SettlementResult(
                reservation_id=reservation.id,
                charged_amount=ZERO,
                released_amount=Decimal(replay.amount) * -1,
                currency=reservation.currency,
                available_after=self.company_totals(account).available,
                replayed=True,
            )

        if reservation.status is BudgetReservationStatus.SETTLED:
            # The money was spent. Releasing it here would erase a real cost.
            raise ConflictError(
                f"Reservation '{reservation.id}' is settled; a real cost was recorded and "
                "cannot be released as though it were unspent. Record a refund or "
                "adjustment entry instead.",
                field="reservationId",
            )
        if reservation.status is not BudgetReservationStatus.ACTIVE:
            raise ConflictError(
                f"Reservation '{reservation.id}' is {reservation.status.value} and cannot "
                "be released",
                field="reservationId",
            )

        moment = self._now()
        account = self._session.get(BudgetAccount, reservation.account_id)
        amount = money(reservation.amount)
        self._append_ledger(
            account=account,
            category=BudgetLedgerCategory.RESERVATION_RELEASED,
            amount=-amount,
            reservation=reservation,
            task=None,
            idempotency_key=f"{idempotency_key}:released",
            billable_operation_id=reservation.billable_operation_id,
            note="reservation released before execution",
            employee_id=reservation.employee_id,
        )
        reservation.status = BudgetReservationStatus.RELEASED
        reservation.settled_at = moment
        self._session.flush()

        totals = self.company_totals(account)
        staged = [
            self._events.stage(
                event_type="budget_released",
                stream_id=STREAM_ID,
                target_id=reservation.id,
                timestamp=moment,
                payload={
                    "companyId": reservation.company_id,
                    "reservationId": reservation.id,
                    "employeeId": reservation.employee_id,
                    "taskId": reservation.task_id,
                    "releasedAmount": str(amount),
                    "currency": reservation.currency,
                    "reason": "cancelled",
                },
            )
        ]
        self._events.commit_and_publish(staged)
        self._session.refresh(reservation)
        logger.info("released reservation %s (%s)", reservation.id, amount)
        return SettlementResult(
            reservation_id=reservation.id,
            charged_amount=ZERO,
            released_amount=amount,
            currency=reservation.currency,
            available_after=totals.available,
        )

    # -- adjustments -------------------------------------------------------

    def adjust_monthly_limit(self, company_id: str, request: BudgetAdjustmentRequest):
        """Change a company's ceiling explicitly, with an audit trail.

        The new ceiling is absolute rather than a delta: "the ceiling is now X" is
        unambiguous, while "add or subtract Y" needs a sign convention that callers
        get wrong.
        """
        moment = self._now()
        company = self._companies.get_company(company_id)
        account = self.current_account(company, now=moment)

        if request.currency.upper() != account.currency:
            raise ConfigurationError(
                f"Company '{company_id}' is configured in {account.currency}; an adjustment "
                f"in {request.currency} would mix currencies",
                field="currency",
            )
        if request.new_monthly_limit <= ZERO:
            raise ConfigurationError(
                "newMonthlyLimit must be greater than zero", field="newMonthlyLimit"
            )

        # Idempotency compares the recorded *ceiling*, not the delta: on a replay the
        # delta is zero because the change already happened.
        replay = self._ledger_by_key(f"{request.idempotency_key}:adjusted")
        if replay is not None:
            recorded = _recorded_ceiling(replay.note)
            if recorded != money(request.new_monthly_limit):
                raise ConflictError(
                    f"Idempotency key '{request.idempotency_key}' was already used to set the "
                    f"ceiling to {recorded}, not {money(request.new_monthly_limit)}",
                    field="idempotencyKey",
                )
            return self.summary(company_id)

        previous_limit = money(account.monthly_limit)
        totals = self.company_totals(account)
        committed = totals.committed
        if money(request.new_monthly_limit) < committed:
            raise ConflictError(
                f"newMonthlyLimit {money(request.new_monthly_limit)} is below the {committed} "
                "already committed (spent plus reserved). Reducing the ceiling below "
                "existing commitments is refused.",
                field="newMonthlyLimit",
                details={
                    "committed": str(committed),
                    "spend": str(totals.spend),
                    "outstanding": str(totals.outstanding),
                },
            )

        new_limit = money(request.new_monthly_limit)
        self._assert_contract_allocations_fit(company, account, new_limit)

        delta = new_limit - previous_limit
        account.monthly_limit = new_limit
        account.version += 1

        self._append_ledger(
            account=account,
            category=BudgetLedgerCategory.BUDGET_INCREASED,
            amount=delta,
            reservation=None,
            task=None,
            idempotency_key=f"{request.idempotency_key}:adjusted",
            billable_operation_id=None,
            note=json.dumps(
                {
                    "previousLimit": str(previous_limit),
                    "newLimit": str(new_limit),
                    "reason": request.reason,
                },
                sort_keys=True,
            ),
        )
        staged = [
            self._events.stage(
                event_type="budget_adjusted",
                stream_id=STREAM_ID,
                target_id=company.id,
                timestamp=moment,
                payload={
                    "companyId": company.id,
                    "previousLimit": str(totals.limit),
                    "newLimit": str(new_limit),
                    "delta": str(delta),
                    "currency": account.currency,
                    "accountVersion": account.version,
                },
            )
        ]
        # Lowering the ceiling onto the money already committed empties it: available
        # is now zero. That is the same exhaustion transition as a reservation consuming
        # the last available money, so it emits the same event. A mere reduction that
        # leaves funds available says nothing about the ceiling being empty.
        staged.extend(
            self._stage_exhaustions(
                account,
                None,
                None,
                request.idempotency_key,
                None,
                company,
                moment,
                levels=(LEVEL_COMPANY,),
                trigger="budget_adjusted",
            )
        )
        self._events.commit_and_publish(staged)
        self._session.refresh(account)
        logger.info(
            "adjusted company %s ceiling to %s %s", company_id, money(request.new_monthly_limit), account.currency
        )
        return self.summary(company_id)

    def _assert_contract_allocations_fit(
        self, company: Company, account: BudgetAccount, new_limit: Decimal
    ) -> None:
        """An activated contract's allocation must remain affordable under the new ceiling."""
        stmt = (
            select(Contract)
            .where(
                Contract.company_id == company.id,
                Contract.status == ContractStatus.ACTIVE,
            )
        )
        total = sum(
            (Decimal(contract.budget_per_month) for contract in self._session.execute(stmt).scalars()),
            ZERO,
        )
        if total > new_limit:
            raise ConflictError(
                f"Active contract allocations total {total}, which exceeds the requested "
                f"ceiling of {new_limit}. Contracts are immutable once activated, so the "
                "ceiling cannot be reduced below them.",
                field="newMonthlyLimit",
                details={"contractAllocations": str(total)},
            )

    # -- read paths --------------------------------------------------------

    def company_totals(self, account: BudgetAccount) -> ScopeTotals:
        """Limit, actual spend and outstanding reservations for a company period."""
        spend = self._spend_for_account(account)
        outstanding = self._outstanding(account_id=account.id)
        return ScopeTotals(limit=Decimal(account.monthly_limit), spend=spend, outstanding=outstanding)

    def employee_totals(self, account: BudgetAccount, contract: Contract) -> ScopeTotals:
        """The same three figures for one employee, against their contract allocation."""
        spend = self._spend_for_account(account, employee_id=contract.employee_id)
        outstanding = self._outstanding(
            account_id=account.id, employee_id=contract.employee_id
        )
        return ScopeTotals(
            limit=Decimal(contract.budget_per_month), spend=spend, outstanding=outstanding
        )

    def task_totals(
        self, account: BudgetAccount, contract: Contract, task: CompanyTask
    ) -> ScopeTotals:
        """Per-task ceiling, aggregated across every operation on that task."""
        spend = self._spend_for_account(
            account, employee_id=contract.employee_id, task_id=task.id
        )
        outstanding = self._outstanding(
            account_id=account.id, employee_id=contract.employee_id, task_id=task.id
        )
        return ScopeTotals(
            limit=Decimal(contract.budget_per_task), spend=spend, outstanding=outstanding
        )

    def available_for_company(self, account: BudgetAccount) -> Decimal:
        return self.company_totals(account).available

    def summary(self, company_id: str):
        """Derived budget position for a company. Never a stored balance."""
        moment = self._now()
        company = self._companies.get_company(company_id)
        account = self.current_account(company, create=False, now=moment)
        if account is None:
            account = self.current_account(company, now=moment)

        totals = self.company_totals(account)

        contracts = list(
            self._session.execute(
                select(Contract).where(
                    Contract.company_id == company_id,
                    Contract.status == ContractStatus.ACTIVE,
                )
            ).scalars()
        )
        by_employee = {contract.employee_id: contract for contract in contracts}
        employees = list(
            self._session.execute(
                select(CompanyEmployee)
                .where(CompanyEmployee.company_id == company_id)
                .order_by(CompanyEmployee.id)
            ).scalars()
        )

        allocations = []
        for employee in employees:
            contract = by_employee.get(employee.id)
            if contract is None:
                continue
            employee_totals = self.employee_totals(account, contract)
            allocations.append(
                {
                    "employeeId": employee.id,
                    "displayName": employee.display_name,
                    "roleKey": contract.role,
                    "contractId": contract.id,
                    "contractVersion": contract.version_number,
                    "monthlyLimit": employee_totals.limit,
                    "monthlySpend": employee_totals.spend,
                    "monthlyOutstanding": employee_totals.outstanding,
                    "monthlyAvailable": employee_totals.available,
                    "perTaskLimit": Decimal(contract.budget_per_task),
                }
            )

        from app.schemas.budget import BudgetSummary

        return BudgetSummary(
            company_id=company_id,
            currency=account.currency,
            account_id=account.id,
            period_start=account.period_start,
            period_end=account.period_end,
            monthly_limit=totals.limit,
            actual_spend=totals.spend,
            outstanding_reservations=totals.outstanding,
            available=totals.available,
            account_version=account.version,
            employee_allocations=allocations,
        )

    def ledger(
        self,
        company_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        category: BudgetLedgerCategory | None = None,
        employee_id: str | None = None,
        task_id: str | None = None,
    ) -> list[BudgetLedgerEntry]:
        """Ledger history, newest first, with deterministic tie-breaking.

        Ordered by ``created_at`` then ``id`` so paging cannot repeat or skip an
        entry when several were written in the same transaction.
        """
        self._companies.get_company(company_id)
        stmt = select(BudgetLedgerEntry).where(BudgetLedgerEntry.company_id == company_id)
        if category is not None:
            stmt = stmt.where(BudgetLedgerEntry.category == category)
        if employee_id is not None:
            stmt = stmt.where(BudgetLedgerEntry.employee_id == employee_id)
        if task_id is not None:
            stmt = stmt.where(BudgetLedgerEntry.task_id == task_id)
        stmt = (
            stmt.order_by(BudgetLedgerEntry.created_at.desc(), BudgetLedgerEntry.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.execute(stmt).scalars())

    # -- internals ---------------------------------------------------------

    def _active_contract(self, company: Company, employee_id: str) -> Contract:
        """The employee's effective contract, verified before it authorises money."""
        employee = self._session.get(CompanyEmployee, employee_id)
        if employee is None or employee.company_id != company.id:
            # Fail closed: an unknown employee and someone else's employee are both
            # "not yours to spend on".
            raise NotFoundError(
                f"Employee '{employee_id}' does not belong to company '{company.id}'",
                field="employeeId",
            )
        contract = (
            self._session.get(Contract, employee.active_contract_id)
            if employee.active_contract_id
            else None
        )
        if (
            contract is None
            or contract.status is not ContractStatus.ACTIVE
            or contract.company_id != company.id
            or contract.employee_id != employee_id
            or contract.activated_at is None
        ):
            raise ConflictError(
                f"Employee '{employee_id}' has no active contract; billable work requires "
                "an activated contract",
                field="employeeId",
            )
        if not verify_content_hash(contract):
            # The contract's terms no longer match their recorded hash, so it cannot
            # be trusted to authorise spending.
            raise ConflictError(
                f"Contract '{contract.id}' failed its integrity check and cannot "
                "authorise spending",
                field="employeeId",
                details={"contractId": contract.id},
            )
        return contract

    def _billable_task(self, contract: Contract, task_id: str | None) -> CompanyTask | None:
        """Validate the task association for this employee.

        Billable employee work must name a task, and the task must belong to this
        employee and fall inside the contract's permitted task categories.
        """
        if task_id is None:
            raise ConfigurationError(
                "taskId is required for billable employee work", field="taskId"
            )
        task = self._session.get(CompanyTask, task_id)
        if task is None:
            raise NotFoundError(f"Task '{task_id}' not found", field="taskId")
        if task.employee_id != contract.employee_id:
            raise ConfigurationError(
                f"Task '{task_id}' is not assigned to employee '{contract.employee_id}'",
                field="taskId",
            )
        if contract.task_scope and task.category not in contract.task_scope:
            raise ConfigurationError(
                f"Task '{task_id}' has category '{task.category}', which the employee's "
                "contract does not permit",
                field="taskId",
            )
        return task

    def _spend_for_account(
        self,
        account: BudgetAccount,
        *,
        employee_id: str | None = None,
        task_id: str | None = None,
    ) -> Decimal:
        """Actual spend from the ledger. Reservations are deliberately excluded."""
        stmt = select(
            BudgetLedgerEntry.amount, BudgetLedgerEntry.category
        ).where(
            BudgetLedgerEntry.account_id == account.id,
            BudgetLedgerEntry.category.in_(SPEND_CATEGORIES),
        )
        if employee_id is not None:
            stmt = stmt.where(BudgetLedgerEntry.employee_id == employee_id)
        if task_id is not None:
            stmt = stmt.where(BudgetLedgerEntry.task_id == task_id)
        return sum((Decimal(row[0]) for row in self._session.execute(stmt)), ZERO)

    def _outstanding(
        self,
        *,
        account_id: str,
        employee_id: str | None = None,
        task_id: str | None = None,
    ) -> Decimal:
        """Committed but not yet spent, from the reservation table."""
        stmt = select(func.sum(BudgetReservation.amount)).where(
            BudgetReservation.account_id == account_id,
            BudgetReservation.status == BudgetReservationStatus.ACTIVE,
        )
        if employee_id is not None:
            stmt = stmt.where(BudgetReservation.employee_id == employee_id)
        if task_id is not None:
            stmt = stmt.where(BudgetReservation.task_id == task_id)
        total = self._session.execute(stmt).scalar()
        return Decimal(total) if total is not None else ZERO

    def _append_ledger(
        self,
        *,
        account: BudgetAccount,
        category: BudgetLedgerCategory,
        amount: Decimal,
        reservation: BudgetReservation | None,
        task: CompanyTask | None,
        idempotency_key: str,
        billable_operation_id: str | None,
        note: str | None = None,
        employee_id: str | None = None,
    ) -> BudgetLedgerEntry:
        """Append one history row. Never modifies an existing one."""
        entry = BudgetLedgerEntry(
            id=new_ledger_entry_id(),
            company_id=account.company_id,
            account_id=account.id,
            reservation_id=reservation.id if reservation else None,
            employee_id=(
                employee_id
                or (reservation.employee_id if reservation else None)
                or (task.employee_id if task else None)
            ),
            task_id=(
                task.id if task else (reservation.task_id if reservation else None)
            ),
            run_id=reservation.run_id if reservation else None,
            category=category,
            amount=amount,
            currency=account.currency,
            balance_after=None,
            idempotency_key=idempotency_key,
            billable_operation_id=billable_operation_id,
            note=note,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def _reservation_by_key(self, idempotency_key: str) -> BudgetReservation | None:
        stmt = select(BudgetReservation).where(
            BudgetReservation.idempotency_key == idempotency_key
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _ledger_by_key(self, idempotency_key: str) -> BudgetLedgerEntry | None:
        stmt = select(BudgetLedgerEntry).where(
            BudgetLedgerEntry.idempotency_key == idempotency_key
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _get_reservation(self, company_id: str, reservation_id: str) -> BudgetReservation:
        reservation = self._session.get(BudgetReservation, reservation_id)
        if reservation is None or reservation.company_id != company_id:
            raise NotFoundError(
                f"Reservation '{reservation_id}' not found for company '{company_id}'",
                field="reservationId",
            )
        return reservation


def _recorded_ceiling(note: str | None) -> Decimal | None:
    """The ceiling an adjustment entry set, read back from its note."""
    if not note:
        return None
    try:
        stored = json.loads(note)
    except (TypeError, ValueError):
        return None
    if not isinstance(stored, dict) or "newLimit" not in stored:
        return None
    return Decimal(str(stored["newLimit"]))


def _restores_capacity(entry: BudgetLedgerEntry) -> bool:
    """Whether a ledger entry handed budget capacity back to its scope.

    Capacity returns when a commitment is released, when a refund reduces recorded
    spend, or when the company ceiling is raised. Those are the only ways an emptied
    ceiling can become non-empty again.
    """
    if entry.category is BudgetLedgerCategory.RESERVATION_RELEASED:
        return True
    if entry.category is BudgetLedgerCategory.REFUND_OR_ADJUSTMENT:
        return Decimal(entry.amount) < ZERO
    if entry.category is BudgetLedgerCategory.BUDGET_INCREASED:
        return Decimal(entry.amount) > ZERO
    return False


def _markers_scope_key(entry: BudgetLedgerEntry) -> str | None:
    """The scope an exhaustion marker belongs to, read back from its note."""
    if not entry.note:
        return None
    try:
        stored = json.loads(entry.note)
    except (TypeError, ValueError):
        return None
    if not isinstance(stored, dict):
        return None
    return stored.get("scopeKey")


def _denial_to_note(denial: Denied) -> str:
    """Serialise a denial so a repeated request can replay it exactly."""
    return json.dumps(
        {
            "scope": denial.scope,
            "reason": denial.reason,
            "requested": str(denial.requested),
            "available": str(denial.available),
            "limit": str(denial.limit),
        },
        sort_keys=True,
    )


def _denial_from_note(note: str | None, fallback: Denied) -> Denied:
    """Rebuild a recorded denial, falling back to the freshly computed one."""
    if not note:
        return fallback
    try:
        stored = json.loads(note)
    except (TypeError, ValueError):
        return fallback
    if not isinstance(stored, dict) or "requested" not in stored:
        return fallback
    return Denied(
        scope=stored.get("scope", fallback.scope),
        reason=stored.get("reason", fallback.reason),
        requested=Decimal(str(stored["requested"])),
        available=Decimal(str(stored.get("available", fallback.available))),
        limit=Decimal(str(stored.get("limit", fallback.limit))),
    )


def get_budget_service(session: Session) -> BudgetService:
    return BudgetService(session)


__all__ = ["BudgetService", "PeriodContext", "get_budget_service"]