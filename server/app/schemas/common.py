"""Shared schema configuration.

API field names are camelCase to match the frontend event contract
(``actorId``, ``taskId``, ``eventType``), so a future WebSocket frame and a REST
response describe the same shape. Database columns stay snake_case.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiSchema(BaseModel):
    """Base for outbound API contracts.

    Reads ORM attributes directly and serialises to camelCase aliases.
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ApiCreate(BaseModel):
    """Base for inbound write payloads."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class HealthResponse(BaseModel):
    """``GET /api/health`` contract."""

    status: str