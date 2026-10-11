"""Seed the versioned role-template catalogue (P0.1).

Idempotent: re-seeding updates the definition for the same
``(key, config_version)`` row and never duplicates it. Runs on application
startup alongside the agent seed, because contract generation in P0.4 needs the
catalogue to exist.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.company.templates import ROLE_SEEDS
from app.models import RoleTemplate

logger = logging.getLogger(__name__)

#: Bump when a role definition changes so existing contracts stay explainable
#: against the version that produced them.
TEMPLATE_CONFIG_VERSION = 1


def seed_role_templates(session: Session) -> int:
    """Insert or refresh the role catalogue. Returns rows written."""
    written = 0
    for role in ROLE_SEEDS:
        identity = (role.key, TEMPLATE_CONFIG_VERSION)
        row = session.get(RoleTemplate, identity)
        if row is None:
            row = RoleTemplate(key=role.key, config_version=TEMPLATE_CONFIG_VERSION)
            session.add(row)
        row.label = role.label
        row.kind = role.kind
        row.summary = role.summary
        row.responsibilities = list(role.responsibilities)
        row.task_categories = list(role.task_categories)
        row.default_data_scope = list(role.data_scope)
        row.default_tool_scope = list(role.tool_scope)
        row.default_restrictions = list(role.restrictions)
        row.template_keys = list(role.template_keys)
        row.config_version = TEMPLATE_CONFIG_VERSION
        row.active = True
        written += 1
    session.commit()
    logger.info("seeded %d role template(s) at v%d", written, TEMPLATE_CONFIG_VERSION)
    return written