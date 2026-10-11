"""Company task service.

A company task is a unit of work assigned to a configured employee. It is the
entity a budget reservation refers to when committing money for billable work.

The service follows the same pattern as every other company service: validate
against persisted state, mutate, stage the governance event, and commit in one
transaction. Nothing is published before the row exists.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company.errors import ConfigurationError, ConflictError, NotFoundError
from app.models import (
    CompanyEmployee,
    CompanyTask,
    Contract,
    ContractStatus,
    TaskStatus,
    new_company_task_id,
)
from app.schemas.company import CompanyTaskCreate, CompanyTaskUpdate
from app.services.companies import STREAM_ID, CompanyService
from app.services.events import EventService

logger = logging.getLogger(__name__)


class CompanyTaskService:
    def __init__(self, session: Session, events: EventService | None = None) -> None:
        self._session = session
        self._events = events or EventService(session)
        self._companies = CompanyService(session, self._events)

    # -- reads -------------------------------------------------------------

    def get_task(self, task_id: str) -> CompanyTask:
        task = self._session.get(CompanyTask, task_id)
        if task is None:
            raise NotFoundError(f"Task '{task_id}' not found", field="taskId")
        return task

    def list_for_company(self, company_id: str) -> list[CompanyTask]:
        self._companies.get_company(company_id)
        stmt = (
            select(CompanyTask)
            .where(CompanyTask.company_id == company_id)
            .order_by(CompanyTask.created_at, CompanyTask.id)
        )
        return list(self._session.execute(stmt).scalars())

    def list_for_employee(self, company_id: str, employee_id: str) -> list[CompanyTask]:
        self._companies.get_company(company_id)
        employee = self._session.get(CompanyEmployee, employee_id)
        if employee is None or employee.company_id != company_id:
            raise NotFoundError(
                f"Employee '{employee_id}' does not belong to company '{company_id}'",
                field="employeeId",
            )
        stmt = (
            select(CompanyTask)
            .where(
                CompanyTask.company_id == company_id,
                CompanyTask.employee_id == employee_id,
            )
            .order_by(CompanyTask.created_at, CompanyTask.id)
        )
        return list(self._session.execute(stmt).scalars())

    # -- create ------------------------------------------------------------

    def create(self, company_id: str, payload: CompanyTaskCreate) -> CompanyTask:
        """Create a task assigned to a company employee.

        The employee must belong to this company. When the employee has an active
        contract, the task category must fall inside the contract's task scope.
        """
        self._companies.get_company(company_id)
        employee = self._session.get(CompanyEmployee, payload.employee_id)
        if employee is None or employee.company_id != company_id:
            raise NotFoundError(
                f"Employee '{payload.employee_id}' does not belong to company '{company_id}'",
                field="employeeId",
            )

        self._validate_category(company_id, payload.employee_id, payload.category)

        task = CompanyTask(
            id=new_company_task_id(),
            company_id=company_id,
            employee_id=payload.employee_id,
            title=payload.title,
            category=payload.category,
            status=TaskStatus.OPEN,
            description=payload.description,
        )
        self._session.add(task)
        self._session.flush()

        event = self._events.stage(
            event_type="company_task_created",
            stream_id=STREAM_ID,
            target_id=task.id,
            payload={
                "companyId": company_id,
                "taskId": task.id,
                "employeeId": task.employee_id,
                "title": task.title,
                "category": task.category,
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(task)
        logger.info("created task %s for employee %s", task.id, task.employee_id)
        return task

    # -- update ------------------------------------------------------------

    def update(self, task_id: str, payload: CompanyTaskUpdate) -> tuple[CompanyTask, bool]:
        """Apply a partial update. Returns the task and whether it changed.

        A PATCH that changes nothing is a read: it returns 200 and emits no event.
        """
        task = self.get_task(task_id)

        changes = payload.model_dump(exclude_unset=True, by_alias=True)
        if not changes:
            return task, False

        if "category" in changes:
            self._validate_category(task.company_id, task.employee_id, changes["category"])

        changed_fields: list[str] = []
        for field in ("title", "category", "status", "description"):
            if field in changes:
                attribute = _FIELD_TO_COLUMN[field]
                value = changes[field]
                if field == "status":
                    value = TaskStatus(value)
                if getattr(task, attribute) != value:
                    setattr(task, attribute, value)
                    changed_fields.append(field)

        if not changed_fields:
            return task, False

        self._session.flush()
        event = self._events.stage(
            event_type="company_task_updated",
            stream_id=STREAM_ID,
            target_id=task.id,
            payload={
                "companyId": task.company_id,
                "taskId": task.id,
                "employeeId": task.employee_id,
                "changedFields": sorted(changed_fields),
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(task)
        logger.info(
            "updated task %s (%s)", task.id, ", ".join(sorted(changed_fields))
        )
        return task, True

    # -- internals ---------------------------------------------------------

    def _validate_category(
        self, company_id: str, employee_id: str, category: str
    ) -> None:
        """Validate the task category against the employee's contract scope.

        When the employee has an active contract, the category must appear in the
        contract's task scope. An employee without an active contract has no scope
        to check against, so any category is accepted.
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
        if contract is None or contract.status is not ContractStatus.ACTIVE:
            return
        if contract.task_scope and category not in contract.task_scope:
            raise ConfigurationError(
                f"Category '{category}' is not in the employee's contract task scope: "
                f"{', '.join(contract.task_scope)}",
                field="category",
            )


#: Incoming camelCase field -> ORM column.
_FIELD_TO_COLUMN = {
    "title": "title",
    "category": "category",
    "status": "status",
    "description": "description",
}


def get_company_task_service(session: Session) -> CompanyTaskService:
    return CompanyTaskService(session)


__all__ = [
    "CompanyTaskService",
    "get_company_task_service",
]
