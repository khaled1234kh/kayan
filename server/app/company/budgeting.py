"""Budget arithmetic.

Kept pure and separate from the service so the rules that decide whether money may
be spent can be read, reviewed and tested without a database.

The hard-ceiling invariant for a scope (a company period, an employee month, or one
employee's work on one task) is::

    available = limit - actual_spend - outstanding_reservations

An operation may only begin if its **maximum** cost fits that. The maximum, not the
expected cost, is what gets committed: a billable operation may cost more than
expected, and the ceiling has to hold for the worst case it was allowed to reach.

Counting rules, which are the part most easily got wrong:

* **Actual spend** comes from ledger entries whose category counts as spend
  (``actual_cost_charged`` and ``refund_or_adjustment``, the latter signed).
* **Outstanding reservations** come from the reservation table, not the ledger.
  A reservation entry is a *commitment*, so counting it as spend too would deduct
  the same money twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models import BudgetLedgerCategory

ZERO = Decimal("0")

#: Categories that contribute to actual committed spend.
SPEND_CATEGORIES: frozenset[BudgetLedgerCategory] = frozenset(
    category for category in BudgetLedgerCategory if category.counts_as_spend
)


@dataclass(frozen=True)
class ScopeTotals:
    """Committed and outstanding money for one scope."""

    limit: Decimal
    spend: Decimal
    outstanding: Decimal

    @property
    def available(self) -> Decimal:
        """What may still be committed in this scope."""
        return self.limit - self.spend - self.outstanding

    @property
    def committed(self) -> Decimal:
        """Everything already spoken for, whether spent or merely reserved."""
        return self.spend + self.outstanding


@dataclass(frozen=True)
class Denied:
    """A reservation that must not proceed, and why.

    A denial is a *result*, not an exception: it is recorded and returned, because a
    refusal that rolls back its own evidence is not an auditable refusal.
    """

    scope: str
    reason: str
    requested: Decimal
    available: Decimal
    limit: Decimal


def available(
    *,
    limit: Decimal,
    spend: Decimal,
    outstanding: Decimal,
) -> Decimal:
    """The amount still committable in a scope."""
    return ScopeTotals(limit=limit, spend=spend, outstanding=outstanding).available


def spend_from_ledger(amounts: list[Decimal], categories: list[BudgetLedgerCategory]) -> Decimal:
    """Sum only the entries that represent real cost."""
    return sum(
        (
            amount
            for amount, category in zip(amounts, categories, strict=True)
            if category in SPEND_CATEGORIES
        ),
        ZERO,
    )


def check_request(
    *,
    scope: str,
    limit: Decimal,
    spend: Decimal,
    outstanding: Decimal,
    amount: Decimal,
) -> Denied | None:
    """Return a denial when ``amount`` does not fit, otherwise ``None``.

    The three applicable levels (company period, employee month, employee task) are
    each checked independently and all of them must fit: a request that fits the
    company budget but not the employee's allocation is still refused.
    """
    totals = ScopeTotals(limit=limit, spend=spend, outstanding=outstanding)
    if amount > totals.available:
        reason = (
            f"insufficient funds in {scope}: requested {amount}, "
            f"available {totals.available} of limit {limit} "
            f"(spent {spend}, reserved {outstanding})"
        )
        return Denied(
            scope=scope,
            reason=reason,
            requested=amount,
            available=totals.available,
            limit=limit,
        )
    return None


__all__ = [
    "Denied",
    "SPEND_CATEGORIES",
    "ScopeTotals",
    "available",
    "check_request",
    "spend_from_ledger",
    "ZERO",
]