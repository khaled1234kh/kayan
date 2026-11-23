"""Report paired per-role uncertainty using saved defensive benchmark outputs."""
from argparse import ArgumentParser
import itertools
from pathlib import Path

import analyze_models as a
import model_bench as benchmark
from role_cases import ROLES


def run(paths, output):
    manifest_path = benchmark.ROOT / "data/roles_frozen.json"
    manifest = a.read_json(manifest_path)
    fixtures = {entry["case"]["id"]: entry["case"]
                for entry in manifest["cases"] if entry["case"]["split"] == "heldout"}
    arms = [a.load_arm(path, manifest_path, manifest, fixtures, "heldout") for path in paths]
    if any(arm["status"] != "complete" for arm in arms):
        raise ValueError("Per-role comparison requires complete arms")
    output.parent.mkdir(parents=True, exist_ok=True)
    comparisons = {}
    for role in ROLES:
        role_arms = [(arm["model"], [row for row in arm["rows"] if row["role"] == role]) for arm in arms]
        comparisons[role] = [{
            "reference": name_a, "candidate": name_b,
            **a.paired_bootstrap(rows_a, rows_b),
        } for (name_a, rows_a), (name_b, rows_b) in itertools.combinations(role_arms, 2)]
    benchmark.write_json(output, {
        "scope": "Exploratory pairwise results. Within-role authored families are the bootstrap unit. "
                 "Intervals are unadjusted for multiple comparisons and do not establish role winners.",
        "manifest_sha256": a.sha256(manifest_path), "comparisons": comparisons,
    })


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.arm, args.output)
