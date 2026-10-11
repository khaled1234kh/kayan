"""Setup catalogue endpoints.

Read-only: these describe what a company *can* be configured with. They are the
input the future onboarding wizard will consume, so the shape is stable and the
ordering deterministic.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from pydantic import AliasChoices

from app.api.deps import DbSession, to_http
from app.company.errors import DomainError
from app.schemas import RoleOut, TemplateOut
from app.schemas.recommendation import RecommendationOut, RecommendationRequest
from app.services.catalog import SetupCatalogService
from app.services.recommendations import RecommendationService

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get(
    "/templates",
    response_model=list[TemplateOut],
    summary="List available company templates",
)
def list_templates(session: DbSession) -> list[TemplateOut]:
    return SetupCatalogService(session).list_templates()


@router.get(
    "/roles",
    response_model=list[RoleOut],
    summary="List versioned role definitions",
)
def list_roles(
    session: DbSession,
    template_key: str | None = Query(
        default=None,
        # Both spellings are accepted. An unrecognised parameter would otherwise be
        # ignored silently, and the caller would receive an unfiltered list while
        # believing it had filtered.
        validation_alias=AliasChoices("template_key", "templateKey"),
        description="Limit to the roles offered by this company template.",
    ),
) -> list[RoleOut]:
    """Current version of each role, ordered by key.

    An unknown ``template_key`` is refused with 422 rather than answered with an
    empty or unfiltered list.
    """
    try:
        return SetupCatalogService(session).list_roles(template_key=template_key)
    except DomainError as error:
        raise to_http(error)


@router.post(
    "/recommendations",
    response_model=RecommendationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Recommend a workforce configuration for a draft company",
)
def create_recommendation(
    payload: RecommendationRequest, session: DbSession
) -> RecommendationOut:
    """Propose a workforce. Nothing about the company changes as a result.

    Budget, currency, template and target are read from the saved company rather
    than taken from the request, so a proposal is always built against the
    configuration the owner actually has.
    """
    try:
        return RecommendationService(session).generate(payload)
    except DomainError as error:
        raise to_http(error)


@router.get(
    "/recommendations/{recommendation_id}",
    response_model=RecommendationOut,
    summary="Retrieve a stored recommendation",
)
def get_recommendation(recommendation_id: str, session: DbSession) -> RecommendationOut:
    """Retrievable after a page reload; the proposal is stored as a snapshot."""
    try:
        return RecommendationService(session).get(recommendation_id)
    except DomainError as error:
        raise to_http(error)