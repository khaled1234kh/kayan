import base64, json
from pathlib import Path
from eval.attack_experiment_a_v3 import preflight, OUT, PRIVATE, CASE_IDS, sha, read, dump, REQUEST_HASH
from eval.attack_evidence_v2 import score
from hashlib import sha256


def compare():
    reg, requests, records, labels, lookup = preflight()
    completion = read(OUT / "completion.json")
    ledger = OUT / "attempts.jsonl"
    assert sha(ledger) == completion["ledger_sha256"]
    raw = [json.loads(x) for x in ledger.read_bytes().splitlines()]
    assert len(raw)==20
    original = {x["id"]:x for x in map(json.loads,(PRIVATE/"run/attempts.jsonl").read_bytes().splitlines())
                if (x["event"],x["arm"],x["pass"])==("result","hybrid192_k5",1)}
    by_case = {}
    for i, (start, result, req) in enumerate(zip(raw[::2],raw[1::2],requests,strict=True),1):
        assert start["event"]=="start" and result["event"]=="result"
        assert start["sequence"] == result["sequence"] == i
        assert all(start[k]==v for k,v in req.items())
        assert all(start[k]==result[k] for k in ("case","condition","reference_ids"))
        wire=base64.b64decode(start["wire_request_base64"])
        assert sha256(wire).hexdigest()==start["wire_request_sha256"] and json.loads(wire)==req["request"]
        cid=result["case"]
        s=result["score"]
        if result["raw_response"] or s["contract"]:
            assert score(records[cid],labels[cid],result["raw_response"],lookup)==s
        names=set(labels[cid]["targets"])
        mapping=[(z["technique"],z["cite"]) for z in s["trace"]]
        keyed={t:[sorted(set(g)-{p for k,p in mapping if k==t}) for g in spec["groups"]]
               for t,spec in labels[cid]["targets"].items()}
        by_case.setdefault(cid,{})[result["condition"]]={
            "sequence":i,"expected_selected":sorted(names&set(s["selected"])),"completed":s["completed"],
            "relevant":s["keyed"]+s["corroborating"],"bad":s["bad_cites"],"trace":s["trace"],
            "extra":sorted(set(s["selected"])-names),"incomplete_expected":sorted(names&set(s["selected"])-set(s["completed"])),
            "missing_by_group":keyed,"valid":s["contract"],"abstain":s["abstain"],"error":s["error"],
            "wall_s":result["wall_s"],"status_code":result["status_code"],
            "reference_ids":result["reference_ids"],"raw":result["raw_response"],
        }
    for cid, arms in by_case.items():
        a=arms["A1"]
        old=original[cid]
        arms["original_v2"]={"same_raw":old["raw"]==a["raw"],
            "same_techniques":set(old["selected"])=={t["technique"] for t in a["trace"]},
            "same_citations":{(t["technique"],t["cite"]) for t in old["trace"]}==
                            {(t["technique"],t["cite"]) for t in a["trace"]},
            "added":sorted({(t["technique"],t["cite"]) for t in a["trace"]}-{(t["technique"],t["cite"]) for t in old["trace"]}),
            "removed":sorted({(t["technique"],t["cite"]) for t in old["trace"]}-{(t["technique"],t["cite"]) for t in a["trace"]}),
            "valid":old["contract"],"abstain":old["abstain"]}
    def aggregate(cases,name):
        cells=[by_case[c][name] for c in cases]
        return {"targets":sum(len(labels[c]["targets"]) for c in cases),
            **{k:sum(len(cell[k]) for cell in cells) for k in ("expected_selected","completed","extra","incomplete_expected")},
            **{k:sum(cell[k] for cell in cells) for k in ("relevant","bad","valid","abstain")},
            "wall_s":sum(cell["wall_s"] for cell in cells)}
    summary={"cases":by_case,"all":{a:aggregate(CASE_IDS,a) for a in ("A1","A2")},
             "exclude_quartz":{a:aggregate([c for c in CASE_IDS if c!="quartz"],a) for a in ("A1","A2")},
             "a1_replay_agreement":{k:sum(c["original_v2"][k] for c in by_case.values()) for k in ("same_raw","same_techniques","same_citations")},
             "hashes":{"requests":REQUEST_HASH,"ledger":sha(ledger),"completion":sha(OUT/"completion.json"),
                       "authorization":sha(OUT/"authorization.json")}}
    return summary

if __name__ == "__main__":
    comparison = compare()
    path = OUT / "comparison.json"
    if path.exists():
        assert read(path) == comparison
        print("Stored Experiment A comparison reproduced")
    else:
        dump(path, comparison)
