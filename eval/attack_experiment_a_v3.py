"""One-shot local replay of authorized Experiment A. Preserves a durable attempt ledger."""
import base64
import json
import os
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import httpx

from eval.attack_evidence_v2 import BOUNDARY_RESERVE, score
from eval.attack_experiment_v2 import (
    LOCK, PRIVATE, ROOT, check_inputs, decode, dump, read, reference, render_prompt, sha, verify_lock,
)
from eval.attack_forensics_v3 import LEDGER_HASH, LOCK_HASH

REQUEST_HASH = "634372410ae089de674f3ea1c3e4b7b4150a6f046ea3087c1124c874eabe3ecc"
FORENSICS = ROOT / "eval/reports/attack_forensics_v3_20261120"
OUT = ROOT / ".build/attack_diagnostics_v3_a"
CASE_IDS = ("birch", "coral", "moss", "quartz", "slate")


def preflight():
    verify_lock()
    assert sha(LOCK) == LOCK_HASH
    assert sha(PRIVATE / "run/attempts.jsonl") == LEDGER_HASH
    assert not (ROOT / ".build/attack_confirmation/run").exists()
    reg = read(LOCK)
    for folder in (FORENSICS, ROOT / "eval/reports/attack_mapping_v2_20261120"):
        for line in (folder / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
            digest, name = line.split(None, 1)
            assert sha(folder / name) == digest
    report = ROOT / "docs/ATTACK_EXPLORATORY_V2_RESULTS_2026-11-20.md"
    import re
    for name, digest in re.findall(r"\| .([^| ]+). \| .([0-9a-f]{64}). \|", report.read_text(encoding="utf-8")):
        artifact = PRIVATE / name
        assert sha(artifact if artifact.is_file() else PRIVATE / "run" / name) == digest
    path = FORENSICS / "oracle-a-requests.json"
    assert sha(path) == REQUEST_HASH
    saved = read(path)
    requests = saved["requests"]
    assert saved["protocol"] == "attack-diagnostics-v3.0" and saved["request_count"] == len(requests) == 10
    cases, labels, lookup, proofs = check_inputs()
    records = {c["id"]: c["records"] for c in cases}
    old_events = [json.loads(line) for line in (PRIVATE / "run/attempts.jsonl").read_bytes().splitlines()]
    controls = {x["id"]:x for x in old_events if (x["event"], x["pass"], x["arm"])==("start",1,"hybrid192_k5")}
    matrix = {x["id"]:x for x in read(FORENSICS / "matrix.json")["cases"]}
    for index, cid in enumerate(CASE_IDS):
        a, b = requests[2*index:2*index+2]
        assert a["case"] == b["case"] == cid
        assert (a["condition"], b["condition"]) == (("A1","A2") if index%2==0 else ("A2","A1"))
        control, oracle = (a,b) if a["condition"]=="A1" else (b,a)
        old = controls[cid]
        assert control["request"] == old["request"] and control["reference_ids"] == old["references"]
        expected = list(old["references"])
        missing = sorted(labels[cid]["targets"].keys() - set(expected))
        assert len(missing)==(2 if cid=="slate" else 1)
        drop = sorted((i for i,t in enumerate(expected) if t not in labels[cid]["targets"]),
                      key=lambda i:matrix[cid]["retrieval"][expected[i]]["ranks_bm25_e5_rrf"][2],reverse=True)
        for i,tid in zip(drop,missing):
            expected[i]=tid
        assert oracle["reference_ids"] == expected
        for row in (control,oracle):
            ids = row["reference_ids"]
            assert len(set(ids))==5
            prompt = render_prompt(records[cid],[reference(lookup[t]) for t in ids])
            assert row["request"] == {"model":reg["model"],"raw":True,"stream":False,"prompt":prompt,
                                      "format":reg["schema"],"options":reg["options"]}
            assert len(prompt.encode()) + BOUNDARY_RESERVE <= proofs[cid]["prompt_token_upper_bound_any_top_five"]
    return reg, requests, records, labels, lookup


def runtime(client, reg):
    version = client.get("/api/version")
    version.raise_for_status()
    tags = client.get("/api/tags")
    tags.raise_for_status()
    status = client.get("http://127.0.0.1:8001/ai/status")
    status.raise_for_status()
    assert status.json()["enabled"] is False
    installed = {m["name"]: m["digest"] for m in tags.json()["models"]}
    assert version.json()["version"] == reg["ollama_version"]
    assert installed.get(reg["model"]) == reg["model_digest"]
    return {"version":reg["ollama_version"],"model":reg["model"],"digest":reg["model_digest"],"sovereign_enabled":False}


def execute():
    assert __debug__, "Run with assertions enabled"
    reg, requests, records, labels, lookup = preflight()
    with httpx.Client(base_url="http://127.0.0.1:11434", timeout=180, trust_env=False) as client:
        before = runtime(client,reg)
        OUT.mkdir(exist_ok=False)
        dump(OUT/"authorization.json",{"study":"attack-diagnostics-v3.0","experiment":"A","approved_on":"2026-11-20",
             "stakeholder":"Khaled Mohamed","source":"Explicit approval in this Codex conversation",
             "authorized_requests":10,"requests_sha256":REQUEST_HASH,"v2_registration_sha256":LOCK_HASH,
             "v2_ledger_sha256":LEDGER_HASH,"runner_sha256":sha(Path(__file__)),"runtime":before})
        with (OUT/"attempts.jsonl").open("x",encoding="utf-8",newline="\n") as ledger:
            def log(row):
                ledger.write(json.dumps(row,ensure_ascii=True,separators=(",",":"))+"\n")
                ledger.flush()
                os.fsync(ledger.fileno())
            for index,cell in enumerate(requests,1):
                cid = cell["case"]
                body = cell["request"]
                key = {k:v for k,v in cell.items() if k!="request"}
                wire = client.build_request("POST","/api/generate",json=body)
                log({"event":"start","sequence":index,**cell,"wire_request_sha256":sha256(wire.content).hexdigest(),
                     "wire_request_base64":base64.b64encode(wire.content).decode()})
                started = perf_counter()
                error = status = raw_wire = None
                raw = ""
                try:
                    reply = client.send(wire)
                    status = reply.status_code
                    raw_wire = base64.b64encode(reply.content).decode()
                    raw = decode(reply,len(body["prompt"].encode())+BOUNDARY_RESERVE)
                except (httpx.HTTPError,ValueError,TypeError,KeyError) as exc:
                    error = str(exc)
                result = score(records[cid],labels[cid],raw,lookup,execution_error=error)
                log({"event":"result","sequence":index,**key,"status_code":status,"raw_response":raw,
                     "raw_body_base64":raw_wire,"wall_s":perf_counter()-started,"score":result})
        after = runtime(client,reg)
        resp = client.get("/api/ps")
        resp.raise_for_status()
        resident = [m for m in resp.json()["models"] if m["name"]==reg["model"]]
        assert len(resident)==1 and resident[0].get("context_length")==reg["options"]["num_ctx"]
    assert sha(FORENSICS/"oracle-a-requests.json")==REQUEST_HASH
    assert sha(PRIVATE/"run/attempts.jsonl")==LEDGER_HASH and sha(LOCK)==LOCK_HASH
    dump(OUT/"completion.json",{"scheduled":10,"runtime":after,"context_length":reg["options"]["num_ctx"],
                                 "ledger_sha256":sha(OUT/"attempts.jsonl")})


if __name__ == "__main__":
    execute()
