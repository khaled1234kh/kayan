"""P0.4 contract generation, editing and integrity.

Generation derives terms from the versioned catalogue with least-privilege defaults
and the owner's explicit allocations. Editing applies to drafts only and always
validates the complete resulting contract. The integrity hash covers every material
term, so a change anywhere in it is visible.
"""

from __future__ import annotations

import json
import pathlib
import re
from decimal import Decimal

import pytest

from app.company.contract_terms import (
    MATERIAL_COLUMNS,
    compute_content_hash,
    contract_terms,
    serialise,
)
from app.company.errors import ConfigurationError, ConflictError
from app.models import CompanyStatus, Contract, ContractStatus
from app.schemas.contract import (
    ContractGenerateRequest,
    ContractPatch,
    EmployeeAllocation,
)
from app.services.contracts import ContractService
from tests.p0_4_helpers import (
    activate,
    active_contracts,
    allocations_for,
    api_allocations,
    api_company,
    api_workforce,
    assert_hashes_match,
    contracts_of,
    draft_contracts,
    generate,
    make_company,
    make_workforce,
    post_generate,
    set_status,
)


@pytest.fixture()
def drafted(seeded_session):
    """A draft company with a workforce and one draft contract per employee."""
    company = make_company(seeded_session)
    employee_ids = make_workforce(seeded_session, company.id)
    contracts = generate(seeded_session, company.id)
    return company, employee_ids, contracts


# -- generation -------------------------------------------------------------


def test_generates_one_contract_per_configured_employee(seeded_session, drafted):
    company, employee_ids, contracts = drafted

    assert len(contracts) == len(employee_ids) == 3
    assert {contract.employee_id for contract in contracts} == set(employee_ids)
    for contract in contracts:
        assert contract.status is ContractStatus.DRAFT
        assert contract.version_number == 1
        assert contract.supersedes_id is None
        assert contract.source == "generated"


def test_generation_records_the_role_template_version(seeded_session, drafted):
    _, _, contracts = drafted

    for contract in contracts:
        assert contract.role_config_version == 1
        assert contract.role in {"ceo", "manager", "sales"}


def test_generation_uses_the_supplied_allocations(seeded_session, drafted):
    _, _, contracts = drafted

    for contract in contracts:
        assert contract.budget_per_month == Decimal("500")
        assert contract.budget_per_task == Decimal("100")


def test_generation_derives_scopes_from_the_catalogue(seeded_session, drafted):
    _, _, contracts = drafted

    sales = next(contract for contract in contracts if contract.role == "sales")
    assert sales.data_scope, "the sales role grants data scope in the catalogue"
    assert sales.tool_scope
    assert "finalize_without_ceo_approval" in sales.restrictions
    # A catalogue restriction becomes an executable approval rule.
    assert sales.approval_rules == [{"action": "finalize", "requiredApprover": "ceo"}]


def test_generation_derives_the_reporting_line_and_communication(seeded_session, drafted):
    _, _, contracts = drafted

    owner = next(contract for contract in contracts if contract.role == "ceo")
    assert owner.reports_to_employee_id is None
    assert owner.communication_policy["broadcast"] is False

    for contract in contracts:
        if contract.role != "ceo":
            assert contract.reports_to_employee_id == owner.employee_id
            assert owner.employee_id in contract.communication_policy["allow"]


def test_generation_marks_human_seats_for_escalation(seeded_session, drafted):
    _, _, contracts = drafted

    ceo = next(contract for contract in contracts if contract.role == "ceo")
    manager = next(contract for contract in contracts if contract.role == "manager")
    assert ceo.requires_human_escalation is True
    assert manager.requires_human_escalation is False


def test_generation_never_touches_the_demo_agents(seeded_session, drafted, factory_for):
    from app.models import Agent

    assert_hashes_match(seeded_session, drafted[0].id)

    session_ = factory_for()
    try:
        assert {row.id for row in session_.query(Agent).all()} == {
            "ceo",
            "employee",
            "manager",
            "sales",
            "operations",
        }
    finally:
        session_.close()


def test_generation_persists_the_set_or_nothing(seeded_session):
    """A failure part-way through leaves no partial draft set."""
    company = make_company(seeded_session)
    make_workforce(seeded_session, company.id)

    bad = allocations_for(seeded_session, company.id)
    bad[0].budget_per_task = Decimal("9999")

    with pytest.raises(ConfigurationError):
        ContractService(seeded_session).generate(
            company.id, ContractGenerateRequest(allocations=bad)
        )
    assert contracts_of(seeded_session, company.id) == []


# -- allocation validation (through the API) --------------------------------


def test_generation_with_valid_allocations_succeeds(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)

    response = post_generate(configured_client, company_id, api_allocations(employee_ids))

    assert response.status_code == 201, response.text
    assert len(response.json()) == 3


def test_allocations_must_cover_every_employee(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)

    response = post_generate(
        configured_client, company_id, api_allocations(employee_ids)[:-1]
    )

    assert response.status_code == 422
    assert "No budget allocation supplied" in response.json()["detail"]["detail"]


def test_allocations_reject_unknown_employees(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    bodies = api_allocations(employee_ids)
    bodies.append({"employeeId": "emp_ghost", "budgetPerMonth": "10", "budgetPerTask": "1"})

    response = post_generate(configured_client, company_id, bodies)

    assert response.status_code == 422
    assert "not in this company" in response.json()["detail"]["detail"]


def test_allocations_reject_duplicate_employees(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    bodies = api_allocations(employee_ids)
    bodies.append(dict(bodies[0]))

    response = post_generate(configured_client, company_id, bodies)

    assert response.status_code == 422
    assert "more than once" in response.json()["detail"]["detail"]


def test_allocations_reject_an_employee_from_another_company(configured_client):
    first = api_company(configured_client, name="First")
    first_employees = api_workforce(configured_client, first)
    second = api_company(configured_client, name="Second")
    second_employees = api_workforce(configured_client, second)

    bodies = api_allocations(second_employees)
    bodies[0]["employeeId"] = first_employees[0]

    response = post_generate(configured_client, second, bodies)

    assert response.status_code == 422
    assert "not in this company" in response.json()["detail"]["detail"]


def test_allocations_reject_a_total_above_the_ceiling(configured_client):
    company_id = api_company(configured_client, monthlyBudget="1000")
    employee_ids = api_workforce(configured_client, company_id)

    response = post_generate(
        configured_client, company_id, api_allocations(employee_ids, monthly="500")
    )

    assert response.status_code == 422
    assert "exceeds the company ceiling" in response.json()["detail"]["detail"]


def test_allocations_reject_a_per_task_ceiling_above_monthly(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)

    response = post_generate(
        configured_client, company_id, api_allocations(employee_ids, monthly="100", per_task="500")
    )

    assert response.status_code == 422
    assert "exceeds the monthly" in response.json()["detail"]["detail"]


def test_allocations_reject_unknown_fields(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    bodies = api_allocations(employee_ids)
    bodies[0]["currency"] = "EUR"

    assert post_generate(configured_client, company_id, bodies).status_code == 422


def test_generation_requires_a_workforce(configured_client):
    company_id = api_company(configured_client)

    response = post_generate(
        configured_client,
        company_id,
        [{"employeeId": "emp_x", "budgetPerMonth": "10", "budgetPerTask": "1"}],
    )

    assert response.status_code == 422
    assert "no configured workforce" in response.json()["detail"]["detail"]


def test_generation_is_refused_for_a_non_draft_company(seeded_session, drafted):
    company, _, _ = drafted
    set_status(seeded_session, company.id, CompanyStatus.ACTIVE)

    from app.company.errors import ConflictError

    with pytest.raises(ConflictError) as caught:
        generate(seeded_session, company.id)
    assert caught.value.field == "status"


# -- regeneration -----------------------------------------------------------


def test_regeneration_replaces_unactivated_drafts(seeded_session, drafted):
    company, _, first = drafted

    second = generate(seeded_session, company.id)

    assert {c.id for c in second}.isdisjoint({c.id for c in first})
    assert len(draft_contracts(seeded_session, company.id)) == 3
    # Replaced drafts are superseded, never deleted: history is append-only.
    assert len(contracts_of(seeded_session, company.id)) == 6
    for contract in first:
        assert seeded_session.get(Contract, contract.id) is not None


def test_regeneration_does_not_destroy_activated_history(seeded_session, drafted):
    company, _, _ = drafted
    activate(seeded_session, company.id)
    before = {c.id: c.status for c in contracts_of(seeded_session, company.id)}

    with pytest.raises(ConflictError):
        generate(seeded_session, company.id)

    after = {c.id: c.status for c in contracts_of(seeded_session, company.id)}
    assert after == before
    assert all(status is ContractStatus.ACTIVE for status in after.values())


def test_a_failed_regeneration_leaves_the_prior_draft_set_intact(seeded_session, drafted):
    company, _, first = drafted

    bad = allocations_for(seeded_session, company.id)
    bad[0].budget_per_task = Decimal("9999")
    with pytest.raises(ConfigurationError):
        ContractService(seeded_session).generate(
            company.id, ContractGenerateRequest(allocations=bad)
        )

    assert {c.id: c.status for c in contracts_of(seeded_session, company.id)} == {
        c.id: ContractStatus.DRAFT for c in first
    }


# -- integrity hash ---------------------------------------------------------


def test_hash_is_canonical_and_stable(seeded_session, drafted):
    _, _, contracts = drafted

    for contract in contracts:
        assert len(contract.content_hash) == 64
        assert contract.content_hash == compute_content_hash(contract)


def test_hash_is_key_order_independent(seeded_session, drafted):
    contract = drafted[2][0]
    shuffled = dict(reversed(list(contract_terms(contract).items())))

    assert serialise(contract_terms(contract)) == serialise(shuffled)
    assert json.loads(serialise(contract_terms(contract)))["role"] == contract.role


def test_hash_treats_equal_decimals_identically(seeded_session, drafted):
    """5000 and 5000.00 are the same money and must hash the same."""
    contract = drafted[2][0]
    original = contract.budget_per_month

    contract.budget_per_month = Decimal("500")
    assert compute_content_hash(contract) == contract.content_hash
    contract.budget_per_month = Decimal("500.00")
    assert compute_content_hash(contract) == contract.content_hash

    contract.budget_per_month = original


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("role", "operations"),
        ("role_config_version", 2),
        ("objective", "something else"),
        ("budget_per_task", Decimal("7")),
        ("budget_per_month", Decimal("999")),
        ("reports_to_employee_id", "emp_other"),
        ("requires_human_escalation", "flip"),
        ("restrictions", ["customer_private_records"]),
        ("task_scope", ["quotation"]),
        ("approval_rules", [{"action": "finalize", "requiredApprover": "ceo"}]),
        ("communication_policy", {"allow": [], "broadcast": True, "maxRounds": 2}),
        ("data_scope", [{"resource": "reports", "operations": ["read"]}]),
        ("tool_scope", [{"tool": "approval", "actions": ["approve"]}]),
        ("responsibilities", ["Do everything"]),
        ("company_id", "cmp_other"),
        ("employee_id", "emp_other"),
        ("version_number", 2),
    ],
)
def test_changing_any_material_term_changes_the_hash(seeded_session, drafted, field, value):
    """Every material column is covered, including identity and budgets."""
    contract = drafted[2][0]
    before = compute_content_hash(contract)

    # "flip" means the opposite of whatever the contract already holds, so the test
    # asserts a change rather than accidentally writing the same value.
    setattr(contract, field, not getattr(contract, field) if value == "flip" else value)

    assert compute_content_hash(contract) != before


def test_lifecycle_changes_do_not_change_the_hash(seeded_session, drafted):
    """Activating a contract changes its state, not what the employee may do."""
    contract = drafted[2][0]
    before = compute_content_hash(contract)

    contract.status = ContractStatus.ACTIVE
    contract.activated_at = None

    assert compute_content_hash(contract) == before


def test_hash_covers_budgets_and_reporting_line(seeded_session, drafted):
    terms = contract_terms(drafted[2][0])

    assert terms["budget_per_month"] == "500"
    assert "reports_to_employee_id" in terms
    assert "communication_policy" in terms


def test_material_columns_match_the_database_trigger():
    """The hash and the database protect the same terms.

    The trigger covers one extra column — ``content_hash`` itself — because a
    contract whose digest can be edited is not protected at all. Everything else
    must line up, or one of the two would guard terms the other ignores.
    """
    migration = (
        pathlib.Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "9d83d34b1083_p0_4_contract_role_version_and_.py"
    )
    source = migration.read_text(encoding="utf-8")
    block = source.split("MATERIAL_COLUMNS: tuple[str, ...] = (", 1)[1].split(")", 1)[0]
    trigger_columns = tuple(re.findall(r'"([a-z_]+)"', block))

    assert set(MATERIAL_COLUMNS) < set(trigger_columns)
    assert set(trigger_columns) - set(MATERIAL_COLUMNS) == {"content_hash"}
    # Order matters only for the trigger's SQL, not for correctness, but a
    # difference in the set itself would be the real signal.
    assert set(MATERIAL_COLUMNS) - set(trigger_columns) == set()


# -- editing ----------------------------------------------------------------


def test_a_valid_draft_patch_succeeds(seeded_session, drafted):
    contract = drafted[2][0]

    updated, changed = ContractService(seeded_session).patch(
        contract.id, ContractPatch(objective="Own the P&L")
    )

    assert changed is True
    assert updated.objective == "Own the P&L"
    assert updated.content_hash == compute_content_hash(updated)


def test_patch_recomputes_the_hash_over_all_terms(seeded_session, drafted):
    contract = drafted[2][0]
    before = contract.content_hash

    updated, _ = ContractService(seeded_session).patch(
        contract.id, ContractPatch(responsibilities=["Decide", "Report"])
    )

    assert updated.content_hash != before
    assert updated.content_hash == compute_content_hash(updated)


def test_a_no_op_patch_produces_no_event(seeded_session, drafted, configured_client):
    from app.services.events import EventService

    contract = drafted[2][0]
    service = EventService(seeded_session)
    before = len(service.list_events(stream_id="main", limit=500))

    updated, changed = ContractService(seeded_session).patch(
        contract.id, ContractPatch(objective=contract.objective)
    )

    assert changed is False
    assert updated.content_hash == contract.content_hash
    assert len(EventService(seeded_session).list_events(stream_id="main", limit=500)) == before


def test_a_material_patch_emits_contract_updated(seeded_session, drafted):
    from app.services.events import EventService

    contract = drafted[2][0]
    ContractService(seeded_session).patch(contract.id, ContractPatch(objective="Own the P&L"))

    events = [
        event
        for event in EventService(seeded_session).list_events(stream_id="main", limit=500)
        if event.event_type == "contract_updated"
    ]
    assert len(events) == 1
    assert events[0].payload["contractId"] == contract.id
    assert events[0].payload["changedFields"] == ["objective"]


def test_activated_contracts_cannot_be_patched(seeded_session, drafted):
    company, _, _ = drafted
    activate(seeded_session, company.id)
    contract = active_contracts(seeded_session, company.id)[0]

    with pytest.raises(ConflictError):
        ContractService(seeded_session).patch(contract.id, ContractPatch(objective="sneaky"))


def test_superseded_contracts_cannot_be_patched(seeded_session, drafted):
    contract = drafted[2][0]
    contract.status = ContractStatus.SUPERSEDED
    seeded_session.commit()

    with pytest.raises(ConflictError):
        ContractService(seeded_session).patch(contract.id, ContractPatch(objective="x"))


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        (
            ContractPatch(dataScope=[{"resource": "unknown_thing", "operations": ["read"]}]),
            "Unknown data resources",
        ),
        (
            ContractPatch(toolScope=[{"tool": "launch_missiles", "actions": ["fire"]}]),
            "Unknown tools",
        ),
        (ContractPatch(restrictions=["can_do_anything"]), "Unknown restrictions"),
        (ContractPatch(taskScope=["teleportation"]), "Unknown task categories"),
        (ContractPatch(role="wizard", roleConfigVersion=1), "does not exist"),
        (
            ContractPatch(budgetPerTask="9999", budgetPerMonth="10"),
            "exceeds the monthly",
        ),
        (ContractPatch(responsibilities=[]), "at least one responsibility"),
    ],
)
def test_invalid_patch_content_is_refused(seeded_session, drafted, payload, fragment):
    contract = drafted[2][0]

    with pytest.raises(ConfigurationError) as caught:
        ContractService(seeded_session).patch(contract.id, payload)
    assert fragment in str(caught.value)


def test_patch_validates_the_whole_contract_not_just_the_patch(seeded_session, drafted):
    """A PATCH fixing one field is still refused if another field is invalid."""
    contract = drafted[2][0]
    contract.task_scope = ["teleportation"]
    seeded_session.commit()

    with pytest.raises(ConfigurationError):
        ContractService(seeded_session).patch(contract.id, ContractPatch(objective="new"))


def test_patch_refuses_a_communication_target_outside_the_company(seeded_session, drafted):
    contract = drafted[2][0]
    policy = {"allow": ["emp_not_here"], "broadcast": False, "maxRounds": 3}

    with pytest.raises(ConfigurationError) as caught:
        ContractService(seeded_session).patch(
            contract.id, ContractPatch(communicationPolicy=policy)
        )
    assert "Communication targets" in str(caught.value)


def test_patch_refuses_an_approval_rule_nobody_can_satisfy(seeded_session, drafted):
    contract = drafted[2][0]

    with pytest.raises(ConfigurationError) as caught:
        ContractService(seeded_session).patch(
            contract.id,
            ContractPatch(
                approvalRules=[{"action": "finalize", "requiredApprover": "nobody"}]
            ),
        )
    assert "requires approval from" in str(caught.value)


def test_patch_allows_an_approver_that_is_a_catalogue_role(seeded_session, drafted):
    contract = drafted[2][0]

    updated, changed = ContractService(seeded_session).patch(
        contract.id,
        ContractPatch(approvalRules=[{"action": "finalize", "requiredApprover": "ceo"}]),
    )

    assert changed is True
    assert updated.approval_rules[0]["requiredApprover"] == "ceo"


def test_patch_rejects_lifecycle_fields(seeded_session, drafted):
    """A version number and a status are not draft edits."""
    contract = drafted[2][0]

    with pytest.raises(Exception):
        ContractService(seeded_session).patch(
            contract.id, {"status": "active", "versionNumber": 5}
        )


def test_patch_of_an_unknown_contract_is_not_found(seeded_session):
    from app.company.errors import NotFoundError

    with pytest.raises(NotFoundError):
        ContractService(seeded_session).patch("ctr_missing", ContractPatch(objective="x"))


# -- API surface ------------------------------------------------------------


def test_contracts_are_listed_and_retrievable(configured_client, factory_for):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    created = post_generate(configured_client, company_id, api_allocations(employee_ids))
    assert created.status_code == 201, created.text

    listed = configured_client.get(f"/api/companies/{company_id}/contracts")
    assert listed.status_code == 200
    assert len(listed.json()) == 3

    one = configured_client.get(f"/api/contracts/{created.json()[0]['id']}")
    assert one.status_code == 200
    body = one.json()
    assert body["status"] == "draft"
    assert body["contentHash"]
    assert body["roleConfigVersion"] == 1
    assert "dataScope" in body


def test_unknown_contract_is_404(configured_client):
    assert configured_client.get("/api/contracts/ctr_missing").status_code == 404


def test_contracts_of_an_unknown_company_is_404(configured_client):
    assert configured_client.get("/api/companies/cmp_missing/contracts").status_code == 404


def test_patch_through_the_api(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    contract_id = post_generate(configured_client, company_id, api_allocations(employee_ids)).json()[0]["id"]

    response = configured_client.patch(
        f"/api/contracts/{contract_id}", json={"objective": "Own the P&L"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["objective"] == "Own the P&L"


def test_invalid_patch_through_the_api_names_the_field(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    contract_id = post_generate(configured_client, company_id, api_allocations(employee_ids)).json()[0]["id"]

    response = configured_client.patch(
        f"/api/contracts/{contract_id}",
        json={"toolScope": [{"tool": "launch_missiles", "actions": ["fire"]}]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "toolScope"


def test_an_unsupported_operation_is_refused_at_the_boundary(configured_client):
    """``delete`` is refused by the schema, before any service call."""
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    contract_id = post_generate(configured_client, company_id, api_allocations(employee_ids)).json()[0]["id"]

    response = configured_client.patch(
        f"/api/contracts/{contract_id}",
        json={"dataScope": [{"resource": "orders", "operations": ["delete"]}]},
    )

    assert response.status_code == 422
    detail = response.text
    assert "unsupported operations" in detail or "delete" in detail


def test_version_endpoint_is_reachable_but_needs_an_activated_source(configured_client):
    company_id = api_company(configured_client)
    employee_ids = api_workforce(configured_client, company_id)
    contract_id = post_generate(configured_client, company_id, api_allocations(employee_ids)).json()[0]["id"]

    response = configured_client.post(f"/api/contracts/{contract_id}/versions", json={})

    assert response.status_code == 409
    assert response.json()["detail"]["field"] == "status"