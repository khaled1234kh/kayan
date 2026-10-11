"""Workforce recommendation service.

Generates, validates, persists and retrieves workforce proposals.

**A recommendation is a proposal, not a change.** Generating one creates a
``recommendations`` row and nothing else: no ``CompanyEmployee``, no contract, no
budget movement, no status change on the company. The owner's roster is untouched
until they explicitly submit a workforce, which is a P0.2 operation.

The order of operations is deliberate:

1. load the company and confirm it is still a draft;
2. build the context from *saved* configuration, never from duplicated request data;
3. ask the provider for a proposal;
4. validate that proposal against the catalogue and the reporting rules;
5. persist the record and its ``recommendation_generated`` event in one transaction.

Step 4 sits between the provider and the database on purpose. A provider that
produces something invalid gets it rejected, and no success event is ever published
for a proposal that was not stored.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.company.errors import ConfigurationError, ConflictError, NotFoundError
from app.company.providers import (
    RecommendationContext,
    RecommendationProvider,
    register_provider,
    resolve_provider,
)
from app.company.recommendation_providers import TemplateProvider
from app.company.recommendation_validation import validate_proposal
from app.company.templates import template_by_key
from app.core.config import Settings, get_settings
from app.models import (
    Company,
    CompanyStatus,
    Recommendation,
    RecommendationStatus,
    RoleTemplate,
    new_recommendation_id,
)
from app.schemas.recommendation import RecommendationOut, RecommendationProposal, RecommendationRequest
from app.services.companies import STREAM_ID, CompanyService
from app.services.events import EventService

logger = logging.getLogger(__name__)

#: Registered once at import. A model provider would register here too, behind
#: configuration; none is registered because none is configured.
register_provider(TemplateProvider())


class RecommendationService:
    def __init__(
        self,
        session: Session,
        events: EventService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._events = events or EventService(session)
        self._companies = CompanyService(session, self._events)
        self._settings = settings or get_settings()

    # -- generation --------------------------------------------------------

    def generate(self, payload: RecommendationRequest) -> RecommendationOut:
        company = self._companies.get_company(payload.company_id)
        if company.status is not CompanyStatus.DRAFT:
            raise ConflictError(
                f"Company '{company.id}' is {company.status.value}; a workforce can only be "
                "recommended while the company is still a draft",
                field="status",
            )

        ceiling = self._current_ceiling(company)
        context = RecommendationContext(
            company_id=company.id,
            template_key=company.template_key,
            currency=company.currency,
            monthly_ceiling=ceiling,
            target=_describe_target(company),
        )

        provider, fell_back = resolve_provider(
            self._session, settings=self._settings, build=self._build_model_provider
        )
        catalogue = self._catalogue()

        try:
            proposal = provider.recommend(payload, catalogue, context)
            proposal = self._validated(proposal, context)
        except Exception as error:
            # A provider failure is a failed generation: nothing is persisted and no
            # success event is published.
            logger.warning(
                "recommendation generation failed for company %s: %s",
                company.id,
                type(error).__name__,
            )
            raise _as_domain_error(error)

        record = Recommendation(
            id=new_recommendation_id(),
            company_id=company.id,
            # The label follows the provider that actually produced the document.
            source=proposal.source,
            provider_name=proposal.provider_name,
            model_name=proposal.model_name,
            # JSON mode, not python mode: amounts are stored as decimal *strings*, never
            # floats, so a snapshot read back years from now is bit-for-bit what was
            # proposed rather than the nearest representable double.
            preferences=payload.preferences.model_dump(by_alias=True, mode="json"),
            role_catalog_version=proposal.role_catalog_version,
            proposal=proposal.model_dump(by_alias=True, mode="json"),
            proposed_employee_count=len(proposal.employees),
            status=RecommendationStatus.PROPOSED,
        )
        self._session.add(record)
        self._session.flush()

        warnings = list(proposal.warnings)
        if fell_back:
            warnings.insert(
                0,
                "A model provider was requested but is not configured; this proposal comes "
                "from the deterministic template fallback.",
            )

        event = self._events.stage(
            event_type="recommendation_generated",
            stream_id=STREAM_ID,
            target_id=company.id,
            payload={
                "companyId": company.id,
                "recommendationId": record.id,
                "source": record.source,
                "proposedEmployeeCount": record.proposed_employee_count,
                "totalSuggestedMonthly": str(proposal.budget.total_suggested_monthly),
                "roleCatalogVersion": record.role_catalog_version,
            },
        )
        # Persisted, then published: the record exists before anyone hears about it.
        self._events.commit_and_publish([event])
        self._session.refresh(record)

        logger.info(
            "generated %s recommendation %s for company %s (%d seats, provider=%s)",
            record.source,
            record.id,
            company.id,
            record.proposed_employee_count,
            provider.name,
        )
        return self._to_out(record, warnings)

    # -- retrieval ---------------------------------------------------------

    def get(self, recommendation_id: str) -> RecommendationOut:
        record = self._session.get(Recommendation, recommendation_id)
        if record is None:
            raise NotFoundError(
                f"Recommendation '{recommendation_id}' not found", field="recommendationId"
            )
        return self._to_out(record)

    def list_for_company(self, company_id: str) -> list[RecommendationOut]:
        self._companies.get_company(company_id)
        stmt = (
            select(Recommendation)
            .where(Recommendation.company_id == company_id)
            .order_by(Recommendation.created_at, Recommendation.id)
        )
        return [self._to_out(record) for record in self._session.execute(stmt).scalars()]

    # -- internals ---------------------------------------------------------

    def _current_ceiling(self, company: Company) -> Decimal:
        """The company's saved monthly ceiling.

        Read from the budget account rather than the request, so a recommendation
        can never be built against a number the company does not actually have.
        """
        account = CompanyService(self._session, self._events).get_budget_account(company.id)
        if account is None:
            raise ConfigurationError(
                f"Company '{company.id}' has no budget account, so there is no monthly "
                "ceiling to allocate against",
                field="companyId",
            )
        return Decimal(account.monthly_limit)

    def _catalogue(self) -> list[RoleTemplate]:
        """Current version of every seeded role, ordered by key."""
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
        return list(self._session.execute(stmt).scalars())

    def _validated(
        self, proposal: RecommendationProposal, context: RecommendationContext
    ) -> RecommendationProposal:
        catalogue = {role.key: role for role in self._catalogue()}
        offered = list((template_by_key(context.template_key) or {}).get("role_keys") or [])
        return validate_proposal(
            proposal,
            catalogue=catalogue,
            offered_role_keys=offered,
            monthly_ceiling=Decimal(context.monthly_ceiling),
            currency=context.currency,
        )

    def _build_model_provider(self) -> RecommendationProvider:
        """Raise unless a model provider is configured.

        No inference client is constructed and no credential is read: this backend
        declares no model dependency. The seam exists so adding one is a
        registration, not a redesign — and so requesting ``model`` today produces the
        labelled template fallback instead of a fabricated call.
        """
        raise ConfigurationError(
            "No model provider is configured in this deployment",
            field="provider",
        )

    def _to_out(self, record: Recommendation, extra_warnings: list[str] | None = None) -> RecommendationOut:
        proposal = RecommendationProposal.model_validate(record.proposal)
        if extra_warnings:
            merged = list(dict.fromkeys([*extra_warnings, *proposal.warnings]))
            proposal = proposal.model_copy(update={"warnings": merged})
        return RecommendationOut(
            id=record.id,
            company_id=record.company_id,
            status=record.status.value,
            created_at=record.created_at,
            preferences=record.preferences,
            proposal=proposal,
        )


def _describe_target(company: Company) -> str | None:
    """The company's own words about success, used in the explanations."""
    parts = []
    if company.target_description:
        parts.append(company.target_description.strip())
    if company.target_metric and company.target_value is not None:
        parts.append(f"target {company.target_metric} = {company.target_value}")
    return " — ".join(parts) if parts else None


def _as_domain_error(error: Exception) -> Exception:
    """Present a provider failure as a configuration error, not a crash."""
    if isinstance(error, ConfigurationError):
        return error
    return ConfigurationError(
        f"The recommendation could not be produced: {error}", field="preferences"
    )


def get_recommendation_service(session: Session) -> RecommendationService:
    return RecommendationService(session)


__all__ = ["RecommendationService", "get_recommendation_service"]