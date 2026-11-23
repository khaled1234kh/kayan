"""Replay recorded model replies with a bounded deterministic action supplement."""

import json
from hashlib import sha256
from pathlib import Path

from eval.archived_reporting_local_ranking import LOCK, SPEC, prepare, selection_from_reply
from eval.archived_reporting_selection import selection_metrics
from eval.attack_evidence_v2 import parse
from pentagi.agents.archived_reporting import ReportSelection, _selection_options, compose, repeated_techniques


TRACE = Path(__file__).with_name("reports") / "archived_reporting_local_ranking_v1.jsonl"
MAX_HIGHLIGHTS = ReportSelection.model_json_schema()["properties"]["highlights"]["maxItems"]


def add_observed_actions(report, selection):
    original = compose(report, selection)
    picked = parse(selection)
    options, _ = _selection_options(report, bool(repeated_techniques(report)))
    covered = {
        (options[key][0]["technique"], options[key][0]["occurrence"])
        for key in picked["highlights"] if "mechanic" in options[key][1]["roles"]
    }
    added = []
    for key, (finding, source) in options.items():
        if len(picked["highlights"]) == MAX_HIGHLIGHTS:
            break
        occurrence = finding["technique"], finding["occurrence"]
        if occurrence not in covered and "mechanic" in source["roles"]:
            covered.add(occurrence)
            picked["highlights"].append(key)
            added.append(key)
    augmented = compose(report, json.dumps(picked))
    assert augmented["summary"][:len(original["summary"])] == original["summary"]
    return augmented, added


def compare_trace(path=TRACE, *, spec_path=SPEC, lock_path=LOCK):
    raw = path.read_bytes()
    header, *rows = map(json.loads, raw.splitlines())
    spec, cases, plan = prepare(spec_path)
    if json.loads(lock_path.read_bytes()) != plan or header["plan"] != plan or header["runtime"] != spec["runtime"]:
        raise ValueError("Trace does not match the frozen local ranking plan")
    details = []
    for case, (review, _), row in zip(spec["cases"], cases, rows, strict=True):
        if case["id"] != row["id"]:
            raise ValueError("Trace case order differs from the frozen plan")
        if row["status"] != "selected":
            continue
        original, _ = selection_from_reply(review, row["raw_reply"], spec["runtime"])
        if selection_metrics(original, case) != row["selected"]:
            raise ValueError("Recorded metrics no longer match the raw reply")
        content = json.loads(row["raw_reply"])["message"]["content"]
        augmented, added = add_observed_actions(review, content)
        details.append({
            "id": case["id"], "added_highlights": added,
            "findings_and_controls_unchanged": all(augmented[field] == original[field] for field in (
                "findings", "withheld", "recommendations",
            )),
            "raw": row["selected"], "augmented": selection_metrics(augmented, case),
        })
    return {"protocol": "archived-reporting-action-coverage-ablation-v1",
            "trace_sha256": sha256(raw).hexdigest(), "cases": details}


if __name__ == "__main__":
    print(json.dumps(compare_trace(), indent=2, ensure_ascii=True))
