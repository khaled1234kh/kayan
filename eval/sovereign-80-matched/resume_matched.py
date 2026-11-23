"""Resume the same authorized 80-case schedule with provider-compliant pacing.

No frozen input, prompt, schema, model, scorer or retry rule changes. Only the
interval between request starts and the cumulative accounting are added.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from decimal import Decimal
from pathlib import Path

import httpx

import frozen_protocol as fp
from run_matched import evaluate, load_secret, now, send, write_json


INTERVAL_S = 4.0  # 15 starts/min, below the documented 20/min provider limit


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(args) -> None:
    manifest = fp.load_manifest()
    entries = fp.heldout_entries(manifest)
    previous = Path(args.resume)
    prior_rows = read_jsonl(previous / "cases.jsonl")
    prior_ledger = read_jsonl(previous / "requests.jsonl")
    prior_finished = json.loads((previous / "finished.json").read_text(encoding="utf-8"))
    if prior_finished["measurement_status"] != "MEASURED":
        raise ValueError("Refusing to resume a mock or incomplete-status run")
    # The final partial request was rejected with 429 and is re-sent, not scored.
    while prior_rows and (prior_rows[-1]["attempts"][-1].get("error") or "").startswith("HTTP 429"):
        prior_rows.pop()
    done_ids = [row["case_id"] for row in prior_rows]
    expected_ids = [entry["case"]["id"] for entry in entries]
    if done_ids != expected_ids[:len(done_ids)]:
        raise ValueError("Partial run does not match the frozen order")
    start_index = len(done_ids)
    remaining = entries[start_index:]

    key = load_secret(Path(args.credential))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy(previous / "run.json", output / "run_prior.json")

    requests_made = int(prior_finished["requests_made"])
    total_egp = Decimal(prior_finished["catalogue_equivalent_egp"])
    stopped = None
    last_start = [0.0]
    log_path = output / "requests.jsonl"
    with log_path.open("x", encoding="utf-8", newline="\n") as ledger, \
            (output / "cases.jsonl").open("x", encoding="utf-8", newline="\n") as cases_log:
        def log(row: dict) -> None:
            text = json.dumps(row, ensure_ascii=True, sort_keys=True)
            if key in text:
                text = text.replace(key, "[redacted]")
            ledger.write(text + "\n")
            ledger.flush()

        for event in prior_ledger:
            text = json.dumps(event, ensure_ascii=True, sort_keys=True)
            if key in text:
                text = text.replace(key, "[redacted]")
            ledger.write(text + "\n")
        for row in prior_rows:
            cases_log.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        cases_log.flush()
        log({"event": "resume", "from_case_index": start_index,
             "reason": prior_finished["stopped_reason"],
             "pacing_interval_s": INTERVAL_S,
             "prior_requests": requests_made,
             "prior_catalogue_egp": str(total_egp),
             "authorized_total_request_cap": fp.MAX_REQUESTS,
             "authorized_spend_ceiling_egp": str(args.spend_ceiling_egp)})

        client = httpx.Client(trust_env=False, follow_redirects=False, timeout=180.0,
                              limits=httpx.Limits(max_connections=1, max_keepalive_connections=0))
        try:
            for entry in remaining:
                if requests_made >= fp.MAX_REQUESTS:
                    stopped = "request cap"
                    break
                if total_egp > Decimal(args.spend_ceiling_egp):
                    stopped = "spend ceiling"
                    break
                case = entry["case"]
                attempts = []
                payload, mapping = fp.build_request(entry)
                log({"event": "request", "number": requests_made + 1, "case_id": case["id"],
                     "role": case["role"], "retry": False, "body": payload,
                     "mapping": mapping})
                wait = INTERVAL_S - (time.monotonic() - last_start[0])
                if wait > 0:
                    time.sleep(wait)
                last_start[0] = time.monotonic()
                raw = send(client, payload, key, None, log)
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
                    correction, _ = fp.build_request(entry, first["contract_errors"][:8])
                    log({"event": "request", "number": requests_made + 1, "case_id": case["id"],
                         "role": case["role"], "retry": True, "body": correction,
                         "errors": first["contract_errors"][:8]})
                    wait = INTERVAL_S - (time.monotonic() - last_start[0])
                    if wait > 0:
                        time.sleep(wait)
                    last_start[0] = time.monotonic()
                    raw2 = send(client, correction, key, None, log)
                    requests_made += 1
                    second = evaluate(entry, raw2)
                    attempts.append(second)
                    log({"event": "response", "number": requests_made, "case_id": case["id"],
                         "retry": True, "raw": raw2, "score": second["score"],
                         "contract_errors": second["contract_errors"]})
                    usage2 = raw2.get("ollama") or {}
                    total_egp += fp.estimate_egp(usage2.get("prompt_eval_count", 0),
                                                 usage2.get("eval_count", 0))
                cases_log.write(json.dumps({
                    "case_id": case["id"], "role": case["role"], "split": case["split"],
                    "family": case.get("family", case["id"]), "model": fp.MODEL,
                    "model_digest": "provider-managed", "attempts": attempts,
                }, ensure_ascii=False, sort_keys=True) + "\n")
                cases_log.flush()
                for attempt in attempts:
                    status = (attempt.get("ollama") or {}).get("http_status")
                    if status in (401, 402, 403, 429) or (status and 300 <= status < 400):
                        stopped = f"HTTP {status}: authorization, spend, or routing"
                        break
                if stopped:
                    break
        finally:
            client.close()
        completed = sum(1 for line in (output / "cases.jsonl").open(encoding="utf-8") if line.strip())
        write_json(output / "finished.json", {
            "finished_utc": now(), "completed": completed,
            "requests_made": requests_made,
            "catalogue_equivalent_egp": str(total_egp),
            "stopped_reason": stopped,
            "measurement_status": "MEASURED",
            "resumed_from": str(previous),
            "pacing_interval_s": INTERVAL_S,
        })
        log({"event": "finished", "requests_made": requests_made,
             "catalogue_equivalent_egp": str(total_egp), "stopped_reason": stopped})
    print(f"resumed: cases={completed} requests={requests_made} egp={total_egp} stopped={stopped}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--credential", required=True)
    parser.add_argument("--spend-ceiling-egp", type=Decimal, default=Decimal("10"))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
