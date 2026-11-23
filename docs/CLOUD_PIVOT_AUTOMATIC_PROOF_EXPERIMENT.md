# Automatic evidence extraction and proof assembly

20 November 2026 · Local defensive development experiment

**Automatic evidence construction did not improve complete grounded findings.** Direct mapping and structured extraction both recovered **0/3** supported findings. The four direct replies validated and all proposed claims were withheld. The four structured replies failed role/value validation before assembly. The human-authored control recovered **3/3**. All eight model generations ran against pinned local Qwen2.5 7B. [Runner](../eval/cloud_automatic_proof_v1.py) · [Frozen contract](../eval/fixtures/ai/cloud_automatic_proof_v1.json)

## Design and implementation

- **A · Direct.** Generate the existing technique/citation envelope and check it with admission v2. Validate the allowed hypotheses, source addresses and citation uniqueness before admission.
- **B · Structured.** Extract atoms with a fixed technique, occurrence anchor, exact original-record address, role and polarity. Roles cover action, actor, authorization, outcome, process/session, provenance, contradiction and uncertainty. The role vocabulary captures categorical claims. Detailed identity, time and authorization scope remain in the underlying cited records and reviewed verifier inputs. The extractor has no field for a review receipt or approval. Every suggested address and role/value pair is checked. Duplicate atoms fail validation.
- **C · Authored proof control.** Send the frozen reviewed citation groups through the same verifier separately. The expected findings and role key are excluded from both model prompts.

The assembler groups valid atoms by technique and action anchor, requires mechanics, adversary attribution, unauthorized scope and completion, and requires a process/session link when enabled by the hypothesis contract. It retains candidate alternatives, adverse citations and missing roles. It emits a flat citation proposal only where one candidate group can be represented without ambiguity. Occurrence and provenance claims stay unverified until the signed-off admission path checks independently supplied fixture facts. Assembly never creates an assertion or receipt. The synthetic catalogue and synthetic fixture receipts serve both automatic arms and C identically.

The four cells are exposed synthetic development material. Windows and Slate are existing reviewed fixtures. The incomplete Windows variant removes the custody record and actor assertion. The authorized Windows variant changes the source policy note and its matching reviewed assertion together. Windows variants share an episode family. Independent evaluation is pending. The paired input uses identical source text, exact addresses and fixed technique hypotheses, one request per arm, alternating order by case, 4,096 context, at most 512 output tokens, temperature 0 and seed 391. All eight responses finished with `stop`. The run used no mocks or retries. The common hypothesis includes a process-link requirement flag, but none of these cases required process linkage. A deterministic test covers forced linkage and cross-occurrence withholding.

## Results

| Metric | Direct | Structured | Authored proof |
| --- | ---: | ---: | ---: |
| First-pass JSON schema validity | 4/4 | 4/4 | 4 fixture proposals |
| Full deterministic contract validity | 4/4 | 0/4 | 4/4 |
| Supported findings admitted | 0/3 | 0/3 | 3/3 |
| Missed supported findings | 3/3 | 3/3 | 0/3 |
| Unsupported eligible findings | 0 | 0 | 0 |
| Correct abstention on incomplete/authorized cases | 0/2 | 0/2 | 2/2 |
| Correct verifier withholding on incomplete/authorized cases | 2/2 | 0/2 reached verifier | Oracle proposals abstained |
| Prompt / generated tokens | 3,754 / 191 | 4,138 / 1,160 | — |
| Total wall seconds across four requests | 9.494 | 22.915 | — |

Direct produced five existing action citations, all scoped to the appropriate action occurrences in the fixture. It supplied no complete group. Structured produced zero admissible atoms at the response level. Precision is undefined with zero admitted atoms, and recall is 0/19 reviewed role tuples. The descriptive audit of raw atoms before rejection matches **1/19 emitted** and **1/19 expected** on the exact tuple of technique, anchor, role, polarity and cited record. Raw precision, recall and F1 are each **1/19 (5.3%)**. This secondary audit does not salvage rejected responses. Both automatic arms emitted zero review items, so unsupported share among emitted items is undefined. The four-case sums imply 13.421 extra wall seconds, 384 extra prompt tokens and 969 extra completion tokens for structured extraction. Cold-start and order effects limit performance interpretation.

| Case | Direct result | Structured failure and missing roles | Authored eligible |
| --- | --- | --- | --- |
| Windows | T1685.005 at E1.1. Withheld for missing authorization and independent attribution. | Used actor=`recorded` and mislabelled custody and permission. Raw 0/4 keyed roles. Missing mechanic, actor, authorization and completion. | T1685.005 |
| Slate | T1486 at E2.1 lacked authorization and attribution. T1490 at E4.1 also lacked completion. Both withheld. | Used `unauthorized` for actor, outcome and process/session. Assigned the recovery occurrence to E3.1 instead of E4.1. Raw 1/8 roles, authorization for encryption only. | T1486 and T1490 |
| Windows incomplete | Proposed the clear at E1.1. Withheld for missing authorization and attribution. | Labelled actor as `authorized` and provenance as `unresolved`. Raw 0/3 roles. Missing mechanic, denied authorization and completion. Attribution was absent from the approved evidence. | None |
| Windows authorized | Proposed the clear at E1.1. Withheld with `conflicting_or_superseded_evidence` plus missing affirmative authorization and attribution proof. | Repeated the positive Windows role/value errors. Raw 0/4 roles. Missed the authorized decision, mechanic, actor and completion. | None |

For B the wire schema enumerates roles and values independently. The model can satisfy JSON Schema while pairing unrelated values. The deterministic checker then rejects the whole extraction. That was the immediate bottleneck, alongside missing and misassigned role evidence. The paired run compares complete pipelines. It cannot isolate assembly quality when structured extraction produces no valid input.

## Retrieval diagnosis

The prior Track A replay recovered 5/10 expected occurrences with BM25 and 4/10 with E5-192 fusion per pass. The pinned Enterprise 20.1 forensic catalogue contains the missed IDs. Five targets are present below rank five in **both** arms. The hybrid-only coverage loss is `birch` T1098.003, rank 3 in BM25, 68 in dense and 12 in fusion. These ranks establish a ranking/coverage shortfall for the observed queries, with no evidence of missing catalogue entries.

| Target missed by both arms | BM25 / E5 / fusion ranks | Rubric-selected action-only fusion rank |
| --- | --- | ---: |
| quartz T1098.003 | 15 / 15 / 7 | 25 |
| coral T1486 | 6 / 130 / 30 | 3 |
| slate T1486 | 15 / 72 / 17 | 1 |
| slate T1490 | 14 / 137 / 41 | 7 |
| moss T1113 | 16 / 105 / 49 | 5 |

Whole-case vocabulary mixes action, attribution and surrounding context. In coral, encoded-file vocabulary favors an obfuscation distractor over the availability impact. In Slate, two effects compete in a single query. The privileged action-only probe improves some ranks while worsening ash T1490 from 2 to 113. Moss ranks poorly despite an untruncated definition. Query construction, vocabulary and fusion are therefore plausible contributors, with no single explanation established. The gold-reference substitution previously recovered 6/6 IDs and 0/6 complete proof groups. A retrieval change from rubric-selected action text would leak the key. This fixed-hypothesis run supplies no reliable automatic event query, so retrieval was held fixed. [Frozen forensic ranks and analysis](ATTACK_ROOT_CAUSE_V3_2026-11-20.md) · [Gold-reference control](ATTACK_DIAGNOSTIC_A_RESULTS_V3_2026-11-20.md)

## Reproduction and next decision

```powershell
python -B -m eval.cloud_automatic_proof_v1 --output .build/cloud-automatic-proof-v1-replication.jsonl
python -B -m pytest -q -p no:cacheprovider tests/test_cloud_automatic_proof_v1.py tests/test_cloud_track_a.py tests/test_attack_evidence_admission_v2.py tests/test_attack_evidence_v2.py
```

The original ledger is `.build/cloud-automatic-proof-v1.jsonl`. It retains requests, wire responses, outcome reasons, role errors, oracle outputs and elapsed time. It has 21 entries and SHA-256 `cd3497dc9d19298829fdd4cf73e01e0e37901edbcc0fd773f211e9eeb1808085`. Contract SHA-256 `1fc3ae08798b43b2216094eba80f3f95e2f857f9ab1ebcae81626d94ee58b36c`. Runtime Ollama 0.40.13 and pinned Qwen2.5 7B digest were checked before requests. Timing and raw output are observations from one run. **121 tests passed**. All 71 historical digests and five recorded sign-off source hashes matched. [Historical and sign-off verification](ATTACK_PROVENANCE_ADMISSION_V2_FINAL_SIGNOFF_2026-11-20.md)

The next bounded comparison should enforce role-specific values in the generation schema and test exact held-out role grounding before measuring group assembly. Keep explicit authorized, incomplete and cross-occurrence controls, including positive process/session evidence. The request builder, wire validation, assembler and admission scoring can be reused with a separately approved transport. SovereignEG remains blocked pending account-owner confirmation of key revocation and rotation, spend controls, routing and written synthetic-only egress authorization. No provider quality or cost estimate follows from this local run.
