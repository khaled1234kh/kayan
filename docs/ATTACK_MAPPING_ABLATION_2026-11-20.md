# ATT&CK mapping ablation and evidence review

**2026-11-20, Africa/Cairo.** Field-weighted BM25 at five references stays the reference comparator. Reciprocal-rank fusion with local E5 at 192 tokens is the one challenger to carry forward. It led on this diagnostic cohort, with uncertainty spanning no gain and a repeat-run score change under identical prompts. Keep deployment and fine-tuning deferred.

## Controlled protocol

The [previous report](ATTACK_RETRIEVAL_AND_EVIDENCE_MAPPING_2026-11-20.md) remains the historical record. This run reused its 32 fictional cases across 16 families, with 16 expected technique–record pairs and 16 negative cases. Labels are author-provided. The cohort was already inspected, so its results support diagnosis and candidate selection only.

Seven arms sent 224 structured requests to local Qwen2.5 7B. All used the same pinned Enterprise ATT&CK 20.1 corpus, common JSON schema, temperature 0, 370 generated tokens, and the same reference formatting and hash-based presentation order. Ollama reported a 4,096-token loaded context. Arm order rotated by case. The second BM25 prompt added a predeclared interpretation check for source reliability, scope, negative evidence and authorization status stated in observations. That wording had no effect on TrustGate permissions. The reranking arm used E5-192 to reorder only the top ten field-BM25 results, then sent the top five.

| Model context | Exact / 32 | TP / FP / FN | Pair precision | Pair recall | Pair F1 | Negative abstention / 16 | Total abstentions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Field BM25 @ 5 | 22 | 8 / 6 / 8 | .571 | .500 | .533 | 14 | 18 |
| Hybrid E5-192 @ 5 | 26 | 11 / 3 / 5 | .786 | .688 | .733 | 15 | 18 |
| Hybrid E5-512 @ 5 | 24 | 10 / 4 / 6 | .714 | .625 | .667 | 14 | 18 |
| Field BM25 @ 3 | 23 | 8 / 5 / 8 | .615 | .500 | .552 | 15 | 20 |
| Field BM25 @ 10 | 24 | 9 / 4 / 7 | .692 | .563 | .621 | 15 | 19 |
| Dense rerank of BM25 shortlist @ 5 | 23 | 8 / 4 / 8 | .667 | .500 | .571 | 15 | 20 |
| Field BM25 @ 5, interpretation prompt | 22 | 7 / 3 / 9 | .700 | .438 | .538 | 16 | 23 |

All 224 responses passed the schema and finished normally. Each stored prediction passed the existing deterministic ID, quote-binding and justification-presence checks, so raw and mechanically released pair counts matched. The checks allow semantically unsupported mappings with literal quotes. They do not establish adjudicated correctness.

### Matched results and uncertainty

For BM25@5 versus hybrid-192@5, both were exact on 21 cases, only BM25 on one, only hybrid on five, and neither on five. The exact difference was +12.5 percentage points, with a descriptive family-paired 95% bootstrap interval of [0.0, +25.0] points. Positive-case recall changed by +18.75 points with an interval of [−6.25, +43.75] points. The 10,000 draws resampled the 16 matched families together with seed 391. These small-cohort estimates include zero and do not establish superiority or equivalence. All secondary exact-case intervals also include zero. The [full matched results](../eval/reports/ai_mapping_ablation_20261120/mapping.json) contain contingencies and the case IDs that changed.

BM25@10 gained one true pair and eliminated two unsupported pairs relative to BM25@5 on this cohort, with nearly twice the prompt tokens. The interpretation suffix eliminated three unsupported pairs and lost one true pair. It abstained on all negatives, while its four retrieved-but-abstained cases exceeded BM25’s two. Keep that measured tradeoff visible. The earlier evidence-first prompt also traded recall for fewer unsupported pairs.

The historical hybrid returned 24/32 exact and 9 / 4 / 7 on the same 32 cases. The repeated hybrid matched all 32 contextual ID lists and prompt hashes, yet only 22 raw response strings and 29 case scores matched. The historical result remains valid for that execution. Temperature 0 and a pinned model did not give exact repeatability in these two runs. The source of the drift remains unisolated.

## E5 implementation and ingestion audit

The local E5 snapshot matched the earlier artifact hashes at revision `ffb93f3bd4047442299a41ebb6fa998a38507c52`. Both arms used the documented asymmetric prefixes, masked mean pooling, and L2 normalization. The largest measured deviation from unit norm was 1.19 × 10⁻⁷. The model card describes English input and a 512-token ceiling. The 192-token cap was a local default. The new optional cap preserves that default and exposes 512 only as an experimental arm. Transformers reported an unexpected `embeddings.position_ids` checkpoint key during both loads. The model encoded successfully, and the default arm reproduced every historical top-ten dense, hybrid and field-BM25 ranking across 32 cases. [E5 model card](https://huggingface.co/intfloat/e5-small-v2)

| Retriever | Top 1 / 16 | Top 3 / 16 | Top 5 / 16 | Top 10 / 16 | MRR@10 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Field BM25 | 6 | 11 | 12 | 14 | .545 | .626 |
| Dense E5-192 | 2 | 3 | 3 | 6 | .173 | .219 |
| Dense E5-512 | 3 | 4 | 6 | 8 | .250 | .307 |
| Hybrid E5-192 | 5 | 12 | 14 | 15 | .531 | .630 |
| Hybrid E5-512 | 6 | 11 | 12 | 14 | .551 | .630 |
| Dense rerank of BM25 shortlist | 3 | 10 | 12 | 14 | .420 | .530 |

The 706 active techniques each had a description, platforms, tactics and a linked detection strategy. The snapshot yielded 479 parent links, 595 techniques with mitigation links, zero aliases in the parsed technique field, and zero legacy detection text. Field BM25 weights identity at 2.0, description at 1.0 and platforms, tactics, detection metadata and parent ID at 0.35. It scores joined and individual record text and takes the maximum. The dense arm uses one passage per technique consisting of name, description and linked detection-strategy names. Its input omits technique IDs, tactics, platforms, mitigations and example relationships. Fusion combines each method’s first 100 ranks with reciprocal-rank constant 60.

Passage token median was 289, with a maximum of 994. The cap truncated 567/706 passages at 192 and 64/706 at 512. The strategy suffix was excluded for at least 549 and 60 passages, respectively, because the prefixed name and description already exceeded the cap. All 32 queries fit within 48 tokens, so the experimental cap changed passage content only. A separate generator formatting step supplies the first 400 description characters with IDs and provenance. It shortens 700/706 descriptions in the catalogue. E5-512 improved standalone retrieval while the fusion retrieved fewer correct top-five candidates and generated fewer correct pairs than E5-192.

## Evidence interpretation

The case matrix links all 32 cases across 12 historical or new arms. The full trace records each author label and evidence ID, full synthetic observations, deciding record, candidate rank, supplied excerpt and provenance, raw citation and justification, literal binding, diagnostic taxonomy and the first actionable failure. Recounting 384 stored responses reproduced their recorded case scores. All correctly predicted pairs in the retrieval-backed arms had their technique supplied in context. Correct BM25@5 and hybrid-192 pairs also quoted the distinguishing action phrases checked by the analyst (8/8 and 11/11 respectively). The phrase checks supplement analyst review of the full record. Ambiguous or disputed labels still need independent adjudication. [Case matrix](../eval/reports/ai_mapping_ablation_20261120/case-matrix.md) · [Full trace](../eval/reports/ai_mapping_ablation_20261120/case-trace.json)

| Case | Failure seen | What the deciding record supports |
| --- | --- | --- |
| fresh-01 · E2 | Hybrid-192 misses the domain-account candidate at rank 10. BM25 supplies it at rank 4 and instead predicts account creation. Oracle abstains. | A completed update under an existing domain account. E2 does not describe account creation. Review whether the record establishes the existing-account use with sufficient specificity. |
| fresh-03 · E1 | Both main arms and the oracle abstain despite supplying the cloud-account candidate. | An established, unauthorized session under an existing cloud billing account, with absent consent confirmed. |
| fresh-07 · E1 | BM25 misses the removal candidate at rank 15. Hybrid succeeds with rank 2, while the earlier oracle abstained. | Existing staff accounts were disabled by an intruder and their owners immediately lost access. |
| fresh-09 · E2 | Both main arms and the oracle predict remote desktop protocol while the screen-capture reference is supplied. | Matching telemetry establishes acquisition of live desktop images. The record supplies no affirmative evidence of a remote desktop session. |
| fresh-13 · E2 and fresh-15 · E1 | Hybrid ranks remote-mail collection 23rd and abstains on fresh-13. It supplies local-email collection third on fresh-15 and still predicts clear mailbox data. | Direct collection from a remote service versus gathering messages from a local archive. Each record excludes the competing location or access path, and neither establishes mailbox clearing. |
| fresh-19 · E1 | BM25 misses service stop at rank 7. Hybrid succeeds at rank 5, while the earlier oracle abstained. | One terminated worker service and explicit evidence that its host stayed online. |
| fresh-22 · E2 | Both main arms map Windows log clearing and cite `the independent collector had a gap and the examiner found no corroboration.` | An unsupported allegation. The exact quote passed the binding check and explicitly states that the evidence was uncorroborated. |
| fresh-24 · E1 | BM25 maps logging disabled and quotes the later correction in the same source record. | The corrected report establishes normal capture and traces the original claim to a tabletop. |

Hybrid-192 had two missing references, one retrieved-but-abstained positive case, two retrieved-but-wrong-technique cases and three unsupported pairs. The historical oracle supplied all expected references and still missed six pairs. This identifies separate retrieval and interpretation limitations. Quote binding should retain its narrower role and semantic review should remain evidence-based. Mapping guidance independently emphasizes observed behavior, specificity and adequate telemetry. [MITRE Center for Threat-Informed Defense mapping guidance](https://center-for-threat-informed-defense.github.io/summiting-the-pyramid/analytic-design/mappingdetections/)

Separate local probes modified retrieved descriptions to request a false mapping with a real quote on two reviewed negatives. Both prompts abstained on all four injected and all four clean controls. The unit test also confirms the prompt channel and rejects a quote borrowed from a reference. These probes cover two examples. The trace’s source-semantics failures still demonstrate a limitation even with verbatim quotes.

## Resource cost and verification

| Arm | Median prompt tokens | Median retrieved JSON bytes | Estimated end-to-end p50 / p95 (ms) |
| --- | ---: | ---: | ---: |
| BM25 @ 5 | 1,445.5 | 3,605.5 | 645 / 2,607 |
| Hybrid E5-192 @ 5 | 1,452.5 | 3,610.0 | 661 / 2,472 |
| Hybrid E5-512 @ 5 | 1,448.5 | 3,615.5 | 639 / 2,562 |
| BM25 @ 3 | 952.0 | 2,167.5 | 463 / 2,390 |
| BM25 @ 10 | 2,678.5 | 7,219.0 | 1,039 / 2,994 |
| Shortlist rerank @ 5 | 1,448.0 | 3,618.0 | 640 / 2,379 |
| BM25 @ 5, interpretation | 1,519.5 | 3,605.5 | 663 / 2,708 |

Estimated end-to-end latency adds per-case retrieval time to the measured local Ollama round trip and excludes catalogue or model cold start. The median retrieval cost was 1.88 ms for BM25 and 20.41 ms for hybrid-192. Index fit took 0.19 s for BM25, 37.58 s for E5-192 and 79.77 s for E5-512. CPU working set was about 170 MiB after BM25, 656 MiB after loading and fitting E5-192, and 894 MiB after the later E5-512 fit, with a 904 MiB sampled process peak. These are cumulative process readings with library and allocator overhead, not isolated per-model memory. Ollama separately reported about 4.43 GiB of resident VRAM at the end. Median generation was nine tokens because of frequent abstentions. No request failed. The [manifest](../eval/reports/ai_mapping_ablation_20261120/manifest.json) and [timing distributions](../eval/reports/ai_mapping_ablation_20261120/mapping.json) record the model digest, per-arm prompt, configuration, environment and detailed distributions.

The pre-change Python suite passed 201 tests. The focused offline suites passed 36, and the complete post-change Python suite passed 205 with the same 81 deprecation warnings. The local console returned HTTP 503 for submit, poll and reindex, with `enabled: false` and empty usage. The provider guard tests covered mock-only cloud transport. The selected engagement's ID, status and response digest matched before and after. Rust, Go and frontend suites were outside this offline pass. [Verification and checksums](../eval/reports/ai_mapping_ablation_20261120/verification.json)

## Reproduce the diagnostic run

Run from the repository root with the pinned corpus, pinned local E5 safetensors snapshot, local Ollama model, and the benchmark-only packages `torch`, `transformers` and `psutil` already present. The model runner checks the model and snapshot hashes. The evidence run avoids downloads. The exact executed runner is retained under `source-baseline`. The current runner delays importing the profiling dependency until a benchmark actually runs.

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$sourceRun = 'eval/reports/ai_mapping_ablation_20261120'
$resultPath = 'eval/reports/ai_mapping_ablation_reproduction'
$e5Snapshot = "$env:USERPROFILE/.cache/huggingface/hub/models--intfloat--e5-small-v2/snapshots/ffb93f3bd4047442299a41ebb6fa998a38507c52"
New-Item -ItemType Directory -Path "$resultPath/source-baseline" -ErrorAction Stop
Copy-Item -LiteralPath "$sourceRun/source-baseline/ranking.py" -Destination "$resultPath/source-baseline/ranking.py"
python -B -m eval.ai_mapping_ablation --output $resultPath --e5-snapshot $e5Snapshot
python -B -m eval.ai_mapping_trace $resultPath
python -B -m eval.ai_mapping_injection "$resultPath/reference-injection-probe.json"
python -B -m pytest tests -q -p no:cacheprovider
```

Four blinded review forms and 24 fresh unlabelled observations are ready. Lock the next comparison to **field BM25 @ 5 versus hybrid E5-192 @ 5, both on the base prompt**. The fresh cohort needs two completed independent reviews, adjudicated labels and a stakeholder-approved decision rule before any model run. Additional diagnostics on the already inspected cohort cannot fulfill that requirement. Keep SovereignEG paused. [Review and confirmation protocol](ATTACK_LABEL_REVIEW_AND_CONFIRMATION_2026-11-20.md)
