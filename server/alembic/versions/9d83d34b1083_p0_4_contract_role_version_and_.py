"""P0.4: the role version behind a contract, and human-escalation terms.

A contract is the formal boundary for an employee's authority, so two things the
P0.1 table lacked have to be part of it:

* ``role_config_version`` — the exact catalogue version the terms were derived from.
  Without it, a role revised in a later ``config_version`` would leave existing
  contracts referring to "sales" while the catalogue meant something else.
* ``requires_human_escalation`` — whether this seat must hand a decision to a human.
  A seat with neither this flag nor an approval rule can complete its own work,
  which makes it a term of authority rather than a UI preference.

Both are added with a temporary server default and the default is dropped
immediately, so the upgrade is safe on a table that already holds contracts.

**The immutability trigger is replaced, not edited.** The original trigger was
created by an applied migration, which must not be rewritten. The replacement covers
the two new columns as well, so the database protects exactly the same set of
material terms the ORM and the content hash do. Leaving the trigger behind would
mean the database considered these terms editable while the hash considered them
material — a silent hole in the guarantee P0.1 established.

Revision ID: 9d83d34b1083
Revises: 2e97ed99de6c
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '9d83d34b1083'
down_revision: str | None = '2e97ed99de6c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Every material term of a contract. This list is the database's view of "the
#: substance"; ``app.company.contract_terms`` is the application's view. They must
#: agree, or the hash protects something the trigger does not.
MATERIAL_COLUMNS: tuple[str, ...] = (
    "company_id",
    "employee_id",
    "version_number",
    "role",
    "role_config_version",
    "objective",
    "responsibilities",
    "data_scope",
    "tool_scope",
    "restrictions",
    "task_scope",
    "communication_policy",
    "approval_rules",
    "budget_per_task",
    "budget_per_month",
    "reports_to_employee_id",
    "requires_human_escalation",
    "content_hash",
)

_IMMUTABLE_UPDATE_TRIGGER = """
CREATE OR REPLACE FUNCTION kayan_guard_contract_terms() RETURNS trigger AS $$
BEGIN
    IF OLD.activated_at IS NOT NULL THEN
        IF ({new_columns}) IS DISTINCT FROM ({old_columns}) THEN
            RAISE EXCEPTION
                'contract % is activated: its terms are immutable (attempted change to %)',
                OLD.id, TG_ARGV[0]
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""


def _create_triggers() -> None:
    op.execute(_IMMUTABLE_UPDATE_TRIGGER.format(
        new_columns=", ".join(f"NEW.{column}" for column in MATERIAL_COLUMNS),
        old_columns=", ".join(f"OLD.{column}" for column in MATERIAL_COLUMNS),
    ))
    op.execute(
        "CREATE TRIGGER trg_contract_terms_immutable BEFORE UPDATE ON contracts "
        "FOR EACH ROW EXECUTE FUNCTION kayan_guard_contract_terms("
        + ", ".join(f"'{column}'" for column in MATERIAL_COLUMNS)
        + ")"
    )


def _drop_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_contract_terms_immutable ON contracts")


def upgrade() -> None:
    op.add_column(
        'contracts',
        sa.Column('role_config_version', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'contracts',
        sa.Column(
            'requires_human_escalation',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.alter_column('contracts', 'role_config_version', server_default=None)
    op.alter_column('contracts', 'requires_human_escalation', server_default=None)

    if op.get_bind().dialect.name == 'postgresql':
        _drop_triggers()
        _create_triggers()


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        _drop_triggers()
        # Restore the P0.1 trigger exactly, so a downgraded database is guarded by
        # the same terms it was before.
        _create_triggers_p01()

    op.drop_column('contracts', 'requires_human_escalation')
    op.drop_column('contracts', 'role_config_version')


def _create_triggers_p01() -> None:
    """The original P0.1 material column set."""
    p01_columns = tuple(column for column in MATERIAL_COLUMNS
                        if column not in ("role_config_version", "requires_human_escalation"))
    op.execute(_IMMUTABLE_UPDATE_TRIGGER.format(
        new_columns=", ".join(f"NEW.{column}" for column in p01_columns),
        old_columns=", ".join(f"OLD.{column}" for column in p01_columns),
    ))
    op.execute(
        "CREATE TRIGGER trg_contract_terms_immutable BEFORE UPDATE ON contracts "
        "FOR EACH ROW EXECUTE FUNCTION kayan_guard_contract_terms("
        + ", ".join(f"'{column}'" for column in p01_columns)
        + ")"
    )