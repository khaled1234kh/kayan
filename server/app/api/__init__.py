"""HTTP API layer.

Read-only endpoints that prove the backend is authoritative for the domain.
ORM models are never returned directly; routes return Pydantic schemas.
"""

from app.api.router import api_router

__all__ = ["api_router"]