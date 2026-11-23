# KAYAN ATT&CK exploratory v2 results

**20 November 2026.** Both registered passes finished with 72 valid responses. Neither arm completed a single expected evidence group. Hybrid E5-192 produced more unsupported findings and incurred a higher mean error cost in both passes. The primary uncertainty interval spans zero. These results come from fictional telemetry and an AI-authored rubric. Independent human validation and production readiness remain unestablished.

## Execution and verification

Khaled Mohamed authorized the local experiment on 20 November 2026. The preflight matched frozen registration SHA-256 `66254d7c5fa4128faac5749bf78ae3a5ba8de324ee232b505098e462d955d8c3`, the registered source and dataset hashes, output schema, scoring settings, three E5 snapshot files, Ollama 0.40.13 and the local Qwen2.5 7B digest. Each of the 18 cases ran once per arm per pass. The ledger contains 72 matching start and result pairs in registered order. Every response reported `stop`, and the model residency check confirmed a 4,096-token context. The runner exited successfully. The console status showed SovereignEG disabled before and after. Scores were recomputed from stored responses and matched the registered aggregation. The original human-gated comparison remained sealed. [Frozen registration](../eval/reports/attack_mapping_v2_20261120/registration.json) · [Run lock](../.build/attack_exploratory_v2/run/run-lock.json)

## Evidence and classification performance

Each column contains 18 responses and ten expected technique occurrences over nine positive cases.

| Metric | Pass 1 BM25 | Pass 1 hybrid | Pass 2 BM25 | Pass 2 hybrid |
| --- | ---: | ---: | ---: | ---: |
| Valid responses | 18/18 | 18/18 | 18/18 | 18/18 |
| Exact cases | 3/18 | 1/18 | 3/18 | 1/18 |
| Technique selection TP / FP / FN | 5 / 39 / 5 | 4 / 48 / 6 | 5 / 39 / 5 | 4 / 49 / 6 |
| Technique-selection F1 | .185 | .129 | .185 | .127 |
| Completed evidence groups | 0/10 | 0/10 | 0/10 | 0/10 |
| Missed grounded behaviors | 10 | 10 | 10 | 10 |
| Unsupported technique claims | 44 | 52 | 44 | 53 |
| Relevant citations | 5/51 (9.8%) | 5/59 (8.5%) | 5/51 (9.8%) | 5/58 (8.6%) |
| Unsupported citations | 46 | 54 | 46 | 53 |
| Record-pair F1 | .135 | .123 | .135 | .122 |
| Abstentions on known negatives | 3/6 | 1/6 | 3/6 | 1/6 |
| Abstentions on inconclusive cases | 0/3 | 0/3 | 0/3 | 0/3 |
| Overall abstentions | 3/18 | 1/18 | 3/18 | 1/18 |
| Total registered error cost | 144 | 168 | 144 | 169 |
| Mean cost per case | 8.000 | 9.333 | 8.000 | 9.389 |

Technique-selection credit requires the keyed ID. Grounding requires the model to cite every statement in a sufficient group. All exact cases were abstentions on known negatives. BM25 abstained on `elm`, `pearl` and `silver`. Hybrid abstained on `elm`. Both arms issued findings on both failed-action cases in both passes. [Registered results](../.build/attack_exploratory_v2/run/results.json)

### Where the evidence failed

BM25's shortlist included five of the ten expected technique occurrences per pass. Hybrid's included four. The model selected all expected IDs that were in its shortlist and selected zero IDs outside its shortlist across the entire run. Even with the keyed technique present, it completed zero evidence groups. This identifies both missing reference coverage and missed use of evidence already in the prompt. It does not establish how the model would behave with an oracle shortlist.

- **`cedar`.** Both arms cited completed log clearing and omitted the independent record linking it to the unauthorized session.
- **`flint`.** Both arms mapped a withdrawn allegation in both passes. Hybrid assigned the Windows event-log clearing technique and cited the examiner's finding of no corroboration.
- **`silver`.** BM25 abstained twice on the authorized role grant. Hybrid assigned the cloud role-change technique twice, citing the grant without evidence of hostile control.
- **`slate`.** Both expected techniques were absent from both arms' shortlists and missed in both passes.

BM25's unsupported citations in each pass comprised 44 unkeyed, one unlinked and one topical citation. Hybrid's pass-one count comprised 47 unkeyed, three topical, two contradictory, one unresolved and one action-only citation. In pass two it had one fewer topical citation. An unkeyed citation lacks support in the frozen authored rubric. [Raw responses and citation traces](../.build/attack_exploratory_v2/run/attempts.jsonl)

## Uncertainty and repeatability

The preregistered primary outcome was pass-one mean cost for BM25 minus hybrid. It was **−1.333 per case**, with a **95% paired family-cluster percentile interval of [−2.944, +0.778]** from 10,000 draws. Negative values favor BM25. Family cost differences totaled audit −7, availability +10, display −6, identity −13, mail −6 and recovery −2. The descriptive second-pass difference was −1.389 per case. The interval spanning zero and the six synthetic case families limit confidence in the comparative effect.

| Same-arm agreement across passes | BM25 | Hybrid |
| --- | ---: | ---: |
| Valid pairs | 18/18 | 18/18 |
| Identical raw text | 17/18 | 16/18 |
| Identical technique sets | 18/18 | 17/18 |
| Identical citation sets | 17/18 | 16/18 |

All 36 case-by-arm request payloads were identical across the two passes. With temperature zero, BM25 still changed citations on `indigo` with no cost change. Hybrid changed `indigo` and `silver`, with costs moving from 12 to 10 and from 12 to 15, respectively. The second pass measures repeatability on the same cases. [Paired analysis](../.build/attack_exploratory_v2/run/results.json)

## Runtime and resource consumption

Total wall time was **190.0 seconds**. Ollama reported **123.1 seconds** in summed request durations. The remaining approximately 67 seconds includes audit, index construction, retrieval, orchestration and logging. The run did not instrument those phases individually.

| Ollama measurement | Pass 1 BM25 | Pass 1 hybrid | Pass 2 BM25 | Pass 2 hybrid |
| --- | ---: | ---: | ---: | ---: |
| Total server time (s) | 33.759 | 32.290 | 27.178 | 29.824 |
| Median request (s) | 1.686 | 1.699 | 1.553 | 1.535 |
| Empirical p95 request (s) | 4.046 | 3.096 | 2.922 | 2.582 |
| Prompt tokens reported | 10,123 | 10,037 | 10,123 | 10,037 |
| Generated tokens | 1,682 | 1,882 | 1,682 | 1,852 |

The largest model load time was 4.380 seconds on pass-one BM25. The request table measures serving time, and cannot isolate incremental E5 latency. The companion sampler recorded 36 snapshots around five seconds apart. The Python runner's sampled peak RSS was **656 MiB**, and its last observed cumulative CPU time was **306.7 seconds**. Minimum sampled available RAM was **17.94 GiB**. RTX 5060 Laptop GPU memory use rose from **1,517 MiB** at the first sample to **6,568 MiB** at the sampled peak. Device-wide sampled GPU peaks were **96% utilization**, **102.45 W** and **68.12 °C**. Periodic sampling can miss brief peaks. Ollama reported 4,755,397,016 bytes of loaded model VRAM after the run. The E5 loader reported an unexpected `embeddings.position_ids` key and continued. The experiment did not isolate any effect from that warning. [Resource samples](../.build/attack_exploratory_v2/resources.jsonl) · [Runner log](../.build/attack_exploratory_v2/runner.log)

## Retained evidence

The private run directory preserves all raw responses, requests, scoring traces and logs. There were no failed or retried cells.

| Artifact | SHA-256 |
| --- | --- |
| `attempts.jsonl` | `3fde89e782aa4c753aabb5b9604ed2d0ea56f90ca6fc6587bc95efca537214ca` |
| `results.json` | `d193412c182f84477a595b229b64b1b117474ebb8b887666c96bd948a72d38d5` |
| `run-lock.json` | `5b8106a4e86d14f1e7a35fc7f65a14eeef95d2f68a087509d4ee4435622b2923` |
| `resources.jsonl` | `2a7cab6d7701bdd59f8b87dd4eb62a2155442bdb0be2eae6598aa74ad78cca97` |
| `runner.log` | `2b5face21a3bf4bb43939bdbd308aed79a71c893ca61a0b513f1e6f1d9deac58` |
| `stakeholder-authorization.json` | `1034705f667a887ae34c5f7f8b88dece6ed09899fa516ccdd0829fa481c2381e` |
