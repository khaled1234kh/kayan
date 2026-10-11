"""Shared route dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.company.errors import DomainError
from app.core.config import get_settings
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]

#: List endpoints are paginated by explicit ``limit``/``offset`` query parameters.
LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


def not_found(entity: str, entity_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{entity} '{entity_id}' not found",
    )


def to_http(error: DomainError) -> HTTPException:
    """Translate a domain error into an HTTP response.

    The body names the offending field and carries the domain's safe details only —
    never a traceback, a query or a connection string.
    """
    return HTTPException(status_code=error.status_code, detail=error.to_payload())


def verify_budget_adjustment_token(
    x_budget_adjustment_token: str | None = Header(default=None),
) -> None:
    """Dev-only shared-secret check for the budget adjustment endpoint.

    When ``BUDGET_ADJUSTMENT_TOKEN`` is set, the request must carry a matching
    ``X-Budget-Adjustment-Token`` header. When it is empty (the default), the
    endpoint is open for local development.

    This is NOT production authentication. KAYAN has no auth in this phase; this
    header is a development convenience so a local endpoint is not accidentally
    exposed on a shared network.
    """
    expected = get_settings().budget_adjustment_token
    if not expected:
        return
    if x_budget_adjustment_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing budget adjustment token",
        )