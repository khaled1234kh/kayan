# Track A offline evidence checkpoint

20 November 2026 · Retrospective defensive evidence only

The 72 archived Qwen2.5 7B replies reproduced **0/72 responses containing a complete proof group** and **0/40 expected technique occurrences with complete evidence**. Mock requests exercised the three proposed cloud configurations. The paired proof experiment raised eligible, fully supported items from **0/4 to 4/4** on fixed synthetic inputs with supplied human-authored evidence groups. That gain belongs to evidence assembly and checking. Model grounding remains unmeasured by the proof experiment.

## Starting state and boundary

The repository already has local FieldBM25 and hybrid E5 retrieval, an offline scorer, an isolated historical runner and signed-off admission v2. The previous hybrid ablation justified carrying E5-192 reciprocal-rank fusion @5 as a challenger. It did not resolve superiority. SovereignEG exists as a configured candidate. Its adapter requires an explicit mock transport and validates the destination before credential handling. The experimental HTTP job route exercises a disabled state in existing tests. Existing analysis tests verify denial before inference and suppression of denied output. The Track A command has no live transport and uses only the pinned synthetic inputs. Configuration, Rust/Cedar, signed-off admission and live orchestration were outside the changes. The optional revised cloud handoff was unavailable at the named Downloads location and in the repository and attachment filename searches. [Security and prior evaluation](CLOUD_PIVOT_SECURITY_AND_EVAL.md) · [Hybrid ablation](ATTACK_MAPPING_ABLATION_2026-11-20.md) · [Provider adapter](../ai/providers/sovereign.py) · [Admission sign-off](ATTACK_PROVENANCE_ADMISSION_V2_FINAL_SIGNOFF_2026-11-20.md)

## Frozen design

The v1 contract pins the 18 exposed synthetic observations, AI-authored rubric, original registration and 144-event ledger by SHA-256. The script validates the registration schedule and exact saved wire text and recomputes every score. Each replay and mock arm uses the same observations and original scorer. The cohort has six families. The two historical passes reuse identical cases, so the 72 outputs are neither 72 independent observations nor a confirmation cohort. A fresh independently labelled cohort is required for a primary comparison. Previously AI-inspected packets remain development evidence. [Contract](../eval/fixtures/ai/cloud_track_a_v1.json) · [Runner](../eval/cloud_track_a.py) · [Frozen original registration](../eval/reports/attack_mapping_v2_20261120/registration.json)

| Arm | Inputs and execution |
| --- | --- |
| A · local Qwen2.5 7B | Both archived real local arms and passes. Field-weighted BM25 @5 and hybrid E5-192 @5. This checkpoint adds no fresh local generation. |
| B · SovereignEG Qwen 27B | Mock POST, same evidence, no retrieved references. |
| C · SovereignEG Qwen 27B | Mock POST, frozen lexical references. |
| D · SovereignEG Qwen 27B | Mock POST, frozen hybrid references. |

The B–D mock envelopes use the configured model identifier, v2 prompt rendering and schema. All three return the same archived pass-one lexical reply for a given case. This isolates request construction and scoring. The mock host is `track-a.invalid` and uses only `httpx.MockTransport`. The tests provide no provider schema, entitlement, output-quality, billing or latency evidence. Real comparison must use a separately approved cohort and matched request/schema budgets across local and actual cloud runs, including a matched local no-RAG run if measuring a model-only effect.

## Archived baseline measurements

Each row covers 18 responses, 10 expected technique occurrences, six known negative cases and three ambiguous cases. TP/FP/FN count exact IDs against the frozen key. Complete evidence uses statement-level jointly sufficient groups. Keyed or permitted corroborating citations count as relevant.

| Pass and retrieval | ID TP/FP/FN | ID precision / recall / F1 | Complete / missed | Unsupported selections | Relevant citations | Negative / ambiguous abstention | Retrieval hits / full case coverage | JSON contract |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| 1 BM25 | 5/39/5 | .114 / .500 / .185 | 0/10 / 10 missed | 44 | 5/51 | 3/6 / 0/3 | 5/10 / 5/9 | 18/18 |
| 1 hybrid | 4/48/6 | .077 / .400 / .129 | 0/10 / 10 missed | 52 | 5/59 | 1/6 / 0/3 | 4/10 / 4/9 | 18/18 |
| 2 BM25 | 5/39/5 | .114 / .500 / .185 | 0/10 / 10 missed | 44 | 5/51 | 3/6 / 0/3 | 5/10 / 5/9 | 18/18 |
| 2 hybrid | 4/49/6 | .075 / .400 / .127 | 0/10 / 10 missed | 53 | 5/58 | 1/6 / 0/3 | 4/10 / 4/9 | 18/18 |

The provider wire envelopes report total duration sums of 33.76, 32.29, 27.18 and 29.82 seconds respectively. Prompt/generated tokens were 10,123/1,682, 10,037/1,882, 10,123/1,682 and 10,037/1,852. Per-case wire metrics are in the generated JSON. Post-verifier contract measures apply only to the controlled proof experiment. The archive does not have independently reviewed occurrence banks for all 18 cases, so no post-verifier eligibility rate is assigned to it. The original paired cost interval spans no benefit and inference beyond these six families remains exploratory. [Original exploratory results](ATTACK_EXPLORATORY_V2_RESULTS_2026-11-20.md#uncertainty-and-repeatability)

### Per-case error matrix

Each line aggregates the four local cells for that case. Expected occurrences are per cell. Complete groups were zero on every line. The generated JSON retains each cell's exact citation addresses, evidence roles, reasons and references.

| Case | Expected per cell | Target references present | Correct IDs selected | Unsupported selections | Unsupported citations |
| --- | ---: | ---: | ---: | ---: | ---: |
| cedar | 1 | 4 | 4 | 8 | 4 |
| flint | 0 | 0 | 0 | 10 | 18 |
| indigo | 0 | 0 | 0 | 14 | 18 |
| coral | 1 | 0 | 0 | 12 | 12 |
| fern | 0 | 0 | 0 | 16 | 16 |
| slate | 2 | 0 | 0 | 14 | 16 |
| larch | 0 | 0 | 0 | 10 | 10 |
| moss | 1 | 0 | 0 | 12 | 12 |
| pearl | 0 | 0 | 0 | 6 | 6 |
| birch | 1 | 2 | 2 | 12 | 10 |
| quartz | 1 | 0 | 0 | 4 | 4 |
| silver | 0 | 0 | 0 | 9 | 9 |
| hazel | 0 | 0 | 0 | 10 | 10 |
| linen | 1 | 4 | 4 | 10 | 6 |
| ochre | 1 | 4 | 4 | 16 | 12 |
| ash | 1 | 4 | 4 | 20 | 26 |
| elm | 0 | 0 | 0 | 0 | 0 |
| opal | 0 | 0 | 0 | 10 | 10 |

The 54 mock requests serialized and scored successfully. Every arm was 18/18 schema-valid with 0/10 complete groups, under the deliberately shared replies. Retrieval coverage was 0/10, 5/10 and 4/10 for B, C and D. There was no provider latency, token or cost measurement and no external request.

## One controlled proof assembly experiment

Across the archive, all 18 retrieved expected technique occurrences were selected, yet none had a complete proof group. Existing Experiment A isolated a similar gap when expected references were inserted. Retrieval is necessary for the current observed selection behavior and insufficient to address assembly. The paired intervention expands a supplied action-only hypothesis only when its citations are a subset of a supplied reviewed proof group. It introduces no new technique and preserves incompatible citations for rejection. Both arms go through the same signed-off v2 custody and verifier with identical evidence and authority. [Experiment A](ATTACK_DIAGNOSTIC_A_RESULTS_V3_2026-11-20.md) · [Frozen proof inputs](../eval/fixtures/ai/cloud_track_a_v1.json) · [Regression controls](../tests/test_cloud_track_a.py)

| Case | Before | After |
| --- | --- | --- |
| Windows | No eligible item | T1685.005 eligible |
| Slate | No eligible items | T1486 and T1490 eligible |
| Slate with missing attribution for recovery | No eligible items | T1486 eligible. T1490 withheld with `independent_attribution_missing`. |
| Windows empty proposal | Abstained | Abstained |

Four expected eligible items across the paired fixture conditions became eligible, and zero unsupported items were emitted. This fixture set reuses Slate in two conditions, so a statistical interval would imply unsupported independence. Human-authored groups are an oracle for this diagnostic. The experiment shows that the verifier can preserve an assembly gain when the necessary evidence is available, and can reject an assembled group with missing proof. It gives no estimate of automatic fact extraction, open-set model retrieval, occurrence attribution on unknown cases or field performance. The historical generation baseline and Experiments A–D remain unchanged.

## Reproduce

```powershell
python -B -m eval.cloud_track_a --output .build/cloud-track-a-v1-replay.json
python -B -m pytest -q -p no:cacheprovider tests/test_cloud_track_a.py tests/test_ai_layer.py tests/test_attack_evidence_admission_v2.py tests/test_attack_evidence_v2.py
```

Use a new output filename on each run. Output is exclusive-create. The first report was written to `.build/cloud-track-a-v1.json` with SHA-256 `53a318e1694a85faef584b69d06ed75febdf655218b5e6d0e3faf72c2ce24cd2`. The contract SHA-256 is `6e6699bce91fd575b5a549e38dd3d0ef36646b484d1f75bf4da02a5334587b48`. **137 tests passed** with zero failures or skips. All **71** historical inventory digests and **5** source hashes recorded at admission sign-off matched. [Historical inventory commands](ATTACK_PROVENANCE_V1_P1_CUSTODY_2026-11-20.md#verification-and-reproduction)

## Next bounded milestone

On fresh, independently labelled synthetic retrospective evidence, compare evidence-role extraction and explicit group assembly against a fixed direct baseline using the same supplied hypotheses. Blind the reference labels, hold evidence and retrieval fixed, and score incomplete, contradictory and abstained cases. Run a matched cloud comparison only after the account owner confirms credential revocation and rotation, spend cap and upstream routing, and the project approves synthetic-only egress and explicit spend. Until then the provider remains blocked. Real-telemetry intake remains unauthorized.
