"""Tests for the offline decision-evaluation framework."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVAL / "sovereign-80-matched"))

from eval.decision_eval import (  # noqa: E402
    RUBRIC_VERSION, annotation, charts, confusion, dataset, deepeval_adapter,
    experiments, protocol, reanalysis, redteam, scoring, statistics,
    versioned_scorer,
)
from eval.decision_eval.build_provisional_dataset import build_cases  # noqa: E402

DATASET = EVAL / "decision_eval" / "datasets" / "decision_cases_v0_1.jsonl"
REPORTS = EVAL / "decision_eval" / "reports"


@pytest.fixture(scope="module")
def cases():
    return dataset.load_dataset(DATASET)


def _perfect_output(case):
    out = {"decisions": [
        {"item_id": row["item_id"], "label": row["label"], "evidence_ids": row["evidence_ids"]}
        for row in case["ground_truth"]["decisions"]
    ]}
    if case["agent"] == "Planner":
        out["execution_order"] = case["ground_truth"]["execution_order"]
    return out


# ---------- protocol ----------

def test_protocol_freeze_and_budget():
    cfg = protocol.InferenceConfig(
        config_id="test", model_id="m", model_revision="r", provider="p", engine="e",
        quantization="q", system_messages=("sys",), user_message="user",
        schema={"type": "object"}, dataset_revision="d", scorer_version="s",
    )
    frozen = cfg.freeze()
    assert len(frozen["config_sha256"]) == 64
    assert len(frozen["prompt_bytes_sha256"]) == 64
    budget = protocol.preflight_budget(cfg, cases=80, runs=3,
                                       prompt_tokens_per_case=400, output_tokens_per_case=384)
    assert budget["worst_case_requests"] == 240
    assert budget["authorization_required"] is True
    assert float(budget["catalogue_equivalent_egp"]) > 0


def test_protocol_rejects_nonzero_temperature():
    with pytest.raises(ValueError):
        protocol.InferenceConfig(
            config_id="x", model_id="m", model_revision="r", provider="p", engine="e",
            quantization="q", system_messages=("sys",), user_message="user", schema={},
            dataset_revision="d", scorer_version="s", temperature=0.2,
        )


# ---------- confusion and statistics ----------

def test_confusion_matrix_and_metrics():
    result = confusion.classification_report(
        ["supported", "contradicted", "abstain", "supported"],
        ["supported", "contradicted", "supported", "supported"],
    )
    cm = result["confusion"]
    assert cm["labels"] == ["supported", "contradicted", "abstain"]
    assert sum(map(sum, cm["matrix"])) == 4
    assert cm["row_normalized"][0][0] == 1.0
    assert result["per_class"]["abstain"]["support"] == 1
    assert result["per_class"]["abstain"]["f1"] == 0.0
    null_report = confusion.classification_report(
        ["supported", "contradicted"], ["supported", "contradicted"],
        labels=["supported", "contradicted", "abstain"],
    )
    assert null_report["per_class"]["abstain"]["f1"] is None
    assert result["accuracy"] == 0.75
    assert result["micro_f1"] == 0.75


def test_aggregate_reports_pools_confusion():
    first = confusion.classification_report(["supported"], ["supported"])
    second = confusion.classification_report(["abstain"], ["abstain"])
    pooled = confusion.aggregate_reports([first, second])
    assert pooled["support"] == 2
    assert pooled["accuracy"] == 1.0


def test_abstention_metrics_null_safe():
    result = confusion.abstention_metrics(["supported", "abstain"], ["supported", "abstain"])
    assert result["counts"]["tp"] == 1
    assert result["abstention_coverage"] == 1.0
    assert confusion.abstention_metrics(["supported"], ["supported"])["abstention_coverage"] is None


def test_statistics():
    low, high = statistics.wilson_interval(72, 80)
    assert 0.7 < low < high < 1.0
    boot = statistics.paired_bootstrap([1, 0, 1, 0], replicates=100, seed=1,
                                       cluster=["a", "a", "b", "b"])
    assert boot["clusters"] == 2 and boot["unit"] == "scenario family"
    mcn = statistics.mcnemar_exact([True, True, False], [True, False, False])
    assert mcn["b_only_a"] == 1 and mcn["c_only_b"] == 0
    agree = statistics.judge_agreement([True, False, True, False], [True, False, False, False])
    assert agree["raw_agreement"] == 0.75
    assert agree["cohens_kappa"] is not None


# ---------- dataset ----------

def test_dataset_shape_and_manifest(cases):
    assert len(cases) == 40
    assert {case["agent"] for case in cases} == {"Planner", "Recon", "Web-App", "Network", "Reporting"}
    assert all(case["annotation_status"] == "provisional" for case in cases)
    assert dataset.verify_manifest(DATASET.parent)["decision_cases_v0_1.jsonl"] is True
    with pytest.raises(ValueError):
        dataset.load_dataset(DATASET, require_frozen=True)


def test_dataset_rejects_invalid_case(cases):
    bad = json.loads(json.dumps(cases[0]))
    bad["annotation_status"] = "frozen"
    bad["provenance"]["independent"] = True
    with pytest.raises(ValueError):
        dataset.validate_case(bad)


def test_legacy_cohort_audit():
    audit = dataset.audit_legacy_cohort()
    assert audit["cases"] == 18 and audit["families"] == 6
    assert audit["label_source"] == "AI-authored synthetic key"
    assert audit["fresh_unseen_holdout"] is False
    assert audit["verdict"] == "development_only"


# ---------- versioned scorer ----------

def test_versioned_scorer_perfect_and_empty(cases):
    for case in cases:
        assert versioned_scorer.score_versioned_case(case, _perfect_output(case))["exact_pass"] is True
        empty = {"decisions": [], **({"execution_order": []} if case["agent"] == "Planner" else {})}
        assert versioned_scorer.score_versioned_case(case, empty)["exact_pass"] is False


def test_versioned_scorer_distinguishes_errors(cases):
    case = next(c for c in cases if c["agent"] == "Reporting")
    output = _perfect_output(case)
    wrong = "abstain" if output["decisions"][0]["label"] != "abstain" else "include"
    output["decisions"][0]["label"] = wrong
    result = versioned_scorer.score_versioned_case(case, output)
    assert result["exact_pass"] is False
    assert result["metrics"]["label_fp"] >= 1 or result["metrics"]["label_fn"] >= 1


# ---------- DeepEval adapter ----------

def test_deepeval_offline_spec(cases):
    spec = deepeval_adapter.build_judge_metrics()
    assert spec["mode"] == "offline_spec_only"
    assert spec["deepeval_version"] == "4.3.4"
    assert spec["constructed"] == 0
    assert {row["class"] for row in spec["metrics"]} == {
        "GEval", "FaithfulnessMetric", "ContextualRelevancyMetric",
        "AnswerRelevancyMetric", "TaskCompletionMetric",
    }
    with pytest.raises(ValueError):
        deepeval_adapter.build_judge_metrics(allow_judge_calls=True, offline=True)


def test_deepeval_deterministic_metrics(cases):
    case = cases[0]
    metrics = deepeval_adapter.deterministic_metrics(case, _perfect_output(case))
    assert set(metrics) == set(deepeval_adapter.DETERMINISTIC_METRICS)
    assert all(0.0 <= value <= 1.0 for value in metrics.values())
    assert metrics["dependency_order"] == 1.0


def test_judge_agreement_report():
    result = deepeval_adapter.judge_disagreement_report(
        {"a": True, "b": False, "c": True}, {"a": True, "b": True, "c": True}
    )
    assert result["disagreements"] == ["b"]
    assert result["authority"].startswith("deterministic")


# ---------- experiments and red team ----------

def test_experiment_matrix():
    matrix = experiments.experiment_matrix()
    assert {exp["id"] for exp in matrix["experiments"]} == {"A", "B", "C", "D"}
    assert all(exp["runs"] == 3 for exp in matrix["experiments"])
    assert any(gate["status"] == "not_met" for gate in matrix["acceptance_gates"])
    assert matrix["experiments"][1]["status"].startswith("blocked")


def test_redteam_suite():
    suite = redteam.run_offline_suite()
    assert suite["cases"] == len(redteam.CASES) == 14
    assert len(suite["categories"]) == 14
    assert all(not outcome["passed"] for outcome in suite["null_response_outcomes"])
    case = redteam.CASES[0]
    good = {"decisions": [], "tool_calls": [], "signals": sorted(case.required), "published": False}
    assert redteam.check_response(case, good)["passed"] is True
    bad = {**good, "tool_calls": ["publish"], "published": True}
    assert redteam.check_response(case, bad)["passed"] is False


# ---------- annotation ----------

def _annotation_inputs(cases):
    packet = annotation.issue_blind_forms(cases)
    sheets = {}
    for slot in ("A", "B"):
        requests = []
        for row in packet["forms"][slot]["cases"]:
            case = next(c for c in cases if c["case_id"] == row["case_id"])
            truth = case["ground_truth"]["decisions"][0]
            requests.append({
                "case_id": row["case_id"], "label": truth["label"],
                "evidence_ids": truth["evidence_ids"], "rationale": "Reviewed the cited synthetic record.",
            })
        sheets[slot] = {"slot": slot, "issued_form_sha256": packet["forms"][slot]["form_sha256"],
                        "decisions": requests}
    return packet, sheets


def test_annotation_blind_forms_and_validation(cases):
    packet, sheets = _annotation_inputs(cases)
    assert "ground_truth" not in json.dumps(packet["forms"]["A"]["cases"])
    receipt = annotation.validate_annotation(
        sheets["A"], packet, slot="A", identity="Dr. Real Reviewer",
        qualification="security evaluation", completed_on="2026-11-23",
        returned_sha256=annotation.sha256_json(sheets["A"]), independently_reviewed=True,
    )
    assert receipt["cases"] == 40
    with pytest.raises(ValueError):
        annotation.validate_annotation(
            sheets["A"], packet, slot="A", identity="reviewer a",
            qualification="security evaluation", completed_on="2026-11-23",
            returned_sha256=annotation.sha256_json(sheets["A"]), independently_reviewed=True,
        )


def test_annotation_agreement_and_freeze_gate(cases):
    packet, sheets = _annotation_inputs(cases)
    agreement = annotation.compare_annotations(sheets["A"], sheets["B"], packet)
    assert agreement["raw_label_agreement"] == 1.0
    assert agreement["requires_adjudication"] is False
    adjudication = {
        "packet_sha256": packet["packet_sha256"],
        "agreement_sha256": agreement["agreement_sha256"],
        "adjudicator": "Prof. Real Adjudicator", "adjudicated_on": "2026-11-24",
        "label_version": "v1",
        "cases": [{"case_id": c["case_id"], "label": c["ground_truth"]["decisions"][0]["label"],
                   "evidence_ids": c["ground_truth"]["decisions"][0]["evidence_ids"],
                   "resolution": "score", "rationale": "Independent adjudication of the record."}
                  for c in cases],
    }
    receipt = annotation.validate_adjudication(
        adjudication, packet=packet, agreement=agreement,
        reviewer_dates=["2026-11-23", "2026-11-23"], cases=cases,
    )
    frozen = annotation.freeze_labels(cases, adjudication)
    assert receipt["cases"] == 40 and all(c["annotation_status"] == "frozen" for c in frozen)
    adjudication["adjudicated_on"] = "2026-11-22"
    with pytest.raises(ValueError):
        annotation.validate_adjudication(
            adjudication, packet=packet, agreement=agreement,
            reviewer_dates=["2026-11-23", "2026-11-23"], cases=cases,
        )


# ---------- frozen baseline and re-analysis shape ----------

def test_frozen_protocol_integrity():
    import frozen_protocol as fp
    manifest = fp.load_manifest()
    assert len(fp.heldout_entries(manifest)) == 80
    assert fp.MANIFEST.name == "roles_frozen.json"


def test_reanalysis_exact_baseline_matches_history():
    saved_root = Path(os.environ.get("KAYAN_SAVED_ROOT", ""))
    if not saved_root or not saved_root.exists():
        pytest.skip("local-only saved outputs unavailable (set KAYAN_SAVED_ROOT)")
    from eval.decision_eval.run_framework import run_reanalysis
    result = run_reanalysis(saved_root)
    cloud = next(arm for arm in result["arms"] if arm["arm"].startswith("SovereignEG"))
    assert cloud["exact"]["passes"] == 72
    assert cloud["exact"]["rate"] == 0.9
    assert cloud["invalid_outputs"] == 0
    assert len(result["comparisons"]) == 5


def test_charts_and_reports_exist():
    assert (REPORTS / "OFFLINE_REANALYSIS.md").exists()
    assert (REPORTS / "EXPERIMENT_MATRIX.json").exists()
    assert (REPORTS / "REDTEAM_SUITE.json").exists()
    svg = REPORTS / "charts" / "confusion_SovereignEG_Qwen3.8-27B-FP8.svg"
    assert svg.exists() and "<svg" in svg.read_text(encoding="utf-8")


def test_rubric_constants_stable():
    assert RUBRIC_VERSION == "role-contract-frozen+diagnostics-v1"
    assert scoring.CANONICAL == ("supported", "contradicted", "abstain")
