"""The autonomous runtime loop: the company works toward its target alone.

One :func:`run_cycle` is one tick: the Manager staffs the next actionable task
and the runtime executes it through the same gates every other backend path
uses. :func:`run_until_target_or_budget` repeats ticks until the work is done,
the money is gone, or a safety bound stops it.

Execution of a single task, in order:

1. Resolve the employee's active contract (:class:`ContractGuard`).
2. Form the role's intent and ask TrustGate. A denial is recorded as
   ``policy_denied``, the task is marked ``blocked`` and the loop continues
   with the next task — a refusal is a result, not a crash.
3. Reserve the category maximum through :class:`BudgetService`.
4. Do the role's scripted work (mock model, per-role shape) and measure it
   with :class:`MockCostMeter`.
5. Settle the actual cost, releasing the remainder.
6. Persist a real artifact object inside an ``artifact_created`` event and mark
   the task ``completed`` (or ``blocked`` with the reason code when money or
   policy refused).

Steps 3–5 run through :class:`BudgetedExecutor`, the existing seam, so budget
and policy keep their documented order (policy first, then money) and the mock
label stays on every figure. All money is :class:`Decimal`; floats never cross
this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.company.errors import ConflictError, DomainError
from app.models import (
    Company,
    CompanyEmployee,
    CompanyStatus,
    CompanyTask,
    CostCategory,
    TaskStatus,
)
from app.runtime.manager import Manager, estimate_for_category
from app.schemas.budget import BudgetReservationRequest
from app.security.trustgate import AgentIntent, authorize_intent
from app.services.budget import BudgetService
from app.services.companies import STREAM_ID
from app.services.events import EventService
from app.services.execution import BudgetedExecutor, ContractGuard, PolicyDenied
from app.services.metering import MeteredUsage, MockCostMeter

logger = logging.getLogger(__name__)

#: Safety stop for :func:`run_until_target_or_budget` when the caller says nothing.
DEFAULT_MAX_ITERATIONS = 50

#: TrustGate identity per employee role. Seats without their own capability
#: contract (hr, support, custom roles) execute as the generic ``employee``
#: contract, whose ``task/*`` scope covers role work phrased as task work.
TRUSTGATE_AGENT_FOR_ROLE: dict[str, str] = {
    "ceo": "ceo",
    "manager": "manager",
    "sales": "sales",
    "operations": "operations",
}

#: Metered tool-call units behind one execution, per task category.
TOOL_CALL_UNITS: dict[str, int] = {
    "quotation": 10,
    "inventory": 8,
    "fulfilment": 8,
    "sourcing": 8,
    "approval": 6,
    "review": 6,
}

#: Stop reasons reported by :func:`run_until_target_or_budget`.
TARGET_REACHED = "target_reached"
BUDGET_EXHAUSTED = "budget_exhausted"
NO_ACTIONABLE_TASKS = "no_actionable_tasks"
MAX_ITERATIONS = "max_iterations"

ZERO = Decimal("0")


@dataclass(frozen=True)
class CycleResult:
    """What one tick did."""

    action: str  # "completed" | "blocked" | "awaiting_human" | "no_tasks"
    task_id: str | None = None
    employee_id: str | None = None
    reason_code: str | None = None
    artifact: dict[str, Any] | None = None


@dataclass
class LoopResult:
    """What a bounded run achieved and why it stopped."""

    stop_reason: str
    cycles: int = 0
    completed: int = 0
    blocked: int = 0
    task_ids: list[str] = field(default_factory=list)


# -- intent and metering -------------------------------------------------


def trustgate_agent_for(role_key: str) -> str:
    """The TrustGate seat an employee role executes as."""
    return TRUSTGATE_AGENT_FOR_ROLE.get(role_key, "employee")


def intent_for_task(agent_id: str, task: CompanyTask, company_id: str) -> AgentIntent:
    """The pre-execution intent for one task, phrased inside task scope.

    The resource is always under ``task/`` so it falls inside every seat's
    capability scope: the default outcome is ALLOW, and a denial means policy
    genuinely refused rather than the runtime misphrasing the work.
    """
    action_by_category = {
        "quotation": "quote.draft",
        "inventory": "inventory.read",
        "fulfilment": "inventory.read",
        "sourcing": "inventory.read",
        "approval": "task.review",
        "review": "task.review",
    }
    return AgentIntent(
        agent_id=agent_id,
        action=action_by_category.get(task.category, "task.execute"),
        resource=f"task/{task.id}",
        source="trusted",
        context={
            "taskId": task.id,
            "companyId": company_id,
            "category": task.category,
        },
    )


def usage_for_task(task: CompanyTask, billable_operation_id: str) -> list[MeteredUsage]:
    """The metered slices behind one execution. Charged once, never twice."""
    units = TOOL_CALL_UNITS.get(task.category, 6)
    return [
        MeteredUsage(
            category=CostCategory.TOOL_CALL,
            units=units,
            billable_operation_id=billable_operation_id,
        ),
        MeteredUsage(
            category=CostCategory.AGENT_MESSAGE,
            units=1,
            billable_operation_id=billable_operation_id,
            note="execution report (recorded, not charged)",
        ),
    ]


# -- artifacts ------------------------------------------------------------


def _stable_offset(task_id: str) -> int:
    """A deterministic small integer from a task id (no hash randomisation)."""
    return sum(ord(character) for character in task_id)


def artifact_for_task(
    company: Company,
    task: CompanyTask,
    employee_id: str,
    role_key: str,
) -> dict[str, Any]:
    """The persisted result object for one executed task, by role shape.

    Every artifact carries real company fields (id, name, template, currency)
    and is labelled ``mock``: the scripted work demonstrates the pipeline, not
    a provider invoice.
    """
    base: dict[str, Any] = {
        "source": "mock",
        "companyId": company.id,
        "companyName": company.name,
        "templateKey": company.template_key,
        "currency": company.currency,
        "taskId": task.id,
        "taskTitle": task.title,
        "category": task.category,
        "preparedBy": employee_id,
        "role": role_key,
    }
    offset = _stable_offset(task.id)
    if task.category == "quotation":
        units = 40 + offset % 11
        total = (Decimal(units * 77)).quantize(Decimal("0.01"))
        return {
            **base,
            "kind": "quotation",
            "units": units,
            "unitPrice": "77.00",
            "totalAmount": str(total),
            "deliveryDays": 14,
        }
    if task.category in ("inventory", "fulfilment", "sourcing"):
        return {
            **base,
            "kind": "stock_evidence",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "available": 40 + offset % 11,
            "required": 50,
            "location": "main-warehouse",
        }
    if task.category in ("approval", "review"):
        return {
            **base,
            "kind": "review",
            "summary": f"Reviewed '{task.title}' against the company template",
            "recommendation": "proceed",
        }
    return {
        **base,
        "kind": "plan",
        "summary": f"Plan for '{task.title}'",
        "nextSteps": [
            "Gather inputs from the company template",
            "Execute within the contracted budget",
            "Report the result as an artifact",
        ],
    }


# -- board state ----------------------------------------------------------


def _counts(session: Session, company_id: str) -> dict[str, int]:
    stmt = (
        select(CompanyTask.status, func.count())
        .where(CompanyTask.company_id == company_id)
        .group_by(CompanyTask.status)
    )
    counts = {TaskStatus.OPEN: 0, TaskStatus.COMPLETED: 0}
    for status, count in session.execute(stmt):
        counts[status] = int(count)
    return {
        "open": counts.get(TaskStatus.OPEN, 0),
        "completed": counts.get(TaskStatus.COMPLETED, 0),
        "awaiting": counts.get(TaskStatus.AWAITING_APPROVAL, 0),
        "blocked": counts.get(TaskStatus.BLOCKED, 0),
    }


def is_target_reached(session: Session, company_id: str) -> bool:
    """The board is fully worked: at least one completion, nothing left open.

    Until revenue is tracked against ``target_value``, a cleared board is the
    measurable proxy for the company target: every task the company defined is
    done and none is blocked or waiting on a person.
    """
    counts = _counts(session, company_id)
    return (
        counts["completed"] > 0
        and counts["open"] == 0
        and counts["awaiting"] == 0
        and counts["blocked"] == 0
    )


def is_budget_exhausted(
    session: Session, company_id: str, budget: BudgetService | None = None
) -> bool:
    """The current period ceiling has no committable money left."""
    service = budget or BudgetService(session)
    company = session.get(Company, company_id)
    if company is None:
        return False
    account = service.current_account(company, create=False)
    if account is None:
        return False
    return service.company_totals(account).available <= ZERO


def get_active_company(session: Session) -> Company | None:
    """The company holding the single active slot, if any."""
    stmt = (
        select(Company)
        .where(Company.status == CompanyStatus.ACTIVE)
        .order_by(Company.created_at, Company.id)
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


# -- one execution --------------------------------------------------------


def execute_task(
    session: Session,
    company_id: str,
    task_id: str,
    employee_id: str,
) -> CycleResult:
    """Execute one assigned task through budget and TrustGate. Never raises.

    Refusals (policy, money, contract) mark the task ``blocked`` with their
    reason code and return; only genuinely executed work marks it completed.
    """
    events = EventService(session)
    budget = BudgetService(session, events)
    company = session.get(Company, company_id)
    task = session.get(CompanyTask, task_id)
    if company is None or task is None:  # pragma: no cover - guarded by the caller
        return CycleResult(action="blocked", task_id=task_id, reason_code="unknown_task")

    try:
        contract = ContractGuard(session).resolve_active_contract(company_id, employee_id)
    except DomainError as exc:
        task.status = TaskStatus.BLOCKED
        session.flush()
        events.record(
            event_type="blocked",
            stream_id=STREAM_ID,
            task_id=task.id,
            payload={
                "companyId": company_id,
                "taskId": task.id,
                "reasonCode": "contract_invalid",
                "reason": str(exc),
            },
        )
        logger.info("task %s blocked: contract invalid (%s)", task.id, exc)
        return CycleResult(
            action="blocked", task_id=task.id, employee_id=employee_id,
            reason_code="contract_invalid",
        )

    employee = session.get(CompanyEmployee, employee_id)
    role_key = contract.role or (employee.role_key if employee else "support")
    agent_id = trustgate_agent_for(role_key)
    intent = intent_for_task(agent_id, task, company_id)
    decision = authorize_intent(intent)
    if not decision.allowed:
        task.status = TaskStatus.BLOCKED
        session.flush()
        events.record(
            event_type="policy_denied",
            stream_id=STREAM_ID,
            actor_id=employee_id,
            task_id=task.id,
            payload={
                "companyId": company_id,
                "taskId": task.id,
                "intent": intent.to_payload(),
                "policyDecision": decision.to_payload(),
            },
        )
        events.record(
            event_type="blocked",
            stream_id=STREAM_ID,
            actor_id=employee_id,
            task_id=task.id,
            payload={
                "companyId": company_id,
                "taskId": task.id,
                "reasonCode": "trustgate_denied",
                "reason": f"TrustGate denied execution of task '{task.id}': {decision.reason}",
            },
        )
        logger.info("task %s blocked: TrustGate denied (%s)", task.id, decision.reason)
        return CycleResult(
            action="blocked", task_id=task.id, employee_id=employee_id,
            reason_code="trustgate_denied",
        )

    meter = MockCostMeter()
    executor = BudgetedExecutor(budget, meter, policy=lambda: decision.allowed)
    maximum = estimate_for_category(task.category)
    operation_id = f"p09:{task.id}"
    request = BudgetReservationRequest(
        companyId=company_id,
        employeeId=employee_id,
        taskId=task.id,
        maximumAmount=maximum,
        idempotencyKey=f"{operation_id}:reserve",
        billableOperationId=operation_id,
    )

    def work() -> tuple[dict[str, Any], list[MeteredUsage]]:
        artifact = artifact_for_task(company, task, employee_id, role_key)
        return artifact, usage_for_task(task, operation_id)

    try:
        outcome = executor.run(reservation=request, work=work)
    except PolicyDenied:  # pragma: no cover - pre-checked above; kept for the race
        task.status = TaskStatus.BLOCKED
        session.flush()
        events.record(
            event_type="blocked",
            stream_id=STREAM_ID,
            actor_id=employee_id,
            task_id=task.id,
            payload={
                "companyId": company_id,
                "taskId": task.id,
                "reasonCode": "trustgate_denied",
                "reason": "policy denied the action before any reservation",
            },
        )
        return CycleResult(
            action="blocked", task_id=task.id, employee_id=employee_id,
            reason_code="trustgate_denied",
        )
    except DomainError as exc:
        task.status = TaskStatus.BLOCKED
        session.flush()
        events.record(
            event_type="blocked",
            stream_id=STREAM_ID,
            actor_id=employee_id,
            task_id=task.id,
            payload={
                "companyId": company_id,
                "taskId": task.id,
                "reasonCode": "execution_refused",
                "reason": str(exc),
            },
        )
        logger.info("task %s blocked: execution refused (%s)", task.id, exc)
        return CycleResult(
            action="blocked", task_id=task.id, employee_id=employee_id,
            reason_code="execution_refused",
        )

    if not outcome.executed:
        task.status = TaskStatus.BLOCKED
        session.flush()
        events.record(
            event_type="blocked",
            stream_id=STREAM_ID,
            actor_id=employee_id,
            task_id=task.id,
            payload={
                "companyId": company_id,
                "taskId": task.id,
                "reasonCode": "budget_exceeded",
                "reason": outcome.denial_reason
                or "budget refused the reservation for this task",
            },
        )
        logger.info("task %s blocked: budget refused (%s)", task.id, outcome.denial_reason)
        return CycleResult(
            action="blocked", task_id=task.id, employee_id=employee_id,
            reason_code="budget_exceeded",
        )

    artifact = outcome.result or {}
    task.status = TaskStatus.COMPLETED
    session.flush()
    charged = outcome.settlement.charged_amount if outcome.settlement else ZERO
    events.record(
        event_type="artifact_created",
        stream_id=STREAM_ID,
        actor_id=employee_id,
        task_id=task.id,
        payload={
            "companyId": company_id,
            "taskId": task.id,
            "artifact": artifact,
            "reservationId": outcome.reservation.reservation_id,
            "chargedAmount": str(charged),
            "currency": outcome.reservation.currency,
            "meterSource": meter.source.value,
        },
    )
    events.record(
        event_type="task_completed",
        stream_id=STREAM_ID,
        actor_id=employee_id,
        task_id=task.id,
        payload={
            "companyId": company_id,
            "taskId": task.id,
            "message": f"Task '{task.title}' completed by {employee_id}",
        },
    )
    logger.info("task %s completed by %s (charged %s)", task.id, employee_id, charged)
    return CycleResult(
        action="completed", task_id=task.id, employee_id=employee_id, artifact=artifact
    )


# -- the loop -------------------------------------------------------------


def run_cycle(session: Session, company_id: str) -> CycleResult:
    """One tick: staff the next task, then execute it. Never raises."""
    outcome = Manager(session).pick_and_assign(company_id)
    if outcome.action == "assigned":
        assert outcome.task_id is not None and outcome.employee_id is not None
        return execute_task(session, company_id, outcome.task_id, outcome.employee_id)
    if outcome.action == "no_tasks":
        return CycleResult(action="no_tasks")
    return CycleResult(
        action="blocked" if outcome.action == "blocked_no_worker" else "awaiting_human",
        task_id=outcome.task_id,
        employee_id=outcome.employee_id,
        reason_code=outcome.reason_code,
    )


def run_until_target_or_budget(
    session: Session,
    company_id: str,
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> LoopResult:
    """Work the board until it is done, broke, empty, or bounded.

    Stop reasons: ``target_reached`` (board fully complete), ``budget_exhausted``
    (the period ceiling has nothing committable left), ``no_actionable_tasks``
    (open work remains but none can be staffed or executed autonomously), or
    ``max_iterations`` (the safety stop).
    """
    company = session.get(Company, company_id)
    if company is None:
        raise ConflictError(
            f"Company '{company_id}' not found", field="companyId"
        )
    if company.status is not CompanyStatus.ACTIVE:
        raise ConflictError(
            f"Company '{company_id}' is {company.status.value}; autonomous "
            "execution requires an active company",
            field="status",
        )

    result = LoopResult(stop_reason=MAX_ITERATIONS)
    while result.cycles < max_iterations:
        if is_target_reached(session, company_id):
            result.stop_reason = TARGET_REACHED
            break
        if is_budget_exhausted(session, company_id):
            result.stop_reason = BUDGET_EXHAUSTED
            break
        cycle = run_cycle(session, company_id)
        result.cycles += 1
        if cycle.task_id is not None:
            result.task_ids.append(cycle.task_id)
        if cycle.action == "completed":
            result.completed += 1
        elif cycle.action in ("blocked", "awaiting_human"):
            result.blocked += 1
        else:  # no_tasks: nothing left the Manager can staff
            if is_target_reached(session, company_id):
                result.stop_reason = TARGET_REACHED
            elif is_budget_exhausted(session, company_id):
                result.stop_reason = BUDGET_EXHAUSTED
            else:
                result.stop_reason = NO_ACTIONABLE_TASKS
            break
    else:
        if is_target_reached(session, company_id):
            result.stop_reason = TARGET_REACHED
        elif is_budget_exhausted(session, company_id):
            result.stop_reason = BUDGET_EXHAUSTED

    logger.info(
        "autonomous run for %s stopped: %s after %d cycles (%d completed, %d blocked)",
        company_id, result.stop_reason, result.cycles, result.completed, result.blocked,
    )
    return result


__all__ = [
    "BUDGET_EXHAUSTED",
    "DEFAULT_MAX_ITERATIONS",
    "MAX_ITERATIONS",
    "NO_ACTIONABLE_TASKS",
    "TARGET_REACHED",
    "CycleResult",
    "LoopResult",
    "artifact_for_task",
    "execute_task",
    "get_active_company",
    "intent_for_task",
    "is_budget_exhausted",
    "is_target_reached",
    "run_cycle",
    "run_until_target_or_budget",
    "trustgate_agent_for",
    "usage_for_task",
]
