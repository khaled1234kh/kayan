from copy import deepcopy
import json

import pytest

from eval import cloud_automatic_proof_v1 as base
from eval.attack_evidence_v2 import compact
from eval.cloud_citation_grounding_v3 import address_schema, prepare, score_case, validate_probe


def atoms(name):
    case, _, _ = base.fixture(name)
    fields = ("technique", "anchor", "role", "value", "cite")
    return [dict(zip(fields, row)) for row in sorted(base.role_key(case))]


def score(name, facts):
    return score_case(name, compact({"facts": facts}))


def test_every_role_uses_the_same_case_registry():
    for name in ("windows", "slate", "windows_incomplete", "windows_authorized"):
        _, _, evidence = base.fixture(name)
        for variant in address_schema(evidence)["$defs"].values():
            for field in ("anchor", "cite"):
                assert variant["properties"][field]["enum"] == sorted(evidence)


@pytest.mark.parametrize("bad", ["Windows Security event", "E2.1", "E9.1"])
def test_prose_unknown_and_withheld_record_ids_are_rejected(bad):
    facts = atoms("windows_incomplete")
    facts[0]["cite"] = bad
    with pytest.raises(ValueError, match="outside the case registry"):
        score("windows_incomplete", facts)


def test_wrong_existing_mechanic_address_matches_schema_but_not_occurrence():
    case = "slate"
    fact = next(x for x in atoms(case) if x["technique"] == "T1486" and x["role"] == "mechanic")
    bad = {**fact, "anchor": "E4.1", "cite": "E4.1"}
    row = score(case, [bad])
    assert row["schema_valid"] and row["error"] is None
    assert row["role_hits"] == [] and row["role_extras"]
    assert row["verdict"]["review_items"] == []


def test_cross_occurrence_and_wrong_role_citations_cannot_release_claim():
    facts = atoms("slate")
    next(x for x in facts if x["technique"] == "T1490" and x["role"] == "outcome")["cite"] = "E2.1"
    next(x for x in facts if x["technique"] == "T1486" and x["role"] == "authorization")["cite"] = "E2.1"
    row = score("slate", facts)
    assert row["schema_valid"] and row["error"] is None
    assert row["semantic_withheld"] == ["T1486", "T1490"]
    assert row["verdict"] is None


@pytest.mark.parametrize(("case", "eligible"), [
    ("slate", 2), ("windows_authorized", 0), ("windows_incomplete", 0),
])
def test_complete_and_adverse_role_sets_use_signed_off_admission(case, eligible):
    row = score(case, atoms(case))
    assert row["error"] is None
    assert len(row["verdict"]["review_items"]) == eligible


def test_empty_answer_abstains_when_support_is_missing():
    assert score("windows_incomplete", [])["verdict"]["batch_state"] == "abstained"


def test_probe_distinguishes_exact_and_existing_but_wrong_addresses():
    from tests.private_artifacts import require_private
    require_private('.build/cloud-reasoning-budget-v2.json')
    parent = base.read(base.ROOT / ".build/cloud-reasoning-budget-v2.json")
    bundle = prepare(parent)
    prompt = json.loads(bundle["request"]["messages"][1]["content"])
    assert len(prompt["observations"]) == 4
    assert all(x in prompt["observations"] for x in ("E2.1", "E4.1"))
    assert "expected" not in prompt
    wire = {"model": bundle["request"]["model"],
            "choices": [{"finish_reason": "stop", "message": {"content": compact(bundle["expected"])}}],
            "usage": {"completion_tokens_details": {"reasoning_tokens": 0}}}
    assert validate_probe(200, {}, wire, bundle)["role_hits"]
    wrong = deepcopy(bundle["expected"])
    wrong["facts"][0].update(anchor="E4.1", cite="E4.1")
    wire["choices"][0]["message"]["content"] = compact(wrong)
    with pytest.raises(ValueError, match="expected nonempty"):
        validate_probe(200, {}, wire, bundle)
