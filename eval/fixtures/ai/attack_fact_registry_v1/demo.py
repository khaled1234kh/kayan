"""Synthetic offline example. Fixture review receipts are not human attestations."""
from dataclasses import replace
from pathlib import Path
import json

from eval.attack_evidence_v2 import spans
from eval.attack_fact_guard_adapter_v1 import evaluate
from eval.attack_fact_registry_v1 import Assertion, VERSION, assertion_digest, bytes_digest, digest, evidence_digest, verify
from eval.attack_windows_event_normalizer_v1 import SessionObservation, normalize, session_candidate, utc_ns

HERE = Path(__file__).parent
AT = "2026-11-20T10:00:00Z"
START = "2026-11-20T09:05:00Z"
END = "2026-11-20T09:15:00Z"
SCOPE = {
    "tenant": "blue", "asset": "jun-4", "authority": "blue-domain",
    "principal": "S-1-5-21-100-200-300-1104", "session": "0x55cd1d",
    "session_generation": "boot-fixture-1",
}
WINDOW = 3600 * 10**9


def proposal(**claims):
    return json.dumps({"mappings": [{"technique": tid, "cite": cite}
                                    for tid, cites in claims.items() for cite in cites]})


def _fixture(case):
    return {"schema_version": VERSION, "case_id": case, "sources": [], "records": [],
            "statements": [], "events": [], "assertions": [], "receipts": []}, {}


def _record(snapshot, payloads, key, raw, source, cite, locator=None):
    media = "application/xml" if locator else "text/plain"
    sha = bytes_digest(raw)
    if source not in {entry["id"] for entry in snapshot["sources"]}:
        snapshot["sources"].append({
            "id": source, "alias": source, "collector": source, "family": source,
            "attestation_ref": "synthetic-source-catalogue",
        })
    snapshot["records"].append({
        "id": key, "revision": 1, "source": source, "native_ref": f"synthetic-export/{key}",
        "media_type": media, "sha256": sha, "byte_length": len(raw), "collected_at": AT,
    })
    payloads[key, 1] = raw
    reference = {"id": key, "cite": cite, "record": {"id": key, "revision": 1}, "sha256": sha}
    if locator:
        reference["xml_path"] = [
            {"namespace": namespace, "name": name, "data_name": data_name}
            for namespace, name, data_name in locator["path"]
        ]
        reference["attribute"] = locator["attribute"]
    else:
        reference["span"] = [0, len(raw)]
    snapshot["statements"].append(reference)


def _event(snapshot, key, scope, time):
    snapshot["events"].append({
        **scope, "id": key, "revision": 1,
        "time": {"source_time": time, "basis": "UTC", "precision_ns": utc_ns(time)[1],
                 "clock_error_ns": 0, "bounds_provenance": "synthetic-reviewed-clock-bounds"},
    })


def _assert(snapshot, event, scope, role, value, *statements, action=None):
    key = f"{event}-{role}"
    snapshot["assertions"].append({
        "id": key, "revision": 1, "event": {"id": event, "revision": 1},
        "scope": scope, "role": role, "value": value, "statements": list(statements),
        "state": "asserted", "receipt": {"id": key, "revision": 1},
        **({"authorization": {"action": action, "start": START, "end": END}} if action else {}),
    })


def windows():
    case, payloads = _fixture("windows-fixture")
    clear_raw, logon_raw = ((HERE / file).read_bytes() for file in ("clear.xml", "logon.xml"))
    clear, logon = normalize(clear_raw), normalize(logon_raw)
    _record(case, payloads, "clear", clear_raw, "audit-origin", "E1.1", clear["locators"]["event_id"])
    _record(case, payloads, "logon", logon_raw, "audit-origin", "E1.2", logon["locators"]["logon_id"])
    _record(case, payloads, "custody", (HERE / "custody.txt").read_bytes(), "custody-origin", "E2.1")
    _record(case, payloads, "permission", (HERE / "permission.txt").read_bytes(), "policy-origin", "E3.1")
    _event(case, "clear-event", SCOPE, clear["original_fields"]["time"])
    _assert(case, "clear-event", SCOPE, "mechanic", "windows_event_log_clear", "clear", "logon")
    _assert(case, "clear-event", SCOPE, "outcome", "completed", "clear")
    _assert(case, "clear-event", SCOPE, "actor", "adversary", "custody")
    _assert(case, "clear-event", SCOPE, "authorization", "unauthorized", "permission",
            action="windows_event_log_clear")
    return case, payloads


def session_inputs(verified=None):
    bounds = (utc_ns("2026-11-20T08:00:00Z")[0], utc_ns("2026-11-20T10:00:00Z")[0])
    return tuple(
        SessionObservation(
            f"{key}.xml", "windows-fixture", "blue", "jun-4", "blue-domain", "boot-fixture-1",
            bounds, 0, normalize((HERE / f"{key}.xml").read_bytes()) if verified is None
            else verified.normalized[key, 1]["fields"],
        )
        for key in ("clear", "logon")
    )


def slate(withhold=False):
    from eval.attack_experiment_d_guard_v3 import ANALYST_FACTS

    case, payloads = _fixture("slate")
    cases = json.loads((HERE.parent / "attack_mapping_v2/observations.json").read_bytes())["cases"]
    spans_by_id = spans(next(item["records"] for item in cases if item["id"] == "slate"))
    recorded = set()
    for group in ("slate_encryption", "slate_recovery"):
        facts = ANALYST_FACTS[group]
        action = facts[0].value
        event = facts[0].event.occurrence
        scope = {**SCOPE, "asset": "se-2", "session": "B19"}
        _event(case, event, scope, "2026-11-20T09:10:00Z")
        for fact in facts:
            if fact.cite not in recorded:
                _record(case, payloads, fact.cite, spans_by_id[fact.cite].encode(),
                        fact.source, fact.cite)
                recorded.add(fact.cite)
            if withhold and group == "slate_recovery" and fact.kind == "actor":
                continue
            _assert(case, event, scope, fact.kind, fact.value, fact.cite,
                    action=action if fact.kind == "authorization" else None)
    return case, payloads


def issue_fixture_receipts(case):
    """Test issuer. Called only for authored fixtures, never by the registry."""
    snapshot = evidence_digest(case)
    receipts = []
    for row in case["assertions"]:
        receipt = {
            **row["receipt"], "reviewer": "synthetic-reviewer", "decision": "approved",
            "reviewed_at": "2026-11-20T09:59:00Z", "expires_at": "2026-11-21T00:00:00Z",
            "rationale": "Fixture-only review of the authored evidence and association",
            "snapshot_sha256": snapshot,
            "assertion_sha256": assertion_digest(Assertion.model_validate(row)),
        }
        receipts.append(receipt)
    case["receipts"] = receipts
    return {"synthetic-reviewer": sorted(digest({**row, "supersedes": None}) for row in receipts)}


def seal_fixture(case):
    receipts = issue_fixture_receipts(case)
    raw = (json.dumps(case, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
    return raw, bytes_digest(raw), receipts


def inputs():
    win, win_data = windows()
    yield "windows", win, win_data, proposal(**{"T1685.005": ("E1.1", "E2.1", "E3.1")})
    mixed, mixed_data = slate(withhold=True)
    yield "mixed", mixed, mixed_data, proposal(**{
        "T1486": ("E1.1", "E2.1"), "T1490": ("E1.1", "E3.1", "E4.1"),
    })


def main():
    pins = json.loads((HERE / "fixture-pins.json").read_bytes())
    runs = {}
    clear, logon = None, None
    for name, _, data, raw_proposal in inputs():
        manifest = (HERE / f"{name}-manifest.json").read_bytes()
        pin = pins[name]
        if name == "windows":
            verified = verify(manifest, data, expected_sha256=pin["manifest_sha256"],
                              approved_receipts=pin["review_receipts"], at=AT)
            clear, logon = session_inputs(verified)
            incomplete = proposal(**{"T1685.005": ("E1.1", "E3.1")})
            runs["windows_without_custody_cite"] = evaluate(
                incomplete, manifest, data, expected_sha256=pin["manifest_sha256"],
                approved_receipts=pin["review_receipts"], at=AT,
            )
        runs[name] = evaluate(raw_proposal, manifest, data, expected_sha256=pin["manifest_sha256"],
                              approved_receipts=pin["review_receipts"], at=AT)
    expected = {"windows": "all_eligible", "mixed": "mixed", "windows_without_custody_cite": "none_eligible"}
    if {name: run["batch_state"] for name, run in runs.items()} != expected:
        raise SystemExit(f"Unexpected fixture results: {runs}")
    print(json.dumps({
        "normalized": [clear.observation, logon.observation],
        "candidate": session_candidate(clear, (logon,), window_ns=WINDOW),
        "review_origin": "authored and pinned synthetic receipts",
        "unknown": ["physical operator identity", "real collector independence", "real organizational authority"],
        "decisions": runs,
    }, indent=2))


if __name__ == "__main__":
    main()
