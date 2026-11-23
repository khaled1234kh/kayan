import pytest

from eval.attack_evidence_v2 import compact, parse
from eval.cloud_automatic_proof_v1 import assemble


def atom(role, value, cite, anchor="E1.1"):
    return {"technique": "T1486", "anchor": anchor, "cite": cite, "role": role, "value": value}


BASE = [
    atom("mechanic", "observed", "E1.1"),
    atom("actor", "adversary", "E2.1"),
    atom("authorization", "unauthorized", "E3.1"),
    atom("outcome", "completed", "E1.1"),
]
EVIDENCE = {f"E{i}.1": "fixture" for i in range(1, 5)}


def run(items, *, linked=False):
    raw, _, diagnostics = assemble(compact({"facts": items}), EVIDENCE, {"T1486": linked})
    return parse(raw)["mappings"], diagnostics["T1486:E1.1"]


def test_complete_group_needs_each_role_within_same_occurrence():
    mappings, _ = run(BASE)
    assert {row["cite"] for row in mappings} == {"E1.1", "E2.1", "E3.1"}
    mappings, diagnostics = run([*BASE[:-1], atom("outcome", "completed", "E1.1", anchor="E4.1")])
    assert not mappings
    assert diagnostics["missing_roles"] == ["outcome"]


def test_link_requirement_and_alternatives_and_adverse_are_retained():
    mappings, diagnostics = run(BASE, linked=True)
    assert not mappings and diagnostics["missing_roles"] == ["process_session"]
    mappings, diagnostics = run([*BASE, atom("actor", "adversary", "E4.1")])
    assert not mappings and len(diagnostics["alternative_groups"]) == 2
    mappings, diagnostics = run([*BASE, atom("authorization", "authorized", "E4.1")])
    assert not mappings and diagnostics["adverse_citations"] == ["E4.1"]


@pytest.mark.parametrize("bad", [
    atom("actor", "adversary", "E9.1"),
    atom("actor", "observed", "E2.1"),
    {**BASE[0], "approved": True},
    BASE[0],
])
def test_schema_addresses_and_duplicate_atoms_fail_closed(bad):
    with pytest.raises(ValueError):
        run([*BASE, bad])
