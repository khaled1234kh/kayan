"""Domain errors for company configuration.

Services raise these; routes translate them to HTTP. Keeping them out of the
service layer means the business rules stay testable without a request, and the
API layer stays free of ``HTTPException``.

Every error carries the *field or relationship* that caused it, so a client can
point at the problem without parsing a traceback.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for company configuration failures."""

    #: HTTP status the API layer maps this to.
    status_code = 422

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        """Response body: what was wrong, and where. Never an internal trace."""
        payload: dict[str, Any] = {"detail": self.message}
        if self.field:
            payload["field"] = self.field
        if self.details:
            payload["details"] = self.details
        return payload


class ConfigurationError(DomainError):
    """The submitted configuration is not valid (422)."""


class RelationshipError(ConfigurationError):
    """A reporting or cross-entity relationship is not valid (422)."""


class NotFoundError(DomainError):
    """The addressed company or employee does not exist (404)."""

    status_code = 404


class ConflictError(DomainError):
    """The operation is not legal for the entity's current state (409)."""

    status_code = 409