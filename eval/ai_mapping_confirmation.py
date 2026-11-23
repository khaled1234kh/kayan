"""Preregister and execute the one-shot, fictional ATT&CK confirmation."""

import argparse
import asyncio
import json
import os
from base64 import b64encode
from collections import defaultdict
from pathlib import Path
from time import perf_counter

import httpx

from ai.mitre.ranking import DenseRanker, FieldBM25, rank_fusion
from eval.ai_confirmation_inputs import (
    ARMS, E5_CAP, K, MODEL_HASH, OPTIONS, PRIVATE, PROTOCOL, audit_packets,
    catalogue, protocol_basis, read_inputs, sha, write_adjudication_draft, write_agreement,
)
from eval.ai_confirmation_scoring import compare, score_case
from eval.ai_mapping_ablation import distribution, ordered_context, prompt_data, timed
from eval.ai_mapping_review import save
from eval.ai_retrieval_mapping import MODEL, SERVER, SYSTEM, Prediction, digest

CONSOLE = "http://127.0.0.1:8001"


async def server_version(client):
    response = await client.get("/api/version")
    response.raise_for_status()
    return response.json()["version"]


async def verify_model(client, expected_version):
    version = await server_version(client)
    tags = await client.get("/api/tags")
    tags.raise_for_status()
    models = {row["name"]: row["digest"] for row in tags.json()["models"]}
    if version != expected_version or models.get(MODEL) != MODEL_HASH:
        raise ValueError("Local Ollama version or model digest differs from the protocol")


async def console_state():
    routes = [("POST", "/ai/assess"), ("GET", "/ai/assess/00000000-0000-0000-0000-000000000000"),
              ("POST", "/ai/mitre/reindex"), ("GET", "/ai/status"), ("GET", "/ai/usage"), ("GET", "/engagement")]
    async with httpx.AsyncClient(base_url=CONSOLE, trust_env=False, timeout=10) as client:
        responses = [await client.request(method, path) for method, path in routes]
    if ([row.status_code for row in responses] != [503, 503, 503, 200, 200, 200]
            or responses[3].json()["enabled"] is not False or responses[4].json() != {}):
        raise ValueError("Experimental routes or console status fail closed-state checks")
    session = responses[5]
    return {"paused_http_codes": [503, 503, 503], "engagement_id": session.json()["engagement_id"],
            "status": session.json()["status"], "engagement_response_sha256": digest(session.content)}


def schedule(cases):
    families = defaultdict(list)
    for case in cases:
        families[case["family"]].append(case)
    for index, family in enumerate(sorted(families)):
        for case in sorted(families[family], key=lambda item: item["id"]):
            for arm in ARMS[::1 if index % 2 == 0 else -1]:
                yield case, arm


def payload(context):
    return {"model": MODEL, "format": Prediction.model_json_schema(), "stream": False, "options": OPTIONS,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": context}]}


async def send_once(client, request):
    start = perf_counter()
    try:
        response = await client.post("/api/chat", json=request)
    except httpx.RequestError as exc:
        return {"error": type(exc).__name__, "content": "", "request_ms": (perf_counter() - start) * 1000}
    result = {"http_status": response.status_code, "raw_body_base64": b64encode(response.content).decode(),
              "content": "", "request_ms": (perf_counter() - start) * 1000}
    if not response.is_success:
        return {**result, "error": f"HTTP {response.status_code}"}
    try:
        data = response.json()
        content = data["message"]["content"]
        if isinstance(content, str):
            result["content"] = content
        result.update(done=data.get("done"), finish_reason=data.get("done_reason"), streamed_model=data.get("model"),
                      prompt_tokens=data.get("prompt_eval_count"), completion_tokens=data.get("eval_count"),
                      load_duration_ns=data.get("load_duration"))
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    return result


def record(stream, event):
    stream.write(json.dumps(event, ensure_ascii=True) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def paired_ranker(snapshot, techniques):
    import psutil

    process = psutil.Process()
    cpu = process.cpu_times()
    resources = {"rss_before_bytes": process.memory_info().rss,
                 "logical_cpus": psutil.cpu_count(), "ram_bytes": psutil.virtual_memory().total}
    bm25, resources["bm25_index_ms"] = timed(FieldBM25, techniques)
    resources["rss_after_bm25_bytes"] = process.memory_info().rss
    dense, resources["e5_encoder_and_index_ms"] = timed(lambda: DenseRanker(snapshot, techniques, max_length=E5_CAP))
    resources["rss_after_e5_bytes"] = process.memory_info().rss
    lookup = {technique.technique_id: technique for technique in techniques}

    def retrieve(records, arm):
        lexical, bm_ms = timed(bm25, records)
        if arm == "bm25_k5":
            return lexical, bm_ms
        semantic, dense_ms = timed(dense, records)
        fused, fusion_ms = timed(rank_fusion, lexical, semantic)
        return fused, bm_ms + dense_ms + fusion_ms

    def resource_report():
        latest = process.cpu_times()
        memory = process.memory_info()
        return {**resources, "rss_at_end_bytes": memory.rss, "peak_windows_working_set_bytes": getattr(memory, "peak_wset", None),
                "runner_cpu_seconds": (latest.user - cpu.user) + (latest.system - cpu.system)}

    return lookup, retrieve, resource_report


async def collect(cases, labels, config, lookup, retrieve, send, stream):
    scored = {arm: [] for arm in ARMS}
    for case, arm in schedule(cases):
        cid = case["id"]
        ranked, retrieval_ms = retrieve(case["records"], arm)
        ids = ordered_context(ranked, cid, lookup, K)
        request = payload(prompt_data(case, ids, lookup, config))
        identity = {"id": cid, "arm": arm, "family": case["family"], "references": ids, "retrieval_ms": retrieval_ms}
        record(stream, {"event": "start", **identity, "request_sha256": digest(json.dumps(request).encode())})
        answer = await send(request)
        error = answer.get("error")
        if error is None and (answer.get("done") is not True or answer.get("finish_reason") != "stop"
                              or answer.get("streamed_model") != MODEL):
            # Preserve a partial response but do not credit a truncated or mismatched execution.
            error = "Incomplete or mismatched model execution"
        result = score_case(labels[cid], case["records"], answer["content"], lookup.keys(), error,
                            transport_error="error" in answer)
        row = {**identity, **answer, "execution_error": error, **result}
        record(stream, {"event": "result", **row})
        scored[arm].append(row)
    return scored


def cost(rows):
    result = {key: distribution([row.get(key) for row in rows])
              for key in ("retrieval_ms", "request_ms", "prompt_tokens", "completion_tokens", "load_duration_ns")}
    result["retrieval_plus_request_ms"] = distribution([row["retrieval_ms"] + row["request_ms"] for row in rows])
    return result


def reserve(directory):
    directory.mkdir(parents=True, exist_ok=False)


async def run(snapshot):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    history, cases, packets = audit_packets()
    config, techniques = catalogue()
    registered = json.loads(PROTOCOL.read_bytes())
    if protocol_basis(history, packets, snapshot, registered["ollama_version"]) != registered:
        raise ValueError("Current inputs, implementation or environment differ from the registered protocol")
    labels, approval, evidence = read_inputs(PRIVATE / "inputs", packets, techniques, sha(PROTOCOL))
    output = PRIVATE / "run"
    if output.exists():
        raise FileExistsError("This cohort has already been attempted")
    before = await console_state()
    async with httpx.AsyncClient(base_url=SERVER, timeout=45, trust_env=False) as client:
        await verify_model(client, registered["ollama_version"])
        reserve(output)
        save(output / "run-lock.json", {"protocol_sha256": sha(PROTOCOL), **evidence, "session_before": before})
        lookup, retrieve, resources = paired_ranker(snapshot, techniques)
        with (output / "attempts.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            results = await collect(cases, labels, config, lookup, retrieve, lambda request: send_once(client, request), stream)
        await verify_model(client, registered["ollama_version"])
        resident = await client.get("/api/ps")
        resident.raise_for_status()
        model_runtime = [row for row in resident.json()["models"] if row["name"] == MODEL]
    after = await console_state()
    if before != after:
        raise ValueError("Selected engagement or paused routes changed during confirmation; retain the ledger")
    if any(row.get("context_length") != OPTIONS["num_ctx"] for row in model_runtime):
        raise ValueError("Ollama reported a different loaded context; retain the ledger")
    result = compare(*(results[arm] for arm in ARMS), approval)
    costs = {arm: cost(rows) for arm, rows in results.items()}
    delta = (costs[ARMS[1]]["retrieval_ms"]["p50"] - costs[ARMS[0]]["retrieval_ms"]["p50"])
    save(output / "summary.json", {**result, "cost": costs, "incremental_median_retrieval_ms": delta,
                                   "index_and_host": resources(), "ollama_residency": model_runtime,
                                   "session_after": after, "ledger_sha256": sha(output / "attempts.jsonl")})


async def prepare_protocol(snapshot):
    history, _, packets = audit_packets()
    catalogue()
    async with httpx.AsyncClient(base_url=SERVER, timeout=10, trust_env=False) as client:
        runtime = await server_version(client)
        await verify_model(client, runtime)
    result = protocol_basis(history, packets, snapshot, runtime)
    PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
    save(PROTOCOL, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit")
    for command in ("agreement", "adjudication-draft"):
        commands.add_parser(command).add_argument("cohort", choices=("diagnostic", "confirmation"))
    for command in ("preregister", "run"):
        commands.add_parser(command).add_argument("--e5-snapshot", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "audit":
        _, _, packets = audit_packets()
        _, techniques = catalogue()
        print(json.dumps({"packets": packets, "active_techniques": len(techniques)}, indent=2))
    elif args.command == "agreement":
        directory = PRIVATE / "inputs"
        write_agreement(directory, args.cohort, directory / args.cohort / "agreement.json")
    elif args.command == "adjudication-draft":
        write_adjudication_draft(PRIVATE / "inputs", args.cohort)
    elif args.command == "preregister":
        asyncio.run(prepare_protocol(args.e5_snapshot))
    else:
        asyncio.run(run(args.e5_snapshot))


if __name__ == "__main__":
    main()
