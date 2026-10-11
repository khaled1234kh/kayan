"""P0.5: company tasks, and an append-only financial ledger.

Two changes:

**``company_tasks``.** P0.1 gave reservations and ledger entries a ``task_id``, and
P0.2 pointed it at the demo workflow's ``tasks`` table. That was the only task
concept available at the time, but it cannot represent company work: those rows
belong to an order run and are owned by agents. Budget enforcement needs a task that
belongs to a company and an employee, because the per-task ceiling is aggregated
over one employee's work on one task and the association has to be verifiable rather
than a free-form string. The foreign key is repointed accordingly; no rows exist
yet, so nothing is rewritten.

**Ledger immutability.** ``budget_ledger_entries`` is financial history. A trigger
now refuses UPDATE and DELETE, in the same spirit as the activated-contract
protection. Corrections are made by appending an adjustment entry, never by editing
a row that already told someone what happened.

Revision ID: ebf974aa3fc6
Revises: 9d83d34b1083
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'ebf974aa3fc6'
down_revision: str | None = '9d83d34b1083'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The task references repointed at the company task table, and back again on
#: downgrade. Named explicitly: an unnamed constraint cannot be dropped.
TASK_FOREIGN_KEYS = (
    ('budget_ledger_entries', 'budget_ledger_entries_task_id_fkey', 'company_tasks'),
    ('budget_reservations', 'budget_reservations_task_id_fkey', 'company_tasks'),
)


_APPEND_ONLY = """
CREATE OR REPLACE FUNCTION kayan_guard_ledger_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'budget_ledger_entries is append-only financial history: % is not permitted. '
        'Record a correcting adjustment entry instead.',
        TG_OP
        USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql
"""


def _guard_ledger() -> None:
    op.execute(_APPEND_ONLY)
    op.execute(
        "CREATE TRIGGER trg_ledger_no_update BEFORE UPDATE ON budget_ledger_entries "
        "FOR EACH ROW EXECUTE FUNCTION kayan_guard_ledger_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_ledger_no_delete BEFORE DELETE ON budget_ledger_entries "
        "FOR EACH ROW EXECUTE FUNCTION kayan_guard_ledger_append_only()"
    )


def _unguard_ledger() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_no_delete ON budget_ledger_entries")
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_no_update ON budget_ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS kayan_guard_ledger_append_only()")


def upgrade() -> None:
    op.create_table(
        'company_tasks',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('company_id', sa.String(length=64), nullable=False),
        sa.Column('employee_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'open', 'awaiting_approval', 'blocked', 'completed',
                name='taskstatus', native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['employee_id'], ['company_employees.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_company_tasks_company_id'), 'company_tasks', ['company_id'], unique=False
    )
    op.create_index(
        op.f('ix_company_tasks_employee_id'), 'company_tasks', ['employee_id'], unique=False
    )
    op.create_index(
        'ix_company_tasks_company_status',
        'company_tasks',
        ['company_id', 'status'],
        unique=False,
    )

    # Repoint the task references at the company task table.
    for table, constraint, target in TASK_FOREIGN_KEYS:
        op.drop_constraint(constraint, table, type_='foreignkey')
        op.create_foreign_key(constraint, table, target, ['task_id'], ['id'], ondelete='SET NULL')

    if op.get_bind().dialect.name == 'postgresql':
        _guard_ledger()


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        _unguard_ledger()

    # Point the task references back at the workflow task table.
    for table, constraint, _target in TASK_FOREIGN_KEYS:
        op.drop_constraint(constraint, table, type_='foreignkey')
        op.create_foreign_key(
            constraint, table, 'tasks', ['task_id'], ['id'], ondelete='SET NULL'
        )

    op.drop_index('ix_company_tasks_company_status', table_name='company_tasks')
    op.drop_index(op.f('ix_company_tasks_employee_id'), table_name='company_tasks')
    op.drop_index(op.f('ix_company_tasks_company_id'), table_name='company_tasks')
    op.drop_table('company_tasks')