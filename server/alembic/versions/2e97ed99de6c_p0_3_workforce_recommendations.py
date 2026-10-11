"""P0.3: workforce recommendation history.

Adds ``recommendations``: a record of what was proposed, for whom, by which
provider, against which catalogue version.

A recommendation is a proposal, not a configuration. Generating one must never
create an employee, a contract or a budget movement, so this table holds no
foreign key to ``company_employees`` or ``contracts`` — only to the company that
asked. Rows cascade when their company is deleted.

The proposal is stored as a self-contained snapshot. A role definition may be
revised in a later ``config_version``, and a historical record has to keep saying
what was actually recommended at the time, so the roles, scopes and explanations
are stored verbatim next to the version they came from.

Revision ID: 2e97ed99de6c
Revises: 05f09d5e2ace
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '2e97ed99de6c'
down_revision: str | None = '05f09d5e2ace'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_COLUMN = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite')


def upgrade() -> None:
    op.create_table(
        'recommendations',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('company_id', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('provider_name', sa.String(length=64), nullable=True),
        sa.Column('model_name', sa.String(length=128), nullable=True),
        sa.Column('preferences', JSON_COLUMN, nullable=False),
        sa.Column('role_catalog_version', sa.Integer(), nullable=False),
        sa.Column('proposal', JSON_COLUMN, nullable=False),
        sa.Column('proposed_employee_count', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'proposed', 'accepted', 'rejected',
                name='recommendationstatus',
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            'proposed_employee_count >= 1', name='ck_recommendation_has_employee'
        ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_recommendations_company_id'), 'recommendations', ['company_id'], unique=False
    )
    op.create_index(
        op.f('ix_recommendations_status'), 'recommendations', ['status'], unique=False
    )
    op.create_index(
        'ix_recommendations_company_created',
        'recommendations',
        ['company_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_recommendations_company_created', table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_status'), table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_company_id'), table_name='recommendations')
    op.drop_table('recommendations')