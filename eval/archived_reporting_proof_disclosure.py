"""Measure exact local proof disclosure independently of summary selection."""

import json
from hashlib import sha256
from pathlib import Path

from eval.archived_reporting_full_summary import FIXTURE as CAPACITY_FIXTURE, case_input
from eval.archived_reporting_projection import archive, fixtures, occurrence
from eval.fixtures.ai.attack_fact_registry_v1.demo import _fixture, _record
from pentagi.agents.archived_reporting import compose, review_archive_document

FIXTURE = Path(__file__).with_name("fixtures") / "ai" / "archived_reporting_proof_disclosure_v1.json"


def read_archive(raw):
    return review_archive_document(json.loads(raw), sha256(raw).hexdigest())


def shared_fixture(spec):
    case, records = _fixture(spec["id"])
    for event in [*spec["occurrences"], *spec["withheld"]]:
        occurrence(case, records, event, authorized=event in spec["withheld"])
    _record(case, records, "shared-context", spec["text"].encode(), "action-ledger", spec["cite"])
    for assertion in case["assertions"]:
        if assertion["role"] == "mechanic":
            assertion["statements"].append("shared-context")
    raw, *_ = archive(case, records)
    expected = {
        ("T1486", f"incident-{event}"): {
            role: [f"E{event}.{cite}" if isinstance(cite, int) else cite for cite in sequence]
            for role, sequence in spec["assertions"].items()
        } for event in spec["occurrences"]
    }
    report = read_archive(raw)
    assert {claim["occurrence"] for claim in report["withheld"]} == {
        f"incident-{number}" for number in spec["withheld"]
    }
    return report, expected


def archives(spec):
    capacity = CAPACITY_FIXTURE.read_bytes()
    if sha256(capacity).hexdigest() != spec["capacity_fixture_sha256"]:
        raise ValueError("Frozen capacity fixture changed")
    for case in json.loads(capacity)["cases"]:
        report, selection, _ = case_input(case)
        expected = {
            ("T1486", f"event-{number}"): {
                role: [f"E{number}.{index}"] for role, index in spec["capacity_source_roles"].items()
            }
            for number in range(1, len(case["assets"]) + 1) if number not in case.get("authorized", ())
        }
        yield case["id"], compose(report, json.dumps(selection), supplement_actions=True), expected

    pinned = dict(fixtures())
    windows = spec["windows"]
    expected = {(windows["technique"], windows["occurrence"]): windows["assertions"]}
    yield "windows-secondary-support", compose(read_archive(pinned["windows-secondary-support"][0])), expected

    report, expected = shared_fixture(spec["shared_context"])
    yield "shared-secondary-support", compose(report), expected
    yield "no-admitted-finding", compose(read_archive(pinned["authorized"][0])), {}


def score(report, expected, *, legacy):
    expected_links = {
        (*event, role, cite, index == 0)
        for event, assertions in expected.items()
        for role, sequence in assertions.items() for index, cite in enumerate(sequence)
    }
    observed = set()
    events = set()
    for finding in report["findings"]:
        event = finding["technique"], finding["occurrence"]
        assert event not in events
        events.add(event)
        sources = {source["id"]: source for source in finding["sources"]}
        if legacy:
            observed.update((*event, role, cite, True)
                            for cite, source in sources.items() for role in source["roles"])
        else:
            for group in finding.get("proof", {}).get("assertions", ()):
                for index, cite in enumerate(group["source_ids"]):
                    assert sources[cite]["statements"]
                    observed.add((*event, group["role"], cite, index == 0))
    uncovered = {row[:2] for row in expected_links ^ observed}
    return {
        "occurrences": len(expected),
        "complete_occurrences": len(events & expected.keys() - uncovered),
        "incorrect_occurrences": sorted(events ^ expected.keys()),
        "exact_links": len(observed & expected_links),
        "expected_links": len(expected_links),
        "missing_links": sorted(expected_links - observed),
        "incorrect_links": sorted(observed - expected_links),
        "summary_size": len(report["summary"]),
        "summary_coverage": report["summary_coverage"],
    }


def evaluate():
    raw = FIXTURE.read_bytes()
    spec = json.loads(raw)
    rows = [
        {"id": case, "archive_sha256": report["source_sha256"],
         "baseline": score(report, expected, legacy=True),
         "disclosure": score(report, expected, legacy=False)}
        for case, report, expected in archives(spec)
    ]
    return {"protocol": spec["protocol"], "fixture_sha256": sha256(raw).hexdigest(), "cases": rows}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, ensure_ascii=True))
