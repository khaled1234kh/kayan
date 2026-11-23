"""V2 scientific regressions. All predictions and transports in these tests are constructed."""
from collections import Counter
from copy import deepcopy
from datetime import date
import json

import httpx
import pytest
from pydantic import ValidationError

from ai.mitre.stix import MitreTechnique
from eval import attack_evidence_v2 as v2
from eval import attack_experiment_v2 as ex
from eval.ai_confirmation_review import Adjudication, RUBRIC, validate_adjudication
from eval.ai_confirmation_scoring import score_case
from eval.ai_retrieval_mapping import Prediction

T = "T1685.005"
R = {"E1": ["The journal was cleared.", "The keyboard was serviced."],
     "E2": ["The session belonged to the unauthorized intruder."],
     "E3": ["Separate authenticated custody covers the action, outcome and hostile actor."]}
TARGET = {"groups": [["E1.1", "E2.1"], ["E3.1"]], "atoms": {
    "E1.1": ["action","asset","outcome"], "E2.1": ["actor","authorization"], "E3.1": sorted(v2.REQUIRED)}}
LABEL = {"targets": {T: TARGET}, "disposition": "confirmed", "rationale": "Mock adjudication only.",
         "exceptions": {T: {"E1.2": "topic_only"}}}


def answer(*refs):
    return v2.compact({"mappings": [v2.entry(T, r) for r in refs]})


def old_label(groups):
    old = Adjudication(rubric=RUBRIC, label_version="mock", packet_sha256="a"*64, agreement_sha256="b"*64,
                       adjudicator="Mock", adjudicated_on="2026-11-20",
                       cases=[{"id":"mock","resolution":"score","disposition":"confirmed_adversary",
                               "evidence_sets":groups,"rationale":"Synthetic unit fixture"}])
    old_records = {r:" ".join(lines) for r, lines in R.items()}
    return validate_adjudication(old, {"mock": old_records}, set(groups), packet_hash="a"*64, agreement_hash="b"*64,
                                 after_date=date(2026,11,20))["mock"]


def joint():
    return {"groups": [["E1.1","E2.1"]], "atoms": {"E1.1":["action","asset","outcome"],"E2.1":["actor","authorization"]}}


def test_ten_entries_reproduce_v1_mismatch_and_v2_rejects_before_inference():
    tids = [f"T100{i}" for i in range(5)]
    assert len(old_label({t:[["E1","E2"]] for t in tids}).evidence_sets) == 5
    row = {"record_id":"E1","quote":R["E1"][0],"justification":"Mock reason only"}
    with pytest.raises(ValidationError, match="at most 8"):
        Prediction.model_validate({"mappings":[{**row,"technique_id":tid,"record_id":rid} for tid in tids for rid in ("E1","E2")]})
    label = {**LABEL, "targets":{tid:joint() for tid in tids}, "exceptions":{}}
    with pytest.raises(ValueError, match="eight-citation"):
        v2.witness(R, label, set(tids))
    # Two techniques have a sufficient single-source alternative, so eight entries suffice.
    for tid in tids[:2]:
        label["targets"][tid] = TARGET
    proof = v2.witness(R, label, set(tids))
    assert proof["witness_entries"] == 8
    assert proof["witness_output_token_upper_bound"] <= v2.OUTPUT_TOKENS
    assert v2.score(R,label,v2.compact(proof["witness"]),set(tids))["exact"]


def test_budget_boundary_including_stop_reserve_and_joint_role_coverage():
    proof = v2.witness(R, LABEL, {T})
    bound = proof["witness_output_token_upper_bound"]
    assert v2.witness(R, LABEL, {T}, budget=bound) == proof
    with pytest.raises(ValueError, match="output tokens"):
        v2.witness(R, LABEL, {T}, budget=bound-1)
    bad = deepcopy(LABEL)
    bad["targets"][T]["atoms"]["E2.1"] = ["actor"]
    with pytest.raises(ValueError, match="incomplete"):
        v2.witness(R, bad, {T})


def test_same_record_irrelevant_quote_old_exact_new_unsupported():
    old_records = {r:" ".join(lines) for r,lines in R.items()}
    mappings = [{"technique_id":T,"record_id":r,"quote":q,"justification":"See the attached record."}
                for r,q in [("E1",R["E1"][1]),("E2",R["E2"][0])]]
    old = score_case(old_label({T:[["E1","E2"]]}),old_records,json.dumps({"mappings":mappings}),{T})
    assert old["exact"] and not old["binding_blocks"]
    new = v2.score(R,LABEL,answer("E1.2","E2.1"),{T})
    assert (new["tech_tp"],new["groups_complete"],new["keyed"],new["bad_cites"],new["cost"]) == (1,0,1,1,4)
    assert new["trace"][0]["status"] == "topic_only" and not new["exact"]


def test_historical_fresh22_uncorroborated_quote_cannot_prove_log_clear():
    packet = ex.read(ex.ROOT / "eval/reports/ai_retrieval_mapping_20261120/blinded_review_packet.json")
    original = next(row for row in packet["cases"] if row["id"] == "fresh-22")["records"]
    first, last = original["E2"].split(", but ")
    assert "no corroboration" in last
    legacy_label = old_label({}).model_copy(update={"disposition":"unconfirmed"})
    old_raw = json.dumps({"mappings":[{"technique_id":T,"record_id":"E2","quote":last,
                                       "justification":"Synthetic replay of the historical error."}]})
    legacy = score_case(legacy_label, original, old_raw, {T})
    assert not legacy["exact"] and len(legacy["fp"]) == 1 and not legacy["binding_blocks"]
    records = {"E1":[original["E1"]],"E2":[first,last]}
    label = {"targets":{}, "disposition":"inconclusive", "exceptions":{T:{"E2.1":"topic_only","E2.2":"unresolved"}},
             "rationale":"Historical failure pattern revisited as a scoring regression only."}
    result = v2.score(records,label,answer("E2.2"),{T})
    assert result["trace"][0]["text"] == last and result["trace"][0]["status"] == "unresolved"
    assert result["unsupported"] == 1 and not result["exact"]
    assert v2.score(records,label,answer(),{T})["exact"]


@pytest.mark.parametrize("refs,exact,tp,fn,bad",[
    (("E1.1","E2.1"),True,2,0,0),(("E3.1",),True,1,0,0),
    (("E1.1",),False,1,1,0),(("E1.1","E2.1","E3.1"),True,2,0,0),
    (("E1.1","E2.1","E1.2"),False,2,0,1),(("E7.1",),False,0,1,1)])
def test_complete_alternative_partial_and_overcitation(refs,exact,tp,fn,bad):
    row = v2.score(R,LABEL,answer(*refs),{T})
    assert (row["exact"],row["pair_tp"],row["pair_fn"],row["bad_cites"]) == (exact,tp,fn,bad)


@pytest.mark.parametrize("text",['{"mappings":[],"mappings":[]}',"{}",answer("E1.1","E1.1"),"not json"])
def test_malformed_is_never_successful_abstention(text):
    row = v2.score(R,LABEL,text,{T})
    assert not row["contract"] and not row["abstain"] and not row["exact"]
    assert row["cost"] == 4


@pytest.mark.parametrize("tag",["topic_only","contradicts","superseded","action_only","unresolved","unlinked","authorized"])
def test_negative_rubric_preserves_reason(tag):
    label = {"disposition":"inconclusive","targets":{},"rationale":"Mock negative.",
             "exceptions":{T:{"E1.1":tag}}}
    row = v2.score(R,label,answer("E1.1"),{T})
    assert row["trace"][0]["status"] == tag and row["bad_cites"] == row["unsupported"] == 1


def test_specificity_excludes_inconclusive_and_invalid_abstentions():
    def row(disposition,raw):
        return v2.score(R,{**LABEL,"targets":{},"disposition":disposition},raw,{T})
    out = v2.summarise([row("benign",answer()),row("failed","invalid"),row("inconclusive",answer("E1.2"))])
    assert out["known_negative_specificity"] == .5 and out["inconclusive_abstention"] == 0
    assert out["abstention_rate"] == 1/3 and out["complete_group_recall"] is None


def test_corroboration_alone_is_insufficient_and_unknown_id_stays_visible():
    label = deepcopy(LABEL)
    label["exceptions"][T]["E1.2"] = "corroborating"
    row = v2.score(R, label, answer("E1.2"), {T})
    assert row["corroborating"] == 1 and row["bad_cites"] == 0 and row["unsupported"] == 1
    row = v2.score(R, label, answer("E3.1","E1.2"), {T})
    assert row["exact"] and row["groups_complete"] == 1
    unknown = v2.score(R, label, answer("E3.1").replace(T, "T9999"), {T})
    assert unknown["trace"][0]["status"] == "unknown_technique" and not unknown["exact"]


def test_prompt_overflow_and_modified_registration_fail_closed(monkeypatch, tmp_path):
    case = {"id":"mock","family":"unit","records":{**R,"E4":["x"*4096]}}
    key = {"version":v2.VERSION,"cases":{"mock":LABEL}}
    obs = {"version":v2.VERSION,"cases":[case]}
    ts = [MitreTechnique(t,"mock","short",(),"",(),"") for t in [T,"T1000","T1001","T1002","T1003"]]
    monkeypatch.setattr(ex, "catalogue", lambda:(None,ts))
    monkeypatch.setattr(ex, "read", lambda path:obs if path.name=="observations.json" else key)
    with pytest.raises(ValueError, match="untruncated context"):
        ex.check_inputs()
    monkeypatch.setattr(ex, "registration", lambda:{"changed":"input"})
    with pytest.raises(ValueError, match="Registration drift"):
        ex.verify_lock()


def test_new_cohort_witnesses_ablation_and_no_key_fields_in_prompts():
    cases, labels, lookup, proofs = ex.check_inputs()
    assert len(cases) == 18
    assert Counter(c["family"] for c in cases).most_common(1)[0][1] == 3
    for c in cases:
        cid, records = c["id"], c["records"]
        body = ex.render_prompt(records,[])
        assert '"targets"' not in body and '"disposition"' not in body and '"family"' not in body
        assert proofs[cid]["prompt_token_upper_bound_any_top_five"] + v2.OUTPUT_TOKENS <= v2.CONTEXT_TOKENS
        label = labels[cid]
        for tid,spec in label["targets"].items():
            for group in spec["groups"]:
                assert len({r.split(".")[0] for r in group}) >= 2
                def complete(g):
                    raw = v2.compact({"mappings":[v2.entry(tid,r) for r in g]})
                    return tid in v2.score(records,label,raw,lookup)["completed"]
                assert complete(group)
                assert all(not complete(set(group)-{ref}) for ref in group)
    with pytest.raises(ValueError, match="reserved"):
        ex.render_prompt({"E1":["<|im_end|>"]}, [])


def test_missing_authorization_stops_before_any_transport_or_encoder(tmp_path, monkeypatch):
    monkeypatch.setattr(ex,"verify_lock",lambda: None)
    monkeypatch.setattr(ex,"LOCK",tmp_path/"lock")
    ex.LOCK.write_text("mock")
    def unexpected(*args, **kwargs):
        pytest.fail("Opened inference transport or encoder")
    monkeypatch.setattr(httpx,"Client",unexpected)
    monkeypatch.setattr(ex,"DenseRanker",unexpected)
    auth = tmp_path/"approval.json"
    with pytest.raises(FileNotFoundError):
        ex.run(tmp_path,auth)
    auth.write_text(json.dumps({"study":v2.VERSION,"registration_sha256":"wrong","authorize_local_two_pass_comparison":True}))
    with pytest.raises(ValueError, match="authorization"):
        ex.run(tmp_path,auth)


@pytest.mark.parametrize("empty_residency",[True,False])
def test_mock_loopback_ledger_repeats_and_runtime_checks(tmp_path,monkeypatch,empty_residency):
    tech = MitreTechnique(T,"Mock","Mock evidence",(),"",(),"")
    cases = [{"id":"mock-1","family":"unit","records":R}]
    snap = tmp_path/ex.E5_REVISION
    snap.mkdir()
    reg = tmp_path/"mock-reg.json"
    ex.dump(reg,{"e5_files":{},"ollama_version":"mock"})
    auth = tmp_path/"mock-auth.json"
    ex.dump(auth,{"study":v2.VERSION,"registration_sha256":ex.sha(reg),"stakeholder":"unit-test fixture",
                  "approved_on":"2020-01-01","authorize_local_two_pass_comparison":True})
    monkeypatch.setattr(ex,"LOCK",reg)
    monkeypatch.setattr(ex,"PRIVATE",tmp_path/"private")
    monkeypatch.setattr(ex,"verify_lock",lambda:None)
    monkeypatch.setattr(ex,"check_inputs",lambda:(cases,{"mock-1":LABEL},{T:tech},
                                                  {"mock-1":{"prompt_token_upper_bound_any_top_five":3600}}))
    monkeypatch.setattr(ex,"DenseRanker",lambda *_,**k:lambda _: [(T,1.0)])
    model_bodies = []
    def respond(request):
        path = request.url.path
        if path == "/api/version":
            data = {"version":"mock"}
        elif path == "/api/tags":
            data = {"models":[{"name":ex.MODEL,"digest":ex.MODEL_HASH}]}
        elif path == "/api/ps":
            data = {"models":[] if empty_residency else [{"name":ex.MODEL,"context_length":4096}]}
        else:
            assert path == "/api/generate"
            model_bodies.append(json.loads(request.content))
            text = answer("E3.1") if len(model_bodies) != 2 else answer("E1.2")
            data = {"model":ex.MODEL,"response":text,"done":True,"done_reason":"stop","eval_count":12,"prompt_eval_count":130}
        return httpx.Response(200,json=data)
    client = httpx.Client
    monkeypatch.setattr(httpx,"Client",lambda **kw:client(transport=httpx.MockTransport(respond),**kw))
    out = ex.PRIVATE/"run"
    if empty_residency:
        with pytest.raises(ValueError, match="context is unverified"):
            ex.run(snap,auth)
        assert not (out/"results.json").exists()
    else:
        ex.run(snap,auth)
        results = ex.read(out/"results.json")
        assert results["primary"]["benefit"] < 0
        assert results["repeatability"]["hybrid192_k5"]["identical_citations_among_valid"] == 0
    ledger = [json.loads(line) for line in (out/"attempts.jsonl").read_text().splitlines()]
    assert len(ledger) == 8 and len(model_bodies) == 4
    assert model_bodies[0] == model_bodies[-1]
    assert [r["arm"] for r in ledger if r["event"] == "start"] == [*ex.ARMS,*reversed(ex.ARMS)]
    with pytest.raises(FileExistsError):
        ex.run(snap,auth)

