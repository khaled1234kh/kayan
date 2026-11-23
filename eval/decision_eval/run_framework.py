"""Reproducible offline framework runner.

Default mode performs zero network or provider calls. It regenerates the
provisional dataset, re-analyses saved local outputs, freezes the experiment
matrix and red-team suite, renders charts and writes SHA-256 manifests.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import RUBRIC_VERSION
from .build_provisional_dataset import main as build_dataset
from .charts import write_charts
from .dataset import sha256_file, write_manifest
from .experiments import experiment_matrix
from .reanalysis import arm_report, compare_arms, load_saved_arm, markdown_summary
from .redteam import run_offline_suite

EVAL_ROOT = Path(__file__).resolve().parent.parent
FRAMEWORK_ROOT = EVAL_ROOT / "decision_eval"
REPORT_DIR = FRAMEWORK_ROOT / "reports"
CHART_DIR = REPORT_DIR / "charts"

# Local-only saved outputs are never copied into the repository. Callers set
# KAYAN_SAVED_ROOT to the directory holding `.build/` and the frozen results.
DEFAULT_SAVED_ROOT = Path(os.environ.get("KAYAN_SAVED_ROOT", ""))
LOCAL_ARMS = {
    "qwen2.5:7b": "qwen2_5-7b",
    "qwen3:8b": "qwen3-8b",
    "granite4.2:8b": "granite4_2-8b",
    "llama3.1:8b": "llama3_1-8b",
    "qwen2.5:1.5b": "qwen2_5-1_5b",
}


def _frozen_protocol():
    if str(EVAL_ROOT / "sovereign-80-matched") not in sys.path:
        sys.path.insert(0, str(EVAL_ROOT / "sovereign-80-matched"))
    import frozen_protocol  # type: ignore
    return frozen_protocol


def run_reanalysis(saved_root: Path) -> dict:
    fp = _frozen_protocol()
    manifest = fp.load_manifest()
    fixtures = {entry["case"]["id"]: entry["case"] for entry in fp.heldout_entries(manifest)}
    cloud_path = saved_root / ".build" / "cloud-matched-2026-11-23-resumed" / "cases.jsonl"
    if not cloud_path.exists():
        raise FileNotFoundError(f"Saved cloud responses not found: {cloud_path}")
    arms: dict[str, list[dict]] = {
        "SovereignEG/Qwen3.8-27B-FP8": load_saved_arm(cloud_path, fixtures, "cloud"),
    }
    for label, directory in LOCAL_ARMS.items():
        path = saved_root / "eval" / "reference" / "role-benchmark" / "results" / directory / "heldout" / "cases.jsonl"
        arms[label] = load_saved_arm(path, fixtures, label)
    reports = [arm_report(arms[name], name) for name in arms]
    comparisons = [
        {"candidate": "SovereignEG/Qwen3.8-27B-FP8", "reference": name,
         **compare_arms(arms["SovereignEG/Qwen3.8-27B-FP8"], arms[name])}
        for name in LOCAL_ARMS
    ]
    return {
        "study": "offline-reanalysis-2026-11-23",
        "rubric_version": RUBRIC_VERSION,
        "manifest_sha256": fp.EXPECTED_MANIFEST_SHA,
        "dataset": "frozen 80-case role holdout (authored synthetic, retrospective)",
        "source": "saved local request ledgers and saved cloud responses only; zero new requests",
        "arms": reports,
        "comparisons": comparisons,
    }


def write_json(name: str, value: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-root", type=Path,
                        default=Path(os.environ.get("KAYAN_SAVED_ROOT", str(DEFAULT_SAVED_ROOT))),
                        help="Directory holding local-only saved outputs (never copied into the repo)")
    parser.add_argument("--skip-reanalysis", action="store_true",
                        help="Skip re-analysis when saved outputs are unavailable")
    args = parser.parse_args()

    build_dataset()
    written: list[Path] = []
    written.append(write_json("EXPERIMENT_MATRIX.json", experiment_matrix()))
    written.append(write_json("REDTEAM_SUITE.json", run_offline_suite()))

    if not args.skip_reanalysis:
        result = run_reanalysis(args.saved_root)
        written.append(write_json("OFFLINE_REANALYSIS.json", result))
        REPORT_DIR.joinpath("OFFLINE_REANALYSIS.md").write_text(
            markdown_summary(result), encoding="utf-8")
        written.append(REPORT_DIR / "OFFLINE_REANALYSIS.md")
        for chart in write_charts(result, CHART_DIR):
            written.append(chart)

    manifest_files = [path for path in written] + [
        FRAMEWORK_ROOT / "datasets" / "decision_cases_v0_1.jsonl",
    ]
    write_manifest([path for path in manifest_files if path.exists()], REPORT_DIR / "SHA256SUMS.txt")
    print(f"Wrote {len(manifest_files)} framework artifacts under {REPORT_DIR}")


if __name__ == "__main__":
    main()
