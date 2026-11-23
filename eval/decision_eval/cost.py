"""Operational accounting kept separate from accuracy."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .statistics import percentile


class ResourceLedger:
    """Append-only accounting for inference and judge calls (no secrets)."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(
        self, *, case_id: str, role: str = "", phase: str = "inference",
        latency_ms: float = 0.0, prompt_tokens: int = 0, completion_tokens: int = 0,
        reasoning_tokens: int = 0, http_status: int | None = None,
        timeouts: int = 0, http_errors: int = 0, retries: int = 0, rate_limits: int = 0,
        cost_egp: str = "0", ram_mib: float | None = None, vram_mib: float | None = None,
        energy_j: float | None = None,
    ) -> None:
        self.events.append({
            "case_id": case_id, "role": role, "phase": phase,
            "latency_ms": float(latency_ms), "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens), "reasoning_tokens": int(reasoning_tokens),
            "http_status": http_status, "timeouts": int(timeouts), "http_errors": int(http_errors),
            "retries": int(retries), "rate_limits": int(rate_limits),
            "cost_egp": str(Decimal(cost_egp)), "ram_mib": ram_mib, "vram_mib": vram_mib,
            "energy_j": energy_j,
        })

    def summarize(self, *, correct_case_ids: set[str] | None = None,
                  accepted_case_ids: set[str] | None = None) -> dict[str, Any]:
        if not self.events:
            return {"events": 0}
        latencies = [event["latency_ms"] for event in self.events]
        cost = sum((Decimal(event["cost_egp"]) for event in self.events), Decimal(0))
        cases = len({event["case_id"] for event in self.events})
        result: dict[str, Any] = {
            "events": len(self.events),
            "cases": cases,
            "requests_per_case": round(len(self.events) / cases, 4),
            "latency_ms": {
                "p50": round(percentile(latencies, 0.5), 3),
                "p90": round(percentile(latencies, 0.9), 3),
                "p95": round(percentile(latencies, 0.95), 3),
            },
            "prompt_tokens": sum(event["prompt_tokens"] for event in self.events),
            "completion_tokens": sum(event["completion_tokens"] for event in self.events),
            "reasoning_tokens": sum(event["reasoning_tokens"] for event in self.events),
            "timeouts": sum(event["timeouts"] for event in self.events),
            "http_errors": sum(event["http_errors"] for event in self.events),
            "retries": sum(event["retries"] for event in self.events),
            "rate_limits": sum(event["rate_limits"] for event in self.events),
            "catalogue_equivalent_egp": str(cost),
            "actual_charge_observed": False,
            "note": "Actual invoice charges are not observable from local ledgers; catalogue equivalent only.",
        }
        for field, ids in (("cost_per_correct_case", correct_case_ids),
                           ("cost_per_accepted_assessment", accepted_case_ids)):
            if ids:
                result[field] = str((cost / Decimal(len(ids))).quantize(Decimal("0.000001")))
        for field in ("ram_mib", "vram_mib", "energy_j"):
            values = [event[field] for event in self.events if event[field] is not None]
            if values:
                result[f"peak_{field}"] = max(values)
        return result
