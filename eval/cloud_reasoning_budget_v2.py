"""Freeze and verify the reasoning-budget correction offline."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from eval.attack_experiment_v2 import dump, read, sha
from eval.cloud_frozen_diagnostic import BUNDLE_SHA, MANIFEST_SHA, MODEL, URL, outgoing
from eval.cloud_real_comparison_prep import LOCK
from eval.cloud_extraction_v2 import ExtractionV2

MANIFEST = Path(__file__).resolve().parent / "fixtures/ai/cloud_reasoning_budget_v2.json"


def prepare(original):
    diagnostics = []
    for case, row in original["cases"].items():
        for arm in ("B", "C", "D"):
            request = outgoing(row["cloud_drafts"][arm], arm)
            request.update(reasoning_effort="none", max_tokens=1024)
            diagnostics.append({"case": case, "arm": arm, "request": request})
    if len(diagnostics) != 12 or any(cell["request"]["model"] != MODEL for cell in diagnostics):
        raise ValueError("Unexpected parent schedule or model")
    probe = dict(diagnostics[2]["request"])
    if diagnostics[2]["arm"] != "D":
        raise ValueError("Probe requires the exact structured schema")
    probe["messages"] = [
        {"role": "system", "content": "Return one mechanic atom from the fictional observation using the provided schema. Use the exact technique, action address for both anchor and cite, and the mechanic value observed."},
        {"role": "user", "content": "Synthetic SOC observation E1.1: the Windows Security event log was cleared. Fixed hypothesis T1685.005. No other evidence is provided."},
    ]
    return {
        "version": "cloud-reasoning-budget/2", "destination": URL,
        "parent_manifest_sha256": MANIFEST_SHA, "parent_bundle_sha256": BUNDLE_SHA,
        "stage_a": {
            "request": probe,
            "expected": {"facts": [{"technique": "T1685.005", "anchor": "E1.1", "cite": "E1.1",
                                    "role": "mechanic", "value": "observed"}]},
        },
        "stage_b": diagnostics,
    }


def check_probe(http_status, headers, wire, expected):
    """Validate a preserved Stage A response without sending a request."""
    if http_status != 200 or wire.get("model") != MODEL:
        raise ValueError("Unexpected probe status or served model")
    header = {name.lower(): value.lower() for name, value in headers.items()}
    if ("x-output-clamped" in header or "x-plan-output-cap" in header
            or any(name in header.get(field, "") for name in ("reasoning_effort", "temperature")
                   for field in ("x-dropped-params", "x-mapped-params"))):
        raise ValueError("Probe configuration was clamped or modified")
    choice = wire["choices"][0]
    usage = wire["usage"]
    reasoning = usage.get("completion_tokens_details", {}).get("reasoning_tokens")
    if choice.get("finish_reason") != "stop" or type(reasoning) is not int or reasoning != 0:
        raise ValueError("Probe did not verify a complete zero-reasoning response")
    content = choice["message"]["content"]
    if ExtractionV2.model_validate_json(content).model_dump(exclude_none=True) != expected:
        raise ValueError("Probe did not return the expected nonempty structured answer")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--parent", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if sha(args.parent) != BUNDLE_SHA or sha(LOCK) != MANIFEST_SHA:
        raise ValueError("Parent comparison input changed")
    frozen = read(MANIFEST)
    if sha(Path(__file__)) != frozen["preparer_sha256"]:
        raise ValueError("Offline preparation source changed")
    prepared = prepare(read(args.parent))
    expected = frozen["bundle_sha256"]
    encoded = (json.dumps(prepared, ensure_ascii=True, indent=2) + "\n").encode("ascii")
    if sha256(encoded).hexdigest() != expected:
        raise ValueError("Prepared request bundle differs from the freeze")
    dump(args.output, prepared)
    print(expected)


if __name__ == "__main__":
    main()
