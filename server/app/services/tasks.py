"""Task queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Task


class TaskService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_tasks(
        self,
        *,
        status: str | None = None,
        assigned_agent_id: str | None = None,
        parent_task_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(Task).order_by(Task.created_at, Task.id)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if assigned_agent_id is not None:
            stmt = stmt.where(Task.assigned_agent_id == assigned_agent_id)
        if parent_task_id is not None:
            stmt = stmt.where(Task.parent_task_id == parent_task_id)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def get_task(self, task_id: str) -> Task | None:
        stmt = (
            select(Task)
            .options(selectinload(Task.assigned_agent), selectinload(Task.subtasks))
            .where(Task.id == task_id)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def add_task(self, task: Task) -> Task:
        self._session.add(task)
        self._session.commit()
        self._session.refresh(task)
        return task

    def set_status(self, task: Task, status: str) -> Task:
        task.status = status
        self._session.commit()
        self._session.refresh(task)
        return task


def get_task_service(session: Session) -> TaskService:
    return TaskService(session)