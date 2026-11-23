from copy import deepcopy

import pytest

from eval import cloud_automatic_proof_v1 as v1
from eval.attack_evidence_v2 import compact
from eval.cloud_extraction_v2 import normalize_v2, score_cell


def fixture(name="windows"):
    case, payloads, evidence = v1.fixture(name)
    key = v1.role_key(case)
    raw, authority = v1.issue(case)
    hypotheses = {t: False for t, *_ in key}

    def admit(claims):
        return v1.evaluate_in_custody(claims, raw, payloads, authority=authority)

    atoms = [dict(zip(("technique", "anchor", "role", "value", "cite"), item)) for item in sorted(key)]
    return atoms, evidence, hypotheses, key, admit


def test_reviewed_positive_and_authorized_control():
    for name, expected in [("windows", 1), ("windows_authorized", 0), ("windows_incomplete", 0)]:
        atoms, *inputs = fixture(name)
        result = score_cell("v2", compact({"facts": atoms}), *inputs)
        assert result["error"] is None
        assert len(result["verdict"]["review_items"]) == expected


def test_role_value_and_approval_schema_controls():
    atoms, evidence, *_ = fixture()
    actor = next(item for item in atoms if item["role"] == "actor")
    with pytest.raises(ValueError):
        normalize_v2(compact({"facts": [{**actor, "value": "authorized"}]}), evidence)
    with pytest.raises(ValueError):
        normalize_v2(compact({"facts": [{**actor, "reviewed": True}]}), evidence)


@pytest.mark.parametrize(("role", "field", "value"), [
    ("actor", "identity_quote", "invented name"),
    ("authorization", "scope_quote", "invented authority window"),
])
def test_invented_quote_is_rejected(role, field, value):
    atoms, *inputs = fixture()
    next(item for item in atoms if item["role"] == role)[field] = value
    result = score_cell("v2", compact({"facts": atoms}), *inputs)
    assert result["verdict"] is None and "absent from cited record" in result["error"]


@pytest.mark.parametrize(("role", "change"), [
    ("actor", {"cite": "E1.2"}),
    ("authorization", {"cite": "E2.1"}),
])
def test_existing_but_unrelated_cite_cannot_supply_proof(role, change):
    atoms, *inputs = fixture()
    next(item for item in atoms if item["role"] == role).update(change)
    result = score_cell("v2", compact({"facts": atoms}), *inputs)
    assert result["error"] is None
    assert result["semantic_withheld"] == ["T1685.005"]
    assert result["verdict"] is None


def test_missing_outcome_wrong_anchor_contradiction_and_duplicates():
    atoms, *inputs = fixture()
    partial = [item for item in atoms if item["role"] != "outcome"]
    out = score_cell("v2", compact({"facts": partial}), *inputs)
    assert out["groups"]["T1685.005:E1.1"]["missing_roles"] == ["outcome"]
    wrong = deepcopy(atoms)
    next(item for item in wrong if item["role"] == "mechanic")["anchor"] = "E1.2"
    assert score_cell("v2", compact({"facts": wrong}), *inputs)["error"]
    contrast = {**atoms[0], "role": "contradiction", "value": "adverse"}
    assert score_cell("v2", compact({"facts": [*atoms, contrast]}), *inputs)["verdict"]["batch_state"] == "abstained"
    assert score_cell("v2", compact({"facts": [*atoms, atoms[0]]}), *inputs)["error"] == "duplicate atom"


def test_cross_occurrence_and_uncertain_actor_do_not_promote():
    atoms, *inputs = fixture("slate")
    wrong = next(item for item in atoms if item["technique"] == "T1490" and item["role"] == "outcome")
    wrong["cite"] = "E2.1"
    actor = next(item for item in atoms if item["technique"] == "T1486" and item["role"] == "actor")
    actor["confidence"] = "uncertain"
    result = score_cell("v2", compact({"facts": atoms}), *inputs)
    assert result["semantic_withheld"] == ["T1490"]
    assert result["groups"]["T1486:E2.1"]["adverse_citations"]
    assert result["verdict"] is None
