"""P0.2 event and transaction integrity.

Configuration changes are auditable facts, so three properties must hold:

* the state change and its event commit together, or neither does;
* an event is never published before its transaction commits;
* a no-op update does not manufacture a change event.

The publication tests subscribe to the real :class:`EventBus`, because the claim
under test is about what a subscriber sees, not about what the database holds.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.events.bus import get_event_bus
from app.events.types import EventType
from app.models import Company, CompanyEmployee
from tests.p0_2_helpers import create_company, seat, workforce


def put_workforce(client: TestClient, company_id: str, *seats):
    return client.put(f"/api/companies/{company_id}/workforce", json=workforce(*seats))


def stream_events(client: TestClient, event_type: str) -> list[dict]:
    response = client.get("/api/events", params={"stream_id": "main", "limit": 500})
    assert response.status_code == 200, response.text
    return [event for event in response.json() if event["type"] == event_type]


@pytest.fixture()
def published():
    """Capture everything the bus publishes during a test."""
    bus = get_event_bus()
    received: list[dict] = []
    unsubscribe = bus.subscribe(received.append)
    try:
        yield received
    finally:
        unsubscribe()


# -- the right events are emitted -------------------------------------------


def test_creation_emits_company_created(configured_client: TestClient):
    company = create_company(configured_client)

    events = stream_events(configured_client, EventType.COMPANY_CREATED.value)
    assert len(events) == 1
    event = events[0]
    assert event["payload"]["companyId"] == company["id"]
    assert event["payload"]["name"] == company["name"]
    assert event["payload"]["templateKey"] == "clothing"
    assert event["payload"]["status"] == "draft"
    assert event["runId"] is None


def test_a_substantive_update_emits_company_updated(configured_client: TestClient):
    company = create_company(configured_client)
    configured_client.patch(f"/api/companies/{company['id']}", json={"name": "Renamed"})

    events = stream_events(configured_client, EventType.COMPANY_UPDATED.value)
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["companyId"] == company["id"]
    assert payload["changedFields"] == ["name"]
    assert payload["revision"] == 2


def test_workforce_replacement_emits_workforce_configured(configured_client: TestClient):
    company = create_company(configured_client)
    created = put_workforce(configured_client, company["id"], seat("Alex", "sales")).json()
    kept = created["employees"][0]["id"]

    put_workforce(
        configured_client, company["id"], created["employees"][0], seat("Sam", "manager")
    )

    events = stream_events(configured_client, EventType.WORKFORCE_CONFIGURED.value)
    assert len(events) == 2

    second = events[-1]["payload"]
    assert second["companyId"] == company["id"]
    assert second["employeeCount"] == 2
    assert second["addedEmployeeIds"] and kept not in second["addedEmployeeIds"]
    assert second["updatedEmployeeIds"] == [kept]


# -- no misleading events ---------------------------------------------------


def test_a_no_op_patch_emits_no_event(configured_client: TestClient):
    company = create_company(configured_client)

    # Same value it already has.
    response = configured_client.patch(
        f"/api/companies/{company['id']}", json={"name": company["name"]}
    )
    assert response.status_code == 200
    assert stream_events(configured_client, EventType.COMPANY_UPDATED.value) == []


def test_an_empty_patch_emits_no_event(configured_client: TestClient):
    company = create_company(configured_client)

    response = configured_client.patch(f"/api/companies/{company['id']}", json={})
    assert response.status_code == 200
    assert stream_events(configured_client, EventType.COMPANY_UPDATED.value) == []
    assert configured_client.get(f"/api/companies/{company['id']}").json()["revision"] == 1


def test_an_unchanged_budget_emits_no_event(configured_client: TestClient):
    """Re-sending the same ceiling is not an adjustment, and says so by staying silent."""
    company = create_company(configured_client)

    configured_client.patch(
        f"/api/companies/{company['id']}", json={"monthlyBudget": company["monthlyBudget"]}
    )
    assert stream_events(configured_client, EventType.COMPANY_UPDATED.value) == []


def test_a_refused_request_emits_nothing(configured_client: TestClient):
    company = create_company(configured_client)
    configured_client.patch(f"/api/companies/{company['id']}", json={"currency": "EUR"})
    put_workforce(configured_client, company["id"], seat("Alex", "wizard"))

    assert stream_events(configured_client, EventType.COMPANY_UPDATED.value) == []
    assert stream_events(configured_client, EventType.WORKFORCE_CONFIGURED.value) == []


# -- transaction integrity --------------------------------------------------


def test_events_are_published_only_after_the_commit(configured_client: TestClient, factory_for):
    """A subscriber must never see an event before its state is durable.

    The subscriber opens its own session and reads the company. If publication
    happened before the commit, that read would come back empty — which is exactly
    the failure this ordering rule exists to prevent.
    """
    seen: list[str | None] = []
    probe = factory_for()

    def assert_state_is_committed(event: dict) -> None:
        if event["type"] != "company_created":
            return
        company_id = event["payload"]["companyId"]
        probe.rollback()  # drop anything this session cached earlier
        seen.append(company_id if probe.get(Company, company_id) is not None else None)

    unsubscribe = get_event_bus().subscribe(assert_state_is_committed)
    try:
        company = create_company(configured_client)
    finally:
        unsubscribe()
        probe.close()

    assert seen == [company["id"]]


def test_a_rolled_back_replacement_publishes_nothing(configured_client: TestClient, published):
    company = create_company(configured_client)
    before = len(published)

    response = put_workforce(
        configured_client,
        company["id"],
        seat("Valid", "sales"),
        {**seat("Loop", "manager"), "id": "emp_loop", "reportsToId": "emp_loop"},
    )
    assert response.status_code == 422

    emitted = [
        event
        for event in published[before:]
        if event["type"] == "workforce_configured"
    ]
    assert emitted == []


def test_a_failed_creation_publishes_nothing(configured_client: TestClient, published):
    before = len(published)
    response = configured_client.post(
        "/api/companies", json={"name": "Bad", "templateKey": "nope", "monthlyBudget": "10", "currency": "USD"}
    )
    assert response.status_code == 422
    assert [event for event in published[before:] if event["type"] == "company_created"] == []


# -- payload shape and timing ----------------------------------------------


def test_configuration_events_carry_no_workflow_run(configured_client: TestClient):
    company = create_company(configured_client)
    put_workforce(configured_client, company["id"], seat("Alex", "sales"))

    for event_type in ("company_created", "workforce_configured"):
        for event in stream_events(configured_client, event_type):
            assert event["runId"] is None
            assert event["taskId"] is None


def test_configuration_events_use_real_time_and_no_logical_offset(
    configured_client: TestClient,
):
    before = datetime.now(timezone.utc) - timedelta(seconds=5)
    company = create_company(configured_client)
    put_workforce(configured_client, company["id"], seat("Alex", "sales"))
    after = datetime.now(timezone.utc) + timedelta(seconds=5)

    response = configured_client.get("/api/events", params={"stream_id": "main", "limit": 500})
    events = [e for e in response.json() if e["type"] in ("company_created", "workforce_configured")]
    assert len(events) == 2

    for event in events:
        stamp = datetime.fromisoformat(event["timestamp"])
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        assert before <= stamp <= after
        # A workflow offset would make a configuration event look like part of a run.
        assert event["clockOffsetMs"] is None


def test_configuration_events_carry_no_private_configuration(configured_client: TestClient):
    company = create_company(configured_client)

    events = stream_events(configured_client, EventType.COMPANY_CREATED.value)
    payload = events[0]["payload"]
    allowed = {"companyId", "name", "templateKey", "currency", "monthlyBudget", "status"}
    assert set(payload) == allowed
    assert not any("secret" in key.lower() or "password" in key.lower() for key in payload)


def test_event_sequence_ordering_stays_valid(configured_client: TestClient):
    company = create_company(configured_client)
    put_workforce(configured_client, company["id"], seat("Alex", "sales"))
    configured_client.patch(f"/api/companies/{company['id']}", json={"name": "Renamed"})

    response = configured_client.get("/api/events", params={"stream_id": "main", "limit": 500})
    events = response.json()
    sequences = [event["sequence"] for event in events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)


def test_repeated_operations_produce_distinct_events(configured_client: TestClient):
    first = create_company(configured_client, name="First")
    second = create_company(configured_client, name="Second")

    events = stream_events(configured_client, EventType.COMPANY_CREATED.value)
    assert {event["payload"]["companyId"] for event in events} == {first["id"], second["id"]}
    assert len({event["id"] for event in events}) == 2


def test_company_state_and_event_survive_a_new_session(
    configured_client: TestClient, factory_for
):
    company = create_company(configured_client)
    put_workforce(configured_client, company["id"], seat("Alex", "sales"))

    session = factory_for()
    try:
        assert session.get(Company, company["id"]) is not None
        assert session.query(CompanyEmployee).filter_by(company_id=company["id"]).count() == 1
    finally:
        session.close()