"""Re-score the matched cloud arm against the five frozen local arms.

Uses the untouched frozen scorer and paired bootstrap. Cloud latency is not
comparable to local host latency and is reported but never used for ranking.
"""
from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal
from pathlib import Path

import frozen_protocol as fp

A = fp.analyze_models
RC = fp.role_cases

LOCAL_ARMS = {
    "qwen2.5:7b": "qwen2_5-7b",
    "qwen3:8b": "qwen3-8b",
    "granite4.2:8b": "granite4_2-8b",
    "llama3.1:8b": "llama3_1-8b",
    "qwen2.5:1.5b": "qwen2_5-1_5b",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_rows(path: Path, fixtures: dict, label: str) -> list[dict]:
    rows = []
    for row in read_jsonl(path):
        case = fixtures[row["case_id"]]
        checked = A.checked_attempt(case, dict(row["attempts"][-1]))
        rows.append({
            "case_id": row["case_id"], "role": case["role"],
            "family": case.get("family", row["case_id"]),
            "attempts": [A.checked_attempt(case, a) for a in row["attempts"]],
        })
        _ = checked
    if len(rows) != 80:
        raise ValueError(f"{label}: expected 80 cases, got {len(rows)}")
    return rows


def describe(rows: list[dict]) -> dict:
    return A.describe(rows)


def compact(row: dict, model: str, status: str, cost: str | None) -> dict:
    m = describe(row)
    return {
        "model": model,
        "status": status,
        "cases": m["cases"],
        "final_pass": m["final_pass"],
        "exact_percent": round(100 * m["final_pass_rate"], 2),
        "affirmative_f1": round(m["final_affirmative"]["f1"], 3),
        "evidence_f1": round(m["final_evidence_f1"], 3),
        "abstention_f1": round(m["final_abstention"]["f1"], 3),
        "unsupported_positive": m["final_unsupported_positive"],
        "invalid_cases": m["final_invalid_cases"],
        "inference_errors": m["inference_error_attempts"],
        "input_tokens": m["input_tokens_observed"],
        "output_tokens": m["output_tokens_observed"],
        "p50_case_ms": round(m["p50_case_ms"], 1),
        "p95_case_ms": round(m["p95_case_ms"], 1),
        "catalogue_equivalent_egp": cost,
        "all_metrics": m,
    }


def write_csv(path: Path, arms: list[dict]) -> None:
    fields = ["model", "status", "cases", "final_pass", "exact_percent", "affirmative_f1",
              "evidence_f1", "abstention_f1", "unsupported_positive", "invalid_cases",
              "inference_errors", "input_tokens", "output_tokens", "p50_case_ms", "p95_case_ms",
              "catalogue_equivalent_egp"]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for arm in arms:
            writer.writerow({key: arm.get(key) for key in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", type=Path, help="Cloud arm directory with cases.jsonl")
    parser.add_argument("--reference-root", type=Path,
                        default=fp.REFERENCE / "results")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = fp.load_manifest()
    fixtures = {e["case"]["id"]: e["case"] for e in fp.heldout_entries(manifest)}
    arms: list[dict] = []
    by_role: dict[str, dict[str, int]] = {}
    pairs = {}

    for label, directory in LOCAL_ARMS.items():
        rows = load_rows(args.reference_root / directory / "heldout" / "cases.jsonl",
                         fixtures, label)
        arms.append(compact(rows, label, "MEASURED_LOCAL", "n/a"))
        by_role[label] = {
            role: describe([r for r in rows if r["role"] == role])["final_pass"]
            for role in RC.ROLES
        }
        pairs[label] = rows

    if args.cloud and (args.cloud / "cases.jsonl").is_file():
        finished = json.loads((args.cloud / "finished.json").read_text(encoding="utf-8"))
        rows = load_rows(args.cloud / "cases.jsonl", fixtures, "cloud")
        cost = finished.get("catalogue_equivalent_egp")
        arms.insert(0, compact(rows, fp.MODEL, finished.get("measurement_status", "MEASURED"), cost))
        by_role[fp.MODEL] = {
            role: describe([r for r in rows if r["role"] == role])["final_pass"]
            for role in RC.ROLES
        }
        cloud_rows = rows
    else:
        arms.insert(0, {
            "model": fp.MODEL, "status": "NOT MEASURED", "cases": 0, "final_pass": None,
            "exact_percent": None, "affirmative_f1": None, "evidence_f1": None,
            "abstention_f1": None, "unsupported_positive": None, "invalid_cases": None,
            "inference_errors": None, "input_tokens": None, "output_tokens": None,
            "p50_case_ms": None, "p95_case_ms": None, "catalogue_equivalent_egp": None,
        })
        by_role[fp.MODEL] = {role: None for role in RC.ROLES}
        cloud_rows = None

    comparisons = []
    if cloud_rows:
        for label, rows in pairs.items():
            diff = A.paired_bootstrap(rows, cloud_rows, replicates=5000)
            differences = diff["differences_candidate_minus_reference"]
            comparisons.append({
                "reference": label,
                "candidate": fp.MODEL,
                "exact_pass_pp": round(100 * differences["final_pass_rate"]["estimate"], 2),
                "exact_pass_ci95_pp": [round(100 * x, 2) for x in differences["final_pass_rate"]["ci95"]],
                "evidence_f1_delta": round(differences["final_evidence_f1"]["estimate"], 3),
                "evidence_f1_ci95": [round(x, 3) for x in differences["final_evidence_f1"]["ci95"]],
                "latency_note": "cloud and local endpoint times are not comparable; excluded from ranking",
            })

    summary = {
        "benchmark": "frozen 80-case KAYAN role contract holdout",
        "manifest_sha256": fp.EXPECTED_MANIFEST_SHA,
        "design": "retrospective matched benchmark; authored synthetic cases, not a fresh blinded human-adjudicated holdout",
        "metric_definitions": {
            "exact_pass": "all expected labels and citations and, for Planner, an acceptable dependency order",
            "evidence_f1": "F1 over item+label+source-reference triples",
            "affirmative_f1": "F1 over each role's affirmative class",
        },
        "arms": arms,
        "by_role_exact_passes": by_role,
        "paired_comparisons_cloud_minus_local": comparisons,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output / "summary.csv", arms)
    with (args.output / "summary.json").open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    for arm in arms:
        print(f"{arm['model']:<28} {arm['status']:<22} "
              f"{str(arm['final_pass']) + '/80' if arm['final_pass'] is not None else 'NOT MEASURED'} "
              f"evidence_f1={arm['evidence_f1']}")


if __name__ == "__main__":
    main()
