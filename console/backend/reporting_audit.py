"""Corroborate captured decisions through TrustGate's read-only ledger view."""

from collections import Counter
from uuid import UUID

import httpx

from pentagi.execution_evidence import ToolEvidenceStore


AUDIT_URL = "http://127.0.0.1:8000"
BATCH_SIZE = 128


def _canonical_uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def _lookup(client, assessment_id, identifiers):
    try:
        response = client.post("/audit/reconcile", json={
            "engagement_id": assessment_id, "entry_ids": identifiers,
        })
        body = response.raise_for_status().json()
        if body["valid"] is False:
            return "ledger_invalid", {}
        entries = body["entries"]
        if body["valid"] is not True or not isinstance(entries, list):
            return "unavailable", {}
        decisions = {entry["entry_id"]: entry for entry in entries}
        if len(decisions) != len(entries) or not decisions.keys() <= set(identifiers):
            return "unavailable", {}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return "unavailable", {}
    return "verified", decisions


def reconcile(snapshot, source_sha256, source_store, *, transport=None):
    assessment_id = snapshot["assessment_id"]
    source_store = source_store or ToolEvidenceStore()
    results, pending = [], []
    for record in snapshot["records"]:
        if "artifact_sha256" not in record:
            continue
        result = {"source_id": record["source_id"], "status": "invalid_source"}
        results.append(result)
        try:
            source = source_store.load(assessment_id, record["occurrence"], record["artifact_sha256"])
            reference = {
                "entry_id": source["audit_entry_id"], "engagement_id": source["engagement_id"],
                "agent_id": source["agent"], "agent_role": source["role"],
                "tool_name": source["tool"], "target": "127.0.0.1",
                "decision": source["authorization_decision"],
            }
        except (ValueError, OSError, TypeError, KeyError):
            continue
        if _canonical_uuid(reference["entry_id"]):
            pending.append((result, reference))
        else:
            result["status"] = "missing_reference"

    use_counts = Counter(reference["entry_id"] for _, reference in pending)
    lookups = []
    for result, reference in pending:
        if use_counts[reference["entry_id"]] > 1:
            result["status"] = "reused_reference"
        else:
            lookups.append((result, reference))

    if lookups:
        with httpx.Client(base_url=AUDIT_URL, timeout=3.0, trust_env=False,
                          follow_redirects=False, transport=transport) as client:
            for start in range(0, len(lookups), BATCH_SIZE):
                batch = lookups[start:start + BATCH_SIZE]
                scope, entries = _lookup(client, assessment_id, [item["entry_id"] for _, item in batch])
                for result, reference in batch:
                    entry = entries.get(reference["entry_id"])
                    if scope != "verified":
                        result["status"] = scope
                    elif entry is None:
                        result["status"] = "missing_entry"
                    elif any(entry.get(key) != expected for key, expected in reference.items()):
                        result["status"] = "mismatch"
                    else:
                        result["status"] = "verified"

    counts = dict(Counter(result["status"] for result in results))
    invalid = snapshot.get("invalid_sources", 0)
    if invalid:
        counts["invalid_source"] = counts.get("invalid_source", 0) + invalid
    return {
        "assessment_id": assessment_id, "source_sha256": source_sha256,
        "counts": counts, "references": results,
    }
