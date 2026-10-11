"""Task read endpoints and the company task update endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, not_found, to_http
from app.company.errors import DomainError
from app.schemas import CompanyTaskOut, CompanyTaskUpdate, TaskOut
from app.services import get_task_service
from app.services.company_tasks import CompanyTaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut], summary="List tasks")
def list_tasks(
    session: DbSession,
    status: str | None = None,
    assigned_agent_id: str | None = None,
    parent_task_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TaskOut]:
    tasks = get_task_service(session).list_tasks(
        status=status,
        assigned_agent_id=assigned_agent_id,
        parent_task_id=parent_task_id,
        limit=limit,
        offset=offset,
    )
    return [TaskOut.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskOut, summary="Get one task")
def get_task(task_id: str, session: DbSession) -> TaskOut:
    task = get_task_service(session).get_task(task_id)
    if task is None:
        raise not_found("Task", task_id)
    return TaskOut.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=CompanyTaskOut,
    summary="Update a company task",
)
def update_task(task_id: str, payload: CompanyTaskUpdate, session: DbSession) -> CompanyTaskOut:
    """Partial update of a company task. A PATCH that changes nothing emits no event."""
    service = CompanyTaskService(session)
    try:
        task, _changed = service.update(task_id, payload)
    except DomainError as error:
        raise to_http(error)
    return CompanyTaskOut.model_validate(task)