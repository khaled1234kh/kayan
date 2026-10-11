"""P0.7 preparation: company task endpoints and the pre-execution contract guard.

A company task is the entity a budget reservation refers to when committing money
for billable work, so it has a contract-scoped category and belongs to one employee
of one company. The :class:`ContractGuard` is the P0.7 seam: before an agent
executes, its company employee must resolve to a live, hash-verified contract, and
the runtime consults the guard before any step runs.

Both were built in the P0.7 backend prep commit; these tests pin the behaviour.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.company.errors import ConfigurationError, ConflictError, NotFoundError
from app.models import Contract, ContractStatus, TaskStatus, WorkflowRun, WorkflowRunStatus
from app.runtime import KayanRuntime
from app.schemas.company import CompanyTaskCreate, CompanyTaskUpdate
from app.services.company_tasks import CompanyTaskService
from app.services.events import EventService
from app.services.execution import ContractGuard
from tests.p0_4_helpers import api_allocations, api_company, api_workforce, post_generate
from tests.p0_5_helpers import make_spendable_company


def _utc(dt: datetime) -> datetime:
    """Normalize a datetime to aware UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def events_of(session, event_type):
    return [
        event
        for event in EventService(session).list_events(stream_id="main", limit=500)
        if event.event_type == event_type
    ]


# -- company tasks: service ---------------------------------------------------


def test_creating_a_task_stages_company_task_created(seeded_session):
    live = make_spendable_company(seeded_session)
    service = CompanyTaskService(seeded_session)

    task = service.create(
        live.company_id,
        CompanyTaskCreate(
            title="Quote the client",
            category="quotation",
            employeeId=live.seller_id,
            description="Draft the quotation from the catalogue",
        ),
    )

    assert task.id.startswith("tsk_")
    assert task.status is TaskStatus.OPEN
    assert task.employee_id == live.seller_id

    created = events_of(seeded_session, "company_task_created")
    assert len(created) == 1
    payload = created[0].payload
    assert payload["taskId"] == task.id
    assert payload["companyId"] == live.company_id
    assert payload["employeeId"] == live.seller_id


def test_a_category_outside_the_contract_scope_is_refused(seeded_session):
    live = make_spendable_company(seeded_session)
    service = CompanyTaskService(seeded_session)

    with pytest.raises(ConfigurationError) as caught:
        service.create(
            live.company_id,
            CompanyTaskCreate(
                title="Handle support",
                category="support",
                employeeId=live.seller_id,
            ),
        )

    assert "task scope" in str(caught.value)


def test_a_task_for_an_employee_of_another_company_is_refused(seeded_session):
    live = make_spendable_company(seeded_session)
    other = make_spendable_company(seeded_session, activate=False)
    service = CompanyTaskService(seeded_session)

    with pytest.raises(NotFoundError):
        service.create(
            live.company_id,
            CompanyTaskCreate(
                title="Cross company work",
                category="quotation",
                employeeId=other.seller_id,
            ),
        )


def test_listing_returns_company_tasks_ordered_by_creation(seeded_session):
    live = make_spendable_company(seeded_session)
    service = CompanyTaskService(seeded_session)
    first = service.create(
        live.company_id,
        CompanyTaskCreate(title="First", category="quotation", employeeId=live.seller_id),
    )
    second = service.create(
        live.company_id,
        CompanyTaskCreate(title="Second", category="quotation", employeeId=live.seller_id),
    )

    listed = service.list_for_company(live.company_id)

    # The fixture itself already created two tasks (task, other_task).
    assert {task.id for task in listed} == {
        first.id,
        second.id,
        live.task.id,
        live.other_task.id,
    }
    # The documented ordering rule: ascending by (created_at, id).
    assert [(_utc(task.created_at), task.id) for task in listed] == sorted(
        (_utc(task.created_at), task.id) for task in listed
    )


def test_updating_a_task_emits_company_task_updated(seeded_session):
    live = make_spendable_company(seeded_session)
    service = CompanyTaskService(seeded_session)
    task = service.create(
        live.company_id,
        CompanyTaskCreate(title="Quote", category="quotation", employeeId=live.seller_id),
    )

    updated, changed = service.update(
        task.id, CompanyTaskUpdate(status="completed", title="Quote and close")
    )

    assert changed is True
    assert updated.status is TaskStatus.COMPLETED
    assert updated.title == "Quote and close"

    updated_events = events_of(seeded_session, "company_task_updated")
    assert len(updated_events) == 1
    assert updated_events[0].payload["taskId"] == task.id
    assert updated_events[0].payload["changedFields"] == ["status", "title"]


def test_a_noop_update_emits_no_event(seeded_session):
    live = make_spendable_company(seeded_session)
    service = CompanyTaskService(seeded_session)
    task = service.create(
        live.company_id,
        CompanyTaskCreate(title="Quote", category="quotation", employeeId=live.seller_id),
    )

    updated, changed = service.update(task.id, CompanyTaskUpdate(title="Quote"))

    assert changed is False
    assert updated.id == task.id
    assert events_of(seeded_session, "company_task_updated") == []


def test_updating_a_category_outside_scope_is_refused(seeded_session):
    live = make_spendable_company(seeded_session)
    service = CompanyTaskService(seeded_session)
    task = service.create(
        live.company_id,
        CompanyTaskCreate(title="Quote", category="quotation", employeeId=live.seller_id),
    )

    with pytest.raises(ConfigurationError):
        service.update(task.id, CompanyTaskUpdate(category="support"))


# -- company tasks: endpoints -------------------------------------------------


def _active_company(client):
    """A company with workforce, contracts and activation, through the API."""
    company_id = api_company(client)
    employee_ids = api_workforce(client, company_id)
    generated = post_generate(client, company_id, api_allocations(employee_ids))
    assert generated.status_code == 201, generated.text
    activated = client.post(f"/api/companies/{company_id}/activate")
    assert activated.status_code == 200, activated.text
    return company_id, employee_ids


def test_create_list_and_patch_a_task_over_http(configured_client):
    company_id, employee_ids = _active_company(configured_client)
    seller_id = employee_ids[2]

    created = configured_client.post(
        f"/api/companies/{company_id}/tasks",
        json={
            "title": "Quote the client",
            "category": "quotation",
            "employeeId": seller_id,
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["id"].startswith("tsk_")
    assert task["status"] == "open"
    assert task["employeeId"] == seller_id

    listed = configured_client.get(f"/api/companies/{company_id}/tasks")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [task["id"]]

    patched = configured_client.patch(
        f"/api/tasks/{task['id']}", json={"status": "completed", "title": "Closed out"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"
    assert patched.json()["title"] == "Closed out"


def test_a_task_category_outside_the_contract_scope_is_422(configured_client):
    company_id, employee_ids = _active_company(configured_client)

    response = configured_client.post(
        f"/api/companies/{company_id}/tasks",
        json={
            "title": "Handle support",
            "category": "support",
            "employeeId": employee_ids[2],
        },
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["field"] == "category"


def test_patching_an_unknown_task_is_404(configured_client):
    response = configured_client.patch("/api/tasks/does_not_exist", json={})

    assert response.status_code == 404, response.text


def test_patching_with_an_unrecognised_status_is_422(configured_client):
    company_id, employee_ids = _active_company(configured_client)
    created = configured_client.post(
        f"/api/companies/{company_id}/tasks",
        json={
            "title": "Quote",
            "category": "quotation",
            "employeeId": employee_ids[2],
        },
    )
    task_id = created.json()["id"]

    response = configured_client.patch(
        f"/api/tasks/{task_id}", json={"status": "in_progress"}
    )

    assert response.status_code == 422, response.text


def test_creating_a_task_for_an_unknown_company_is_404(configured_client):
    response = configured_client.post(
        "/api/companies/does_not_exist/tasks",
        json={"title": "Quote", "category": "quotation", "employeeId": "emp_x"},
    )

    assert response.status_code == 404, response.text


# -- the pre-execution contract guard -----------------------------------------


def test_the_guard_resolves_an_active_contract(seeded_session):
    live = make_spendable_company(seeded_session)
    expected = live.contract_for(live.seller_id)

    resolved = ContractGuard(seeded_session).resolve_active_contract(
        live.company_id, live.seller_id
    )

    assert resolved.id == expected.id
    assert resolved.status is ContractStatus.ACTIVE
    assert resolved.company_id == live.company_id
    assert resolved.employee_id == live.seller_id


def test_the_guard_fails_closed_on_a_tampered_contract(seeded_session):
    live = make_spendable_company(seeded_session)
    contract = live.contract_for(live.seller_id)
    contract.content_hash = "0" * 64
    seeded_session.commit()

    with pytest.raises(ConflictError) as caught:
        ContractGuard(seeded_session).resolve_active_contract(
            live.company_id, live.seller_id
        )

    assert "integrity" in str(caught.value)


def test_the_guard_refuses_an_employee_with_no_active_contract(seeded_session):
    live = make_spendable_company(seeded_session, activate=False)

    with pytest.raises(ConflictError) as caught:
        ContractGuard(seeded_session).resolve_active_contract(
            live.company_id, live.seller_id
        )

    assert "no active contract" in str(caught.value)


def test_the_guard_refuses_an_employee_of_another_company(seeded_session):
    live = make_spendable_company(seeded_session)
    other = make_spendable_company(seeded_session, activate=False)

    with pytest.raises(NotFoundError):
        ContractGuard(seeded_session).resolve_active_contract(
            live.company_id, other.seller_id
        )


def test_the_guard_refuses_an_unknown_employee(seeded_session):
    live = make_spendable_company(seeded_session)

    with pytest.raises(NotFoundError):
        ContractGuard(seeded_session).resolve_active_contract(
            live.company_id, "emp_does_not_exist"
        )


# -- the runtime consults the guard before any step ----------------------------


def test_request_order_resolves_the_active_contract_and_completes(seeded_session):
    live = make_spendable_company(seeded_session)

    run = KayanRuntime().request_order(
        seeded_session,
        order_id="1042",
        request_id="req-p0.7-ok",
        employee_id=live.seller_id,
        company_id=live.company_id,
    )

    assert run.status is WorkflowRunStatus.COMPLETED
    events = EventService(seeded_session).list_events(run_id=run.id, limit=500)
    assert run.event_count == len(events) == 43


def test_request_order_stops_before_any_work_without_an_active_contract(
    seeded_session,
):
    live = make_spendable_company(seeded_session, activate=False)

    with pytest.raises(ConflictError):
        KayanRuntime().request_order(
            seeded_session,
            order_id="1042",
            request_id="req-p0.7-blocked",
            employee_id=live.seller_id,
            company_id=live.company_id,
        )

    # The guard runs before the run is created: nothing was persisted.
    assert seeded_session.query(WorkflowRun).count() == 0


def test_a_runtime_run_without_the_seam_still_works(seeded_session):
    """Omitting the ids keeps the original P0.5 behaviour."""
    run = KayanRuntime().request_order(
        seeded_session, order_id="1042", request_id="req-p0.7-plain"
    )

    assert run.status is WorkflowRunStatus.COMPLETED
    assert run.event_count == 43