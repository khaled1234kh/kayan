"""Run the owner-approved synthetic SovereignEG diagnostic once."""
import argparse
import json
from pathlib import Path
import re
import time
from decimal import Decimal

import httpx

from eval import cloud_automatic_proof_v1 as base
from eval.cloud_extraction_v2 import score_cell
from eval.cloud_real_comparison_prep import LOCK, verified_inputs

URL = "https://backend.sovereigneg.com/v1/chat/completions"
MODEL = "SovereignEG/Qwen3.8-27B-FP8"
BUNDLE_SHA = "7701b717960ec8806ce7eaaea1d4417825fb748d009cd6cd2d042da8b7338e53"
MANIFEST_SHA = "c3713861ca304a9ed7c84c3629684865eba517f650860087d2c0d700d7b7c840"
PROBE = base.ROOT / ".build/sovereigneg-capability-probe-2026-11-21.json"
RUN_LOCK = base.ROOT / ".build/sovereigneg-diagnostic-authorized-2026-11-21.lock"
MAX_REQUEST_EGP = (92_000 * Decimal("8.41") + 512 * Decimal("67.29")) / 1_000_000


def load_secret(path):
    path = path.resolve(strict=True)
    if path.is_relative_to(base.ROOT.resolve()):
        raise ValueError("Credential must reside outside the checkout")
    text = path.read_text(encoding="utf-8-sig").strip()
    assignments = re.findall(
        r"""(?m)^\s*(?:export\s+)?SOVEREIGNEG_API_KEY\s*=\s*["']?(sk-[A-Za-z0-9_-]+)["']?\s*$""", text
    )
    if len(assignments) == 1:
        return assignments[0]
    if re.fullmatch(r"sk-[A-Za-z0-9_-]+", text):
        return text
    raise ValueError("Credential format not recognized")


def outgoing(draft, arm):
    return {
        "model": draft["model"], "messages": draft["messages"],
        "max_tokens": draft["max_output_tokens"], "temperature": draft["temperature"],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "extraction_v2" if arm == "D" else "direct_mapping",
            "strict": True, "schema": draft["schema"],
        }},
    }


def measure(case_name, arm, content):
    config = base.read(base.LOCK)["cases"][case_name]
    case, payloads, observations = base.fixture(case_name)
    manifest, authority = base.issue(case)

    def admit(raw):
        return base.evaluate_in_custody(raw, manifest, payloads, authority=authority)

    return score_cell("v2" if arm == "D" else "direct", content, observations,
                      config["hypotheses"], base.role_key(case), admit)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--bundle", type=Path, required=True)
    cli.add_argument("--credential", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--student-fallback-verified", action="store_true", required=True)
    args = cli.parse_args()
    if base.sha(args.bundle) != BUNDLE_SHA or base.sha(LOCK) != MANIFEST_SHA:
        raise ValueError("Frozen input mismatch")
    plan = verified_inputs()
    probe = base.read(PROBE)
    if (probe.get("attempted"), probe.get("http_status"), probe.get("returned_model"),
            probe.get("matched_empty_schema")) != (1, 200, MODEL, True):
        raise ValueError("Single capability probe did not clear preflight")
    bundle = base.read(args.bundle)
    cases = bundle["cases"]
    cells = [(name, arm, outgoing(cases[name]["cloud_drafts"][arm], arm))
             for name in plan["cases"] for arm in ("B", "C", "D")]
    if len(cells) != 12 or any(p["model"] != MODEL or p["max_tokens"] != 512 for _, _, p in cells):
        raise ValueError("Approved schedule mismatch")
    if (len(cells) + 1) * MAX_REQUEST_EGP > Decimal("20"):
        raise ValueError("Catalog reservation exceeds authorized budget")
    key = load_secret(args.credential)
    with RUN_LOCK.open("x", encoding="utf-8") as lock:
        lock.write(BUNDLE_SHA + "\n")
    args.output.mkdir(exist_ok=False)
    with (args.output / "requests.jsonl").open("x", encoding="utf-8", newline="\n") as ledger:
        def log(row):
            ledger.write(json.dumps(row, ensure_ascii=True).replace(key, "[redacted]") + "\n")
            ledger.flush()

        log({"event": "run", "bundle_sha256": BUNDLE_SHA, "manifest_sha256": MANIFEST_SHA,
             "reserved_egp_per_call_at_catalog_rates": str(MAX_REQUEST_EGP), "probe": probe})
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=90.0) as client:
            for i, (name, arm, body) in enumerate(cells, 1):
                log({"event": "attempt", "case": name, "arm": arm, "number": i, "request": body})
                started = time.monotonic()
                result = {"event": "result", "case": name, "arm": arm, "number": i}
                stop = False
                try:
                    response = client.post(URL, json=body, headers={"Authorization": f"Bearer {key}"})
                except httpx.HTTPError as exc:
                    result["error"] = type(exc).__name__
                    stop = True  # Billing and upstream status are unknown.
                else:
                    result["http_status"] = response.status_code
                    result["headers"] = {k: v for k, v in response.headers.items()
                                         if k == "x-request-id" or re.search(
                                             r"^x-(?:provider|upstream|ratelimit|plan|cost|billed|allowance)", k
                                         )}
                    result["wire"] = response.text
                    if response.is_success:
                        try:
                            parsed = response.json()
                            usage = parsed["usage"]
                            choice = parsed["choices"][0]
                            if parsed.get("model") != MODEL or usage["prompt_tokens"] > 92_000 or usage["completion_tokens"] > 512:
                                raise ValueError("Model identity or usage fell outside the approved reservation")
                            result["usage"] = usage
                            result["finish"] = choice.get("finish_reason")
                            if result["finish"] == "stop" and isinstance(choice["message"].get("content"), str):
                                result["metrics"] = measure(name, arm, choice["message"]["content"])
                        except (ValueError, KeyError, TypeError, IndexError) as exc:
                            result["error"] = str(exc)
                            stop = True
                    elif response.status_code in (401, 402, 403, 429) or 300 <= response.status_code < 400:
                        stop = True
                    elif response.status_code == 400 and arm == "D":
                        stop = True  # Exact structured arm compatibility is required.
                result["wall_seconds"] = round(time.monotonic() - started, 3)
                log(result)
                print(name, arm, result.get("http_status", result.get("error")), flush=True)
                if stop:
                    log({"event": "stopped", "after_attempt": i})
                    break
                if i < len(cells):
                    time.sleep(max(0, 3.2 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
