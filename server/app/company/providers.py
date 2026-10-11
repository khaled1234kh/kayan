"""Recommendation providers.

A provider turns a company's configuration into a proposed workforce. The
interface is narrow on purpose: it receives the request and the versioned role
catalogue rows, and returns a proposal document.

**No model provider is configured in this deployment.** The backend declares no
inference dependency and holds no inference credentials, so nothing here invents
them or treats a coding subscription as an inference endpoint. What exists is the
seam — a registry, a selection policy and an explicit fallback rule — so that adding
a real provider later is a configuration change rather than a redesign.

Two invariants matter more than the feature itself:

* **The source label is earned.** A proposal says ``template`` when the template
  provider produced it and ``model`` when a configured model did. A fallback is
  never presented as a model result, and a model result is never presented as a
  template one.
* **A provider's output is untrusted input.** Whatever produces the document, it
  is validated against the catalogue and the reporting rules before it can be
  persisted or shown as authority. A provider cannot define executable permissions
  by asserting them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.company.errors import ConfigurationError
from app.models import RoleTemplate
from app.schemas.recommendation import RecommendationProposal, RecommendationRequest

logger = logging.getLogger(__name__)


@runtime_checkable
class RecommendationProvider(Protocol):
    """Produces a workforce proposal for a draft company."""

    #: Stable identifier recorded on the recommendation, e.g. ``template``.
    name: str

    #: The value written to ``Recommendation.source``.
    source: str

    #: Provider/model identifiers for a model-backed source; ``None`` otherwise.
    def identify(self) -> tuple[str | None, str | None]:
        """Return ``(provider_name, model_name)`` for the record."""

    def recommend(
        self,
        request: RecommendationRequest,
        roles: list[RoleTemplate],
        context: "RecommendationContext",
    ) -> RecommendationProposal:
        """Build a proposal. Must not touch the database or publish events."""


class RecommendationContext:
    """Read-only company configuration a provider may consult.

    Handed to the provider instead of the ORM objects so a provider cannot mutate
    the company, and so the values it reasons about are the values the owner saved.
    """

    __slots__ = ("company_id", "template_key", "currency", "monthly_ceiling", "target")

    def __init__(
        self,
        *,
        company_id: str,
        template_key: str,
        currency: str,
        monthly_ceiling,
        target: str | None,
    ) -> None:
        self.company_id = company_id
        self.template_key = template_key
        self.currency = currency
        self.monthly_ceiling = monthly_ceiling
        self.target = target

    def describe_target(self) -> str:
        """The company's own words about what success means, or a neutral default."""
        if not self.target:
            return "no explicit target recorded"
        return self.target


#: Providers registered by name. Populated by ``register_provider``.
_PROVIDERS: dict[str, RecommendationProvider] = {}


def register_provider(provider: RecommendationProvider) -> None:
    """Make a provider available for selection."""
    _PROVIDERS[provider.name] = provider


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)


def get_provider(name: str) -> RecommendationProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ConfigurationError(
            f"recommendation provider '{name}' is not registered; "
            f"available: {', '.join(available_providers()) or 'none'}",
            field="provider",
        )
    return provider


def resolve_provider(
    session: Session, *, settings: Any, build: Callable[[], RecommendationProvider]
) -> tuple[RecommendationProvider, bool]:
    """Choose the provider to use, and whether a fallback was taken.

    Policy, stated explicitly rather than implied:

    * ``RECOMMENDATION_PROVIDER=model`` with a model provider registered and
      configured → use it.
    * Otherwise → the deterministic template provider.

    The returned flag is ``True`` when the configured provider was requested but
    could not be used, so the caller can record *why* the source is ``template``
    instead of merely recording ``template``.
    """
    requested = (getattr(settings, "recommendation_provider", "template") or "template").lower()

    if requested == "model":
        try:
            provider = build()
        except Exception as error:  # pragma: no cover - no model provider exists yet
            logger.warning(
                "model recommendation provider unavailable (%s); using the template fallback",
                type(error).__name__,
            )
            return get_provider("template"), True
        if provider.source != "model":
            # A provider that cannot honestly label itself as a model is not one.
            logger.warning(
                "provider '%s' is not a model provider; using the template fallback",
                provider.name,
            )
            return get_provider("template"), True
        return provider, False

    return get_provider(requested), False


__all__ = [
    "RecommendationContext",
    "RecommendationProvider",
    "available_providers",
    "get_provider",
    "register_provider",
    "resolve_provider",
]