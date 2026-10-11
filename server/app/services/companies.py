"""Company configuration service.

Owns company creation, reads and draft edits, including the budget account that
represents the company's monthly ceiling.

Two rules shape the whole module:

* **The state change and its audit event commit together.** Domain rows are written
  first, the governance event is *staged* through :class:`EventService`, and both
  are committed in one transaction. Publication happens after that commit, so no
  client can observe a company that was never recorded — or an event for a
  company that was rolled back.
* **A company is created in draft.** Activation is a later stage and this service
  never writes ``status`` beyond ``draft``. Multiple drafts are allowed; the
  single-active-company rule stays a database constraint.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company.errors import ConfigurationError, ConflictError, NotFoundError
from app.company.templates import TEMPLATE_KEYS
from app.models import (
    BudgetAccount,
    Company,
    CompanyStatus,
    new_company_id,
)
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.events import EventService

logger = logging.getLogger(__name__)

#: Configuration changes travel on the same stream as workflow events, with no run.
STREAM_ID = "main"


def current_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The UTC calendar month containing ``now``, as ``[start, end)``."""
    moment = now or datetime.now(timezone.utc)
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day) + timedelta(days=1)
    return start, end


class CompanyService:
    def __init__(self, session: Session, events: EventService | None = None) -> None:
        self._session = session
        self._events = events or EventService(session)

    # -- reads -------------------------------------------------------------

    def get_company(self, company_id: str) -> Company:
        company = self._session.get(Company, company_id)
        if company is None:
            raise NotFoundError(
                f"Company '{company_id}' not found", field="companyId"
            )
        return company

    def list_companies(self, *, status: CompanyStatus | None = None) -> list[Company]:
        stmt = select(Company).order_by(Company.created_at, Company.id)
        if status is not None:
            stmt = stmt.where(Company.status == status)
        return list(self._session.execute(stmt).scalars())

    def get_budget_account(self, company_id: str, *, period_start: datetime | None = None) -> BudgetAccount | None:
        """The company's budget account for a period (default: current month)."""
        start = period_start or current_period()[0]
        stmt = select(BudgetAccount).where(
            BudgetAccount.company_id == company_id,
            BudgetAccount.period_start == start,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    # -- create ------------------------------------------------------------

    def create_company(self, payload: CompanyCreate) -> Company:
        """Create a draft company with its initial monthly budget account.

        Both rows and the ``company_created`` event are committed together, so a
        failure anywhere leaves no half-created company behind.
        """
        template_key = self._validate_template(payload.template_key)
        company = Company(
            id=new_company_id(),
            name=payload.name,
            industry=payload.industry,
            template_key=template_key,
            target_description=payload.target_description,
            target_metric=payload.target_metric,
            target_value=payload.target_value,
            target_unit=payload.target_unit,
            target_period=payload.target_period,
            currency=payload.currency,
            status=CompanyStatus.DRAFT,
            revision=1,
        )
        self._session.add(company)
        # The company row must exist before its budget account: the two tables are
        # linked by a foreign key but not by an ORM relationship, so the unit of work
        # is not obliged to order their inserts.
        self._session.flush()

        period_start, period_end = current_period()
        account = BudgetAccount(
            id=f"bac_{company.id.removeprefix('cmp_')}",
            company_id=company.id,
            currency=payload.currency,
            monthly_limit=payload.monthly_budget,
            period_start=period_start,
            period_end=period_end,
        )
        self._session.add(account)
        # Flush so the event payload can carry real ids before the commit.
        self._session.flush()

        event = self._events.stage(
            event_type="company_created",
            stream_id=STREAM_ID,
            target_id=company.id,
            payload={
                "companyId": company.id,
                "name": company.name,
                "templateKey": company.template_key,
                "currency": company.currency,
                "monthlyBudget": str(account.monthly_limit),
                "status": company.status.value,
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(company)
        logger.info("created draft company %s (%s)", company.id, company.template_key)
        return company

    # -- update ------------------------------------------------------------

    def update_company(self, company_id: str, payload: CompanyUpdate) -> tuple[Company, bool]:
        """Apply a partial draft update. Returns the company and whether it changed.

        A PATCH that changes nothing is not an event: reporting a change that did
        not happen would make the audit trail lie.
        """
        company = self.get_company(company_id)
        if company.status is not CompanyStatus.DRAFT:
            raise ConflictError(
                f"Company '{company_id}' is {company.status.value}; only a draft company "
                "can be edited. Lifecycle changes are a separate operation.",
                field="status",
            )

        # By alias, so the keys below are the camelCase API names rather than the
        # snake_case column names — the two differ, and a mismatch here would
        # silently drop an update.
        changes = payload.model_dump(exclude_unset=True, by_alias=True)
        if not changes:
            return company, False

        changed_fields: list[str] = []
        budget_changed = False

        if "monthlyBudget" in changes or "currency" in changes:
            if self._apply_budget_change(company, changes):
                budget_changed = True
        if budget_changed:
            changed_fields.append("monthlyBudget")
        if "currency" in changes and changes["currency"] != company.currency:
            changed_fields.append("currency")

        for field in (
            "name",
            "industry",
            "targetDescription",
            "targetMetric",
            "targetValue",
            "targetUnit",
            "targetPeriod",
        ):
            if field in changes:
                attribute = _SNAKE_TO_CAMEL_TO_COLUMN[field]
                value = changes[field]
                if getattr(company, attribute) != value:
                    setattr(company, attribute, value)
                    changed_fields.append(field)

        if "templateKey" in changes:
            template_key = self._validate_template(changes["templateKey"])
            if template_key != company.template_key:
                company.template_key = template_key
                changed_fields.append("templateKey")

        if not changed_fields:
            return company, False

        # A change to configuration is a new revision, so a client holding the old
        # roster or settings can detect that it is stale.
        company.revision += 1
        self._session.flush()

        event = self._events.stage(
            event_type="company_updated",
            stream_id=STREAM_ID,
            target_id=company.id,
            payload={
                "companyId": company.id,
                "revision": company.revision,
                "changedFields": sorted(set(changed_fields)),
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(company)
        logger.info(
            "updated draft company %s (%s)", company.id, ", ".join(sorted(set(changed_fields)))
        )
        return company, True

    # -- internals ---------------------------------------------------------

    def _validate_template(self, template_key: str) -> str:
        if template_key not in TEMPLATE_KEYS:
            raise ConfigurationError(
                f"templateKey '{template_key}' is not a supported template; "
                f"expected one of {', '.join(TEMPLATE_KEYS)}",
                field="templateKey",
            )
        return template_key

    def _apply_budget_change(self, company: Company, changes: dict[str, Any]) -> bool:
        """Keep the company and its budget account consistent.

        Minimal by design: the account's ceiling is adjusted and versioned. No
        reservation, ledger entry or adjustment event is produced here — budget
        enforcement is P0.5's job, and inventing an adjustment now would create
        history this stage has no meaning for.
        """
        currency = changes.get("currency") or company.currency
        new_limit = changes.get("monthlyBudget")

        account = self.get_budget_account(company.id)
        if account is None:
            if new_limit is None:
                return False
            period_start, period_end = current_period()
            account = BudgetAccount(
                id=f"bac_{company.id.removeprefix('cmp_')}",
                company_id=company.id,
                currency=currency,
                monthly_limit=new_limit,
                period_start=period_start,
                period_end=period_end,
            )
            self._session.add(account)
            return True

        if account.currency != currency:
            # One currency per company for P0: a mismatch is refused, never
            # converted, because no FX rate is authoritative here.
            raise ConfigurationError(
                f"Company '{company.id}' is configured in {company.currency}; it cannot be "
                f"changed to {currency}. Currency conversion is not supported.",
                field="currency",
            )

        if new_limit is not None and account.monthly_limit != new_limit:
            account.monthly_limit = new_limit
            account.version += 1
            return True
        return False


#: Incoming camelCase field -> ORM column. Explicit so a new API field cannot be
#: silently written to a column that does not exist.
_SNAKE_TO_CAMEL_TO_COLUMN = {
    "name": "name",
    "industry": "industry",
    "targetDescription": "target_description",
    "targetMetric": "target_metric",
    "targetValue": "target_value",
    "targetUnit": "target_unit",
    "targetPeriod": "target_period",
}


def get_company_service(session: Session) -> CompanyService:
    return CompanyService(session)


__all__ = [
    "CompanyService",
    "STREAM_ID",
    "current_period",
    "get_company_service",
]