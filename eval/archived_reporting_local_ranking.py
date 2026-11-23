"""Bounded loopback inference against a frozen, synthetic Reporting ranking set."""

import argparse
import json
import os
from hashlib import file_digest, sha256
from pathlib import Path
from time import perf_counter

import httpx

from eval.archived_reporting_projection import archive
from eval.archived_reporting_selection import selection_metrics
from eval.attack_evidence_guard_v3 import MECHANICS
from eval.fixtures.ai.attack_fact_registry_v1.demo import SCOPE, _assert, _event, _fixture, _record
from pentagi.agents.archived_reporting import compose, request_for, review_archive_document


FIXTURES = Path(__file__).with_name("fixtures") / "ai"
SPEC = FIXTURES / "archived_reporting_local_ranking_v1.json"
LOCK = FIXTURES / "archived_reporting_local_ranking_v1.lock.json"
LOOPBACK = "http://127.0.0.1:11534"
TIMINGS = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")
COUNTS = ("prompt_eval_count", "eval_count")


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def prepare_case(case, runtime):
    fixture, records = _fixture(case["id"])
    for number, event in enumerate(case["events"], 1):
        event_id = f"event-{number}"
        scope = {**SCOPE, "session": f"ranking-session-{number}"}
        _event(fixture, event_id, scope, "2026-11-20T09:10:00Z")
        mechanic = MECHANICS[event["technique"]]
        authorization = "authorized" if event.get("authorized", False) else "unauthorized"
        actor = "benign" if authorization == "authorized" else "adversary"
        facts = (
            ("mechanic", mechanic, event["action"]),
            ("actor", actor, f"Independent attribution review assigned {event_id} to the {actor}."),
            ("outcome", "completed", event["outcome"]),
            ("authorization", authorization, f"The signed scope review classified {event_id} as {authorization}."),
        )
        for index, (role, value, text) in enumerate(facts, 1):
            record = f"{event_id}-{role}"
            _record(fixture, records, record, text.encode(), f"{role}-ledger", f"E{number}.{index}")
            _assert(fixture, event_id, scope, role, value, record,
                    action=mechanic if role == "authorization" else None)
    raw, *_ = archive(fixture, records)
    review = review_archive_document(json.loads(raw), sha256(raw).hexdigest())
    prepared = request_for(review)
    if prepared is None:
        return review, None
    messages, fmt, _ = prepared
    return review, {
        "model": runtime["model"], "messages": [message.as_dict() for message in messages],
        "format": fmt["json_schema"]["schema"], "stream": False,
        "keep_alive": runtime["keep_alive"], "options": runtime["options"],
    }


def prepare(spec_path=SPEC):
    raw = spec_path.read_bytes()
    spec = json.loads(raw)
    cases = [prepare_case(case, spec["runtime"]) for case in spec["cases"]]
    plan = {
        "protocol": spec["protocol"], "fixture_sha256": sha256(raw).hexdigest(),
        "cases": [{"id": case["id"], "archive_sha256": report["source_sha256"],
                   "request_sha256": sha256(canonical(payload)).hexdigest() if payload else None}
                  for case, (report, payload) in zip(spec["cases"], cases, strict=True)],
    }
    return spec, cases, plan


def verified_installation(root, runtime):
    manifest = root / "manifests/registry.ollama.ai/library/qwen2.5/7b"
    raw = manifest.read_bytes()
    if sha256(raw).hexdigest() != runtime["installation_manifest_sha256"]:
        raise ValueError("Local Ollama manifest digest mismatch")
    entries = json.loads(raw)
    blobs = [entries["config"], *entries["layers"]]
    for blob in blobs:
        algorithm, digest = blob["digest"].split(":", 1)
        path = root / "blobs" / f"{algorithm}-{digest}"
        if path.stat().st_size != blob["size"]:
            raise ValueError("Local Ollama blob size mismatch")
        with path.open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("Local Ollama blob digest mismatch")
    return len(blobs)


def preflight(client, runtime):
    version = client.get("/api/version").raise_for_status().json()["version"]
    models = client.get("/api/tags").raise_for_status().json()["models"]
    if version != runtime["version"]:
        raise ValueError("Local Ollama version mismatch")
    matches = [model for model in models if model["name"] == runtime["model"]]
    if (len(matches) != 1 or matches[0]["digest"] != runtime["digest"]
            or matches[0]["details"]["quantization_level"] != runtime["quantization"]):
        raise ValueError("Local Ollama model identity mismatch")


def selection_from_reply(review, raw, runtime):
    reply = json.loads(raw)
    message = reply["message"]
    if (reply.get("model") != runtime["model"] or reply.get("done") is not True
            or reply.get("done_reason") != "stop" or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)):
        raise ValueError("Incomplete or mismatched local response")
    return compose(review, message["content"]), {key: reply.get(key) for key in (*TIMINGS, *COUNTS)}


def evaluate_case(client, case, review, payload, runtime):
    local = compose(review)
    row = {"id": case["id"], "local": selection_metrics(local, case), "attempts": 0,
           "status": "blocked", "raw_reply": None, "failure": None}
    result = local
    row["selected"] = None
    if payload is not None:
        row["attempts"] = 1
        start = perf_counter()
        try:
            reply = client.post("/api/chat", content=canonical(payload), headers={"Content-Type": "application/json"})
            row["http_status"] = reply.status_code
            row["raw_reply"] = reply.text
            reply.raise_for_status()
            result, row["usage"] = selection_from_reply(review, reply.text, runtime)
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
            row["failure"] = type(error).__name__
            row["status"] = "fallback"
        else:
            row["status"] = "selected"
            row["selected"] = selection_metrics(result, case)
        row["elapsed_s"] = round(perf_counter() - start, 4)
    row["findings_unchanged"] = all(result[field] == review[field] for field in ("findings", "withheld"))
    return row


def run(output, startup_log, spec, cases, plan, lock_path=LOCK):
    if json.loads(lock_path.read_bytes()) != plan:
        raise ValueError("Frozen ranking plan changed")
    if "Ollama cloud disabled: true" not in startup_log.read_text(encoding="utf-8"):
        raise ValueError("Missing isolated local-only Ollama startup evidence")
    runtime = spec["runtime"]
    blobs = verified_installation(Path.home() / ".ollama" / "models", runtime)
    with httpx.Client(base_url=LOOPBACK, trust_env=False, follow_redirects=False,
                      timeout=runtime["timeout_seconds"]) as client:
        preflight(client, runtime)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            def append(record):
                stream.write(canonical(record).decode() + "\n")
                stream.flush()
                os.fsync(stream.fileno())

            append({"plan": plan, "runtime": runtime, "verified_local_blobs": blobs})
            for case, (review, payload) in zip(spec["cases"], cases, strict=True):
                result = evaluate_case(client, case, review, payload, runtime)
                append(result)
                print(f'{case["id"]}: {result["status"]}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "run"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--startup-log", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--lock", type=Path)
    args = parser.parse_args()
    spec, cases, plan = prepare(args.fixture or SPEC)
    if args.mode == "plan":
        print(json.dumps(plan, indent=2, ensure_ascii=True))
    elif args.output is None or args.startup_log is None:
        parser.error("run requires --output and --startup-log")
    elif (args.fixture is None) != (args.lock is None):
        parser.error("custom runs require both --fixture and --lock")
    else:
        run(args.output, args.startup_log, spec, cases, plan, args.lock or LOCK)


if __name__ == "__main__":
    main()
