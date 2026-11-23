# Evidence extraction v2 · Paired local results

21 November 2026 · Exposed synthetic development cohort

**Role-specific constraints improved contract validity from 0/4 to 2/4. They did not improve complete grounded findings.** Direct generation, extraction v1 and extraction v2 each recovered 0/3 supported findings. The separate human-authored diagnostic recovered 3/3. Stop schema tuning on these exposed cases. [Frozen experiment manifest](../eval/fixtures/ai/cloud_extraction_v2.json) · [Previous experiment](CLOUD_PIVOT_AUTOMATIC_PROOF_EXPERIMENT.md)

## Contract and trust boundary

Extraction v2 uses eight strict JSON Schema object variants, each with its own role and allowed values. Every variant requires technique, occurrence anchor, exact citation, role and value. Actor and authorization variants can carry exact identity or scope quotations. Other optional fields express relationship, source context and missing roles. The validator checks quotes against the cited original record, treats uncertain actor confidence as unresolved, and rejects unknown addresses, duplicates and inconsistent mechanic anchors before assembly. Provenance is recorded context. It supplies no evidence of independence. [Schema and scoring](../eval/cloud_extraction_v2.py)

The assembler groups by technique and occurrence anchor and requires all enabled roles. It retains incomplete and conflicting candidates for diagnosis. Before admission, a separate comparison with the synthetic reviewed role key vetoes candidate techniques with unsupported core atoms. This check cannot insert evidence or repair an assembled group. Both structured arms use that same veto. Final decisions still run through the signed-off custody and admission entry point. Fixture authority comes from the existing synthetic issuer. The prompts receive neither proof groups nor review decisions, and extraction supplies neither receipts nor trusted facts. [Admission sign-off](ATTACK_PROVENANCE_ADMISSION_V2_FINAL_SIGNOFF_2026-11-20.md) · [Failure controls](../tests/test_cloud_extraction_v2.py)

## Paired design and evidence

Four cases reused the frozen Windows, Slate, incomplete Windows and authorized Windows development inputs. Three share the Windows family. Each case received the same addressed source text and fixed hypotheses in A, B and C. The 12 scheduled requests used the installed Qwen2.5 7B, its pinned digest, Ollama 0.40.13, temperature 0, seed 391, a 4,096-token context and a 512-token output cap. Direct and v1 used their unchanged prompts and schema. V2 used a shorter contract-specific prompt and the role-specific schema. This tests the prompt and schema together. Prompt lengths and generated token usage differ. The first preflight rejected a longer v2 prompt before any generation. The recorded manifest preserves that preflight revision and froze requests and scoring before the only run. D is the separately scored human-authored reference group control.

The development key is synthetic. Earlier AI exposure rules out an independent holdout claim. The cohort contains authorized and incomplete controls. Explicit ambiguity, contradictory and cross-occurrence controls also ran deterministically. The live-model cohort contains no enabled process-link requirement, so this run gives no estimate of process/session extraction accuracy. A genuinely untouched cohort requires separate study approval and independent labels.

## Results

| Metric | A · Direct | B · Structured v1 | C · Structured v2 | D · Authored control |
| --- | ---: | ---: | ---: | ---: |
| Wire schema passes | 4/4 | 4/4 | 4/4 | — |
| Full extraction or mapping contract passes | 4/4 | 0/4 | 2/4 | 4/4 |
| Complete automatically assembled groups | — | 0 | 0 | — |
| Supported findings recovered | 0/3 | 0/3 | 0/3 | 3/3 |
| Missed supported findings | 3/3 | 3/3 | 3/3 | 0/3 |
| Proposals without complete support | 5 | 0 forwarded | 0 | 0 |
| Unsupported eligible items | 0 | 0 | 0 | 0 |
| Correct abstentions on authorized/incomplete cases | 0/2 | 0/2 | 2/2 | 2/2 |
| Prompt / generated tokens | 3,754 / 191 | 4,138 / 1,164 | 3,898 / 1,198 | — |
| Total endpoint wall seconds | 8.358 | 20.988 | 22.032 | — |

Direct proposed only action citations and the verifier withheld all five claims. Three proposed types corresponded to supported occurrences, but none had a complete group. Extraction v1 invalidity contributed failures, never abstentions. Extraction v2 abstained on both negative controls because it assembled no group. It missed the explicit authorization polarity, so the abstentions supply limited evidence of interpreting counterevidence. Unsupported eligibility is a zero count. For arms emitting zero review items, the error fraction among emitted items is undefined.

### Semantic role and occurrence measurements

Raw role scoring uses distinct tuples of technique, anchor, role, polarity and citation per case, including parses rejected downstream. V1 matched **1/19** emitted and **1/19** expected. Precision, recall and F1 were **5.3%** each. V2 matched **3/15** emitted and **3/19** expected. Precision was **20.0%**, recall **15.8%** and F1 **17.6%**. All three exact v2 matches were mechanics. One was in a rejected duplicate-bearing reply. Across valid extractions, v1 recovered no accepted roles and v2 recovered two exact roles. V1 accepted-role precision is undefined. Direct output has no role labels.

V1 identified 4/5 expected occurrence anchors and correctly linked 5/13 distinct expected occurrence/citation pairs when role and polarity were ignored. V2 recovered 3/5 anchors and 3/13 occurrence/citation pairs. Existing record addresses appeared in 19/19 raw v1 rows and 15/19 raw v2 rows, counting duplicates for this wire-level address check. Thus a higher keyed role score coexisted with worse address and occurrence recovery. The exploratory denominator is small and clustered. Timing is one run with order and warm-up effects. Compared with v1, v2 cost 1.044 more elapsed seconds and 34 more output tokens, with 240 fewer input tokens.

### Case failures

| Case | Direct | Extraction v1 | Extraction v2 | Authored eligible |
| --- | --- | --- | --- | --- |
| Windows | E1.1 action only. Missing authorization and independent attribution. | Invalid role/value combination. Raw role hits 0/4. | Eight mechanic rows repeat four addresses. Duplicate atoms rejected. E1.1 is the only keyed mechanic, and required actor, authorization and outcome are absent. Raw 1/4. | T1685.005 |
| Slate | Correct action anchors for both hypotheses. Both lack authority and attribution. Recovery also lacks completion. | Invalid polarity across roles. Raw 1/8, encryption authorization. | Four rows put source text fragments in citation fields. All four addresses fail. Recovery is anchored on E3.1 instead of E4.1. Raw 0/8. | T1486 and T1490 |
| Windows incomplete | Withheld. No supporting attribution and no cited authorization. | Invalid role/value combination. Raw 0/3. | Valid partial extraction and abstention. Correct E1.1 mechanic, spurious E1.2 mechanic, no supporting authority or completion. Actor evidence is absent. Raw 1/3. | None |
| Windows authorized | Withheld, including applicable contrary authorization evidence. | Invalid role/value combination. Raw 0/4. | Valid partial extraction and abstention. Correct E1.1 mechanic, extra mechanic anchors and no recognized approved authorization decision. Raw 1/4. | None |

## Reproduction and decision

```powershell
python -B -m eval.cloud_extraction_v2 --output .build/cloud-extraction-v2-replication.jsonl
python -B -m pytest -q -p no:cacheprovider tests/test_cloud_extraction_v2.py tests/test_cloud_automatic_proof_v1.py tests/test_attack_evidence_admission_v2.py tests/test_ai_layer.py
```

The original ledger `.build/cloud-extraction-v2.jsonl` contains 29 rows with request bodies, response envelopes, role scoring and per-claim decisions. Locate each raw reply by case and arm with `event=result`. Ledger SHA-256 `7fa5c9f119b1a90af3a9a7ce339f74796fa4b97df224f2ee8727e736673023c4`. Frozen manifest SHA-256 `2782c88b42d90c85e651965c5f38a7cecc6961ab1f668f525fe956249ba46b58`. All 20 referenced input hashes matched, including the original v1 ledger. **121 tests passed**, and all **71** historical inventory entries and **5** signed-off source hashes matched.

The schema enforced role-specific polarity in the observed v2 replies and the raw role metric increased. Complete proof recovery remained zero. Address substitutions, repetition and insufficient actor, authority and outcome grounding are the remaining failures. Preserve the contract as a baseline and stop tuning it on this cohort. The reusable request and scoring functions accept the same evidence, hypotheses and candidate responses for a future approved run. The manifest records the SovereignEG candidate. The existing adapter still rejects a live transport, and this experiment used zero cloud or mocked responses. A matched cloud run requires documented credential rotation, spend controls, model routing and written synthetic-only egress approval, plus provider support for role-specific structured responses. [Cloud adapter](../ai/providers/sovereign.py) · [Track A](CLOUD_PIVOT_ACCURACY_CHECKPOINT.md)
