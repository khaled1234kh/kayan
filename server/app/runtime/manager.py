"""The Manager agent: deterministic task assignment for an active company.

The Manager reads the :class:`CompanyTask` board and assigns work. It decides
nothing by mood and nothing by wall clock: the same board, the same activated
contracts and the same budget position always produce the same assignment.

Rules, in order:

1. Only ``open`` tasks are actionable. ``blocked``, ``completed`` and
   ``awaiting_approval`` (paused for a human) tasks are never picked.
2. ``CompanyTask`` carries no dependency columns, so every open task's
   dependencies are trivially satisfied. If dependency edges are added later,
   they must be honoured here before anything else changes.
3. An employee is *eligible* for a task when all three hold:

   * they have an activated, hash-verified contract (same check the execution
     seam applies, but non-raising: an employee without one is skipped, not
     fatal),
   * the task category appears in their contract ``task_scope``,
   * the estimated maximum fits their remaining employee budget, the task
     ceiling and the company ceiling.
4. The best fit is the most specialised eligible seat first (fewest categories
   in ``task_scope`` — a sales seat beats a generalist manager seat for a
   quotation), then the lowest budget usage ratio, then the lowest employee
   id. Every tiebreak is total, so the winner is unique.
5. No eligible employee: the task is marked ``blocked`` and the reason code
   ``no_eligible_worker`` is recorded in the event payload (there is no
   reason-code column by design; the audit event is the record).
6. A human seat (``kind == "human"``) or a contract with
   ``requires_human_escalation`` cannot be executed autonomously: the Manager
   emits ``awaiting_info`` with reason code ``human_clarification_required``
   and pauses the task as ``awaiting_approval``. No budget is reserved and no
   TrustGate call is made for work that will not run.

The existing event vocabulary is reused deliberately (``task_assigned``,
``blocked``, ``awaiting_info``, ``task_completed``): the frontend catalogue
parity test requires every backend event type to exist in the client
catalogue, and the autonomous phase must not touch the frontend. New
situations travel as reason codes inside those payloads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company.contract_terms import verify_content_hash
from app.company.errors import NotFoundError
from app.models import (
    Company,
    CompanyEmployee,
    CompanyTask,
    Contract,
    ContractStatus,
    TaskStatus,
)
from app.services.budget import BudgetService
from app.services.companies import STREAM_ID
from app.services.events import EventService

logger = logging.getLogger(__name__)

#: Reason recorded when a task cannot be staffed.
NO_ELIGIBLE_WORKER = "no_eligible_worker"

#: Reason recorded when autonomous execution must wait for a person.
HUMAN_CLARIFICATION_REQUIRED = "human_clarification_required"

#: Worst-case cost committed per task category, in company currency units.
#: This is the *maximum*, not the expected cost: the ceiling must hold for the
#: worst case the Manager allowed, and settlement releases whatever was not
#: actually spent. All values are ``Decimal``; floats never authorise money.
MAXIMUM_FOR_CATEGORY: dict[str, Decimal] = {
    "quotation": Decimal("2.000000"),
    "inventory": Decimal("2.000000"),
    "fulfilment": Decimal("2.000000"),
    "sourcing": Decimal("2.000000"),
    "approval": Decimal("1.000000"),
    "review": Decimal("1.000000"),
    "hr": Decimal("1.000000"),
    "support": Decimal("1.000000"),
}

#: Fallback maximum for a category the table does not name.
DEFAULT_MAXIMUM = Decimal("1.000000")

ZERO = Decimal("0")


def estimate_for_category(category: str) -> Decimal:
    """The worst-case cost the Manager commits for one task of this category."""
    return MAXIMUM_FOR_CATEGORY.get(category, DEFAULT_MAXIMUM)


@dataclass(frozen=True)
class Candidate:
    """One eligible employee, with the figures that decided their rank."""

    employee_id: str
    contract_id: str
    #: Fewer categories in scope means a more specialised seat.
    scope_size: int
    #: Committed (spent + outstanding) over the monthly limit, 0 when unlimited.
    usage_ratio: Decimal


@dataclass(frozen=True)
class PickOutcome:
    """What one Manager pass did. Exactly one action is set."""

    action: str  # "assigned" | "blocked_no_worker" | "awaiting_human" | "no_tasks"
    task_id: str | None = None
    employee_id: str | None = None
    contract_id: str | None = None
    estimate: Decimal | None = None
    reason_code: str | None = None


class Manager:
    """Deterministic assignment of company tasks to contracted employees."""

    def __init__(self, session: Session, events: EventService | None = None) -> None:
        self._session = session
        self._events = events or EventService(session)
        self._budget = BudgetService(session, self._events)

    # -- board -----------------------------------------------------------

    def board(self, company_id: str) -> list[CompanyTask]:
        """Every task of the company, oldest first, id as total tiebreak."""
        self._company(company_id)  # raises NotFoundError for an unknown company
        stmt = (
            select(CompanyTask)
            .where(CompanyTask.company_id == company_id)
            .order_by(CompanyTask.created_at, CompanyTask.id)
        )
        return list(self._session.execute(stmt).scalars())

    def actionable(self, tasks: list[CompanyTask]) -> list[CompanyTask]:
        """The tasks the loop may work on: open, with dependencies satisfied.

        ``CompanyTask`` has no dependency columns, so satisfaction is vacuous
        and documented as such rather than faked.
        """
        return [task for task in tasks if task.status is TaskStatus.OPEN]

    # -- eligibility -----------------------------------------------------

    def _active_contract_for(
        self, company_id: str, employee_id: str
    ) -> Contract | None:
        """The employee's verified active contract, or ``None`` when unusable.

        Mirrors :class:`ContractGuard` without raising: ineligibility is a
        ranking input here, not a failure.
        """
        employee = self._session.get(CompanyEmployee, employee_id)
        if employee is None or employee.company_id != company_id:
            return None
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
            return None
        if not verify_content_hash(contract):
            return None
        return contract

    def _company(self, company_id: str) -> Company:
        company = self._session.get(Company, company_id)
        if company is None:
            raise NotFoundError(f"Company '{company_id}' not found", field="companyId")
        return company

    def eligible_candidates(
        self, company_id: str, task: CompanyTask
    ) -> list[Candidate]:
        """Every employee who may take this task, best fit first.

        Pure read apart from resolving the current budget account (which never
        writes when ``create=False`` finds the existing period account). The
        returned order is the assignment order.
        """
        company = self._company(company_id)
        estimate = estimate_for_category(task.category)
        account = self._budget.current_account(company, create=False)
        company_available = (
            self._budget.company_totals(account).available if account is not None else None
        )

        stmt = (
            select(CompanyEmployee)
            .where(CompanyEmployee.company_id == company_id)
            .order_by(CompanyEmployee.id)
        )
        candidates: list[Candidate] = []
        for employee in self._session.execute(stmt).scalars():
            contract = self._active_contract_for(company_id, employee.id)
            if contract is None:
                continue
            if contract.task_scope and task.category not in contract.task_scope:
                continue
            if Decimal(contract.budget_per_task) < estimate:
                continue
            if account is not None:
                employee_available = self._budget.employee_totals(
                    account, contract
                ).available
                if employee_available < estimate:
                    continue
                if task.employee_id == employee.id:
                    task_available = self._budget.task_totals(
                        account, contract, task
                    ).available
                    if task_available < estimate:
                        continue
                if (
                    company_available is not None
                    and company_available < estimate
                ):
                    continue
            limit = Decimal(contract.budget_per_month)
            if account is not None and limit > ZERO:
                totals = self._budget.employee_totals(account, contract)
                usage = totals.committed / limit
            else:
                usage = ZERO
            candidates.append(
                Candidate(
                    employee_id=employee.id,
                    contract_id=contract.id,
                    scope_size=len(contract.task_scope or []),
                    usage_ratio=usage,
                )
            )
        candidates.sort(
            key=lambda candidate: (
                candidate.scope_size,
                candidate.usage_ratio,
                candidate.employee_id,
            )
        )
        return candidates

    # -- the pass --------------------------------------------------------

    def pick_and_assign(self, company_id: str) -> PickOutcome:
        """Pick the next actionable task and staff it, or record why not.

        Mutates at most one task and emits at most two events (an assignment
        plus, for a blocked or paused task, its state event). Every mutation
        commits with its event, so the audit trail never describes a staffing
        decision that was rolled back.
        """
        tasks = self.board(company_id)
        actionable = self.actionable(tasks)
        if not actionable:
            return PickOutcome(action="no_tasks")

        task = actionable[0]
        estimate = estimate_for_category(task.category)
        candidates = self.eligible_candidates(company_id, task)
        if not candidates:
            task.status = TaskStatus.BLOCKED
            self._session.flush()
            self._events.record(
                event_type="blocked",
                stream_id=STREAM_ID,
                task_id=task.id,
                payload={
                    "companyId": company_id,
                    "taskId": task.id,
                    "category": task.category,
                    "reasonCode": NO_ELIGIBLE_WORKER,
                    "reason": (
                        f"Task '{task.id}' has no eligible worker: no active "
                        "contract permits its category within the remaining "
                        "budget"
                    ),
                },
            )
            logger.info("task %s blocked: %s", task.id, NO_ELIGIBLE_WORKER)
            return PickOutcome(
                action="blocked_no_worker",
                task_id=task.id,
                reason_code=NO_ELIGIBLE_WORKER,
            )

        best = candidates[0]
        employee = self._session.get(CompanyEmployee, best.employee_id)
        contract = self._session.get(Contract, best.contract_id)
        needs_human = (
            employee is not None
            and (employee.kind == "human" or (contract is not None and contract.requires_human_escalation))
        )
        if needs_human:
            task.status = TaskStatus.AWAITING_APPROVAL
            self._session.flush()
            self._events.record(
                event_type="awaiting_info",
                stream_id=STREAM_ID,
                actor_id=best.employee_id,
                task_id=task.id,
                payload={
                    "companyId": company_id,
                    "taskId": task.id,
                    "employeeId": best.employee_id,
                    "reasonCode": HUMAN_CLARIFICATION_REQUIRED,
                    "reason": (
                        f"Task '{task.id}' needs information from the user "
                        "before autonomous execution can proceed"
                    ),
                },
            )
            logger.info("task %s paused: %s", task.id, HUMAN_CLARIFICATION_REQUIRED)
            return PickOutcome(
                action="awaiting_human",
                task_id=task.id,
                employee_id=best.employee_id,
                reason_code=HUMAN_CLARIFICATION_REQUIRED,
            )

        if task.employee_id != best.employee_id:
            previous = task.employee_id
            task.employee_id = best.employee_id
            self._session.flush()
            self._events.record(
                event_type="task_assigned",
                stream_id=STREAM_ID,
                actor_id=best.employee_id,
                task_id=task.id,
                payload={
                    "companyId": company_id,
                    "taskId": task.id,
                    "employeeId": best.employee_id,
                    "contractId": best.contract_id,
                    "previousEmployeeId": previous,
                    "category": task.category,
                    "reason": "role match first, then lowest budget usage",
                },
            )
            logger.info(
                "task %s assigned to %s (was %s)", task.id, best.employee_id, previous
            )
        return PickOutcome(
            action="assigned",
            task_id=task.id,
            employee_id=best.employee_id,
            contract_id=best.contract_id,
            estimate=estimate,
        )


__all__ = [
    "DEFAULT_MAXIMUM",
    "HUMAN_CLARIFICATION_REQUIRED",
    "MAXIMUM_FOR_CATEGORY",
    "NO_ELIGIBLE_WORKER",
    "Candidate",
    "Manager",
    "PickOutcome",
    "estimate_for_category",
]
