"""Cost metering.

A meter turns an executed operation into a priced record. It is an abstraction
because the day a real inference provider is configured, its costs replace the
mock's — but the accounting around them does not change.

**No inference provider is configured in this deployment.** The backend declares no
inference dependency and holds no credentials, so the only meter here is
:class:`MockCostMeter`, and everything it produces is labelled ``mock``. A simulated
charge is never presented as a provider invoice or as real money spent.

Charging happens once per billable operation. A communication and the model call
that produced it describe the same operation, so both may be *recorded* under one
``billable_operation_id``, but only one of them is charged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.models import CostCategory, MeterSource

#: Deterministic mock prices, per unit. Chosen to be obvious in a test rather than
#: to resemble any real provider's pricing.
MOCK_UNIT_PRICES: dict[CostCategory, Decimal] = {
    CostCategory.LLM_INPUT_TOKENS: Decimal("0.000001"),
    CostCategory.LLM_OUTPUT_TOKENS: Decimal("0.000002"),
    CostCategory.TOOL_CALL: Decimal("0.000500"),
    CostCategory.AGENT_MESSAGE: Decimal("0.000100"),
    CostCategory.OTHER: Decimal("0.000250"),
}


@dataclass(frozen=True)
class MeteredUsage:
    """One measured slice of a billable operation."""

    category: CostCategory
    units: int
    billable_operation_id: str
    #: Optional detail kept for investigation, never for authorization.
    note: str | None = None

    @property
    def chargeable(self) -> bool:
        """Whether this slice represents a cost rather than a description of one.

        A message is a communication about work; the tokens behind it are the cost.
        Recording both is useful, charging both would double-bill.
        """
        return self.category is not CostCategory.AGENT_MESSAGE


@dataclass(frozen=True)
class CostRecord:
    """What a meter produced, ready to be reconciled against a reservation."""

    billable_operation_id: str
    #: Where the figures came from. Always stated, never implied.
    source: MeterSource
    currency: str
    total: Decimal
    lines: tuple[MeteredUsage, ...] = field(default_factory=tuple)

    @property
    def operation_count(self) -> int:
        """How many billable operations this record covers. Always one.

        A record spans a single operation by construction, so this exists to make
        the double-charge question answerable rather than assumed.
        """
        return len({line.billable_operation_id for line in self.lines}) or 1


@runtime_checkable
class CostMeter(Protocol):
    """Prices an executed operation."""

    #: Written onto every cost record this meter produces.
    source: MeterSource

    def estimate_maximum(self, usage: list[MeteredUsage], *, currency: str) -> Decimal:
        """The worst-case cost, used to reserve *before* execution."""

    def measure(self, usage: list[MeteredUsage], *, currency: str) -> CostRecord:
        """The actual cost of what was executed."""


class MockCostMeter:
    """A deterministic meter for development and tests.

    Explicitly identified as ``mock``. It never contacts anything, never sleeps, and
    produces the same figure for the same usage every time.
    """

    source = MeterSource.MOCK

    def __init__(self, unit_prices: dict[CostCategory, Decimal] | None = None) -> None:
        self._prices = unit_prices or MOCK_UNIT_PRICES

    def price_of(self, usage: MeteredUsage) -> Decimal:
        """Cost of one usage slice, or zero for a non-chargeable one."""
        if not usage.chargeable:
            return Decimal("0")
        if usage.units < 0:
            raise ValueError("metered units must not be negative")
        return self._prices[usage.category] * usage.units

    def estimate_maximum(self, usage: list[MeteredUsage], *, currency: str) -> Decimal:
        """Worst case: every unit of every chargeable slice costs full price."""
        total = sum((self.price_of(item) for item in usage), Decimal("0"))
        return total.quantize(Decimal("0.000001"))

    def measure(self, usage: list[MeteredUsage], *, currency: str) -> CostRecord:
        total = sum((self.price_of(item) for item in usage), Decimal("0"))
        return CostRecord(
            billable_operation_id=_operation_id(usage),
            source=self.source,
            currency=currency,
            total=total.quantize(Decimal("0.000001")),
            lines=tuple(usage),
        )


def _operation_id(usage: list[MeteredUsage]) -> str:
    """Every slice of an operation shares one billable id."""
    ids = {item.billable_operation_id for item in usage}
    if len(ids) != 1:
        raise ValueError(
            "every metered slice must share one billable operation id; got "
            f"{len(ids)}"
        )
    return ids.pop()


def get_meter(name: str = "mock") -> CostMeter:
    """The configured meter.

    Only the mock exists. A provider meter would be registered here, keeping its own
    ``source`` so a provider charge is never labelled ``mock`` and vice versa.
    """
    if name != "mock":
        raise ValueError(
            f"no cost meter named '{name}' is configured; this deployment has no "
            "inference provider"
        )
    return MockCostMeter()


__all__ = [
    "CostMeter",
    "CostRecord",
    "MOCK_UNIT_PRICES",
    "MeteredUsage",
    "MockCostMeter",
    "get_meter",
]