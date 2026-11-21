"""Compare deterministic Reporting with a frozen, synthetic occurrence oracle."""

import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from eval.attack_evidence_admission_v2 import VERSION, evaluate_in_custody
from eval.fixtures.ai.attack_admission_v2 import issue
from eval.fixtures.ai.attack_fact_registry_v1.demo import SCOPE, _assert, _event, _fixture, _record, windows
from pentagi.agents.archived_reporting import review_archive_document


LOCK = Path(__file__).with_name("fixtures") / "ai" / "archived_reporting_projection_v1.json"
MECHANIC = "availability_impact_encryption"


def archive(case, payloads, *, omit=None):
    case["schema_version"] = VERSION
    for source in case["sources"]:
        source["upstream"] = []
    manifest, authority = issue(case)
    records = {key: value for key, value in payloads.items() if key != omit}
    package = {
        "assessment_id": case["case_id"], "title": "Synthetic Reporting evaluation",
        "status": "completed", "snapshot": manifest.decode("ascii"), "custody": asdict(authority),
        "records": [{"id": key, "revision": revision, "text": raw.decode()}
                    for (key, revision), raw in sorted(records.items())],
    }
    raw = json.dumps(package, default=sorted, sort_keys=True, separators=(",", ":")).encode()
    return raw, manifest, records, authority


def occurrence(case, records, index, *, authorized=False, incomplete=False,
               disputed=False, shared_primary=False):
    event = f"incident-{index}"
    scope = {**SCOPE, "session": f"fixture-session-{index}"}
    _event(case, event, scope, "2026-11-20T09:10:00Z")
    primary = "effect-1" if shared_primary else f"effect-{index}"
    if not shared_primary:
        _record(case, records, primary, f"Archive impact was independently logged for {event}.".encode(),
                "action-ledger", f"E{index}.1")
    _assert(case, event, scope, "mechanic", MECHANIC, primary)
    _assert(case, event, scope, "outcome", "completed", primary)
    if not incomplete:
        actor = f"actor-{index}"
        _record(case, records, actor, f"Independent analyst associated the untrusted actor with {event}.".encode(),
                "attribution-ledger", f"E{index}.2")
        _assert(case, event, scope, "actor", "adversary", actor)
    permission = f"permission-{index}"
    decision = "authorized" if authorized else "unauthorized"
    _record(case, records, permission, f"Independent scope review classified {event} as {decision}.".encode(),
            "scope-ledger", f"E{index}.3")
    _assert(case, event, scope, "authorization", decision, permission, action=MECHANIC)
    if disputed:
        correction = f"correction-{index}"
        _record(case, records, correction, f"The independent analyst retracted the occurrence claim for {event}.".encode(),
                "corrections-ledger", f"E{index}.4")
        _assert(case, event, scope, "veto", "retracted", correction)


def fixtures():
    case, data = windows()
    yield "windows-secondary-support", archive(case, data)
    case, data = windows()
    yield "missing-record", archive(case, data, omit=("logon", 1))
    case, data = _fixture("empty")
    yield "empty", archive(case, data)
    variants = {
        "disputed": ({"disputed": True},),
        "authorized": ({"authorized": True},),
        "missing-attribution": ({"incomplete": True},),
        "repeated-supported": ({}, {}),
        "repeated-mixed": ({}, {"authorized": True}),
        "shared-ambiguous-anchor": ({}, {"shared_primary": True}),
    }
    for case_id, variants in variants.items():
        case, data = _fixture(case_id)
        for index, variant in enumerate(variants, 1):
            occurrence(case, data, index, **variant)
        yield case_id, archive(case, data)


def compare(project=review_archive_document):
    locked = json.loads(LOCK.read_bytes())
    expected = locked["cases"]
    cases = dict(fixtures())
    if cases.keys() != expected.keys():
        raise ValueError("Projection fixture identities changed")
    results = []
    counts = dict(eligible=0, withheld=0, invalid=0, empty=0,
                  false_admissions=0, false_withholdings=0, false_rejections=0,
                  invalid_accepted=0, citation_errors=0, verifier_disagreements=0)
    for case_id, (raw, manifest, records, authority) in cases.items():
        oracle = expected[case_id]
        digest = sha256(raw).hexdigest()
        if digest != oracle["archive_sha256"]:
            raise ValueError(f"Projection fixture bytes changed for {case_id}")
        before = {}
        for event, claim in oracle["claims"].items():
            proposal = {"mappings": [{"technique": claim["technique"], "cite": address}
                                     for address in claim["proposal"]]}
            verdict = evaluate_in_custody(json.dumps(proposal), manifest, records, authority=authority)
            items = verdict["review_items"]
            if items and (len(items) != 1 or items[0]["event"]["occurrence"] != event
                          or items[0]["technique"] != claim["technique"]):
                before[event] = "misbound"
            else:
                before[event] = "eligible" if items else (
                    "invalid" if verdict["batch_state"] == "invalid" else "withheld")
            counts["verifier_disagreements"] += before[event] != claim["expected"]
        try:
            report = project(json.loads(raw), digest)
            by_event = {(f["technique"], f["occurrence"]): f for f in report["findings"]}
            if len(by_event) != len(report["findings"]):
                raise AssertionError("Duplicate occurrence in projected findings")
        except ValueError as error:
            report = None
            by_event = {}
            failure = str(error)
        else:
            failure = None
        allowed = {(c["technique"], event) for event, c in oracle["claims"].items() if c["expected"] == "eligible"}
        negative = sum(c["expected"] == "withheld" for c in oracle["claims"].values())
        counts["eligible"] += len(allowed)
        counts["withheld"] += negative
        counts["invalid"] += oracle["invalid"]
        counts["empty"] += not oracle["claims"]
        counts["false_admissions"] += len(by_event.keys() - allowed)
        counts["false_withholdings"] += len(allowed - by_event.keys())
        counts["false_rejections"] += report is None and not oracle["invalid"]
        counts["invalid_accepted"] += report is not None and oracle["invalid"]
        citation_errors = []
        for technique, event in sorted(by_event.keys() & allowed):
            sources = sorted(s["id"] for s in by_event[technique, event]["sources"])
            if sources != sorted(oracle["claims"][event]["sources"]):
                citation_errors.append(event)
        counts["citation_errors"] += len(citation_errors)
        results.append({"case": case_id, "archive_sha256": digest, "verifier": before,
                        "projected": [list(pair) for pair in sorted(by_event)],
                        "withheld": report["withheld"] if report is not None else [],
                        "citation_errors": citation_errors, "error": failure})
    return {"protocol": locked["protocol"], "counts": counts, "cases": results}


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2, ensure_ascii=True))
