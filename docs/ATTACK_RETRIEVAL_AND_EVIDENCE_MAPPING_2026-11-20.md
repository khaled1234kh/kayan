# ATT&CK retrieval and evidence mapping

20 November 2026

This is the original retrieval and mapping checkpoint. The follow-up compares field BM25 directly with hybrid retrieval on the reused cohort and records independent-review preparation. [November 20 matched ablation](ATTACK_MAPPING_ABLATION_2026-11-20.md)

This compares retrieval and model decisions on fictional retrospective records. The catalogue remains Enterprise ATT&CK 20.1, SHA-256 `539a843a7b53ed9749740b2123dddae3726b1a4831841c32aca740b011b910b5`. The previous 16 cases were used for selection and diagnostics. The 32 new cases were frozen before ranking the new cohort. They use different incident families, matched benign or unconfirmed variants, and author-supplied evidence pointers. An independent assessment of their labels is pending. Give reviewers the blinded packet without the author labels or model outputs. [MITRE release](https://github.com/mitre-attack/attack-stix-data/releases/tag/v20.1) · [Blinded review packet](../eval/reports/ai_retrieval_mapping_20261120/blinded_review_packet.json)

## Audit of the original benchmark

The new audit replayed 96 archived responses across six arms against the original gold evidence pairs and matched the archived contract, exact, correct, unsupported and missed counts. Positive-case recall counts a positive case only when at least one correct evidence pair was predicted. Negative specificity counts well-formed empty predictions on negative cases. Invalid responses cannot earn credit as abstentions. Unsupported counts cover parsed mappings.

| Historical arm | Exact cases | Positive cases with a correct pair | Negative specificity | Pair precision | Pair recall | Pair F1 | Explicit abstentions | Unsupported pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7B unconstrained, no retrieval | 7/16 | 0/8 | 7/8 | Undefined | 0/9 | 0.000 | 8/16 | 0 |
| 7B unconstrained, TF-IDF | 7/16 | 0/8 | 7/8 | Undefined | 0/9 | 0.000 | 10/16 | 0 |
| 7B structured, no retrieval | 7/16 | 1/8 | 7/8 | 1/9 | 1/9 | 0.111 | 8/16 | 8 |
| 7B structured, TF-IDF | 8/16 | 1/8 | 7/8 | 1/6 | 1/9 | 0.133 | 10/16 | 5 |
| 1.5B structured, no retrieval | 8/16 | 0/8 | 8/8 | 0/3 | 0/9 | 0.000 | 13/16 | 3 |
| 1.5B structured, TF-IDF | 3/16 | 0/8 | 3/8 | 0/13 | 0/9 | 0.000 | 4/16 | 13 |

All eight exact matches in the 1.5B structured no-retrieval arm came from negatives. The unconstrained runs generated malformed JSON. Their zero parsed unsupported count reflects that scoring boundary and does not establish absence of unsupported text.

## Retrieval

The original TF-IDF baseline uses the first 900 characters per catalogue entry. Plain BM25 uses that same text with normalized lexical tokens. Field-weighted BM25 also indexes full behavior descriptions and separately weights technique names and identifiers, aliases if present, platform and tactic names, legacy detection text and linked detection strategy names. Only valid, active STIX relationships are used. The local E5 small encoder uses a pinned safetensors snapshot and masked mean pooling. The hybrid ranks by reciprocal rank fusion of field-weighted BM25 and E5. Scores tie-break by technique ID. The frozen selection rule maximized top-five development hits, then development MRR@10, and picked the hybrid before the new cohort was ranked. [BM25 reference](https://www.nowpublishers.com/article/Details/INR-019) · [Pinned E5 revision](https://huggingface.co/intfloat/e5-small-v2/commit/ffb93f3bd4047442299a41ebb6fa998a38507c52)

| Ranker | Development hits at 1 / 3 / 5 / 10 (of 9) | New cohort hits at 1 / 3 / 5 / 10 (of 16) | New MRR@10 | New nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| Historical TF-IDF | 2 / 2 / 2 / 2 | 3 / 10 / 11 / 11 | 0.401 | 0.474 |
| Plain BM25 | 3 / 5 / 5 / 5 | 4 / 9 / 9 / 11 | 0.402 | 0.471 |
| Field-weighted BM25 | 2 / 3 / 5 / 5 | 6 / 11 / 12 / 14 | 0.545 | 0.626 |
| Dense E5 | 1 / 2 / 3 / 5 | 2 / 3 / 3 / 6 | 0.173 | 0.219 |
| Hybrid BM25 and E5 | 1 / 5 / 7 / 9 | 5 / 12 / 14 / 15 | 0.531 | 0.630 |

The hybrid recovered 14/16 expected labels in its top five compared with 11/16 for TF-IDF. Field-weighted BM25 ranked the first relevant item higher on average at depth ten. Dense retrieval alone underperformed both lexical baselines.

### Why the original top five missed

The archive and the repeat run gave identical top-five lists on all 16 development cases. The after-the-fact query isolation and truncation diagnostic held the TF-IDF parameters fixed. A change in rank under either test helps identify a contributing factor. It cannot prove the remaining differences come from a single feature.

| Case and gold label | TF-IDF rank | Same TF-IDF without cap | TF-IDF on supporting record alone | Hybrid rank | Evidence and diagnosis |
| --- | ---: | ---: | ---: | ---: | --- |
| A1 T1078 | 164 | 99 | 164 | 3 | Completed unauthorized session through an existing account. The short entry shared mainly account terms. Full text improves rank, while the dense arm reaches rank 4, consistent with vocabulary and ranking effects. |
| B1 T1098 | 61 | 108 | 61 | 4 | Confirmed unauthorized access change. Distinctive access and preservation terms were present. BM25 reached rank 1, consistent with weighting and normalization effects. |
| C1 T1685.005 | 1 | 1 | 1 | 1 | Intentional clearing of Windows event logs. Direct title match. The active sub-technique outranked alternatives. |
| D1 T1489 | 28 | 36 | 28 | 2 | An intruder stopped a service. Relevant vocabulary was present. Plain BM25 reaches rank 3, while removing the cap did not help. |
| E1 T1486 | 352 | 89 | 352 | 2 | Unauthorized encryption made records inaccessible. Shared behavior stems were absent in the capped text. Full indexing helped and dense similarity supplied a stronger candidate. |
| F1 T1078 | 142 | 97 | 150 | 9 | Unauthorized use under an existing account. Removing the second record did not help the capped baseline. Vocabulary and ranking remain plausible contributors. |
| F1 T1098 | 60 | 140 | 28 | 4 | A second record confirmed an unauthorized access change. Isolating it recovered rank 28. The term-weighted variants reached rank 2, showing query composition and weighting both matter. |
| F2 T1098 | 75 | 135 | 24 | 10 | A verified access change was accompanied by an unrelated exercise about a session. Removing the exercise record raised the baseline rank from 75 to 24. Coverage still depended on the ranking method. |
| G1 T1059.001 | 1 | 1 | 1 | 2 | Telemetry established PowerShell execution. The distinctive term was sufficient in the baseline. |

Neither gold sub-technique had its parent in the baseline top five. The active catalogue excluded all revoked and deprecated entries, including historical T1070.001. Each gold ID had an active corpus record. [Current Clear Windows Event Logs entry](https://attack.mitre.org/techniques/T1685/005/) · [Per-case ranks and shared terms](../eval/reports/ai_retrieval_mapping_20261120/retrieval.json) · [Uncapped TF-IDF replay](../eval/reports/ai_retrieval_mapping_20261120/retrieval_ablation.json)

## Mapping with the same local 7B checkpoint

Each run used the installed Qwen2.5 7B model at temperature zero and the same strict schema. A candidate mapping includes an active technique ID, record ID, verbatim evidence and a short justification. Model arms use the same observation records and rotate order across cases. The four retrieval arms receive five references in a deterministic order. The oracle inserts missing gold techniques by replacing irrelevant candidates, while negative cases receive the same references as in the hybrid arm. The evidence-first variant adds instructions to check source reliability and authorization before making a mapping.

| New cohort arm | Exact | Positive cases with a correct pair | Negative specificity | Correct / unsupported / missed | Pair precision | Pair recall | Pair F1 | Abstentions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No retrieval | 16/32 | 0/16 | 16/16 | 0 / 6 / 16 | 0.000 | 0.000 | 0.000 | 26/32 |
| Historical TF-IDF | 21/32 | 7/16 | 14/16 | 7 / 3 / 9 | 0.700 | 0.438 | 0.538 | 22/32 |
| Hybrid BM25 and E5 | 24/32 | 9/16 | 15/16 | 9 / 4 / 7 | 0.692 | 0.562 | 0.621 | 19/32 |
| Gold-reference oracle | 25/32 | 10/16 | 15/16 | 10 / 3 / 6 | 0.769 | 0.625 | 0.690 | 19/32 |
| Hybrid with evidence-first instructions | 23/32 | 8/16 | 15/16 | 8 / 3 / 8 | 0.727 | 0.500 | 0.593 | 21/32 |


The hybrid gained three exact cases over TF-IDF and one additional unsupported pair. The paired family-bootstrap 95% interval for the exact gain was −3.1 to +21.9 percentage points. On development the exact counts were 8, 10, 12, 13 and 12 in the same arm order, out of 16 each. One generated response was scored per case and arm. The eight and sixteen incident families limit precision, and the reference labels still need independent assessment.

The oracle supplied all 16 expected techniques and still recovered only 10 pairs. Its context differed from hybrid on two positive cases. Inserting the remote-mail reference corrected the local-versus-remote mail mismatch. Inserting the Domain Accounts reference still produced an abstention. The six oracle misses included four abstentions and two wrong technique choices. The evidence-first instruction lost one correct pair and removed one unsupported pair compared with the normal hybrid prompt. This exercise shows a retrieval gain alongside a remaining interpretation and classification gap.

All 240 model responses passed the output contract. The deterministic validator checks active IDs, record IDs, verbatim quotes and the presence of a justification. On the 32-case cohort it removed none of the unsupported mappings. A source quote proves the cited words exist. Establishing that those words support the technique still requires semantic assessment.

Keep the hybrid retriever as a research candidate. Preserve both the false positives and the oracle misses for a new experiment on evidence interpretation. Defer fine-tuning and cloud comparison until independent label review and a fresh controlled comparison resolve whether the improvement transfers.

[Model results and paired intervals](../eval/reports/ai_retrieval_mapping_20261120/mapping.json) · [Raw responses](../eval/reports/ai_retrieval_mapping_20261120/responses.jsonl)

## Experimental boundary

The console backend reported healthy. It returned HTTP 503 for experimental assessment submission, job polling and reindex. Status reported cloud disabled. In source, the provider registry rejects SovereignEG before constructing a client, and direct construction of the dormant adapter permits only in-process mock transport. Mock calls use no provider key. The experimental Ollama and Gate clients validate a literal loopback endpoint and disregard environment proxies. The public graph entry point requires an existing engagement and withholds report output on denial. The raw graph builder is internal.

The verification covers supported entry points and regression tests. It does not certify isolation against code that already runs with arbitrary process access. The encoder weights came from a public repository, and all benchmark text was processed locally. The evaluator uses neither tool dispatch nor authorization requests. The live five-role architecture and historical records remain separate from the experiment.


## Verification and reproduction

Before the changes the full Python suite passed 191 tests. After the changes it passed 201 tests with 81 retained deprecation warnings. The focused test run passed 32 tests. The audit independently recounted the 240 new responses and matched the original benchmark runner's hash and all three recorded historical grounding hashes. The scoped source scan found no candidate credential strings. The local environment file is ignored and untracked.

Use an unused output directory and a local copy of the pinned E5 safetensors snapshot. Run from the repository root with local Ollama available for the model comparison. Add `--retrieval-only` for candidate metrics without inference. Without `--e5-snapshot`, the run compares lexical rankers only.

~~~powershell
python -B -m pytest tests -q -p no:cacheprovider
$e5 = Join-Path $env:USERPROFILE '.cache/huggingface/hub/models--intfloat--e5-small-v2/snapshots/ffb93f3bd4047442299a41ebb6fa998a38507c52'
python -B -m eval.ai_retrieval_mapping --e5-snapshot $e5 --output eval/reports/ai_retrieval_mapping_replay
~~~

[Run manifest](../eval/reports/ai_retrieval_mapping_20261120/manifest.json) · [Score and hash verification](../eval/reports/ai_retrieval_mapping_20261120/verification.json) · [Working-tree status](../eval/reports/ai_retrieval_mapping_20261120/git-status.txt)
