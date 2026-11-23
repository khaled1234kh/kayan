# Cloud pivot security and evaluation

20 November 2026

Keep SovereignEG as a research candidate. Pause remote execution and use the offline defensive evidence benchmark to resolve retrieval and mapping quality before committing to more model work.

The later [retrieval and evidence mapping benchmark](ATTACK_RETRIEVAL_AND_EVIDENCE_MAPPING_2026-11-20.md) compares five retrieval methods and adds an oracle test on a separate cohort. It also records the direct-provider pause. This document preserves the preceding results.

## Boundary fixes

| Confirmed behavior in the original experiment | Change and verification |
| --- | --- |
| An HTTP caller could ask the experimental analysis service to sign and load a loopback ROE for a chosen engagement. The issue window extended to 2099. | Removed ROE issuance from the analysis client. Direct analysis requires an existing engagement and a loopback Ollama configuration. Experimental agents identify themselves with their own roles. No Cedar permissions were added. |
| Status, reindex and assessment paths could initialize cloud embeddings. The retrieval query included caller-controlled text. The JSON job routes exposed results by job ID. | Status now reads non-secret configuration only. Usage returns an empty object. Job creation, polling and reindex return HTTP 503 before credential loading, classification, storage, indexing or network initialization. This contains the path while job ownership and any future outbound data approval remain engineering work. |
| The aggregate could return a consolidated report and model outputs when report authorization failed. | A denial or outage withholds both. A mocked test covers successful agent responses followed by report denial. |
| Retries bypassed the sliding-window count, arbitrary provider error bodies could be surfaced, and fallback was the registry default. | Count every attempted HTTP dispatch against the shared limiter. Cap concurrent chat and embedding calls at two per configured adapter. Treat 402 as terminal, respect bounded 429 backoff and report transport errors without response bodies. Pin the adapter's credential destination to the documented HTTPS API and require explicit fallback selection. The limiter applies to one adapter instance in one process. |
| Reindex used a moving STIX URL. Cache validation used technique IDs and could accept weak provenance. Mitigation parsing kept at most one relationship. | Load a named local ZIP member, verify SHA-256 and the embedded Enterprise collection version, and build a local lexical index. Include per-record technique ID, source URL, STIX ID, object version and corpus digest in retrieval results. Traverse active mitigation and sub-technique parent relationships and exclude revoked or deprecated entries. |

The pinned Enterprise 20.1 JSON is 55,277,605 bytes and contains 26,699 objects. The active index contains 227 parent techniques and 479 sub-techniques. SHA-256 is `539a843a7b53ed9749740b2123dddae3726b1a4831841c32aca740b011b910b5`. The pre-run fixture check found that T1070.001 was revoked, so the event-log case uses the active successor T1685.005. [MITRE release](https://github.com/mitre-attack/attack-stix-data/releases/tag/v20.1)

The console backend was restarted in review mode after its selected session was confirmed failed. The restored selection retained engagement `0d6ebb9f-02d6-49db-aa74-25ed78eb0f27` and its failed state. The running instance returned `enabled: false` for cloud status and HTTP 503 for job creation. Existing native Gate and lab listeners were observed during preflight. Those observations establish local listener state only. The adopted boundary covers the experimental cloud API. Existing production identity and isolation limitations are tracked in the master handoff.

## Frozen defensive evidence benchmark

The fixture contains 16 fictional cases in eight families, with nine expected evidence and technique pairs. Cases model retrospective review, including approved maintenance, blocked actions, contradicted allegations and an instruction embedded inside an evidence record. Gold labels are authored by the experimenter. The loader verifies the fixture hash and checks all gold technique IDs and evidence record IDs.

The two matched arms give the model identical observation records and use the same scorer. The retrieval arm adds five local TF-IDF candidate references. Call order alternates by case. The scorer checks the raw response contract and the exact technique and evidence pairs. Malformed responses count as contract failures. Reported unsupported pairs count only parsed responses. The frozen inputs, model digests, settings, token counts, per-case responses and full retrieval provenance are in the run artifacts.

| Local model and output format | Context | Contract | Exact | Correct / unsupported / missed pairs | Pair F1 | p95 seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen2.5 7B, unconstrained | No retrieval | 8/16 | 7/16 | 0 / 0 / 9 | 0.000 | 6.844 |
| Qwen2.5 7B, unconstrained | Lexical | 10/16 | 7/16 | 0 / 0 / 9 | 0.000 | 10.454 |
| Qwen2.5 7B, JSON Schema | No retrieval | 16/16 | 7/16 | 1 / 8 / 8 | 0.111 | 0.719 |
| Qwen2.5 7B, JSON Schema | Lexical | 16/16 | 8/16 | 1 / 5 / 8 | 0.133 | 0.671 |
| Qwen2.5 1.5B, JSON Schema | No retrieval | 16/16 | 8/16 | 0 / 3 / 9 | 0.000 | 2.344 |
| Qwen2.5 1.5B, JSON Schema | Lexical | 16/16 | 3/16 | 0 / 13 / 9 | 0.000 | 0.281 |

Retrieval recovered **2/9 expected technique occurrences**, with MRR@5 and nDCG@5 both **0.250** across eight positive cases. The 7B structured arm gained one exact case with retrieval. Its exploratory paired interval was **−12.5 to +25.0 percentage points** across families. The 1.5B structured arm lost five exact cases, with an interval of **−56.25 to −12.5 points**. Twelve parsed invalid IDs appeared in that lexical arm. Both structured experiments reused the original cases, so their results are diagnostic. One warm/cold sequence per model makes p95 sensitive to model loading. Ollama supports a native JSON schema parameter. [Ollama chat API](https://docs.ollama.com/api/chat)

The historical 173/4 checkpoint, the earlier 15 recognized technique IDs and the historical Planner 24/30 and 26/30 scores measure different tasks. Keep those records alongside the November 1 grounding regression and bounded follow-up tie. This benchmark used fictional records and local inference only. It did not execute specialist tools or create new vulnerability findings.

## Provider and decision

The public catalogue lists `SovereignEG/Qwen3.8-27B-FP8` as Egypt-hosted. Plan entitlements can change, Student access is personal, overages can use account credit, and the provider supports model-specific upstream routes. The dashboard and authenticated model metadata are needed to establish account caps and actual routing. The handoff records prior key exposure. The account holder needs to revoke and replace it, confirm automatic balance use is off and confirm actual spending limits before a live provider comparison. [Model catalogue](https://sovereigneg.com/models/SovereignEG%2FQwen3.8-27B-FP8) · [Student plan](https://sovereigneg.com/docs/student-plan) · [Rate limits](https://sovereigneg.com/docs/rate-limits) · [Provider disclosure](https://sovereigneg.com/legal/provider-disclosure)

Cloud quality, billed cost and latency are unmeasured in this pass. Qwen3 8B and Granite 4.2 8B were absent from local Ollama. Distributed rate limits, account routing, cloud egress approvals, comparative semantic retrieval and comparative single-agent versus parallel quality remain open. Keep this experiment outside the live tool-dispatch workflow. The measured retrieval miss rate and evidence errors give concrete targets for the next independently labelled offline benchmark. Defer fine-tuning until a fresh cohort isolates a persistent error after retrieval and output-format fixes.

## Verification

The pre-change Python suite passed 177 tests. The revised suite passed 191, with 81 deprecation warnings. Offline Rust checks passed 28 tests and the focused Go governance suite passed 10. The 3D console TypeScript check passed. The score audit recomputed parsed response scores, verified the runner for the original 7B run, and matched all three historical November 1 grounding hashes. [Score audit](../eval/reports/ai_cloud_20261120_verification/score-audit.json) · [Restart evidence](../eval/reports/ai_cloud_20261120_verification/runtime.json) · [Working-tree status](../eval/reports/ai_cloud_20261120_verification/git-status.txt)

## Reproduction and artifacts

From the repository root, choose unused output directories.

```powershell
python -B -m pytest tests -q -p no:cacheprovider
cargo test --offline --locked --manifest-path trustgate/service/Cargo.toml --target-dir .build/rust -q
python -B -m eval.ai_benchmark --output eval/reports/ai_cloud_retrieval_replay
python -B -m eval.ai_benchmark --model qwen2.5:7b --output eval/reports/ai_cloud_qwen7b_replay
python -B -m eval.ai_benchmark --model qwen2.5:7b --structured --output eval/reports/ai_cloud_qwen7b_schema_replay
python -B -m eval.ai_benchmark --model qwen2.5:1.5b --structured --output eval/reports/ai_cloud_qwen15b_schema_replay
```

[Frozen cases](../eval/fixtures/ai/defensive_evidence_v1.json) · [Retrieval](../eval/reports/ai_cloud_20261120_retrieval/results.json) · [Original 7B](../eval/reports/ai_cloud_20261120_qwen25_7b/results.json) · [Structured 7B](../eval/reports/ai_cloud_20261120_qwen25_7b_structured/results.json) · [Structured 1.5B](../eval/reports/ai_cloud_20261120_qwen25_15b_structured/results.json)
