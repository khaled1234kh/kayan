"""P0.1: configuration schema, governance catalogue and timestamp convention.

Three things are locked down here:

1. Configured employees are configuration only. They get their own id space and
   never enter the canonical ``agents`` table.
2. The governance event vocabulary exists on both sides of the wire, so the
   frontend and backend catalogues cannot drift apart.
3. One timestamp convention: ``events.timestamp`` is always real UTC, and the
   reproducible logical position of a workflow event is carried separately in
   ``clock_offset_ms``. Experiment timing must depend on the offset, never on how
   fast the machine happened to run.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.company.templates import (
    CLOTHING,
    CUSTOM,
    CUSTOMIZED_GIFTS,
    ROLE_SEEDS,
    TEMPLATE_KEYS,
    roles_for_template,
)
from app.db.seed_roles import TEMPLATE_CONFIG_VERSION, seed_role_templates
from app.events.types import EVENT_CATALOGUE, EventCategory, EventType
from app.models import (
    BudgetAccount,
    BudgetReservation,
    Company,
    CompanyEmployee,
    CompanyStatus,
    Contract,
    ContractStatus,
    EmployeeStatus,
    RoleTemplate,
    new_employee_id,
)
from app.runtime.runtime import KayanRuntime
from app.services.events import EventService

#: The canonical demo workforce. P0 configuration must never reuse these ids.
DEMO_AGENT_IDS = {"ceo", "employee", "manager", "sales", "operations"}

FRONTEND_EVENTS_TS = (
    Path(__file__).resolve().parents[2] / "kayan-3d" / "src" / "types" / "events.ts"
)


# -- helpers ---------------------------------------------------------------


def make_company(session, **overrides) -> Company:
    values = {
        "id": "cmp_test",
        "name": "Test Brand",
        "template_key": CLOTHING,
        "currency": "USD",
        "status": CompanyStatus.DRAFT,
    }
    values.update(overrides)
    company = Company(**values)
    session.add(company)
    session.commit()
    return company


def make_employee(session, company_id="cmp_test", employee_id="emp_1", **overrides):
    values = {
        "id": employee_id,
        "company_id": company_id,
        "display_name": "Alex",
        "kind": "human",
        "role_key": "sales",
        "status": EmployeeStatus.ACTIVE,
    }
    values.update(overrides)
    employee = CompanyEmployee(**values)
    session.add(employee)
    session.commit()
    return employee


def make_contract(session, employee_id="emp_1", contract_id="ctr_1", **overrides) -> Contract:
    values = {
        "id": contract_id,
        "company_id": "cmp_test",
        "employee_id": employee_id,
        "version_number": 1,
        "status": ContractStatus.DRAFT,
        "role": "Sales",
        "budget_per_task": Decimal("5"),
        "budget_per_month": Decimal("50"),
        "content_hash": "hash-1",
        "source": "template",
    }
    values.update(overrides)
    contract = Contract(**values)
    session.add(contract)
    session.commit()
    return contract


# -- configuration-only identity -------------------------------------------


def test_configured_employee_ids_cannot_collide_with_demo_agents():
    employee_id = new_employee_id("1")
    assert employee_id not in DEMO_AGENT_IDS
    assert employee_id.startswith("emp_")


def test_configured_employees_never_enter_the_agent_table(seeded_session):
    """P0 does not insert configured employees into ``agents``.

    The demo workforce stays exactly as it was; the company workforce lives in
    its own table. Inserting into ``agents`` here is the mistake this test exists
    to catch, because it would let a configured seat inherit demo privileges.
    """
    make_company(seeded_session)
    make_employee(seeded_session)

    from app.models import Agent

    agent_ids = {row.id for row in seeded_session.query(Agent).all()}
    assert agent_ids == DEMO_AGENT_IDS
    assert not any(identifier.startswith("emp_") for identifier in agent_ids)


def test_company_employees_are_related_to_their_company(session):
    company = make_company(session)
    employee = make_employee(session)
    assert employee.company_id == company.id
    assert [row.id for row in company.employees] == ["emp_1"]


# -- company lifecycle constraints -----------------------------------------


def test_only_one_company_can_be_active(session):
    make_company(session, id="cmp_a", status=CompanyStatus.ACTIVE)
    session.add(
        Company(
            id="cmp_b",
            name="Second",
            template_key=CLOTHING,
            currency="USD",
            status=CompanyStatus.ACTIVE,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_multiple_drafts_may_coexist(session):
    make_company(session, id="cmp_a")
    make_company(session, id="cmp_b")
    make_company(session, id="cmp_c")
    assert session.query(Company).count() == 3


def test_a_paused_company_does_not_consume_the_active_slot(session):
    """Pause and resume are reversible, so a paused company must not block a new one."""
    make_company(session, id="cmp_a", status=CompanyStatus.PAUSED)
    make_company(session, id="cmp_b", status=CompanyStatus.ACTIVE)
    assert session.query(Company).count() == 2


def test_company_currency_must_be_three_characters(session):
    with pytest.raises(IntegrityError):
        make_company(session, currency="US")
    session.rollback()


def test_employee_cannot_report_to_itself(session):
    make_company(session)
    make_employee(session)
    session.add(
        CompanyEmployee(
            id="emp_2",
            company_id="cmp_test",
            display_name="Sam",
            kind="ai",
            role_key="operations",
            status=EmployeeStatus.ACTIVE,
            reports_to_id="emp_2",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# -- role template catalogue ------------------------------------------------


def test_role_template_seed_is_idempotent(session):
    assert seed_role_templates(session) == len(ROLE_SEEDS)
    assert seed_role_templates(session) == len(ROLE_SEEDS)
    assert session.query(RoleTemplate).count() == len(ROLE_SEEDS)


def test_role_template_versions_can_coexist(session):
    """A redefined role becomes a new version, so old contracts stay explainable."""
    seed_role_templates(session)
    session.add(
        RoleTemplate(
            key="sales",
            config_version=TEMPLATE_CONFIG_VERSION + 1,
            label="Sales (revised)",
            kind="ai",
        )
    )
    session.commit()
    versions = [
        row.config_version
        for row in session.query(RoleTemplate).filter_by(key="sales").all()
    ]
    assert versions == [TEMPLATE_CONFIG_VERSION, TEMPLATE_CONFIG_VERSION + 1]


def test_role_template_seed_covers_the_configurable_roles():
    keys = {role.key for role in ROLE_SEEDS}
    assert {"ceo", "manager", "sales", "operations", "hr", "support"} <= keys


def test_every_template_offers_roles_with_structured_scopes():
    assert TEMPLATE_KEYS == (CLOTHING, CUSTOMIZED_GIFTS, CUSTOM)
    for template_key in TEMPLATE_KEYS:
        roles = roles_for_template(template_key)
        assert roles, f"{template_key} offers no roles"
        for role in roles:
            assert role.data_scope or role.responsibilities
            assert role.template_keys


# -- contract constraints ---------------------------------------------------


def test_contract_versions_are_unique_per_employee(session):
    make_company(session)
    make_employee(session)
    make_contract(session, version_number=1)
    session.add(
        Contract(
            id="ctr_2",
            company_id="cmp_test",
            employee_id="emp_1",
            version_number=1,
            status=ContractStatus.DRAFT,
            role="Sales",
            budget_per_task=Decimal("5"),
            budget_per_month=Decimal("50"),
            content_hash="hash-2",
            source="template",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_only_one_active_contract_per_employee(session):
    make_company(session)
    make_employee(session)
    make_contract(session, status=ContractStatus.ACTIVE)
    session.add(
        Contract(
            id="ctr_2",
            company_id="cmp_test",
            employee_id="emp_1",
            version_number=2,
            status=ContractStatus.ACTIVE,
            role="Sales",
            budget_per_task=Decimal("5"),
            budget_per_month=Decimal("50"),
            content_hash="hash-2",
            source="template",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_superseding_frees_the_single_active_slot(session):
    """The lifecycle path: activate, supersede, activate the next version."""
    make_company(session)
    make_employee(session)
    make_contract(session, status=ContractStatus.ACTIVE)
    contract = session.get(Contract, "ctr_1")
    contract.status = ContractStatus.SUPERSEDED
    session.commit()
    make_contract(session, contract_id="ctr_2", version_number=2, status=ContractStatus.ACTIVE)
    assert session.query(Contract).count() == 2


def test_contract_money_is_exact_decimal(session):
    make_company(session)
    make_employee(session)
    contract = make_contract(
        session, budget_per_task=Decimal("0.100000"), budget_per_month=Decimal("1234.5")
    )
    session.refresh(contract)
    assert isinstance(contract.budget_per_task, Decimal)
    assert contract.budget_per_task == Decimal("0.100000")
    assert contract.budget_per_month == Decimal("1234.500000")


def test_contract_budget_cannot_be_negative(session):
    make_company(session)
    make_employee(session)
    with pytest.raises(IntegrityError):
        make_contract(session, budget_per_month=Decimal("-1"))
    session.rollback()


def test_active_contract_link_is_a_real_relationship(session):
    make_company(session)
    employee = make_employee(session)
    contract = make_contract(session, status=ContractStatus.ACTIVE)
    employee.active_contract_id = contract.id
    session.commit()
    session.refresh(employee)
    assert employee.active_contract_id == "ctr_1"


# -- budget constraints -----------------------------------------------------


def make_account(session, **overrides) -> BudgetAccount:
    values = {
        "id": "bac_1",
        "company_id": "cmp_test",
        "currency": "USD",
        "monthly_limit": Decimal("1000"),
        "period_start": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "period_end": datetime(2026, 2, 1, tzinfo=timezone.utc),
    }
    values.update(overrides)
    account = BudgetAccount(**values)
    session.add(account)
    session.commit()
    return account


def test_budget_period_must_be_ordered(session):
    make_company(session)
    with pytest.raises(IntegrityError):
        make_account(
            session,
            period_end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
    session.rollback()


def test_one_budget_account_per_company_period(session):
    make_company(session)
    make_account(session)
    with pytest.raises(IntegrityError):
        make_account(session, id="bac_2")
    session.rollback()


def test_reservation_amount_must_be_positive(session):
    make_company(session)
    account = make_account(session)
    session.add(
        BudgetReservation(
            id="res_1",
            account_id=account.id,
            company_id="cmp_test",
            amount=Decimal("0"),
            currency="USD",
            idempotency_key="idem-1",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_reservation_idempotency_key_is_unique(session):
    """A redelivered reserve must be a no-op, which the key enforces at the database."""
    make_company(session)
    account = make_account(session)
    values = {
        "account_id": account.id,
        "company_id": "cmp_test",
        "amount": Decimal("10"),
        "currency": "USD",
        "idempotency_key": "idem-1",
    }
    session.add(BudgetReservation(id="res_1", **values))
    session.commit()
    session.add(BudgetReservation(id="res_2", **values))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# -- governance vocabulary --------------------------------------------------


def test_governance_category_exists():
    assert EventCategory.GOVERNANCE.value == "governance"


def test_every_event_type_has_a_category():
    missing = [event.value for event in EventType if event not in EVENT_CATALOGUE]
    assert missing == []


@pytest.mark.parametrize(
    "event_type",
    [
        "company_created",
        "company_updated",
        "workforce_configured",
        "recommendation_generated",
        "recommendation_accepted",
        "contract_generated",
        "contract_activated",
        "contract_superseded",
        "budget_adjusted",
        "budget_reserved",
        "budget_released",
        "budget_charged",
        "budget_reservation_denied",
        "budget_limit_reached",
        "company_activated",
        "company_paused",
        "company_resumed",
    ],
)
def test_governance_events_are_catalogue_members(event_type):
    assert EVENT_CATALOGUE[EventType(event_type)] is EventCategory.GOVERNANCE


def _frontend_source() -> str | None:
    if not FRONTEND_EVENTS_TS.exists():
        return None
    return FRONTEND_EVENTS_TS.read_text(encoding="utf-8")


def test_frontend_catalogue_lists_every_backend_event_type():
    source = _frontend_source()
    if source is None:
        pytest.skip("frontend catalogue not present in this checkout")
    union = source.split("export type KayanEventType =", 1)[1].split(";", 1)[0]
    frontend_types = set(re.findall(r"'([a-z_]+)'", union))
    backend_types = {event.value for event in EventType}
    assert backend_types - frontend_types == set()


def test_frontend_catalogue_defines_every_backend_event_type():
    source = _frontend_source()
    if source is None:
        pytest.skip("frontend catalogue not present in this checkout")
    definitions = source.split("export const EVENT_DEFS", 1)[1]
    frontend_defs = dict(
        re.findall(r"(\w+):\s*\{[^}]*?category:\s*'(\w+)'", definitions, re.S)
    )
    backend = {event.value: category.value for event, category in EVENT_CATALOGUE.items()}
    assert backend == frontend_defs


def test_frontend_offers_a_governance_filter():
    source = _frontend_source()
    if source is None:
        pytest.skip("frontend catalogue not present in this checkout")
    assert "'governance'" in source


# -- timestamp convention ---------------------------------------------------


@pytest.fixture()
def executed_run(session):
    from app.db.seed import seed_agents

    seed_agents(session)
    run = KayanRuntime().request_order(session, order_id="1042", request_id="req-p0-1")
    events = EventService(session).list_events(run_id=run.id, limit=500)
    return run, events


def test_workflow_events_carry_real_timestamps(session):
    """The feed shows real time, so configuration changes and runs share one clock."""
    from app.db.seed import seed_agents

    seed_agents(session)
    before = datetime.now(timezone.utc)
    run = KayanRuntime().request_order(session, order_id="1042", request_id="req-p0-2")
    after = datetime.now(timezone.utc)
    events = EventService(session).list_events(run_id=run.id, limit=500)

    # SQLite returns naive datetimes; compare on the same footing.
    for event in events:
        stamp = event.timestamp
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        assert before - timedelta(seconds=5) <= stamp <= after + timedelta(seconds=5)


def test_workflow_events_carry_a_monotonic_logical_offset(executed_run):
    _, events = executed_run
    offsets = [event.clock_offset_ms for event in events]
    assert all(isinstance(offset, int) for offset in offsets)
    assert offsets == sorted(offsets)
    assert len(set(offsets)) > 1, "a run's events must span more than one logical instant"


def test_duration_is_measured_from_offsets_not_wall_clock(executed_run):
    run, events = executed_run
    offsets = [event.clock_offset_ms for event in events]
    assert run.duration_ms == max(offsets) - min(offsets)


def test_two_runs_report_the_same_duration_despite_real_time(session):
    """The regression this convention exists to prevent.

    With timestamps on the virtual clock, logical time and real time were the same
    thing. Now that ``timestamp`` is real UTC, reproducibility has to come from
    the logical offset or repeated trials would report jittery durations.
    """
    from app.db.seed import seed_agents

    seed_agents(session)
    runtime = KayanRuntime()
    first = runtime.request_order(session, order_id="1042", request_id="req-p0-a")
    second = runtime.request_order(session, order_id="1042", request_id="req-p0-b")

    first_events = EventService(session).list_events(run_id=first.id, limit=500)
    second_events = EventService(session).list_events(run_id=second.id, limit=500)

    assert first.duration_ms == second.duration_ms
    assert [e.event_type for e in first_events] == [e.event_type for e in second_events]
    assert [e.clock_offset_ms for e in first_events] == [
        e.clock_offset_ms for e in second_events
    ]


def test_configuration_events_have_no_logical_offset(session):
    """Governance events belong to real time only; they are not part of a run."""
    service = EventService(session)
    event = service.record(
        event_type="company_created",
        stream_id="main",
        payload={"companyId": "cmp_test"},
    )
    assert event.run_id is None
    assert event.clock_offset_ms is None


def test_wire_projection_carries_the_logical_offset(executed_run):
    _, events = executed_run
    projected = EventService.to_wire(events[-1])
    assert "clockOffsetMs" in projected
    assert projected["clockOffsetMs"] == events[-1].clock_offset_ms