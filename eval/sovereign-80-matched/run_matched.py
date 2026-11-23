"""Matched 80-case cloud arm. Mock by default; live only with explicit authorization.

This runner writes frozen-compatible cases.jsonl rows so the untouched scorer and
paired bootstrap in analyze_models.py can re-check every response. Credentials are
read from a file outside the checkout and never logged.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx

import frozen_protocol as fp


INTERESTING_HEADERS = re.compile(
    r"^(?:x-request-id|x-dropped-params|x-mapped-params|x-output-clamped|x-plan-output-cap"
    r"|x-(?:provider|upstream|ratelimit|plan|cost|billed|allowance))", re.I
)
WORKTREE = Path(__file__).resolve().parents[2]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def load_secret(path: Path) -> str:
    path = path.resolve(strict=True)
    if path.is_relative_to(WORKTREE.resolve()):
        raise ValueError("Credential must reside outside the checkout")
    text = path.read_text(encoding="utf-8-sig").strip()
    assignments = re.findall(
        r"""(?m)^\s*(?:export\s+)?SOVEREIGNEG_API_KEY\s*=\s*["']?(sk-[A-Za-z0-9_-]+)["']?\s*$""",
        text,
    )
    if len(assignments) == 1:
        return assignments[0]
    if re.fullmatch(r"sk-[A-Za-z0-9_-]+", text):
        return text
    raise ValueError("Credential format not recognized")


def mock_client(responses: dict) -> httpx.Client:
    calls: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Case routing for mock validation only, via an internal header that is
        # never part of a live provider request.
        hint = request.headers.get("X-Mock-Case-Hint")
        cell = responses.get(hint) if hint else None
        if isinstance(cell, dict) and "sequence" in cell:
            sequence = cell["sequence"]
            index = calls.get(hint or "", 0)
            calls[hint or ""] = index + 1
            cell = sequence[min(index, len(sequence) - 1)]
        if cell is None:
            cell = responses.get("default", {"status": 200, "content": "{}", "usage": {
                "prompt_tokens": 1, "completion_tokens": 1}})
        return httpx.Response(cell.get("status", 200), json={
            "id": cell.get("id", "mock-req"),
            "model": cell.get("model", fp.MODEL),
            "choices": [{
                "message": {"content": cell.get("content", "{}"),
                            "reasoning_content": cell.get("reasoning", "")},
                "finish_reason": cell.get("finish_reason", "stop"),
            }],
            "usage": {
                "prompt_tokens": cell.get("usage", {}).get("prompt_tokens", 1),
                "completion_tokens": cell.get("usage", {}).get("completion_tokens", 1),
                "completion_tokens_details": {"reasoning_tokens": cell.get("reasoning_tokens", 0)},
            },
        }, headers=cell.get("headers", {}))
    return httpx.Client(transport=httpx.MockTransport(handler), trust_env=False,
                        follow_redirects=False, timeout=180.0)


def send(client: httpx.Client, payload: dict, key: str | None, hint: str | None, log) -> dict:
    outgoing = dict(payload)
    started = time.monotonic()
    result = {"elapsed_ms": None, "error": None, "ollama": None, "content": ""}
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    if hint:
        headers["X-Mock-Case-Hint"] = hint
    try:
        response = client.post(fp.ENDPOINT, json=outgoing, headers=headers)
    except httpx.HTTPError as exc:
        result["error"] = f"{type(exc).__name__}: transport outcome unknown"
        result["elapsed_ms"] = round(1000 * (time.monotonic() - started), 3)
        log({"event": "transport_error", "error": result["error"]})
        return result
    result["elapsed_ms"] = round(1000 * (time.monotonic() - started), 3)
    picked = {k: v for k, v in response.headers.items() if INTERESTING_HEADERS.match(k)}
    log({"event": "http", "status": response.status_code, "headers": picked})
    if not response.is_success:
        result["error"] = f"HTTP {response.status_code}"
        result["ollama"] = {"provider": "sovereigneg", "http_status": response.status_code,
                            "headers": picked}
        return result
    try:
        data = response.json()
        usage = data["usage"]
        choice = data["choices"][0]
        message = choice["message"]
        content = str(message.get("content") or "")
        detail = usage.get("completion_tokens_details") or {}
        result["content"] = content
        result["ollama"] = {
            "provider": "sovereigneg",
            "served_model": data.get("model"),
            "request_id": data.get("id"),
            "http_status": response.status_code,
            "headers": picked,
            "finish_reason": choice.get("finish_reason"),
            "reasoning_content": str(message.get("reasoning_content") or ""),
            "reasoning_tokens": int(detail.get("reasoning_tokens") or 0),
            "prompt_eval_count": int(usage.get("prompt_tokens") or 0),
            "eval_count": int(usage.get("completion_tokens") or 0),
        }
        if data.get("model") != fp.MODEL:
            raise ValueError("Served model differs from authorized model")
        if any(k in picked for k in ("x-dropped-params", "x-mapped-params", "x-output-clamped")):
            raise ValueError("Provider reported a parameter or output adjustment")
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        result["error"] = f"envelope: {exc}"
    return result


def evaluate(entry: dict, raw: dict) -> dict:
    return fp.model_bench.evaluate(entry["case"], entry["schema"], raw, fp.role_cases.score)


def run(args) -> None:
    manifest = fp.load_manifest()
    entries = fp.heldout_entries(manifest)
    if args.mode == "live" and not args.authorized:
        raise ValueError("Live mode requires --authorized after explicit owner approval")
    key = load_secret(Path(args.credential)) if args.mode == "live" else None
    if args.mode == "mock":
        responses = json.loads(Path(args.responses).read_text(encoding="utf-8"))["responses"]
        client = mock_client(responses)
    else:
        client = httpx.Client(trust_env=False, follow_redirects=False, timeout=180.0,
                              limits=httpx.Limits(max_connections=1, max_keepalive_connections=0))

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    config = {
        "started_utc": now(),
        "mode": args.mode,
        "provider": "sovereigneg" if args.mode == "live" else "mock-transport",
        "endpoint": fp.ENDPOINT if args.mode == "live" else "httpx.MockTransport",
        "model": fp.MODEL,
        "manifest_sha256": fp.EXPECTED_MANIFEST_SHA,
        "options": manifest["options"],
        "split": "heldout",
        "order": [entry["case"]["id"] for entry in entries],
        "parameter_mapping": fp.parameter_mapping(),
        "limits": {"primary": fp.MAX_PRIMARY, "structural_retries": fp.MAX_RETRIES,
                   "total_requests": fp.MAX_REQUESTS,
                   "spend_ceiling_egp": str(args.spend_ceiling_egp)},
        "pricing_egp_per_million": {"input": str(fp.INPUT_EGP_PER_M),
                                    "output": str(fp.OUTPUT_EGP_PER_M)},
        "scope": "80 frozen synthetic held-out role cases; no calibration, no real data",
    }
    write_json(output / "run.json", config)

    requests_made = 0
    total_egp = Decimal("0")
    stopped_reason = None
    log_path = output / "requests.jsonl"
    with log_path.open("x", encoding="utf-8", newline="\n") as ledger, \
            (output / "cases.jsonl").open("x", encoding="utf-8", newline="\n") as cases_log:
        def log(row: dict) -> None:
            text = json.dumps(row, ensure_ascii=True, sort_keys=True)
            if key:
                text = text.replace(key, "[redacted]")
            ledger.write(text + "\n")
            ledger.flush()

        log({"event": "run", **config, "credential": "external path, contents never recorded"})
        try:
            for entry in entries:
                if requests_made >= fp.MAX_REQUESTS:
                    stopped_reason = "request cap"
                    break
                if total_egp > Decimal(args.spend_ceiling_egp):
                    stopped_reason = "spend ceiling"
                    break
                case = entry["case"]
                attempts = []
                payload, mapping = fp.build_request(entry)
                hint = case["id"] if args.mode == "mock" else None
                log({"event": "request", "number": requests_made + 1, "case_id": case["id"],
                     "role": case["role"], "retry": False, "body": payload,
                     "mapping": mapping})
                raw = send(client, payload, key, hint, log)
                requests_made += 1
                first = evaluate(entry, raw)
                attempts.append(first)
                log({"event": "response", "number": requests_made, "case_id": case["id"],
                     "raw": raw, "score": first["score"],
                     "contract_errors": first["contract_errors"]})
                usage = raw.get("ollama") or {}
                total_egp += fp.estimate_egp(usage.get("prompt_eval_count", 0),
                                             usage.get("eval_count", 0))
                if first["contract_errors"] and not first["error"] and requests_made < fp.MAX_REQUESTS:
                    correction_payload, _ = fp.build_request(entry, first["contract_errors"][:8])
                    log({"event": "request", "number": requests_made + 1, "case_id": case["id"],
                         "role": case["role"], "retry": True, "body": correction_payload,
                         "errors": first["contract_errors"][:8]})
                    raw2 = send(client, correction_payload, key, hint, log)
                    requests_made += 1
                    second = evaluate(entry, raw2)
                    attempts.append(second)
                    log({"event": "response", "number": requests_made, "case_id": case["id"],
                         "retry": True, "raw": raw2, "score": second["score"],
                         "contract_errors": second["contract_errors"]})
                    usage2 = raw2.get("ollama") or {}
                    total_egp += fp.estimate_egp(usage2.get("prompt_eval_count", 0),
                                                 usage2.get("eval_count", 0))
                row = {"case_id": case["id"], "role": case["role"], "split": case["split"],
                       "family": case.get("family", case["id"]),
                       "model": fp.MODEL if args.mode == "live" else "mock-transport",
                       "model_digest": "provider-managed", "attempts": attempts}
                cases_log.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                cases_log.flush()
                fatal = False
                for attempt in attempts:
                    status = (attempt.get("ollama") or {}).get("http_status")
                    if status in (401, 402, 403, 429) or (status and 300 <= status < 400):
                        stopped_reason = f"HTTP {status}: authorization, spend, or routing"
                        fatal = True
                if fatal:
                    break
        finally:
            client.close()
        completed = sum(1 for line in (output / "cases.jsonl").open(encoding="utf-8") if line.strip())
        write_json(output / "finished.json", {
            "finished_utc": now(),
            "completed": completed,
            "requests_made": requests_made,
            "catalogue_equivalent_egp": str(total_egp),
            "stopped_reason": stopped_reason,
            "measurement_status": "MOCK_VALIDATION_NOT_A_MEASUREMENT" if args.mode == "mock"
                                  else "MEASURED",
        })
        log({"event": "finished", "requests_made": requests_made,
             "catalogue_equivalent_egp": str(total_egp),
             "stopped_reason": stopped_reason})
    print(f"{args.mode}: cases={completed} requests={requests_made} egp={total_egp} "
          f"stopped={stopped_reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    parser.add_argument("--output", required=True)
    parser.add_argument("--responses", help="Mock response fixture (mock mode)")
    parser.add_argument("--credential", help="External secret file (live mode only)")
    parser.add_argument("--authorized", action="store_true",
                        help="Set only after explicit bounded owner authorization")
    parser.add_argument("--spend-ceiling-egp", type=Decimal, default=Decimal("10"))
    args = parser.parse_args()
    if args.mode == "mock" and not args.responses:
        parser.error("mock mode requires --responses")
    if args.mode == "live" and not args.credential:
        parser.error("live mode requires --credential")
    run(args)


if __name__ == "__main__":
    main()
