"""Matched local ablations on the already inspected fictional ATT&CK cohort."""

import argparse
import asyncio
import json
import platform
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from statistics import quantiles
from time import perf_counter

import httpx
import psutil

from ai.config import load_config
from ai.mitre.ranking import E5_REVISION, DenseRanker, FieldBM25, rank_fusion
from ai.mitre.stix import load_techniques
from ai.providers.base import ChatMessage
from ai.providers.ollama import OllamaProvider
from eval.ai_retrieval_mapping import (
    FIXTURES, MODEL, ROOT, SERVER, SYSTEM, Prediction, digest, fixture, paired, references,
    retrieval_metrics, score, summary,
)

HISTORY = ROOT / "eval/reports/ai_retrieval_mapping_20261120"
DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
BEHAVIOR = (
    " Before mapping, check what action completed, what object or system it affected, where it happened, and "
    "which reliable record actually confirms the action was unauthorized. Use verified dispositions when records "
    "conflict. An explicit finding that an action did not happen rules it out, even when the reference matches "
    "the topic. Choose no mapping when the distinguishing facts are missing. Keep these checks internal."
)
ARMS = {
    "bm25_k5": ("bm25", 5, SYSTEM),
    "hybrid192_k5": ("hybrid192", 5, SYSTEM),
    "hybrid512_k5": ("hybrid512", 5, SYSTEM),
    "bm25_k3": ("bm25", 3, SYSTEM),
    "bm25_k10": ("bm25", 10, SYSTEM),
    "shortlist_k5": ("shortlist", 5, SYSTEM),
    "bm25_behavior_k5": ("bm25", 5, SYSTEM + BEHAVIOR),
}


def write_json(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def distribution(values):
    values = [value for value in values if value is not None]
    if not values:
        return {"n": 0}
    percentiles = quantiles(values, n=100, method="inclusive") if len(values) > 1 else values * 99
    return {"n": len(values), "p50": percentiles[49], "p95": percentiles[94], "max": max(values)}


def timed(call, *args):
    start = perf_counter()
    value = call(*args)
    return value, (perf_counter() - start) * 1000


def rerank(lexical, dense):
    dense_ranks = {tid: position for position, (tid, _) in enumerate(dense)}
    return sorted(lexical[:10], key=lambda item: dense_ranks.get(item[0], len(dense)))


def prompt_data(case, ids, lookup, config):
    request = {"observation_records": case["records"],
               "public_candidate_references": references(ids, lookup, config)}
    return json.dumps(request)


def ordered_context(ranked, case_id, lookup, k):
    selected = [tid for tid, _ in ranked[:k]]

    def sort_key(tid):
        return digest(f"{case_id}:{tid}".encode())

    if len(selected) < k:
        selected.extend(sorted(set(lookup) - set(selected), key=sort_key)[:k - len(selected)])
    return sorted(selected, key=sort_key)


def lengths_audit(lengths):
    return {**distribution(lengths), "over_192": sum(n > 192 for n in lengths),
            "over_512": sum(n > 512 for n in lengths)}


def index_and_rank(snapshot, techniques, cases):
    process = psutil.Process()
    resource = {"rss_before_indices_bytes": process.memory_info().rss}
    lex, resource["bm25_fit_ms"] = timed(FieldBM25, techniques)
    resource["rss_after_bm25_bytes"] = process.memory_info().rss
    dense192, resource["e5_192_fit_ms"] = timed(DenseRanker, snapshot, techniques)
    resource["rss_after_e5_192_bytes"] = process.memory_info().rss
    doc_texts = [dense192.passage_text(technique) for technique in techniques]
    name_and_description = ["passage: " + technique.name + " " + technique.description for technique in techniques]
    full_lengths = dense192.token_lengths(doc_texts)
    prefix_lengths = dense192.token_lengths(name_and_description)
    query_lengths = dense192.token_lengths([dense192.query_text(case["records"]) for case in cases])
    audit = {"passages": lengths_audit(full_lengths), "queries": lengths_audit(query_lengths),
             "max_unit_norm_error_192": float((dense192._passages.norm(dim=1) - 1).abs().max()),
             "populated_fields": {field: sum(bool(getattr(t, field)) for t in techniques) for field in (
                 "description", "detection", "platforms", "tactics", "aliases", "parent_id",
                 "mitigation_ids", "detection_strategies", "raw_text")},
             "generator_descriptions_over_400_chars": sum(len(t.description) > 400 for t in techniques),
             "strategy_passage_suffix_excluded": {
                 cutoff: sum(bool(t.detection_strategies) and n > cutoff
                             for t, n in zip(techniques, prefix_lengths, strict=True))
                 for cutoff in (192, 512)
             }}
    rankings, costs = {}, {}
    for case in cases:
        lexical, lex_ms = timed(lex, case["records"])
        semantic, dense_ms = timed(dense192, case["records"])
        hybrid, fusion_ms = timed(rank_fusion, lexical, semantic)
        shortlist, rerank_ms = timed(rerank, lexical, semantic)
        rankings[case["id"]] = {"bm25": lexical, "dense192": semantic, "hybrid192": hybrid, "shortlist": shortlist}
        costs[case["id"]] = {"bm25": lex_ms, "dense192": dense_ms, "hybrid192": lex_ms + dense_ms + fusion_ms,
                             "shortlist": lex_ms + dense_ms + rerank_ms}
    del dense192
    resource["rss_before_e5_512_bytes"] = process.memory_info().rss
    def fit512():
        return DenseRanker(snapshot, techniques, max_length=512)

    dense512, resource["e5_512_fit_ms"] = timed(fit512)
    resource["rss_after_e5_512_bytes"] = process.memory_info().rss
    audit["max_unit_norm_error_512"] = float((dense512._passages.norm(dim=1) - 1).abs().max())
    for case in cases:
        methods = rankings[case["id"]]
        query_cost = costs[case["id"]]
        semantic, dense_ms = timed(dense512, case["records"])
        hybrid, fusion_ms = timed(rank_fusion, methods["bm25"], semantic)
        methods.update(dense512=semantic, hybrid512=hybrid)
        query_cost.update(dense512=dense_ms, hybrid512=query_cost["bm25"] + dense_ms + fusion_ms)
    resource["rss_after_retrieval_bytes"] = process.memory_info().rss
    resource["windows_peak_working_set_bytes"] = getattr(process.memory_info(), "peak_wset", None)
    return rankings, costs, audit, resource


async def local_model_info(client):
    response = await client.get("/api/ps")
    response.raise_for_status()
    fields = ("name", "digest", "size", "size_vram", "context_length")
    return [{name: item.get(name) for name in fields} for item in response.json()["models"] if item["name"] == MODEL]


def paired_outcomes(a, b):
    counts = {key: 0 for key in ("both_exact", "a_only", "b_only", "neither_exact")}
    for first, second in zip(a, b, strict=True):
        a_exact, b_exact = first["score"]["exact"], second["score"]["exact"]
        key = "both_exact" if a_exact and b_exact else "a_only" if a_exact else "b_only" if b_exact else "neither_exact"
        counts[key] += 1
    return counts


async def run(output, snapshot):
    config = load_config(load_env=False)
    cases = fixture("evaluation")
    techniques = load_techniques(config.mitre)
    lookup = {item.technique_id: item for item in techniques}
    active_ids = set(lookup)
    historical = json.loads((HISTORY / "manifest.json").read_bytes())
    snapshot_hashes = {path.name: digest(path.read_bytes()) for path in sorted(snapshot.iterdir()) if path.is_file()}
    if snapshot.name != E5_REVISION or snapshot_hashes != historical["dense_file_hashes"]:
        raise ValueError("E5 snapshot does not match the previous benchmark")
    async with httpx.AsyncClient(base_url=SERVER, trust_env=False, timeout=10) as client:
        tags = await client.get("/api/tags")
        tags.raise_for_status()
        model_digest = {item["name"]: item["digest"] for item in tags.json()["models"]}[MODEL]
        if model_digest != DIGEST or historical["model_digest"] != model_digest:
            raise ValueError("Ollama model digest changed")
        model_before = await local_model_info(client)
    schema = Prediction.model_json_schema()
    paths = (*historical["code_sha256"], "eval/ai_mapping_ablation.py")
    write_json(output / "manifest.json", {
        "cohort": "Already inspected, author-labelled diagnostic cohort",
        "fixture_sha256": FIXTURES["evaluation"][1],
        "historical_manifest_sha256": digest((HISTORY / "manifest.json").read_bytes()),
        "source_sha256": {path: digest((ROOT / path).read_bytes()) for path in paths},
        "historical_ranker_snapshot_sha256": digest((output / "source-baseline/ranking.py").read_bytes()),
        "bundle_version": config.mitre.version, "bundle_sha256": config.mitre.sha256, "schema": schema,
        "arms": {name: {"retrieval": method, "k": k, "system": system} for name, (method, k, system) in ARMS.items()},
        "model": MODEL, "model_digest": model_digest, "num_predict": 370, "temperature": 0,
        "num_ctx": "Ollama server-managed, sampled through /api/ps", "model_before": model_before,
        "bootstrap_seed": 391, "bootstrap_draws": 10000, "e5_revision": E5_REVISION,
        "e5_file_hashes": snapshot_hashes, "query_order": "Rotated by case index",
        "host": {"platform": platform.platform(), "cpu_threads": psutil.cpu_count(),
                 "ram_bytes": psutil.virtual_memory().total, "python": platform.python_version()},
        "software_versions": {name: version(name) for name in (
            "torch", "transformers", "psutil", "pydantic", "httpx", "scikit-learn")},
        "inference": "Only 127.0.0.1 Ollama, using fictional retrospective records",
    })
    rankings, costs, audit, resource = index_and_rank(snapshot, techniques, cases)
    old_ranks = json.loads((HISTORY / "retrieval.json").read_bytes())["ranked_ids"]["evaluation"]
    full_ranked_ids = {cid: {method: [tid for tid, _ in rows] for method, rows in methods.items()}
                       for cid, methods in rankings.items()}
    rank_agreement = {method: sum(full_ranked_ids[cid][method][:10] == old_ranks[cid][historical_method][:10]
                                  for cid in rankings) for method, historical_method in (
        ("bm25", "field_bm25"), ("dense192", "dense_e5"), ("hybrid192", "hybrid_e5"))}
    write_json(output / "retrieval.json", {
        "metrics": retrieval_metrics(cases, rankings), "historical_top10_equal_cases": rank_agreement,
        "audit": audit, "resources": resource, "latency_ms": {
            method: distribution([row[method] for row in costs.values()]) for method in next(iter(costs.values()))},
        "per_case_latency_ms": costs, "ranked_ids": full_ranked_ids,
    })
    print("Retrieval complete. Running matched Ollama ablations.", flush=True)
    provider = OllamaProvider(replace(config.get_provider("ollama"), base_url=SERVER, chat_model=MODEL,
                                      request_timeout_s=45, max_tokens=370, temperature=0))
    names = list(ARMS)
    grouped = {name: [] for name in names}
    try:
        with (output / "responses.jsonl").open("x", encoding="utf-8", newline="\n") as out:
            for index, case in enumerate(cases):
                shift = index % len(names)
                for name in names[shift:] + names[:shift]:
                    method, k, system = ARMS[name]
                    ids = ordered_context(rankings[case["id"]][method], case["id"], lookup, k)
                    request = prompt_data(case, ids, lookup, config.mitre)
                    row = {"id": case["id"], "family": case["family"], "arm": name, "context_ids": ids,
                           "prompt_sha256": digest(request.encode()), "request_bytes": len(request.encode()),
                           "references_bytes": len(json.dumps(json.loads(request)["public_candidate_references"]).encode()),
                           "raw": ""}
                    start = perf_counter()
                    try:
                        answer = await provider.chat([ChatMessage("system", system), ChatMessage("user", request)],
                            response_format={"type": "json_schema", "json_schema": {"schema": schema}})
                        row.update(raw=answer.content, provider_latency_s=answer.latency_s, finish=answer.finish_reason,
                                   prompt_tokens=answer.prompt_tokens, completion_tokens=answer.completion_tokens)
                    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                        row["error"] = type(exc).__name__
                    row["latency_ms"] = (perf_counter() - start) * 1000
                    row["score"] = score(case, row["raw"], active_ids)
                    grouped[name].append(row)
                    out.write(json.dumps(row) + "\n")
                    out.flush()
                print(f"Model case {index + 1}/{len(cases)}", flush=True)
    finally:
        await provider.close()
    async with httpx.AsyncClient(base_url=SERVER, trust_env=False, timeout=10) as client:
        model_after = await local_model_info(client)
    comparisons = (("bm25_k5", name) for name in names if name != "bm25_k5")
    write_json(output / "mapping.json", {
        "arms": {name: summary(rows) for name, rows in grouped.items()},
        "cost": {name: {**{key: distribution([row.get(key) for row in rows]) for key in (
            "prompt_tokens", "completion_tokens", "latency_ms", "request_bytes", "references_bytes")},
            "estimated_end_to_end_ms": distribution([row["latency_ms"] + costs[row["id"]][ARMS[name][0]]
                                                     for row in rows]),
            "inference_errors": sum("error" in row for row in rows)} for name, rows in grouped.items()},
        "paired": {f"{b}_vs_{a}": {**paired(grouped[a], grouped[b]), "exact_contingency": paired_outcomes(grouped[a], grouped[b]),
                                     "case_deltas": [y["id"] for x, y in zip(grouped[a], grouped[b], strict=True)
                                                     if x["score"]["exact"] != y["score"]["exact"]]}
                   for a, b in comparisons},
        "model_after": model_after,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--e5-snapshot", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.output, args.e5_snapshot))
