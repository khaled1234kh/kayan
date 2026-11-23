"""Canonical inference protocol and bounded pre-flight budgeting.

This module records the *exact* configuration that any future experiment must
use, including settings that were remapped, clamped or ignored by a provider.
It performs no inference and makes no network request.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any

PROTOCOL_VERSION = "kayan-inference-protocol/1"
CATALOGUE_INPUT_EGP_PER_M = Decimal("8.41")
CATALOGUE_OUTPUT_EGP_PER_M = Decimal("67.29")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class InferenceConfig:
    """One frozen inference arm. All non-scalar fields are hashed in ``freeze``."""

    config_id: str
    model_id: str
    model_revision: str
    provider: str
    engine: str
    quantization: str
    system_messages: tuple[str, ...]
    user_message: str
    schema: dict[str, Any]
    dataset_revision: str
    scorer_version: str
    temperature: float = 0.0
    seed: int | None = 42
    max_tokens: int = 384
    reasoning_mode: str = "off"
    reasoning_budget: int | None = None
    stop: tuple[str, ...] = ()
    retrieval: dict[str, Any] = field(default_factory=lambda: {
        "enabled": False, "index_revision": None, "k": 0, "query_mode": "none",
    })
    timeout_s: float = 60.0
    max_attempts: int = 1
    retry_policy: str = "no transport retry; one structural repair on contract error only"
    remappings: dict[str, str] = field(default_factory=dict)
    clamped: dict[str, str] = field(default_factory=dict)
    ignored: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        if self.temperature != 0:
            raise ValueError("Canonical protocol requires temperature 0")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not self.system_messages or not self.user_message:
            raise ValueError("Prompt bytes must be non-empty")

    def freeze(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["protocol_version"] = PROTOCOL_VERSION
        payload["prompt_bytes_sha256"] = sha256_bytes(
            canonical_json({"system": self.system_messages, "user": self.user_message}).encode("utf-8")
        )
        payload["schema_sha256"] = sha256_bytes(canonical_json(self.schema).encode("utf-8"))
        payload["config_sha256"] = sha256_bytes(canonical_json(payload).encode("utf-8"))
        return payload

    def request_preview(self) -> dict[str, Any]:
        """Return the provider-neutral request without sending it."""
        return {
            "model": self.model_id,
            "messages": [{"role": "system", "content": text} for text in self.system_messages]
            + [{"role": "user", "content": self.user_message}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "schema_sha256": sha256_bytes(canonical_json(self.schema).encode("utf-8")),
            "dataset_revision": self.dataset_revision,
            "scorer_version": self.scorer_version,
        }


def preflight_budget(
    config: InferenceConfig,
    *,
    cases: int,
    runs: int,
    prompt_tokens_per_case: int,
    output_tokens_per_case: int,
    reasoning_tokens_per_case: int = 0,
    input_egp_per_m: Decimal = CATALOGUE_INPUT_EGP_PER_M,
    output_egp_per_m: Decimal = CATALOGUE_OUTPUT_EGP_PER_M,
) -> dict[str, Any]:
    """Worst-case request, token and catalogue-equivalent cost envelope.

    Structural-repair attempts are included at the configured ``max_attempts``.
    This is a budget gate only: it must be presented for bounded authorization
    before any real provider call, and repeats are never counted as new cases.
    """
    if cases < 1 or runs < 1:
        raise ValueError("cases and runs must be positive")
    attempts = cases * runs * config.max_attempts
    prompt_tokens = attempts * prompt_tokens_per_case
    output_tokens = attempts * (output_tokens_per_case + reasoning_tokens_per_case)
    cost = (Decimal(prompt_tokens) * input_egp_per_m
            + Decimal(output_tokens) * output_egp_per_m) / Decimal(1_000_000)
    return {
        "config_id": config.config_id,
        "config_sha256": config.freeze()["config_sha256"],
        "cases": cases,
        "runs": runs,
        "attempts_per_case_run": config.max_attempts,
        "worst_case_requests": attempts,
        "worst_case_prompt_tokens": prompt_tokens,
        "worst_case_output_tokens": output_tokens,
        "catalogue_equivalent_egp": str(cost.quantize(Decimal("0.0001"))),
        "authorization_required": True,
        "note": "Estimate uses catalogue rates, not a quote. Confirm allowance and overage policy before approval.",
    }
