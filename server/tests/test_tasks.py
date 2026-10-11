"""Task persistence and Manager -> subordinate delegation."""

from __future__ import annotations

from app.models import Task, TaskStatus
from app.services import get_task_service


def _task(**kwargs) -> Task:
    return Task(title="Draft quotation", objective="Draft from visible data", **kwargs)


def test_task_round_trip(seeded_session):
    task = get_task_service(seeded_session).add_task(
        _task(id="task-1", assigned_agent_id="manager", status=TaskStatus.OPEN)
    )
    stored = seeded_session.get(Task, "task-1")
    assert stored is not None
    assert stored.title == task.title
    assert stored.assigned_agent_id == "manager"
    assert stored.created_at is not None


def test_task_parent_child_delegation(seeded_session):
    service = get_task_service(seeded_session)
    service.add_task(_task(id="parent", assigned_agent_id="manager"))
    service.add_task(_task(id="child", assigned_agent_id="sales", parent_task_id="parent"))

    parent = service.get_task("parent")
    assert [t.id for t in parent.subtasks] == ["child"]
    assert service.get_task("child").parent_task_id == "parent"


def test_task_relationship_to_agent(seeded_session):
    get_task_service(seeded_session).add_task(
        _task(id="task-1", assigned_agent_id="sales")
    )
    task = get_task_service(seeded_session).get_task("task-1")
    assert task.assigned_agent.id == "sales"


def test_task_filter_by_assignee_and_status(seeded_session):
    service = get_task_service(seeded_session)
    service.add_task(_task(id="t-a", assigned_agent_id="sales"))
    service.add_task(_task(id="t-b", assigned_agent_id="manager", status=TaskStatus.COMPLETED))

    assert [t.id for t in service.list_tasks(assigned_agent_id="sales")] == ["t-a"]
    assert [t.id for t in service.list_tasks(status="completed")] == ["t-b"]


def test_tasks_api_lists_tasks(client):
    response = client.get("/api/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_tasks_api_shape_after_seed(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    body = client.get("/api/tasks").json()
    ids = {t["id"] for t in body}
    assert {"task-order-1042", "task-quote-1042"} <= ids
    subtask = next(t for t in body if t["id"] == "task-quote-1042")
    assert subtask["parentTaskId"] == "task-order-1042"
    assert subtask["assignedAgentId"] == "sales"


def test_tasks_api_404(client):
    assert client.get("/api/tasks/does-not-exist").status_code == 404