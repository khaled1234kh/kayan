"""Replay exposed defensive evidence benchmarks and exercise mocked cloud arms offline."""
import argparse
from base64 import b64decode
from collections import defaultdict
from pathlib import Path

import httpx

from eval.attack_evidence_admission_v2 import evaluate_in_custody
from eval.attack_evidence_v2 import Response, compact, parse, score, summarise
from eval.attack_experiment_v2 import (
    ROOT, check_inputs, dump, read, reference, render_prompt, schedule, sha,
)
from eval.fixtures.ai.attack_admission_v2 import VERSION, issue
from eval.fixtures.ai.attack_fact_registry_v1.demo import proposal, slate, windows

LOCK = ROOT / "eval/fixtures/ai/cloud_track_a_v1.json"
LOCK_SHA = "6e6699bce91fd575b5a549e38dd3d0ef36646b484d1f75bf4da02a5334587b48"
LEDGER = ".build/attack_exploratory_v2/run/attempts.jsonl"


def assemble_reviewed_groups(seeds, groups):
    """Expand only an existing hypothesis compatible with one supplied proof group."""
    return {
        technique: groups[technique]
        if technique in groups and citations and set(citations) <= set(groups[technique])
        else citations
        for technique, citations in seeds.items()
    }


def proof_experiment(design):
    outputs = {}
    for name, cell in design.items():
        if name.startswith("windows"):
            case, payloads = windows()
        else:
            case, payloads = slate(withhold=name == "slate_missing_attribution")
        case["schema_version"] = VERSION
        for source in case["sources"]:
            source["upstream"] = []
        manifest, authority = issue(case)
        staged = assemble_reviewed_groups(cell["seed"], cell["groups"])
        before, after = (
            evaluate_in_custody(proposal(**claims), manifest, payloads, authority=authority)
            for claims in (cell["seed"], staged)
        )
        outputs[name] = {"expected_eligible": cell["eligible"], "before": before, "after": after}
    return outputs


def report_arm(rows):
    result = summarise(rows)
    counts = result["counts"]
    tp, fp, fn = (counts[name] for name in ("tech_tp", "tech_fp", "tech_fn"))
    result["technique_precision"] = tp / (tp + fp) if tp + fp else None
    result["technique_recall"] = tp / (tp + fn) if tp + fn else None
    result["retrieval"] = {
        "hits": sum(row["retrieved"] for row in rows),
        "targets": sum(row["targets"] for row in rows),
        "positive_cases_all_targets_retrieved": sum(
            0 < row["targets"] == row["retrieved"] for row in rows
        ),
        "positive_cases": sum(row["targets"] > 0 for row in rows),
    }
    return result


def replay(cases, labels, lookup):
    events = iter(parse(line) for line in (ROOT / LEDGER).read_bytes().splitlines())
    rows, archived = defaultdict(list), {}
    for repeat, case, arm in schedule(cases):
        start, result = next(events), next(events)
        for record, event in ((start, "start"), (result, "result")):
            observed = tuple(record[key] for key in ("event", "pass", "id", "arm", "family"))
            if observed != (event, repeat, case["id"], arm, case["family"]):
                raise ValueError("Archived schedule differs from the frozen registration")
        if start["references"] != result["references"]:
            raise ValueError("Archived shortlist mismatch")
        wire = parse(b64decode(result["raw_body_base64"], validate=True))
        if wire["response"] != result["raw"] or wire.get("done_reason") != "stop":
            raise ValueError("Unexpected historical wire envelope")
        label = labels[case["id"]]
        scored = score(case["records"], label, result["raw"], lookup)
        if any(result[key] != value for key, value in scored.items()):
            raise ValueError("Archived score failed replay")
        row = {
            **scored, "id": case["id"], "references": start["references"],
            "retrieved": len(label["targets"].keys() & set(start["references"])),
            "provider_metrics": {
                k: wire.get(k) for k in ("total_duration", "prompt_eval_count", "eval_count")
            },
        }
        rows[f"{repeat}:{arm}"].append(row)
        if repeat == 1:
            archived[case["id"], arm] = (start["references"], result["raw"])
    if next(events, None) is not None:
        raise ValueError("Unexpected trailing archived events")
    return rows, archived


def mock_arms(plan, cases, labels, lookup, archived):
    outputs = {}
    for arm in ("B", "C", "D"):
        config = plan["arms"][arm]
        rows = []
        for case in cases:
            cid = case["id"]
            lexical_reply = archived[cid, "bm25_k5"][1]
            retrieval = config["retrieval"]
            refs = archived[cid, retrieval][0] if retrieval else []
            body = {"model": config["model"], "temperature": 0,
                    "schema": Response.model_json_schema(),
                    "prompt": render_prompt(case["records"], [reference(lookup[ref]) for ref in refs])}

            def fixture_reply(request):
                if parse(request.content) != body:
                    raise ValueError("Mock request changed during serialization")
                return httpx.Response(200, json={"response": lexical_reply})

            with httpx.Client(transport=httpx.MockTransport(fixture_reply), trust_env=False) as client:
                response = client.post("https://track-a.invalid/fixture", json=body)
                response.raise_for_status()
            label = labels[cid]
            rows.append({
                **score(case["records"], label, response.json()["response"], lookup),
                "id": cid, "references": refs, "request_bytes": len(compact(body).encode()),
                "retrieved": len(label["targets"].keys() & set(refs)),
            })
        outputs[arm] = {"mode": "mock", "per_case": rows, "summary": report_arm(rows)}
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha(LOCK) != LOCK_SHA:
        raise ValueError("Track A contract changed")
    plan = read(LOCK)
    for path, expected in plan["files"].items():
        if sha(ROOT / path) != expected:
            raise ValueError(f"Frozen Track A input changed: {path}")
    cases, labels, lookup, _ = check_inputs()
    rows, archived = replay(cases, labels, lookup)
    dump(args.output, {
        "contract_sha256": LOCK_SHA, "provider_status": "blocked_pending_separate_approval",
        "historical_local": {name: {"per_case": run, "summary": report_arm(run)}
                             for name, run in rows.items()},
        "cloud_mocks": mock_arms(plan, cases, labels, lookup, archived),
        "reviewed_proof_experiment": proof_experiment(plan["proof_experiment"]),
    })


if __name__ == "__main__":
    main()
