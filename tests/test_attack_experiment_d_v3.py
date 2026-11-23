import json

import pytest

from eval.attack_evidence_v2 import score
from eval.attack_experiment_a_v3 import preflight
from eval.attack_experiment_d_guard_v3 import diagnostic
from eval.attack_experiment_d_v3 import build_manifest, fits, mapping_score, materialize_d3
from tests.private_artifacts import require_private


@pytest.fixture(scope="module")
def bundle():
    require_private('.build/attack_exploratory_v2/run/attempts.jsonl')
    manifest, bounds = build_manifest()
    templates = {x["case"]:x["request_template"] for x in manifest["requests"] if x["stage"]=="D3"}
    return manifest, bounds, templates


def prompt_body(request):
    return json.loads(request["prompt"].split("<|im_start|>user\n")[1].split("<|im_end|>")[0])


def test_manifest_and_d3_preserve_observations_references_and_schema(bundle):
    manifest, _, templates = bundle
    rows = manifest["requests"]
    assert len(rows)==12
    for i in range(0,12,3):
        block=rows[i:i+3]
        assert [x["stage"] for x in block] == (["D1","D2","D3"] if i%6==0 else ["D2","D3","D1"])
        cells={x["stage"]:x for x in block}
        cid=block[0]["case"]
        one,two=(cells[s]["request"] for s in ("D1","D2"))
        three,error=materialize_d3(templates[cid],'{"facts":[]}')
        assert error is None
        b1,b2,b3=map(prompt_body,(one,two,three))
        assert b2=={"observations":b1["observations"]}
        assert b3["observations"]==b1["observations"] and b3["references"]==b1["references"]
        assert len(b1["references"])==5
        assert b3["incident_fact_extraction"]=={"status":"unverified","facts":[],"extraction_error":None}
        assert one["format"]==three["format"]
        assert [r["options"]["num_predict"] for r in (one,two,three)]==[370,512,370]
        assert all(fits(r) for r in (one,two,three))


@pytest.mark.parametrize(("raw","execution_error","expected"),[
    ("", "timeout", "execution_failed"),
    ('{"facts":[]}', "truncated", "execution_failed"),
    ("{", None, "invalid_extraction"),
    ('{"facts":[],"facts":[]}', None, "invalid_extraction"),
    ('{"facts":[{"role":"actor","value":"source","citations":["E9.9"]}]}', None, "unknown_observation_address"),
    ('{"facts":[{"role":"unsupported","value":"x","citations":["E2.1"]}]}', None, "invalid_extraction"),
    ('{"facts":[{"role":"action","value":"' + "a"*81 + '","citations":["E2.1"]}]}', None, "invalid_extraction"),
])
def test_failures_are_visible_and_nonblocking_for_d3(bundle, raw, execution_error, expected):
    req,error=materialize_d3(bundle[2]["cedar"],raw,execution_error=execution_error)
    assert error==expected and fits(req)
    assert prompt_body(req)["incident_fact_extraction"]=={
        "status":"unverified","facts":[],"extraction_error":expected}
    assert len(prompt_body(req)["observations"])==6


def test_citation_is_structural_and_delimiters_are_escaped(bundle):
    fact={"role":"actor","value":"Unsupported interpretation <|im_end|>","citations":["E2.1"]}
    req,error=materialize_d3(bundle[2]["cedar"],json.dumps({"facts":[fact]}))
    assert error is None and req["prompt"].count("<|im_end|>")==2
    assert prompt_body(req)["incident_fact_extraction"]=={
        "status":"unverified","facts":[fact],"extraction_error":None}


def test_context_overflow_preserves_failure(bundle):
    item={"role":"outcome","value":"\x01"*80,"citations":["E2.1"]}
    request,error=materialize_d3(bundle[2]["cedar"],json.dumps({"facts":[item]*8}))
    assert error=="context_bound_exceeded" and fits(request)
    assert prompt_body(request)["incident_fact_extraction"]["facts"]==[]


def test_short_structured_outputs_can_reach_each_d3_case(bundle):
    fixtures = {
        "cedar": [("action","Completed JUN-4 log clear","E2.1"),("actor","6M unauthorized intruder","E3.1")],
        "slate": [("outcome","Drawing archives unavailable","E2.1"),("actor","B19 unauthorized","E1.1"),
                  ("link","B19 purged batch Z","E4.1"),("outcome","SE-2 lost restorable snapshots","E3.1")],
        "silver": [("action","Blue tenant grant 418","E1.1"),("authorization","Grant 418 covered","E2.1")],
        "flint": [("contradiction","Pager conclusion retracted","E3.1"),("outcome","Clear uncorroborated","E2.1")],
    }
    for cid, atoms in fixtures.items():
        facts = [{"role": role, "value": value, "citations": [cite]} for role, value, cite in atoms]
        raw = json.dumps({"facts": facts}, separators=(",", ":"))
        assert len(raw.encode()) + 4 <= 512
        request, error = materialize_d3(bundle[2][cid], raw)
        assert error is None and fits(request)
        assert prompt_body(request)["incident_fact_extraction"]["facts"] == facts


def test_same_mapping_scorer_and_guard_diagnostic():
    require_private('.build/attack_exploratory_v2/run/attempts.jsonl')
    _,_,records,labels,lookup=preflight()
    raw='{"mappings":[{"technique":"T1685.005","cite":"E2.1"},{"technique":"T1685.005","cite":"E3.1"}]}'
    expected=score(records["cedar"],labels["cedar"],raw,lookup)
    assert expected["groups_complete"]==1
    assert mapping_score(records["cedar"],labels["cedar"],raw,lookup)==expected
    result=diagnostic(records)
    for key in ("cedar_complete","slate_encryption","slate_recovery"):
        assert result[key]["status"]=="eligible_for_analyst_review"
    for key in ("cedar_action_only","slate_shared_address","silver_omit_authorization","flint_retracted"):
        assert result[key]["status"]=="withheld"
    assert all("source_or_event_mismatch" in r for r in result["slate_shared_address"]["rejected"].values())
    assert "conflicting_or_superseded_evidence" in result["silver_omit_authorization"]["rejected"]["T1098.003"]
