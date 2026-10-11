"""The pre-execution seam.

This is where the two independent gates meet, and the order matters:

```
intent
  -> TrustGate policy evaluation      (existing, authoritative)
       DENY -> record the decision; do not execute
  -> budget reservation               (P0.5)
       INSUFFICIENT -> record the denial; do not execute
  -> execute
  -> settle actual cost, release the remainder
```

A TrustGate ALLOW says the action is *permitted*. It says nothing about whether the
company can afford it, so the budget check is a separate mandatory gate that runs
afterwards. The reverse is equally true: budget availability never overrides a
security denial, because this function checks policy first and stops.

P0.5 connects nothing to the autonomous runtime. Company employees are not mapped to
executing agents yet, so this seam is exercised directly: it takes a callable, and
the proof that matters is that the callable is **not** reached when money is refused.

P0.7 foundation: :class:`ContractGuard` resolves an employee's active contract and
verifies its integrity hash before any execution. The runtime consults it before
running work, so an executing agent can only act under a valid, hash-verified
contract.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy.orm import Session

from app.company.contract_terms import verify_content_hash
from app.company.errors import ConflictError, NotFoundError
from app.models import CompanyEmployee, Contract, ContractStatus
from app.schemas.budget import (
    BudgetReservationRequest,
    BudgetSettlementRequest,
    ReserveResult,
    SettlementResult,
)
from app.services.budget import BudgetService
from app.services.metering import CostMeter, MeteredUsage

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PolicyDenied(Exception):
    """The security gate refused the action.

    A distinct type from a budget denial, because the two mean different things: one
    is "this is not allowed", the other is "this cannot be afforded".
    """


@dataclass
class BudgetedOutcome:
    """What happened, including the evidence for a refusal."""

    executed: bool
    result: T | None
    reservation: ReserveResult
    settlement: SettlementResult | None = None
    denial_reason: str | None = None


class BudgetedExecutor:
    """Runs work only if policy allows it and the money is committed.

    ``policy`` is optional so the budget boundary can be exercised on its own; when
    supplied it is evaluated first and a refusal short-circuits before any reservation
    is attempted — holding money for work that may not happen is itself a distortion.
    """

    def __init__(
        self,
        budget: BudgetService,
        meter: CostMeter,
        *,
        policy: Callable[[], bool] | None = None,
    ) -> None:
        self._budget = budget
        self._meter = meter
        self._policy = policy

    def run(
        self,
        *,
        reservation: BudgetReservationRequest,
        work: Callable[[], tuple[T, list[MeteredUsage]]],
        settlement: BudgetSettlementRequest | None = None,
    ) -> BudgetedOutcome:
        """Reserve, execute, then settle. ``work`` runs only after a reservation."""
        if self._policy is not None and not self._policy():
            logger.info("policy denied execution; no budget reservation attempted")
            raise PolicyDenied("policy denied the action")

        reserved = self._budget.reserve(reservation)
        if not reserved.allowed:
            # The whole point of this seam: `work` has not been called.
            logger.info(
                "budget denied execution: %s",
                reserved.denied.reason if reserved.denied else "unknown",
            )
            return BudgetedOutcome(
                executed=False,
                result=None,
                reservation=reserved,
                denial_reason=reserved.denied.reason if reserved.denied else None,
            )

        result, usage = work()

        request = settlement or BudgetSettlementRequest(
            companyId=reservation.company_id,
            reservationId=reserved.reservation_id,
            actualAmount=self._meter.measure(
                usage, currency=reserved.currency
            ).total,
            idempotencyKey=f"{reservation.idempotency_key}:settle",
            meterSource=self._meter.source,
        )
        settled = self._budget.settle(request)
        return BudgetedOutcome(
            executed=True,
            result=result,
            reservation=reserved,
            settlement=settled,
        )

    def reserve_only(self, reservation: BudgetReservationRequest) -> ReserveResult:
        """Reserve without executing, for a caller that runs the work itself."""
        return self._budget.reserve(reservation)

    def release(self, reservation_id: str, *, idempotency_key: str) -> SettlementResult:
        """Cancel a reservation for work that will not run."""
        return self._budget.release(reservation_id, idempotency_key=idempotency_key)


class ContractGuard:
    """Resolves and verifies an employee's active contract before execution.

    P0.7 foundation: an executing agent must act under a valid, hash-verified
    contract. This guard is the single place that resolves an employee to their
    active contract and checks its integrity.

    The runtime consults this guard before running work. If the employee has no
    active contract, or the contract's hash does not match its terms, the guard
    raises and the run stops before any step executes.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_active_contract(
        self, company_id: str, employee_id: str
    ) -> Contract:
        """Resolve the employee's active contract, verified and ready to execute.

        Raises ``NotFoundError`` when the employee does not belong to the company,
        ``ConflictError`` when there is no active contract or the hash does not match.
        """
        employee = self._session.get(CompanyEmployee, employee_id)
        if employee is None or employee.company_id != company_id:
            raise NotFoundError(
                f"Employee '{employee_id}' does not belong to company '{company_id}'",
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
            or contract.company_id != company_id
            or contract.employee_id != employee_id
            or contract.activated_at is None
        ):
            raise ConflictError(
                f"Employee '{employee_id}' has no active contract; execution requires "
                "an activated contract",
                field="employeeId",
            )
        if not verify_content_hash(contract):
            raise ConflictError(
                f"Contract '{contract.id}' failed its integrity check and cannot "
                "authorise execution",
                field="employeeId",
                details={"contractId": contract.id},
            )
        return contract


__all__ = ["BudgetedExecutor", "BudgetedOutcome", "ContractGuard", "PolicyDenied"]