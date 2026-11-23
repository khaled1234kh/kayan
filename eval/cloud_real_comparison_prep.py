"""Prepare synthetic matched requests and replay local results without network access."""
import argparse
import json
from pathlib import Path

from ai.mitre.ranking import FieldBM25
from eval import cloud_automatic_proof_v1 as base
from eval.ai_confirmation_inputs import catalogue
from eval.attack_evidence_v2 import Response, parse
from eval.attack_experiment_v2 import dump, reference
from eval.cloud_extraction_v2 import ExtractionV2, STRUCTURED, score_cell

LOCK = base.ROOT / "eval/fixtures/ai/cloud_real_comparison_v1.json"
LEDGER = ".build/cloud-extraction-v2.jsonl"


def verified_inputs():
    plan = base.read(LOCK)
    for path, digest in plan["files"].items():
        if base.sha(base.ROOT / path) != digest:
            raise ValueError(f"Frozen comparison input changed: {path}")
    return plan


def prepare(plan):
    design = base.read(base.LOCK)
    _, techniques = catalogue()
    lookup = {technique.technique_id: technique for technique in techniques}
    ranker = FieldBM25(techniques)
    saved = [parse(line) for line in (base.ROOT / LEDGER).read_bytes().splitlines()]
    local = {(row["case"], row["event"]): row for row in saved if row.get("arm") == "direct"}
    rows = {}
    for name in plan["cases"]:
        cell = design["cases"][name]
        case, payloads, evidence = base.fixture(name)
        hypotheses = cell["hypotheses"]
        display = {tid: {"mechanic": base.MECHANICS[tid], "requires_process_link": linked}
                   for tid, linked in hypotheses.items()}
        local_request = base.request(base.DIRECT, Response, evidence, display)
        start = local[name, "start"]
        result = local[name, "result"]
        if start["request"] != local_request or result["error"] is not None:
            raise ValueError(f"Frozen baseline mismatch for {name}")
        ranked = ranker(evidence)[:plan["retrieval_k"]]
        refs = [reference(lookup[item[0]]) for item in ranked]
        common = {"observations": evidence, "hypotheses": display}
        variants = {
            "B": (base.DIRECT, common, Response),
            "C": (base.DIRECT, {**common, "references": refs}, Response),
            "D": (STRUCTURED, common, ExtractionV2),
        }
        # Neutral request envelopes for later provider capability review.
        # This module has no provider client or send action.
        envelopes = {
            arm: {"model": plan["cloud_model"], "temperature": base.OPTIONS["temperature"],
                  "max_output_tokens": base.OPTIONS["num_predict"],
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": json.dumps(body, ensure_ascii=True)}],
                  "schema": schema.model_json_schema()}
            for arm, (system, body, schema) in variants.items()
        }
        manifest, authority = base.issue(case)

        def admit(raw):
            return base.evaluate_in_custody(raw, manifest, payloads, authority=authority)

        wire = result["wire"]
        metrics = score_cell("direct", wire["response"], evidence, hypotheses, base.role_key(case), admit)
        if any(metrics[key] != result[key] for key in ("error", "schema_valid", "assembled", "verdict")):
            raise ValueError(f"Archived local result did not reproduce for {name}")
        oracle = admit(base.proposal(**cell["oracle"]))
        rows[name] = {
            "local_request": local_request, "local_result_replay": metrics,
            "local_measured": {"wall_seconds": result["wall_seconds"],
                               "prompt_tokens": wire["prompt_eval_count"], "output_tokens": wire["eval_count"]},
            "cloud_drafts": envelopes, "lexical_references": refs,
            "authored_control": oracle, "cloud_results": None,
        }
    return {"manifest_sha256": base.sha(LOCK), "cloud_status": "blocked", "cases": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    dump(args.output, prepare(verified_inputs()))


if __name__ == "__main__":
    main()
