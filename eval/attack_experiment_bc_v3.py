"""Prepare and audit the fixed-technique diagnostic. This module has no inference transport."""
import argparse
import json
from itertools import chain

from eval.attack_evidence_v2 import BOUNDARY_RESERVE, score, spans
from eval.attack_experiment_a_v3 import OUT as A_OUT, preflight as audit_a_inputs
from eval.attack_experiment_v2 import LOCK, ROOT, SYSTEM, compact, dump, read, reference, sha

PAIRS = (
    ("cedar", "T1685.005"), ("flint", "T1685.005"),
    ("birch", "T1098.003"), ("silver", "T1098.003"),
    ("ochre", "T1114.003"), ("hazel", "T1114.003"),
    ("moss", "T1113"), ("larch", "T1113"),
)
FOLDER = ROOT / "eval/reports/attack_diagnostics_bc_v3_20261120"
REQUESTS = FOLDER / "fixed-technique-requests.json"
SYSTEM_BC = (
    SYSTEM.replace(" You may use an active technique outside the shortlist.", "")
    + " Evaluate only the single technique in the references. Does the observation evidence "
    "support that technique as completed, attributable adversary behavior? If it does, return that "
    "technique ID with the source statements that jointly establish the finding. Otherwise return an "
    "empty mappings array. Use no other technique ID."
)
A_HASHES = {
    "attempts.jsonl": "4e7cb6d9fcdbb33f7dc02cef39c4449c50a358034759012666a1f79195bc7202",
    "authorization.json": "406731d1ff1ce48a8a4932fa25201967d80f88f646c096b2829e6d0315ab92c0",
    "completion.json": "397b51d1708d914802a9debde5453f0e9ddb2b2e5683c0b65320f27b292c80e8",
    "comparison.json": "634bc5b4b350dd00311a8a6e5266b8358c43a0c2a862e442174c79a22de34370",
}


def build_manifest():
    registered, _, records, labels, lookup = audit_a_inputs()
    for name, digest in A_HASHES.items():
        if sha(A_OUT / name) != digest:
            raise ValueError(f"Experiment A hash mismatch for {name}")
    requests, bounds = [], {}
    options = registered["options"]
    for sequence, (case, technique) in enumerate(PAIRS, 1):
        expected = {technique} if sequence % 2 else set()
        if labels[case]["targets"].keys() != expected:
            raise ValueError(f"Frozen rubric differs from protocol contrast for {case}")
        data = compact({"observations": spans(records[case]), "references": [reference(lookup[technique])]})
        if "<|" in data:
            raise ValueError(f"Reserved prompt delimiter in {case}")
        prompt = f"<|im_start|>system\n{SYSTEM_BC}<|im_end|>\n<|im_start|>user\n{data}<|im_end|>\n<|im_start|>assistant\n"
        bound = len(prompt.encode("utf-8")) + BOUNDARY_RESERVE
        if bound + options["num_predict"] > options["num_ctx"]:
            raise ValueError(f"Context bound exceeded in {case}")
        output_bound = registered["feasibility"][case]["witness_output_token_upper_bound"]
        if output_bound > options["num_predict"]:
            raise ValueError(f"Witness failed output feasibility in {case}")
        bounds[case] = {"prompt_token_upper_bound": bound, "witness_output_token_upper_bound": output_bound}
        requests.append({"sequence": sequence, "case": case, "fixed_technique": technique,
                         "request": {"model": registered["model"], "raw": True, "stream": False, "prompt": prompt,
                                     "format": registered["schema"], "options": options}})
    return {"protocol": "attack-diagnostics-v3.0", "experiment": "B/C", "request_count": len(requests),
            "requests": requests}, bounds


def interpret(case_records, label, active_techniques, technique, raw, *, execution_error=None):
    """Score archived text. Transport and finish validation supply execution_error before grading."""
    result = score(case_records, label, raw, active_techniques, execution_error=execution_error)
    off_target = sorted(set(result["selected"]) - {technique})
    valid = result["contract"] and not off_target
    positive = technique in label["targets"]
    selected = technique in result["selected"]
    complete = technique in result["completed"]
    keyed = {row["cite"] for row in result["trace"]
             if row["technique"] == technique and row["status"] == "keyed_support"}
    missing = []
    if positive:
        spec = label["targets"][technique]
        for group in spec["groups"]:
            absent = sorted(set(group) - keyed)
            missing.append({
                "missing_statements": absent,
                "missing_roles": sorted(set(chain.from_iterable(spec["atoms"][ref] for ref in absent))),
                "required_records": sorted({ref.split(".")[0] for ref in group}),
                "missing_records": sorted({ref.split(".")[0] for ref in group}
                                          - {ref.split(".")[0] for ref in set(group) & keyed}),
            })
    return {
        "valid": valid,
        "invalid_reason": result["error"] or ("off_target_technique" if off_target else None),
        "complete_positive": valid and positive and complete,
        "correct_negative_abstention": valid and not positive and result["abstain"],
        "false_mapping_on_negative_case": valid and not positive and selected,
        "positive_fixed_id_selected": valid and positive and selected,
        "positive_fixed_id_incomplete": valid and positive and selected and not complete,
        "off_target_techniques": off_target,
        "relevant_citations": result["keyed"] + result["corroborating"],
        "unsupported_citations": result["bad_cites"],
        "unsupported_claims": result["unsupported"],
        "missing_by_alternative": missing if result["contract"] else None,
        "v2_trace": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "audit"))
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("Assertions must be enabled for historical preflight checks")
    manifest, bounds = build_manifest()
    if args.operation == "prepare":
        FOLDER.mkdir(exist_ok=True)
        dump(REQUESTS, manifest)
    elif REQUESTS.read_bytes() != (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8"):
        raise ValueError("Request manifest differs from the audited protocol inputs")
    print(f"{len(manifest['requests'])} requests SHA-256 {sha(REQUESTS)}")
    print(f"Frozen v2 registration SHA-256 {sha(LOCK)}")
    print(bounds)


if __name__ == "__main__":
    main()
