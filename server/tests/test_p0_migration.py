"""P0.1 migration behaviour on a real PostgreSQL database.

The interesting P0 rules are enforced by the database, not the service layer:
the single active company, contract term immutability, the refusal to delete an
activated contract, and one active contract per employee. Those cannot be tested
through ``Base.metadata.create_all``, because the rules live in the migration
itself.

So this module builds a throwaway database, runs the real Alembic chain from
empty, and asserts both the schema and the behaviour. It is skipped unless
``KAYAN_TEST_DATABASE_URL`` points at PostgreSQL, so the default suite still runs
with no external service.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("KAYAN_TEST_DATABASE_URL", "").startswith("postgres"),
    reason="migration behaviour is only asserted against real PostgreSQL",
)

TEMP_DATABASE = "kayan_p0_migration_test"


@pytest.fixture(scope="module")
def migrated_db():
    """A fresh database migrated from empty, torn down afterwards."""
    import psycopg
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.engine import make_url

    from app.core.config import get_settings

    test_url = make_url(os.environ["KAYAN_TEST_DATABASE_URL"])
    # psycopg cannot parse the SQLAlchemy "+psycopg" driver name.
    admin_url = test_url.set(database="postgres", drivername="postgresql")
    previous_url = os.environ.get("DATABASE_URL")

    admin = psycopg.connect(str(admin_url), autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{TEMP_DATABASE}" WITH (FORCE)')
    admin.execute(f'CREATE DATABASE "{TEMP_DATABASE}"')
    admin.close()

    alembic_ini = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini"
    )
    config = Config(alembic_ini)
    config.set_main_option("sqlalchemy.url", str(test_url.set(database=TEMP_DATABASE)))
    # alembic/env.py reads the URL from application settings.
    os.environ["DATABASE_URL"] = str(test_url.set(database=TEMP_DATABASE))
    get_settings.cache_clear()
    try:
        command.upgrade(config, "head")
        yield config
    finally:
        get_settings.cache_clear()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        admin = psycopg.connect(str(admin_url), autocommit=True)
        admin.execute(f'DROP DATABASE IF EXISTS "{TEMP_DATABASE}" WITH (FORCE)')
        admin.close()


@pytest.fixture()
def conn(migrated_db):
    import psycopg
    from sqlalchemy.engine import make_url

    from app.core.config import get_settings

    url = make_url(get_settings().database_url).set(drivername="postgresql")
    connection = psycopg.connect(str(url), autocommit=True)
    connection.execute(
        "TRUNCATE contracts, company_employees, companies, budget_reservations, "
        "budget_ledger_entries, budget_accounts CASCADE"
    )
    try:
        yield connection
    finally:
        connection.close()


def insert_company(conn, identifier, status="draft", template="clothing", currency="USD"):
    conn.execute(
        """INSERT INTO companies (id, name, template_key, currency, status, revision)
           VALUES (%s, %s, %s, %s, %s, 1)""",
        (identifier, identifier.title(), template, currency, status),
    )


def insert_employee(conn, identifier, company_id="cmp_a", role_key="sales"):
    # ``responsibilities`` is NOT NULL with no server default, so a raw insert must
    # supply it. The ORM fills it from the column default.
    conn.execute(
        """INSERT INTO company_employees (id, company_id, display_name, kind, role_key,
             status, responsibilities)
           VALUES (%s, %s, %s, 'human', %s, 'active', '[]')""",
        (identifier, company_id, identifier.title(), role_key),
    )


def insert_contract(
    conn,
    identifier,
    employee_id="emp_1",
    version=1,
    status="draft",
    role="Sales",
    activated=False,
):
    conn.execute(
        """INSERT INTO contracts (id, company_id, employee_id, version_number, status, role,
             role_config_version, responsibilities, data_scope, tool_scope,
             restrictions, task_scope, communication_policy, approval_rules,
             budget_per_task, budget_per_month, requires_human_escalation,
             content_hash, source, activated_at)
           VALUES (%s, 'cmp_a', %s, %s, %s, %s, 1, '[]', '[]', '[]', '[]', '[]',
                   '{}', '[]', 5, 50, false, %s, 'template',
                   CASE WHEN %s THEN now() ELSE NULL END)""",
        (identifier, employee_id, version, status, role, f"hash-{identifier}", activated),
    )


# -- schema -----------------------------------------------------------------


def test_migration_adds_the_p0_tables(conn):
    import psycopg

    names = {
        row[0]
        for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    }
    assert {
        "companies",
        "role_templates",
        "company_employees",
        "contracts",
        "budget_accounts",
        "budget_reservations",
        "budget_ledger_entries",
    } <= names


def test_events_gains_the_logical_offset_column(conn):
    columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'events'"
        ).fetchall()
    }
    assert "clock_offset_ms" in columns


def test_single_active_company_is_a_partial_index(conn):
    """The unique index must apply only to active rows, not to every company."""
    definition = conn.execute(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_one_active_company'"
    ).fetchone()[0]
    assert "UNIQUE" in definition
    assert "WHERE" in definition and "active" in definition


def test_models_and_migration_agree(migrated_db):
    """``alembic check`` fails if the models have drifted from the migration."""
    from alembic import command

    command.check(migrated_db)


# -- single active company --------------------------------------------------


def test_second_active_company_is_refused(conn):
    import psycopg

    insert_company(conn, "cmp_a", status="active")
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_company(conn, "cmp_b", status="active")


def test_drafts_and_a_paused_company_are_allowed(conn):
    insert_company(conn, "cmp_a", status="draft")
    insert_company(conn, "cmp_b", status="draft")
    insert_company(conn, "cmp_c", status="paused")
    insert_company(conn, "cmp_d", status="active")
    count = conn.execute("SELECT count(*) FROM companies").fetchone()[0]
    assert count == 4


# -- contract immutability ---------------------------------------------------


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("role", "'Rewritten'"),
        ("objective", "'A new objective'"),
        ("budget_per_month", "999999"),
        ("budget_per_task", "0"),
        ("data_scope", "'[{\"resource\": \"customer/records\"}]'"),
        ("tool_scope", "'[{\"tool\": \"anything\"}]'"),
        ("responsibilities", "'[\"anything\"]'"),
        ("restrictions", "'[\"anything\"]'"),
        ("task_scope", "'[\"anything\"]'"),
        ("communication_policy", "'{\"allow\": [\"*\"], \"broadcast\": true}'"),
        ("approval_rules", "'[{\"action\": \"anything\", \"requiredApprover\": \"emp_1\"}]'"),
        ("reports_to_employee_id", "'emp_1'"),
        ("content_hash", "'tampered'"),
    ],
)
def test_activated_contract_rejects_material_edits(conn, column, value):
    """Every material term is frozen at activation, including the budgets.

    Covers the whole set rather than one representative column: a gap in the
    trigger's column list would otherwise leave a term editable.
    """
    import psycopg

    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_contract(conn, "ctr_1", status="active", activated=True)

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(f"UPDATE contracts SET {column} = {value} WHERE id = 'ctr_1'")


def test_activated_contract_still_allows_a_lifecycle_transition(conn):
    """Immutability covers the terms, not the lifecycle."""
    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_contract(conn, "ctr_1", status="active", activated=True)

    conn.execute(
        "UPDATE contracts SET status = 'superseded', superseded_at = now() WHERE id = 'ctr_1'"
    )
    status = conn.execute("SELECT status FROM contracts WHERE id = 'ctr_1'").fetchone()[0]
    assert status == "superseded"


def test_draft_contract_terms_are_still_editable(conn):
    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_contract(conn, "ctr_1")
    conn.execute("UPDATE contracts SET role = 'Sales Lead' WHERE id = 'ctr_1'")
    role = conn.execute("SELECT role FROM contracts WHERE id = 'ctr_1'").fetchone()[0]
    assert role == "Sales Lead"


def test_activated_contract_cannot_be_deleted(conn):
    import psycopg

    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_contract(conn, "ctr_1", status="active", activated=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("DELETE FROM contracts WHERE id = 'ctr_1'")


def test_the_extended_trigger_covers_the_p0_4_columns(conn):
    """P0.4's new material terms are protected by the database, not just the ORM.

    The trigger was replaced by the P0.4 migration rather than edited in place. If
    the replacement had kept the old column list, these two columns would be
    editable while the content hash treated them as material.
    """
    import psycopg

    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_employee(conn, "emp_2")
    insert_contract(conn, "ctr_1", status="active", activated=True)

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE contracts SET role_config_version = 2 WHERE id = 'ctr_1'")

    # The helper inserts requires_human_escalation as false, so flipping it *to true*
    # is the edit; writing false again would be a no-op the trigger rightly ignores.
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "UPDATE contracts SET requires_human_escalation = true WHERE id = 'ctr_1'"
        )

    # The lifecycle exception must survive the trigger replacement.
    conn.execute(
        "UPDATE contracts SET status = 'superseded', superseded_at = now() WHERE id = 'ctr_1'"
    )
    assert (
        conn.execute("SELECT status FROM contracts WHERE id = 'ctr_1'").fetchone()[0]
        == "superseded"
    )


def test_draft_contract_can_be_deleted(conn):
    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_contract(conn, "ctr_1")
    conn.execute("DELETE FROM contracts WHERE id = 'ctr_1'")
    remaining = conn.execute("SELECT count(*) FROM contracts").fetchone()[0]
    assert remaining == 0


def test_only_one_active_contract_per_employee(conn):
    import psycopg

    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_contract(conn, "ctr_1", status="active", activated=True)
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_contract(conn, "ctr_2", version=2, status="active", activated=True)


# -- money and configuration guards -----------------------------------------


def test_money_is_stored_as_exact_decimal(conn):
    """No float rounding: authorisation decisions must not depend on binary floats."""
    insert_company(conn, "cmp_a")
    conn.execute(
        """INSERT INTO budget_accounts (id, company_id, currency, monthly_limit,
             period_start, period_end, version)
           VALUES ('bac_1', 'cmp_a', 'USD', 1000.10, now(), now() + interval '30 days', 1)"""
    )
    limit = conn.execute("SELECT monthly_limit FROM budget_accounts").fetchone()[0]
    assert limit == Decimal("1000.100000")
    assert str(limit) == "1000.100000"


def test_currency_must_be_three_characters(conn):
    """Money is refused before it is stored, not when it is reported."""
    import psycopg

    insert_company(conn, "cmp_a")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            """INSERT INTO budget_accounts (id, company_id, currency, monthly_limit,
                 period_start, period_end, version)
               VALUES ('bac_1', 'cmp_a', 'US', 100, now(), now() + interval '30 days', 1)"""
        )
    conn.execute(
        """INSERT INTO budget_accounts (id, company_id, currency, monthly_limit,
             period_start, period_end, version)
           VALUES ('bac_2', 'cmp_a', 'USD', 100, now(), now() + interval '30 days', 1)"""
    )
    assert conn.execute("SELECT count(*) FROM budget_accounts").fetchone()[0] == 1


def test_the_ledger_is_append_only(conn):
    """Financial history cannot be edited or deleted.

    Correcting a mistake is a new entry; rewriting a row would change what the
    history says happened.
    """
    import psycopg

    insert_company(conn, "cmp_a")
    insert_employee(conn, "emp_1")
    insert_contract(conn, "ctr_1", status="active", activated=True)
    conn.execute(
        """INSERT INTO budget_accounts (id, company_id, currency, monthly_limit,
             period_start, period_end, version)
           VALUES ('bac_1', 'cmp_a', 'USD', 1000, now(), now() + interval '30 days', 1)"""
    )
    conn.execute(
        """INSERT INTO budget_ledger_entries (id, company_id, account_id, employee_id,
             category, amount, currency, idempotency_key)
           VALUES ('led_1', 'cmp_a', 'bac_1', 'emp_1', 'actual_cost_charged', 10,
                   'USD', 'idem-1')"""
    )
    conn.commit()

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE budget_ledger_entries SET amount = 0 WHERE id = 'led_1'")
    conn.rollback()

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("DELETE FROM budget_ledger_entries WHERE id = 'led_1'")
    conn.rollback()

    amount = conn.execute(
        "SELECT amount FROM budget_ledger_entries WHERE id = 'led_1'"
    ).fetchone()[0]
    assert amount == 10, "the ledger row survived untouched"


def test_p0_2_column_is_added_safely_to_a_populated_table():
    """``responsibilities`` is NOT NULL, so the upgrade must cope with existing rows.

    Adding a NOT NULL column with no default to a table that already holds rows
    fails outright. This migrates to the previous revision, writes a row, then
    upgrades: the row must survive with an empty list.
    """
    import psycopg
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.engine import make_url

    from app.core.config import get_settings

    # Two forms of the same URL: the SQLAlchemy driver name for the application
    # and Alembic, and the plain libpq name psycopg itself understands.
    sa_url = make_url(os.environ["KAYAN_TEST_DATABASE_URL"])
    pg_url = sa_url.set(drivername="postgresql")
    admin_url = pg_url.set(database="postgres")
    previous_url = os.environ.get("DATABASE_URL")
    database = "kayan_p0_2_migration_test"

    admin = psycopg.connect(str(admin_url), autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
    admin.execute(f'CREATE DATABASE "{database}"')
    admin.close()

    alembic_ini = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini"
    )
    config = Config(alembic_ini)
    os.environ["DATABASE_URL"] = str(sa_url.set(database=database))
    get_settings.cache_clear()
    target_url = pg_url.set(database=database)
    try:
        # Stop one revision short: the schema before the new column exists.
        command.upgrade(config, "90c90b1427fa")
        conn = psycopg.connect(str(target_url), autocommit=True)
        try:
            conn.execute(
                """INSERT INTO companies (id, name, template_key, currency, status, revision)
                   VALUES ('cmp_pop', 'Populated', 'clothing', 'USD', 'draft', 1)"""
            )
            # The pre-upgrade schema has no responsibilities column, which is the
            # whole point: this row is what the upgrade has to cope with.
            conn.execute(
                """INSERT INTO company_employees (id, company_id, display_name, kind,
                     role_key, status)
                   VALUES ('emp_pop', 'cmp_pop', 'Existing', 'human', 'ceo', 'draft')"""
            )
        finally:
            conn.close()

        command.upgrade(config, "head")

        conn = psycopg.connect(str(target_url), autocommit=True)
        try:
            row = conn.execute(
                "SELECT responsibilities FROM company_employees WHERE id = 'emp_pop'"
            ).fetchone()
            assert row is not None, "the existing employee must survive the upgrade"
            assert row[0] == [], "an absent list defaults to empty, not null"
        finally:
            conn.close()
    finally:
        get_settings.cache_clear()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        admin = psycopg.connect(str(admin_url), autocommit=True)
        admin.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
        admin.close()