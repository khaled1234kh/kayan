"""Reconstruct v2 ranking, prompt inclusion and evidence binding. No generation endpoint."""
import argparse
import base64
from collections import Counter
from pathlib import Path

from ai.mitre.ranking import DenseRanker, E5_REVISION, FieldBM25, rank_fusion
from eval.attack_evidence_v2 import parse, score, spans
from eval.attack_experiment_v2 import (
    ARMS, LOCK, PRIVATE, analysis, check_inputs, dump, ordered_context, read, reference,
    render_prompt, schedule, sha, verify_lock,
)

LOCK_HASH = "66254d7c5fa4128faac5749bf78ae3a5ba8de324ee232b505098e462d955d8c3"
LEDGER_HASH = "3fde89e782aa4c753aabb5b9604ed2d0ea56f90ca6fc6587bc95efca537214ca"


def ranks(ranking):
    return {tid: i for i, (tid, _) in enumerate(ranking, 1)}


def field_explanation(lex, records, tid):
    queries = {"all": " ".join(records.values()), **records}
    scores = {}
    for rid, query in queries.items():
        scores[rid] = [weight * field.score(query).get(tid, 0) for weight, field in lex._fields]
    winner = max(scores, key=lambda name: sum(scores[name]))
    return {"max_query": winner, "weighted_identity_description_context": scores[winner]}


def investigate(out, snapshot):
    verify_lock()
    reg = read(LOCK)
    ledger = PRIVATE / "run" / "attempts.jsonl"
    if sha(LOCK) != LOCK_HASH or sha(ledger) != LEDGER_HASH:
        raise ValueError("Unrecognized frozen study or ledger")
    if {p.name: sha(p) for p in snapshot.iterdir() if p.is_file()} != reg["e5_files"]:
        raise ValueError("Local E5 snapshot drift")
    cases, labels, lookup, proofs = check_inputs()
    events = [parse(line) for line in ledger.read_bytes().splitlines()]
    starts, results = events[::2], events[1::2]
    registered = read(PRIVATE / "run/results.json")
    for k, v in analysis(results, cases).items():
        assert registered[k] == v
    for (p,c,arm), start, res in zip(schedule(cases), starts, results, strict=True):
        assert start["event"] == "start" and res["event"] == "result"
        assert all((x["pass"], x["id"], x["arm"]) == (p,c["id"],arm) for x in (start,res))
        wire = parse(base64.b64decode(res["raw_body_base64"]))
        assert wire["response"] == res["raw"] and wire["done_reason"] == "stop"
        recomputed = score(c["records"], labels[c["id"]], res["raw"], lookup)
        assert all(res[k] == v for k,v in recomputed.items())
    lex = FieldBM25(list(lookup.values()))
    dense = DenseRanker(snapshot, list(lookup.values()), max_length=192)
    lengths = dense.token_lengths([dense.passage_text(t) for t in lookup.values()])
    passage = dict(zip(lookup, lengths, strict=True))
    cases_out = []
    counts = Counter()
    for c in cases:
        cid = c["id"]
        statements = spans(c["records"])
        source = {rid:" ".join(lines) for rid, lines in c["records"].items()}
        label = labels[cid]
        bm, e5 = lex(source), dense(source)
        fused = rank_fusion(bm, e5)
        positions = [ranks(ranking) for ranking in (bm,e5,fused)]
        ranked = {}
        visible = set(t for t,_ in bm[:5]+fused[:5]) | set(label["targets"])
        for tid in sorted(visible):
            item = lookup[tid]
            ranked[tid] = {"name":item.name, "full_definition":item.description,
                "shown_reference":reference(item), "passage_tokens":passage[tid],
                "ranks_bm25_e5_rrf":[r.get(tid) for r in positions],
                "rrf_terms":[1/(60+r[tid]) if r.get(tid,101)<=100 else 0 for r in positions[:2]],
                "bm25_contributions":field_explanation(lex,source,tid)}
        ablations = {}
        for tid, spec in label["targets"].items():
            # Privileged query diagnostic. Available only with the benchmark key.
            action = {ref:statements[ref] for ref, roles in spec["atoms"].items() if "action" in roles}
            if action:
                a, b = lex(action), dense(action)
                ablations[tid] = [ranks(q).get(tid) for q in (a,b,rank_fusion(a,b))]
        rows = []
        for start, res in zip(starts,results,strict=True):
            if res["id"] != cid:
                continue
            arm = res["arm"]
            ids = ordered_context(bm if arm==ARMS[0] else fused, cid, lookup, 5)
            assert ids==start["references"]==res["references"]
            assert render_prompt(c["records"], [reference(lookup[i]) for i in ids])==start["request"]["prompt"]
            citations = res["trace"]
            cited = {r["cite"] for r in citations}
            missing, roles = {}, {}
            for tid,spec in label["targets"].items():
                attached = {r["cite"] for r in citations if r["technique"]==tid}
                missing[tid] = [sorted(set(g)-attached) for g in spec["groups"]]
                roles[tid] = sorted({role for ref in attached for role in spec["atoms"].get(ref,[])})
                if res["pass"]==1 and any(set(g)<=cited for g in spec["groups"]):
                    counts[arm+"_complete_addresses_any_technique"]+=1
            cats = []
            if label["targets"].keys()-set(ids): cats.append("expected_reference_absent")
            if label["targets"].keys() & set(res["selected"])-set(res["completed"]): cats.append("correct_id_incomplete_group")
            if set(res["selected"])-label["targets"].keys(): cats.append("extra_technique")
            if not label["targets"] and res["selected"]: cats.append("finding_on_"+label["disposition"])
            if res["bad_cites"]: cats.append("citation_without_keyed_support")
            if res["abstain"]: cats.append("abstained")
            rows.append({"pass":res["pass"],"arm":arm,"ordered_references":ids,"selected":res["selected"],
                         "cited_statements":citations,"roles_shown_for_target":roles,"missing_by_alternative":missing,
                         "group_complete":res["completed"],"failure_or_outcome":cats,"raw_response":res["raw"],
                         "cost":res["cost"],"keyed":res["keyed"],"bad":res["bad_cites"]})
        cases_out.append({"id":cid,"family":c["family"],"statements":statements,"rubric":label,
                          "query_tokens":dense.token_lengths([dense.query_text(source)])[0],
                          "retrieval":ranked,"privileged_action_only_ranks":ablations,
                          "feasible_witness":proofs[cid],"cells":rows})
    dump(out, {"version":"attack-forensics-v3","registration_sha256":LOCK_HASH,"ledger_sha256":LEDGER_HASH,
               "cases":cases_out,"passage_truncations":sum(n>192 for n in lengths),
               "pooled_address_upper_bound_pass1":dict(counts)})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", required=True,type=Path)
    cli.add_argument("--snapshot",type=Path,default=Path.home()/".cache/huggingface/hub/models--intfloat--e5-small-v2/snapshots"/E5_REVISION)
    args = cli.parse_args()
    investigate(args.out,args.snapshot)
