"""P0.4 activation, versioning and pause/resume.

The claims under test are the ones with teeth: activation is atomic or it does not
happen, activated terms are immutable at the database as well as in the service, a
successor never disturbs its predecessor, and a failure at any point leaves no
partial state behind.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.company.contract_terms import compute_content_hash
from app.company.errors import ConfigurationError, ConflictError
from app.models import (
    Agent,
    BudgetAccount,
    CompanyEmployee,
    CompanyStatus,
    Contract,
    ContractStatus,
    EmployeeStatus,
)
from app.schemas.contract import ContractPatch, ContractVersionRequest, ResumeRequest
from app.services.contracts import ContractService
from app.services.events import EventService
from app.services.lifecycle import CompanyLifecycleService
from tests.p0_4_helpers import (
    activate,
    active_contracts,
    allocations_for,
    assert_hashes_match,
    contracts_of,
    draft_contracts,
    generate,
    make_company,
    make_workforce,
    pause_of,
    resume as do_resume,
    set_status,
)


@pytest.fixture()
def ready(seeded_session):
    """A company with a workforce and draft contracts, ready to activate."""
    company = make_company(seeded_session)
    make_workforce(seeded_session, company.id)
    generate(seeded_session, company.id)
    return company


@pytest.fixture()
def live(seeded_session, ready):
    """A company that has been activated."""
    activate(seeded_session, ready.id)
    return ready


def events_of(session, event_type):
    return [
        event
        for event in EventService(session).list_events(stream_id="main", limit=500)
        if event.event_type == event_type
    ]


# -- initial activation -----------------------------------------------------


def test_a_valid_company_activates(seeded_session, ready):
    result = activate(seeded_session, ready.id)

    assert result.status == "active"
    assert result.employee_count == 3
    assert len(result.contract_ids) == 3
    assert result.activated_at.tzinfo is not None


def test_activation_sets_contracts_employees_and_company(seeded_session, ready):
    before = seeded_session.get(type(ready), ready.id).revision
    activate(seeded_session, ready.id)

    company = seeded_session.get(type(ready), ready.id)
    assert company.status is CompanyStatus.ACTIVE
    # Activation is itself a configuration change: the revision moves so a client
    # holding the old roster can detect staleness.
    assert company.revision == before + 1

    employees = seeded_session.query(CompanyEmployee).filter_by(company_id=ready.id).all()
    assert len(employees) == 3
    for employee in employees:
        assert employee.status is EmployeeStatus.ACTIVE
        assert employee.active_contract_id is not None
        contract = seeded_session.get(Contract, employee.active_contract_id)
        assert contract.status is ContractStatus.ACTIVE
        assert contract.activated_at is not None
        assert contract.effective_at is not None


def test_activation_commits_its_events(seeded_session, ready):
    activate(seeded_session, ready.id)

    assert len(events_of(seeded_session, "contract_activated")) == 3
    activated = events_of(seeded_session, "company_activated")
    assert len(activated) == 1
    payload = activated[0].payload
    assert payload["companyId"] == ready.id
    assert len(payload["employeeIds"]) == 3
    assert len(payload["contractIds"]) == 3
    assert payload["activatedAt"]


def test_company_activated_payload_carries_no_contract_bodies(seeded_session, ready):
    activate(seeded_session, ready.id)

    payload = events_of(seeded_session, "company_activated")[0].payload
    assert set(payload) == {
        "companyId",
        "revision",
        "employeeIds",
        "contractIds",
        "activatedAt",
    }
    serialised = str(payload)
    assert "responsibilities" not in serialised
    assert "budgetPerMonth" not in serialised


def test_activation_requires_contracts_for_every_employee(seeded_session, ready):
    # Remove one employee's draft contract, as if it had never been generated.
    victim = draft_contracts(seeded_session, ready.id)[0]
    seeded_session.delete(victim)
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "no draft contract" in str(caught.value)


def test_activation_refuses_a_company_with_no_workforce(seeded_session):
    company = make_company(seeded_session)

    with pytest.raises(ConfigurationError):
        activate(seeded_session, company.id)


def test_activation_refuses_an_incomplete_target(seeded_session, ready):
    ready.target_metric = "revenue"
    ready.target_value = None
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "target value" in str(caught.value)


def test_activation_refuses_an_allocations_total_above_the_ceiling(seeded_session, ready):
    account = (
        seeded_session.query(BudgetAccount).filter_by(company_id=ready.id).one()
    )
    account.monthly_limit = Decimal("100")  # below the 3x500 already allocated
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "exceeds the company ceiling" in str(caught.value)


def test_activation_refuses_a_currency_mismatch(seeded_session, ready):
    account = seeded_session.query(BudgetAccount).filter_by(company_id=ready.id).one()
    account.currency = "EUR"
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "budget account is in EUR" in str(caught.value)


def test_activation_refuses_a_stale_hash(seeded_session, ready):
    """A contract edited behind the service is caught by the integrity check."""
    victim = draft_contracts(seeded_session, ready.id)[0]
    victim.objective = "quietly rewritten"
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "integrity check" in str(caught.value)


def test_activation_refuses_an_invalid_scope(seeded_session, ready):
    victim = draft_contracts(seeded_session, ready.id)[0]
    victim.tool_scope = [{"tool": "launch_missiles", "actions": ["fire"]}]
    victim.content_hash = compute_content_hash(victim)
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "Unknown tools" in str(caught.value)


def test_activation_refuses_a_communication_target_outside_the_company(seeded_session, ready):
    victim = draft_contracts(seeded_session, ready.id)[0]
    victim.communication_policy = {"allow": ["emp_elsewhere"], "broadcast": False, "maxRounds": 3}
    victim.content_hash = compute_content_hash(victim)
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "Communication targets" in str(caught.value)


def test_activation_refuses_a_reporting_cycle(seeded_session, ready):
    """A cycle introduced after generation is still refused."""
    contracts = draft_contracts(seeded_session, ready.id)
    # Find the seat that reports to nobody and close the loop through it.
    top = next(contract for contract in contracts if contract.reports_to_employee_id is None)
    other = next(contract for contract in contracts if contract.employee_id != top.employee_id)
    top.reports_to_employee_id = other.employee_id
    top.content_hash = compute_content_hash(top)
    seeded_session.commit()

    with pytest.raises(ConfigurationError):
        activate(seeded_session, ready.id)


def test_activation_refuses_a_role_missing_from_the_catalogue(seeded_session, ready):
    victim = draft_contracts(seeded_session, ready.id)[0]
    victim.role = "wizard"
    victim.content_hash = compute_content_hash(victim)
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "does not exist" in str(caught.value)


def test_activation_refuses_a_role_version_mismatch(seeded_session, ready):
    victim = draft_contracts(seeded_session, ready.id)[0]
    victim.role_config_version = 99
    victim.content_hash = compute_content_hash(victim)
    seeded_session.commit()

    with pytest.raises(ConfigurationError) as caught:
        activate(seeded_session, ready.id)
    assert "version 99" in str(caught.value)


def test_activation_refuses_an_employee_with_an_existing_active_contract(
    seeded_session, ready, live
):
    """Re-activating a paused company is a resume, not a second activation."""
    pause_of(seeded_session, ready.id)

    with pytest.raises(ConflictError):
        activate(seeded_session, ready.id)


def test_a_failed_activation_changes_nothing(seeded_session, ready):
    victim = draft_contracts(seeded_session, ready.id)[0]
    victim.role = "wizard"
    victim.content_hash = compute_content_hash(victim)
    seeded_session.commit()

    before_contracts = {c.id: (c.status, c.activated_at) for c in contracts_of(seeded_session, ready.id)}
    before_employees = {
        e.id: (e.status, e.active_contract_id)
        for e in seeded_session.query(CompanyEmployee).filter_by(company_id=ready.id).all()
    }
    before_events = len(EventService(seeded_session).list_events(stream_id="main", limit=500))

    with pytest.raises(ConfigurationError):
        activate(seeded_session, ready.id)

    assert {c.id: (c.status, c.activated_at) for c in contracts_of(seeded_session, ready.id)} == before_contracts
    assert {
        e.id: (e.status, e.active_contract_id)
        for e in seeded_session.query(CompanyEmployee).filter_by(company_id=ready.id).all()
    } == before_employees
    assert len(EventService(seeded_session).list_events(stream_id="main", limit=500)) == before_events
    assert seeded_session.get(type(ready), ready.id).status is CompanyStatus.DRAFT


def test_a_mid_activation_failure_rolls_everything_back(seeded_session, ready, monkeypatch):
    """A failure while staging events must undo the contract and company changes."""
    service = CompanyLifecycleService(seeded_session)
    real_stage = service._events.stage

    calls = {"n": 0}

    def exploding_stage(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("storage failed mid-activation")
        return real_stage(**kwargs)

    monkeypatch.setattr(service._events, "stage", exploding_stage)

    with pytest.raises(RuntimeError):
        service.activate(ready.id)

    seeded_session.rollback()
    company = seeded_session.get(type(ready), ready.id)
    assert company.status is CompanyStatus.DRAFT
    assert all(
        contract.status is ContractStatus.DRAFT
        for contract in contracts_of(seeded_session, ready.id)
    )
    assert events_of(seeded_session, "company_activated") == []


def test_only_one_company_can_hold_the_active_slot(seeded_session, live):
    """The partial unique index is the final arbiter."""
    second = make_company(seeded_session, name="Second")
    make_workforce(seeded_session, second.id)
    generate(seeded_session, second.id)

    with pytest.raises(ConflictError) as caught:
        activate(seeded_session, second.id)
    assert "already active" in str(caught.value)

    assert seeded_session.get(type(live), live.id).status is CompanyStatus.ACTIVE
    assert seeded_session.get(type(second), second.id).status is CompanyStatus.DRAFT


def test_activation_never_touches_the_canonical_agents(seeded_session, live, factory_for):
    probe = factory_for()
    try:
        assert {row.id for row in probe.query(Agent).all()} == {
            "ceo",
            "employee",
            "manager",
            "sales",
            "operations",
        }
    finally:
        probe.close()


def test_activation_does_not_move_the_budget_account(seeded_session, live, factory_for):
    probe = factory_for()
    try:
        account = probe.query(BudgetAccount).filter_by(company_id=live.id).one()
        assert account.monthly_limit == Decimal("4000")
        assert account.version == 1
    finally:
        probe.close()


# -- activated immutability -------------------------------------------------


def test_an_activated_contract_cannot_be_edited_through_the_service(seeded_session, live):
    contract = active_contracts(seeded_session, live.id)[0]

    with pytest.raises(ConflictError):
        ContractService(seeded_session).patch(
            contract.id, ContractPatch(objective="widen my authority")
        )


def test_hashes_still_match_after_activation(seeded_session, live):
    assert_hashes_match(seeded_session, live.id)


# -- versioning -------------------------------------------------------------


def test_a_successor_references_its_predecessor(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]

    successor = ContractService(seeded_session).create_successor(
        original.id, ContractVersionRequest(reason="quarterly review")
    )

    assert successor.id != original.id
    assert successor.supersedes_id == original.id
    assert successor.employee_id == original.employee_id
    assert successor.company_id == original.company_id
    assert successor.version_number == original.version_number + 1
    assert successor.status is ContractStatus.DRAFT


def test_creating_a_successor_leaves_the_predecessor_active(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]
    before_hash = original.content_hash

    ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())

    stored = seeded_session.get(Contract, original.id)
    assert stored.status is ContractStatus.ACTIVE
    assert stored.superseded_at is None
    assert stored.content_hash == before_hash


def test_a_successor_copies_content_and_rehashes(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]

    successor = ContractService(seeded_session).create_successor(
        original.id,
        ContractVersionRequest(patch=ContractPatch(objective="new objective")),
    )

    assert successor.responsibilities == original.responsibilities
    assert successor.data_scope == original.data_scope
    assert successor.restrictions == original.restrictions
    assert successor.objective == "new objective"
    assert successor.content_hash != original.content_hash
    assert successor.content_hash == compute_content_hash(successor)


def test_a_successor_is_editable_until_activated(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]
    successor = ContractService(seeded_session).create_successor(
        original.id, ContractVersionRequest()
    )

    updated, changed = ContractService(seeded_session).patch(
        successor.id, ContractPatch(objective="tuned during review")
    )
    assert changed is True
    assert updated.objective == "tuned during review"


def test_version_numbers_increase_across_successive_successors(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]

    first = ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())
    second = ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())

    assert first.version_number == original.version_number + 1
    assert second.version_number == original.version_number + 2


def test_a_draft_cannot_be_versioned(seeded_session, ready):
    draft = draft_contracts(seeded_session, ready.id)[0]

    with pytest.raises(ConflictError) as caught:
        ContractService(seeded_session).create_successor(draft.id, ContractVersionRequest())
    assert "only an activated contract" in str(caught.value)


def test_versioning_an_unknown_contract_is_not_found(seeded_session, live):
    from app.company.errors import NotFoundError

    with pytest.raises(NotFoundError):
        ContractService(seeded_session).create_successor("ctr_missing", ContractVersionRequest())


def test_a_successor_creation_emits_its_own_event(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]

    successor = ContractService(seeded_session).create_successor(
        original.id, ContractVersionRequest(reason="annual review")
    )

    events = events_of(seeded_session, "contract_version_created")
    assert len(events) == 1
    assert events[0].payload["contractId"] == successor.id
    assert events[0].payload["predecessorContractId"] == original.id
    # Creating a successor supersedes nothing yet.
    assert events_of(seeded_session, "contract_superseded") == []


# -- pause ------------------------------------------------------------------


def test_an_active_company_pauses(seeded_session, live):
    result = pause_of(seeded_session, live.id)

    assert result.status == "paused"
    assert seeded_session.get(type(live), live.id).status is CompanyStatus.PAUSED
    assert len(events_of(seeded_session, "company_paused")) == 1


def test_pause_keeps_every_contract_and_pointer(seeded_session, live):
    before = {
        c.id: (c.status, c.content_hash) for c in contracts_of(seeded_session, live.id)
    }
    employees_before = {
        e.id: e.active_contract_id
        for e in seeded_session.query(CompanyEmployee).filter_by(company_id=live.id).all()
    }

    pause_of(seeded_session, live.id)

    assert {c.id: (c.status, c.content_hash) for c in contracts_of(seeded_session, live.id)} == before
    assert {
        e.id: e.active_contract_id
        for e in seeded_session.query(CompanyEmployee).filter_by(company_id=live.id).all()
    } == employees_before


def test_a_draft_company_cannot_pause(seeded_session, ready):
    with pytest.raises(ConflictError):
        pause_of(seeded_session, ready.id)


def test_a_paused_company_cannot_pause_twice(seeded_session, live):
    pause_of(seeded_session, live.id)

    with pytest.raises(ConflictError):
        pause_of(seeded_session, live.id)


# -- resume -----------------------------------------------------------------


def test_a_paused_company_resumes_on_its_active_contracts(seeded_session, live):
    pause_of(seeded_session, live.id)

    result = do_resume(seeded_session, live.id)

    assert result.status == "active"
    assert result.superseded_contract_ids == []
    assert len(active_contracts(seeded_session, live.id)) == 3
    assert len(events_of(seeded_session, "company_resumed")) == 1


def test_a_draft_company_cannot_resume(seeded_session, ready):
    with pytest.raises(ConflictError):
        do_resume(seeded_session, ready.id)


def test_an_active_company_cannot_resume(seeded_session, live):
    with pytest.raises(ConflictError):
        do_resume(seeded_session, live.id)


def test_resume_can_activate_a_reviewed_successor(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]
    successor = ContractService(seeded_session).create_successor(
        original.id,
        ContractVersionRequest(patch=ContractPatch(objective="narrower authority")),
    )
    pause_of(seeded_session, live.id)

    result = do_resume(seeded_session, live.id, [successor.id])

    assert result.status == "active"
    assert result.superseded_contract_ids == [original.id]
    assert seeded_session.get(Contract, original.id).status is ContractStatus.SUPERSEDED
    assert seeded_session.get(Contract, successor.id).status is ContractStatus.ACTIVE
    assert seeded_session.get(Contract, successor.id).objective == "narrower authority"

    employee = seeded_session.get(CompanyEmployee, original.employee_id)
    assert employee.active_contract_id == successor.id


def test_resume_emits_the_full_event_set(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]
    successor = ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())
    pause_of(seeded_session, live.id)

    do_resume(seeded_session, live.id, [successor.id])

    assert len(events_of(seeded_session, "contract_superseded")) == 1
    assert len(events_of(seeded_session, "contract_activated")) == 4  # 3 + the successor
    assert len(events_of(seeded_session, "company_resumed")) == 1


def test_a_draft_contract_is_not_activated_merely_by_being_selected(seeded_session, live):
    original = active_contracts(seeded_session, live.id)[0]
    draft = ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())

    # Selecting the *predecessor* keeps the current terms in force.
    pause_of(seeded_session, live.id)
    result = do_resume(seeded_session, live.id, [])

    assert seeded_session.get(Contract, draft.id).status is ContractStatus.DRAFT
    assert result.superseded_contract_ids == []


def test_an_invalid_successor_rolls_the_whole_resume_back(seeded_session, live):
    """Selecting an already-active contract is refused, and nothing changes."""
    original = active_contracts(seeded_session, live.id)[0]
    successor = ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())
    other = active_contracts(seeded_session, live.id)[1]
    pause_of(seeded_session, live.id)

    before = {c.id: (c.status, c.activated_at) for c in contracts_of(seeded_session, live.id)}
    before_company = seeded_session.get(type(live), live.id).status
    before_pointers = {
        e.id: e.active_contract_id
        for e in seeded_session.query(CompanyEmployee).filter_by(company_id=live.id).all()
    }

    with pytest.raises((ConflictError, ConfigurationError)):
        do_resume(seeded_session, live.id, [successor.id, other.id])

    assert {c.id: (c.status, c.activated_at) for c in contracts_of(seeded_session, live.id)} == before
    assert seeded_session.get(type(live), live.id).status == before_company
    assert {
        e.id: e.active_contract_id
        for e in seeded_session.query(CompanyEmployee).filter_by(company_id=live.id).all()
    } == before_pointers
    assert events_of(seeded_session, "company_resumed") == []


def test_resume_refuses_an_allocation_that_no_longer_fits(seeded_session, live):
    """The ceiling is re-checked on resume, not only at generation.

    Which of the two independent checks fires first depends on row order, so this
    asserts the guarantee — the resume is refused and nothing changes — rather than
    a particular message.
    """
    victim = active_contracts(seeded_session, live.id)[0]
    victim.budget_per_month = Decimal("999999")
    seeded_session.commit()
    pause_of(seeded_session, live.id)

    before = seeded_session.get(type(live), live.id).status
    with pytest.raises(ConfigurationError) as caught:
        do_resume(seeded_session, live.id)

    assert (
        "exceeds the company ceiling" in str(caught.value)
        or "integrity check" in str(caught.value)
    )
    assert seeded_session.get(type(live), live.id).status == before
    assert events_of(seeded_session, "company_resumed") == []


def test_resume_refuses_a_contract_from_another_company(seeded_session, live):
    from app.company.errors import NotFoundError

    other_company = make_company(seeded_session, name="Other")
    make_workforce(seeded_session, other_company.id)
    pause_of(seeded_session, live.id)

    with pytest.raises((NotFoundError, ConfigurationError)):
        do_resume(seeded_session, live.id, ["ctr_from_elsewhere"])


def test_resume_refuses_a_non_successor_draft(seeded_session, live):
    """A draft that is not a successor version cannot be activated on resume."""
    employee_id = active_contracts(seeded_session, live.id)[0].employee_id
    stray = Contract(
        id="ctr_stray",
        company_id=live.id,
        employee_id=employee_id,
        version_number=9,
        status=ContractStatus.DRAFT,
        role="sales",
        role_config_version=1,
        objective="stray",
        responsibilities=["Do things"],
        data_scope=[],
        tool_scope=[],
        restrictions=[],
        task_scope=[],
        communication_policy={"allow": [], "broadcast": False, "maxRounds": 3},
        approval_rules=[],
        budget_per_task=Decimal("10"),
        budget_per_month=Decimal("100"),
        requires_human_escalation=False,
        content_hash="",
        source="generated",
    )
    stray.content_hash = compute_content_hash(stray)
    seeded_session.add(stray)
    seeded_session.commit()
    pause_of(seeded_session, live.id)

    with pytest.raises(ConfigurationError) as caught:
        do_resume(seeded_session, live.id, [stray.id])
    assert "not a successor version" in str(caught.value)


def test_resume_fails_cleanly_when_another_company_holds_the_slot(seeded_session, live):
    """The single active slot is respected across a pause/resume handoff."""
    second = make_company(seeded_session, name="Second")
    make_workforce(seeded_session, second.id)
    generate(seeded_session, second.id)

    # Free the slot, then let another company take it.
    pause_of(seeded_session, live.id)
    activate(seeded_session, second.id)

    with pytest.raises(ConflictError) as caught:
        do_resume(seeded_session, live.id)
    assert "already active" in str(caught.value)

    assert seeded_session.get(type(live), live.id).status is CompanyStatus.PAUSED
    assert seeded_session.get(type(second), second.id).status is CompanyStatus.ACTIVE
    assert events_of(seeded_session, "company_resumed") == []


def test_resume_validates_a_tampered_active_contract(seeded_session, live):
    """Terms changed behind the service are caught by the integrity check."""
    victim = active_contracts(seeded_session, live.id)[0]
    victim.objective = "quietly rewritten while active"
    seeded_session.commit()
    pause_of(seeded_session, live.id)

    with pytest.raises(ConfigurationError) as caught:
        do_resume(seeded_session, live.id)
    assert "integrity check" in str(caught.value)


def test_pause_and_resume_round_trip_keeps_one_active_contract_per_employee(
    seeded_session, live
):
    original = active_contracts(seeded_session, live.id)[0]
    successor = ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())
    pause_of(seeded_session, live.id)
    do_resume(seeded_session, live.id, [successor.id])

    per_employee: dict[str, int] = {}
    for contract in contracts_of(seeded_session, live.id):
        if contract.status is ContractStatus.ACTIVE:
            per_employee[contract.employee_id] = per_employee.get(contract.employee_id, 0) + 1

    assert set(per_employee.values()) == {1}


# -- events -----------------------------------------------------------------


def test_lifecycle_events_use_real_time_and_no_workflow_run(seeded_session, live):
    before = datetime.now(timezone.utc)
    original = active_contracts(seeded_session, live.id)[0]
    ContractService(seeded_session).create_successor(original.id, ContractVersionRequest())
    pause_of(seeded_session, live.id)
    after = datetime.now(timezone.utc)

    for event_type in ("contract_version_created", "company_paused"):
        for event in events_of(seeded_session, event_type):
            assert event.run_id is None
            assert event.clock_offset_ms is None
            stamp = event.timestamp
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            assert before <= stamp <= after


def test_event_sequence_ordering_is_valid_after_activation(seeded_session, live):
    events = EventService(seeded_session).list_events(stream_id="main", limit=500)
    sequences = [event.sequence for event in events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)


def test_events_are_published_only_after_the_commit(seeded_session, ready, factory_for):
    """A subscriber must find the company already active when the event arrives."""
    from app.events.bus import get_event_bus

    seen: list[str | None] = []
    probe = factory_for()

    def check(event):
        if event["type"] != "company_activated":
            return
        from app.models import Company

        probe.rollback()
        row = probe.get(Company, event["payload"]["companyId"])
        seen.append(None if row is None else row.status.value)

    unsubscribe = get_event_bus().subscribe(check)
    try:
        activate(seeded_session, ready.id)
    finally:
        unsubscribe()
        probe.close()

    assert seen == ["active"]