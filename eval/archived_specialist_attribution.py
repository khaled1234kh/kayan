"""Score passive archived observation attribution with authored case oracles."""

import argparse
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from console.backend.reporting_evidence import capture, digest
from integration.trustgate_client import AuthorizationResult
from pentagi.execution_evidence import LAB_URL, ToolEvidenceStore


FIXTURE = Path(__file__).with_name("fixtures") / "archived_specialist_attribution_v1.json"
CASE = "bbbbbbbb-1111-2222-3333-444444444444"
FOREIGN = "aaaaaaaa-1111-2222-3333-444444444444"


def fixture_session(case, source):
    events = []
    for number, event in enumerate(case["events"], 1):
        role = event["role"]
        status = event.get("status", "completed")
        task = f"tool-{number:032x}"
        meta = {"engagement_id": CASE, "task_id": task, "agent_id": f"test-only-{role}",
                "agent_role": role, "tool_name": "inert_fixture_observation", "target": "127.0.0.1"}
        if status in ("transcript_only", "foreign"):
            events.append({**meta, "engagement_id": FOREIGN if status == "foreign" else CASE,
                           "id": task, "kind": "tool_result", "result": event["outcome"]})
            continue
        allowed = status != "denied"
        audit_id = None if status == "authorization_unverified" else f"{number:08x}-1111-2222-3333-444444444444"
        verdict = "ALLOW" if allowed else "DENY"
        authorization = AuthorizationResult(allowed, verdict, "test only", audit_entry_id=audit_id)
        outcome = {"error": "simulated observation failure"} if status == "failed" else event.get("outcome")
        bindings = {"engagement": CASE, "agent": meta["agent_id"], "role": role, "task": task,
                    "tool": meta["tool_name"], "target": meta["target"], "auth": authorization,
                    "dispatched": status in ("completed", "failed")}
        proof = source.record(**bindings, result=outcome)
        alteration = event.get("alteration")
        if alteration == "other_role":
            meta["agent_role"] = "recon_agent"
        decision = {**meta, "kind": "authorization_decision", "decision": verdict, "audit_entry_id": audit_id}
        record = {**meta, "kind": "tool_result" if allowed else "tool_denied", "source_artifact_sha256": proof}
        events.extend((decision, record))
        if alteration == "late_conflict":
            events.append({**decision, "decision": "DENY"})
        elif alteration == "duplicate":
            events.append(dict(record))
        elif alteration == "two_hashes":
            events.append({**record, "source_artifact_sha256": source.record(
                **bindings, result={"status_code": 204},
            )})
    for role in case.get("declared_complete", []):
        events.append({"engagement_id": CASE, "agent_role": "planner_agent", "kind": "specialist_outcome",
                       "specialist_outcome": {"role": role, "status": "completed", "coverage": {"complete": True}}})
    return {"engagement_id": CASE, "status": "completed", "execution_engine": "local_llm",
            "target": LAB_URL, "roe": {"targets": ["127.0.0.1"]}, "transcript": events}


def describe_records(records):
    counts = {}
    for row in records:
        if "artifact_sha256" not in row:
            category = "transcript_only"
        elif row["status"] != "completed":
            category = row["status"]
        elif not row["outcome"]:
            category = "empty"
        else:
            category = "projected" if row["truncated"] else "completed"
        counts.setdefault(row["agent"], Counter())[category] += 1
    return {role: dict(items) for role, items in counts.items()}


def run(fixture=FIXTURE):
    raw = fixture.read_bytes()
    cases = []
    for case in json.loads(raw)["cases"]:
        with TemporaryDirectory(prefix="kayan-observation-replay-") as directory:
            evidence = ToolEvidenceStore(Path(directory))
            snapshot = capture(fixture_session(case, evidence), evidence)
        counted = describe_records(snapshot["records"])
        invalid = snapshot.get("invalid_sources", 0)
        cases.append({
            "id": case["id"], "expected": case["expected"], "observed": counted,
            "expected_invalid_sources": case["invalid_sources"], "observed_invalid_sources": invalid,
            "exact": counted == case["expected"] and invalid == case["invalid_sources"],
        })
    return {"fixture_sha256": digest(raw), "cases": cases,
            "exact_cases": sum(row["exact"] for row in cases)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New output path")
    args = parser.parse_args()
    results = run()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(results, stream, indent=2)
        stream.write("\n")
    failures = [row["id"] for row in results["cases"] if not row["exact"]]
    print(f'{results["exact_cases"]}/{len(results["cases"])} exact; mismatches: {", ".join(failures) or "none"}')
