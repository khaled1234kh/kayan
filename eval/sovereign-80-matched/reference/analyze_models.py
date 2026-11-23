"""Re-score offline model outputs and compare complete matched arms."""
from argparse import ArgumentParser
from collections import defaultdict
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re
from statistics import mean

import role_cases

ROOT = Path(__file__).resolve().parent
METRICS = ("first_pass_rate", "final_pass_rate", "final_evidence_f1", "p95_case_ms")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path, partial=False):
    if partial and not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if partial and text and not text.endswith("\n"):
        # A running process may have written part of the final JSON record.
        lines.pop()
    return [json.loads(line) for line in lines if line.strip()]


def strict_json(content):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate property {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"invalid JSON constant {value}")

    return json.loads(content, object_pairs_hook=pairs, parse_constant=reject_constant)


def percentile(numbers, p):
    if not numbers:
        return None
    values = sorted(numbers)
    i = (len(values) - 1) * p
    lo = math.floor(i)
    hi = math.ceil(i)
    return values[lo] + (i - lo) * (values[hi] - values[lo])


def ratio(num, denom):
    return num / denom if denom else None


def mean_or_none(values):
    return mean(values) if values else None


def checked_attempt(case, attempt):
    value = None
    if not attempt["error"]:
        try:
            value = strict_json(attempt["content"])
        except (ValueError, TypeError, RecursionError):
            pass
    fresh = role_cases.score(case, value)
    stored = attempt["score"]
    if fresh["passed"] and attempt.get("contract_errors"):
        raise ValueError(f"Runner structural rejection disagrees with scorer for {case['id']}")
    if fresh != stored:
        raise ValueError(f"Stored score differs from raw output for {case['id']}")
    elapsed = attempt["elapsed_ms"]
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError(f"Invalid timing for {case['id']}")
    return {**attempt, "score": fresh}


def resource_summary(directory, partial):
    values = []
    gpu_path = directory / "gpu.csv"
    if gpu_path.is_file():
        with gpu_path.open(encoding="utf-8", newline="", errors="replace") as handle:
            for row in csv.DictReader(handle, skipinitialspace=True):
                column = next((v for k, v in row.items() if k and k.strip().startswith("memory.used")), None)
                if column and (match := re.fullmatch(r"\s*(\d+)\s*(?:MiB)?\s*", column)):
                    values.append(int(match[1]))
    ram_path = directory / "ram.jsonl"
    ram_values = [
        (sample["total"] - sample["available"]) / (1024 ** 2)
        for sample in read_jsonl(ram_path, partial=partial)
    ] if ram_path.is_file() else []
    return {
        "gpu_samples": len(values),
        "peak_machine_gpu_used_mib": max(values, default=None),
        "ram_samples": len(ram_values),
        "peak_machine_ram_used_mib": max(ram_values, default=None),
    }


def load_arm(directory, manifest_path, manifest, fixtures, split):
    run = read_json(directory / "run.json")
    model, digest = run["model"]["name"], run["model"]["digest"]
    if run["manifest_sha256"] != sha256(manifest_path) or run["options"] != manifest["options"]:
        raise ValueError(f"{directory} does not match the frozen manifest")
    expected = set(fixtures)
    order = run["order"]
    if run["split"] != split or len(order) != len(expected) or set(order) != expected:
        raise ValueError(f"{directory} has an incompatible split or case order")
    finished_path = directory / "finished.json"
    finished = read_json(finished_path) if finished_path.is_file() else None
    raw = read_jsonl(directory / "cases.jsonl", partial=finished is None)
    checked = []
    for i, row in enumerate(raw):
        case_id = row["case_id"]
        if i >= len(order) or case_id != order[i]:
            raise ValueError(f"{directory} output order differs from recorded order at {i}")
        case = fixtures[case_id]
        if (row["model"] != model or row["model_digest"] != digest or row["split"] != split
                or row["role"] != case["role"] or row["family"] != case["family"]):
            raise ValueError(f"{directory} row metadata differs at {case_id}")
        if not 1 <= len(row["attempts"]) <= 2:
            raise ValueError(f"{directory} invalid attempt count at {case_id}")
        if len(row["attempts"]) == 2 and (
            not row["attempts"][0].get("contract_errors") or row["attempts"][0]["error"]
        ):
            raise ValueError(f"{directory} correction was outside the frozen protocol at {case_id}")
        checked.append({
            **row,
            "control": case["control"],
            "attempts": [checked_attempt(case, attempt) for attempt in row["attempts"]],
        })
    complete = finished is not None
    if complete and (finished["completed"] != len(expected) or len(checked) != len(expected)):
        raise ValueError(f"{directory} finished marker disagrees with observed coverage")
    return {
        "model": model,
        "model_digest": digest,
        "ollama": run["ollama"],
        "directory": str(directory),
        "status": "complete" if complete else "incomplete",
        "expected_cases": len(expected),
        "rows": checked,
        "resources": resource_summary(directory, partial=not complete),
    }


def classification(scores, prefix=""):
    tp, fp, fn = [sum(s[prefix + key] for s in scores) for key in ("tp", "fp", "fn")]
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def describe(rows):
    first = [row["attempts"][0]["score"] for row in rows]
    final = [row["attempts"][-1]["score"] for row in rows]
    attempts = [attempt for row in rows for attempt in row["attempts"]]
    timings = [sum(a["elapsed_ms"] for a in row["attempts"]) for row in rows]
    warm_timings = timings[1:]
    prompt_counts = [(a["ollama"] or {}).get("prompt_eval_count") for a in attempts]
    output_counts = [(a["ollama"] or {}).get("eval_count") for a in attempts]
    observed_prompt_counts = [x for x in prompt_counts if isinstance(x, int)]
    observed_output_counts = [x for x in output_counts if isinstance(x, int)]
    successful = [a for a in attempts if not a["error"]]
    server_ms = lambda key: [
        a["ollama"][key] / 1_000_000 for a in successful
        if a["ollama"] and isinstance(a["ollama"].get(key), (int, float))
    ]
    return {
        "cases": len(rows),
        "first_pass": sum(s["passed"] for s in first),
        "final_pass": sum(s["passed"] for s in final),
        "first_pass_rate": ratio(sum(s["passed"] for s in first), len(rows)),
        "final_pass_rate": ratio(sum(s["passed"] for s in final), len(rows)),
        "first_affirmative": classification(first),
        "final_affirmative": classification(final),
        "first_all_labels": classification(first, "label_"),
        "final_all_labels": classification(final, "label_"),
        "first_evidence": classification(first, "evidence_"),
        "final_evidence": classification(final, "evidence_"),
        "final_evidence_f1": classification(final, "evidence_")["f1"],
        "final_abstention": classification(final, "abstain_"),
        "correction_attempts": sum(len(row["attempts"]) - 1 for row in rows),
        "correction_rescues": sum(not a["passed"] and b["passed"] for a, b in zip(first, final)),
        "first_invalid_cases": sum(bool(row["attempts"][0]["contract_errors"]) for row in rows),
        "final_invalid_cases": sum(bool(row["attempts"][-1]["contract_errors"]) for row in rows),
        "inference_error_attempts": sum(bool(a["error"]) for a in attempts),
        "final_unsupported_positive": sum(s["unsupported_positive"] for s in final),
        "final_unsupported_items": sum(s["unsupported_items"] for s in final),
        "final_dependency_violations": sum(s["dependency_violations"] or 0 for s in final),
        "planner_invalid_orders": sum(s["order_valid"] is False for s in final),
        "inference_attempts": len(attempts),
        "input_tokens_observed": sum(observed_prompt_counts) if observed_prompt_counts else None,
        "output_tokens_observed": sum(observed_output_counts) if observed_output_counts else None,
        "input_token_samples": len(observed_prompt_counts),
        "output_token_samples": len(observed_output_counts),
        "mean_input_tokens": mean_or_none(observed_prompt_counts),
        "mean_output_tokens": mean_or_none(observed_output_counts),
        "total_case_ms": sum(timings),
        "first_case_ms": timings[0] if timings else None,
        "p50_case_ms": percentile(timings, .5),
        "p95_case_ms": percentile(timings, .95),
        "p95_excluding_first_case_ms": percentile(warm_timings, .95),
        "p50_server_load_ms": percentile(server_ms("load_duration"), .5),
        "p50_server_prefill_ms": percentile(server_ms("prompt_eval_duration"), .5),
        "p50_server_decode_ms": percentile(server_ms("eval_duration"), .5),
    }


def compact_metrics(rows):
    final = [row["attempts"][-1]["score"] for row in rows]
    return {
        "first_pass_rate": mean(row["attempts"][0]["score"]["passed"] for row in rows),
        "final_pass_rate": mean(s["passed"] for s in final),
        "final_evidence_f1": classification(final, "evidence_")["f1"],
        "p95_case_ms": percentile([sum(a["elapsed_ms"] for a in row["attempts"]) for row in rows], .95),
    }


def paired_bootstrap(reference, candidate, replicates=5000, seed=20261112):
    """Sample families with replacement within role and reuse each paired draw."""
    ref = {r["case_id"]: r for r in reference}
    alt = {r["case_id"]: r for r in candidate}
    if len(ref) != len(reference) or len(alt) != len(candidate) or ref.keys() != alt.keys() or not ref:
        raise ValueError("Paired arms do not contain the same unique case IDs")
    families = defaultdict(lambda: defaultdict(list))
    for case_id in sorted(ref):
        role, family = ref[case_id]["role"], ref[case_id]["family"]
        if (role, family) != (alt[case_id]["role"], alt[case_id]["family"]):
            raise ValueError(f"Paired metadata differs for {case_id}")
        families[role][family].append(case_id)
    buckets = [list(group.values()) for group in families.values()]
    rng = random.Random(seed)
    deltas = {metric: [] for metric in METRICS}
    for _ in range(replicates):
        sample = [
            case_id for role in buckets for _ in role
            for case_id in rng.choice(role)
        ]
        base = compact_metrics([ref[key] for key in sample])
        test = compact_metrics([alt[key] for key in sample])
        for metric in METRICS:
            deltas[metric].append(test[metric] - base[metric])
    base = compact_metrics(list(ref.values()))
    test = compact_metrics(list(alt.values()))
    return {
        "paired_cases": len(ref),
        "families_by_role": {role: len(group) for role, group in families.items()},
        "replicates": replicates,
        "seed": seed,
        "differences_candidate_minus_reference": {
            metric: {
                "estimate": test[metric] - base[metric],
                "ci95": [percentile(deltas[metric], .025), percentile(deltas[metric], .975)],
            }
            for metric in METRICS
        },
    }


def summarize(arm):
    rows = arm["rows"]
    return {
        **{key: value for key, value in arm.items() if key != "rows"},
        "observed_cases": len(rows),
        "all": describe(rows),
        "by_role": {role: describe([r for r in rows if r["role"] == role]) for role in role_cases.ROLES},
        "by_control": {
            control: describe([r for r in rows if r["control"] == control])
            for control in ("benign", "quoted_instruction")
        },
    }


def write_csv(path, arms):
    with path.open("x", encoding="utf-8", newline="") as handle:
        fields = [
            "model", "status", "role", "cases", "first_pass", "final_pass",
            "first_pass_rate", "final_pass_rate", "precision", "recall", "f1", "evidence_f1",
            "correction_attempts", "correction_rescues", "final_invalid_cases",
            "inference_error_attempts", "input_tokens_observed", "output_tokens_observed",
            "p50_case_ms", "p95_case_ms", "peak_machine_gpu_used_mib", "peak_machine_ram_used_mib",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for arm in arms:
            for role, metrics in {"all": arm["all"], **arm["by_role"]}.items():
                values = {
                    "model": arm["model"], "status": arm["status"], "role": role,
                    **metrics,
                    "precision": metrics["final_affirmative"]["precision"],
                    "recall": metrics["final_affirmative"]["recall"],
                    "f1": metrics["final_affirmative"]["f1"],
                    "evidence_f1": metrics["final_evidence_f1"],
                    **(arm["resources"] if role == "all" else {}),
                }
                writer.writerow({field: values.get(field) for field in fields})


def plot(path, arms):
    """Optional chart; analysis remains reproducible without matplotlib."""
    try:
        import matplotlib
        matplotlib.use("svg")
        from matplotlib import pyplot as plt
    except ImportError:
        return False
    complete = [arm for arm in arms if arm["status"] == "complete"]
    if not complete:
        return False
    labels = [arm["model"] for arm in complete]
    x = list(range(len(labels)))
    figure, (quality, latency) = plt.subplots(1, 2, figsize=(10, 4.2), layout="constrained")
    width = .32
    quality.bar([i - width / 2 for i in x], [100 * a["all"]["first_pass_rate"] for a in complete],
                width, label="First response", color="#2563EB")
    quality.bar([i + width / 2 for i in x], [100 * a["all"]["final_pass_rate"] for a in complete],
                width, label="After contract retry", color="#14B8A6")
    quality.set(ylabel="Exact case passes (%)", ylim=(0, 105), title="Synthetic role contracts")
    quality.legend(loc="lower right", fontsize=8)
    latency.bar(x, [a["all"]["p95_case_ms"] / 1000 for a in complete], width=.60, color="#7C3AED")
    latency.set(ylabel="Seconds", title="p95 case time, including retries")
    for axis in (quality, latency):
        axis.set_xticks(x, labels, rotation=15, ha="right")
        axis.grid(axis="y", alpha=.25)
        axis.set_axisbelow(True)
    figure.savefig(path, format="svg", metadata={"Date": None})
    plt.close(figure)
    return True


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("calibration", "heldout"), default="heldout")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "roles_frozen.json")
    parser.add_argument("--arm", type=Path, action="append", help="Directory with run.json and cases.jsonl")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--replicates", type=int, default=5000)
    args = parser.parse_args()
    if args.replicates < 1:
        parser.error("--replicates must be positive")
    manifest = read_json(args.manifest)
    if sha256(ROOT / "role_cases.py") != manifest["source_sha256"]:
        raise ValueError("Local scorer differs from the frozen source")
    fixtures = {
        entry["case"]["id"]: entry["case"]
        for entry in manifest["cases"] if entry["case"]["split"] == args.split
    }
    arms = [
        load_arm(directory, args.manifest, manifest, fixtures, args.split)
        for directory in (args.arm or sorted(path.parent for path in (ROOT / "results").glob(f"*/{args.split}/run.json")))
    ]
    if not arms:
        parser.error("no matching model run directories")
    if len({arm["model"] for arm in arms}) != len(arms):
        raise ValueError("Model names must be unique within a comparison")
    complete = [a for a in arms if a["status"] == "complete"]
    if len({json.dumps(a["ollama"], sort_keys=True) for a in complete}) > 1:
        raise ValueError("Complete arms use different Ollama versions")
    comparisons = [
        {"reference": ref["model"], "candidate": candidate["model"],
         **paired_bootstrap(ref["rows"], candidate["rows"], args.replicates)}
        for ref, candidate in itertools.combinations(complete, 2)
    ]
    summary = {
        "manifest_sha256": sha256(args.manifest),
        "split": args.split,
        "method": "paired, role-stratified family-cluster percentile bootstrap over complete arms",
        "latency_scope": "per-case sum of measured HTTP times including any retries; no distinct queue timing",
        "sampling_limits": "small authored synthetic families; intervals are exploratory, not population estimates",
        "arms": [summarize(a) for a in arms],
        "paired_comparisons": comparisons,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output / "summary.csv", summary["arms"])
    summary["chart_generated"] = plot(args.output / "comparison.svg", summary["arms"])
    with (args.output / "summary.json").open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    for arm in summary["arms"]:
        a = arm["all"]
        print(f"{arm['model']} [{arm['status']}] {a['first_pass']}/{a['cases']} first, "
              f"{a['final_pass']}/{a['cases']} final, p95 {a['p95_case_ms']} ms")


if __name__ == "__main__":
    main()

