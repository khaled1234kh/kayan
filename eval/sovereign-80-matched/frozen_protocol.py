"""Read-only access to the verified frozen 80-case role benchmark.

No production code is imported or modified. The reference harness lives in the
isolated worktree under eval/reference/role-benchmark and is loaded verbatim.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import random
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "reference" / "role-benchmark"
MANIFEST = REFERENCE / "data" / "roles_frozen.json"
EXPECTED_MANIFEST_SHA = "09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0"

ENDPOINT = "https://backend.sovereigneg.com/v1/chat/completions"
MODEL = "SovereignEG/Qwen3.8-27B-FP8"

# Frozen generation contract (from roles_frozen.json "options").
MAX_OUTPUT_TOKENS = 384            # num_predict -> max_tokens
TEMPERATURE = 0                    # unchanged
SEED = 42                          # no documented provider equivalent; not sent
NUM_CTX = 4096                     # no documented provider equivalent; not sent

# Request budget. 80 primary + at most one structural-repair retry per case,
# exactly as in the frozen runner. Transport failures are never retried.
MAX_PRIMARY = 80
MAX_RETRIES = 80
MAX_REQUESTS = MAX_PRIMARY + MAX_RETRIES

# Catalogue rates documented in docs/CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md.
INPUT_EGP_PER_M = Decimal("8.41")
OUTPUT_EGP_PER_M = Decimal("67.29")

if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

role_cases = importlib.import_module("role_cases")
model_bench = importlib.import_module("model_bench")
analyze_models = importlib.import_module("analyze_models")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest() -> dict:
    if sha256(MANIFEST) != EXPECTED_MANIFEST_SHA:
        raise ValueError("Frozen manifest hash changed; stop")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data["source_sha256"] != sha256(REFERENCE / "role_cases.py"):
        raise ValueError("Frozen scorer changed; stop")
    if data["runner_sha256"] != sha256(REFERENCE / "model_bench.py"):
        raise ValueError("Frozen runner changed; stop")
    if data["options"] != {"temperature": 0, "num_ctx": 4096, "num_predict": 384, "seed": 42}:
        raise ValueError("Frozen generation options changed; stop")
    return data


def heldout_entries(manifest: dict) -> list[dict]:
    entries = [entry for entry in manifest["cases"] if entry["case"]["split"] == "heldout"]
    if len(entries) != MAX_PRIMARY:
        raise ValueError(f"Expected 80 held-out cases, found {len(entries)}")
    random.Random(20261112).shuffle(entries)  # identical to frozen model_bench.run
    return entries


def parameter_mapping() -> dict:
    """Explicit record of every frozen field and its cloud treatment."""
    return {
        "model": {"frozen": "<case-checkpoint>", "sent": MODEL, "status": "substituted by design: cloud arm"},
        "messages.system": {"frozen": "SYSTEM constant", "sent": "identical text", "status": "unchanged"},
        "messages.user": {"frozen": "json.dumps({role,case}, sort_keys=True)", "sent": "identical serialization", "status": "unchanged"},
        "format": {"frozen": "Ollama JSON schema", "sent": "response_format.json_schema.strict", "status": "remapped"},
        "temperature": {"frozen": 0, "sent": TEMPERATURE, "status": "unchanged"},
        "seed": {"frozen": SEED, "sent": None, "status": "ignored: no documented provider equivalent"},
        "num_ctx": {"frozen": NUM_CTX, "sent": None, "status": "ignored: provider-specific context"},
        "num_predict": {"frozen": MAX_OUTPUT_TOKENS, "sent": "max_tokens", "status": "remapped"},
        "think": {"frozen": False, "sent": "reasoning_effort=none", "status": "remapped"},
        "stream": {"frozen": False, "sent": False, "status": "unchanged"},
        "keep_alive": {"frozen": "3m", "sent": None, "status": "ignored: connection reuse is provider-managed"},
        "network_retry": {"frozen": "none", "sent": "none", "status": "unchanged"},
        "structural_retry": {"frozen": "at most one, contract errors only", "sent": "same", "status": "unchanged"},
    }


def build_request(entry: dict, correction: list[str] | None = None) -> tuple[dict, dict]:
    case, schema = entry["case"], entry["schema"]
    content = json.dumps({"role": case["role"], "case": case["input"]},
                         ensure_ascii=False, sort_keys=True)
    messages = [
        {"role": "system", "content": model_bench.SYSTEM},
        {"role": "user", "content": content},
    ]
    if correction:
        messages.append({"role": "user", "content": (
            "The first response was rejected by the output contract. Correct these issues: "
            + "; ".join(correction) + ". Return the full JSON object."
        )})
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "reasoning_effort": "none",
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "kayan_role_contract",
                "strict": True,
                "schema": schema,
            },
        },
    }
    return payload, parameter_mapping()


def estimate_egp(prompt_tokens: int, completion_tokens: int) -> Decimal:
    return (Decimal(prompt_tokens) * INPUT_EGP_PER_M
            + Decimal(completion_tokens) * OUTPUT_EGP_PER_M) / Decimal(1_000_000)
