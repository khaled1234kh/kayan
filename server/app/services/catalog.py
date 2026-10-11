"""Setup catalogue: company templates and versioned roles.

Roles come from the seeded ``role_templates`` table, which is the source of truth —
this service holds no second role list. A key may exist at several
``config_version`` values; only the current one is exposed, so a client never has
to choose a version and the endpoint cannot return a stale definition alongside a
fresh one.

Ordering is deterministic (templates by declared order, roles by key) because the
onboarding wizard renders these lists directly.
"""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.company.errors import ConfigurationError
from app.company.templates import TEMPLATES, TEMPLATE_KEYS
from app.models import RoleTemplate
from app.schemas.company import RoleOut, TemplateOut


class SetupCatalogService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_templates(self) -> list[TemplateOut]:
        """Every company template the backend can configure, in catalogue order."""
        return [TemplateOut(**template) for template in TEMPLATES]

    def list_roles(self, *, template_key: str | None = None) -> list[RoleOut]:
        """Current role definitions, optionally limited to one template's roles.

        An unknown ``template_key`` is refused rather than silently returning an
        empty or unfiltered list: a wizard asking for roles of a template that does
        not exist should be told, not handed a plausible-looking answer.
        """
        if template_key is not None and template_key not in TEMPLATE_KEYS:
            raise ConfigurationError(
                f"templateKey '{template_key}' is not a supported template; "
                f"expected one of {', '.join(TEMPLATE_KEYS)}",
                field="templateKey",
            )

        # Highest config_version per key: the catalogue is versioned, the API is not.
        newest = (
            select(
                RoleTemplate.key.label("key"),
                func.max(RoleTemplate.config_version).label("version"),
            )
            .group_by(RoleTemplate.key)
            .subquery()
        )
        stmt = (
            select(RoleTemplate)
            .join(
                newest,
                and_(
                    newest.c.key == RoleTemplate.key,
                    newest.c.version == RoleTemplate.config_version,
                ),
            )
            .order_by(RoleTemplate.key)
        )
        rows = list(self._session.execute(stmt).scalars())

        if template_key is not None:
            rows = [row for row in rows if template_key in (row.template_keys or [])]
        return [RoleOut.model_validate(row) for row in rows]


def get_setup_catalog_service(session: Session) -> SetupCatalogService:
    return SetupCatalogService(session)


__all__ = ["SetupCatalogService", "get_setup_catalog_service"]