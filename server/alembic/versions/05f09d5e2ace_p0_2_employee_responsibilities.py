"""P0.2: draft responsibilities on configured employees.

Adds ``company_employees.responsibilities`` so the workforce API can accept an
explicit responsibility list per seat. Empty means "inherit the role template's
default", which is resolved when a contract is generated in P0.4 — the contract
becomes authoritative once a company is activated, so this column stays a draft
input rather than a second source of authority.

The column is ``NOT NULL``. Because a deployment may already hold rows, it is
added with a server default and the default is dropped immediately afterwards:
existing rows become ``[]``, and new inserts are governed by the ORM default, so
the database never carries a default that silently overrides application logic.

Revision ID: 05f09d5e2ace
Revises: 90c90b1427fa
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '05f09d5e2ace'
down_revision: str | None = '90c90b1427fa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_COLUMN = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite')


def upgrade() -> None:
    op.add_column(
        'company_employees',
        sa.Column('responsibilities', JSON_COLUMN, nullable=False, server_default='[]'),
    )
    # The default existed only to populate existing rows.
    op.alter_column('company_employees', 'responsibilities', server_default=None)


def downgrade() -> None:
    op.drop_column('company_employees', 'responsibilities')