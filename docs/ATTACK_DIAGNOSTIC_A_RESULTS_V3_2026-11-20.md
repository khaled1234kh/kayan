# ATT&CK v3 Experiment A · candidate availability

**20 November 2026.** Replacing selected distractors with the expected references changed keyed technique selection from **0/6 to 6/6**, while complete evidence groups stayed at **0/6**. All ten responses were valid. The five A1 response texts, technique sets and citation sets exactly matched their original v2 counterparts. Results apply to these five exposed fictional cases and this specific candidate substitution. [Machine-readable comparison](../.build/attack_diagnostics_v3_a/comparison.json)

## Execution and integrity

Khaled Mohamed authorized ten local Qwen2.5 7B generations under `attack-diagnostics-v3.0`. Before inference, the runner verified the authorized request-file SHA-256 `634372410ae089de674f3ea1c3e4b7b4150a6f046ea3087c1124c874eabe3ecc`, the v2 registration and run artifacts, the case order and alternating condition order, all five exact v2 controls, the A2 substitutions at the required display slots, the original observations and instructions, output schema and prompt budgets. It checked Ollama 0.40.13, the pinned model digest, and the disabled console status. The pinned E5 snapshot hashes matched, and A used already materialized references.

The ledger contains one start and one result for each authorized cell, including the serialized request, raw response body and frozen rubric trace. All responses returned HTTP 200 and passed the registered generation and schema checks. Zero cells were retried. The postflight verified the model, loaded 4,096-token context and disabled console status. The original human-gated run directory was absent. Logged request wall times sum to 19.90 seconds, including the cold first A1 call. [Exact requests](../eval/reports/attack_forensics_v3_20261120/oracle-a-requests.json) · [Authorization](../.build/attack_diagnostics_v3_a/authorization.json) · [Completion](../.build/attack_diagnostics_v3_a/completion.json) · [Attempt ledger](../.build/attack_diagnostics_v3_a/attempts.jsonl)

## Paired outcomes

Citation counts use the frozen rubric. Extra techniques exclude keyed IDs with incomplete evidence, which are still unsupported as findings. Each valid/abstention entry is A1 → A2.

| Case | Keyed IDs selected A1 → A2 | Complete A1 → A2 | Relevant citations A1 → A2 | Unsupported citations A1 → A2 | Extra techniques A1 → A2 | Valid / abstained |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| birch | ∅ → T1098.003 | 0/1 → 0/1 | 0 → 1 | 3 → 4 | 3 → 4 | Yes → Yes / No → No |
| coral | ∅ → T1486 | 0/1 → 0/1 | 0 → 1 | 3 → 2 | 3 → 2 | Yes → Yes / No → No |
| moss | ∅ → T1113 | 0/1 → 0/1 | 0 → 1 | 3 → 2 | 3 → 2 | Yes → Yes / No → No |
| quartz | ∅ → T1098.003 | 0/1 → 0/1 | 0 → 1 | 1 → 1 | 1 → 1 | Yes → Yes / No → No |
| slate | ∅ → T1486, T1490 | 0/2 → 0/2 | 0 → 2 | 2 → 1 | 2 → 1 | Yes → Yes / No → No |
| **Total** | **0/6 → 6/6** | **0/6 → 0/6** | **0/12 → 6/16** | **12 → 10** | **12 → 10** | **5/5 → 5/5 / 0/5 → 0/5** |

- **Birch.** A2 cited the grantee's recorded role change at E1.1 and omitted E2.1, which supplies hostile account control and owner consent status.
- **Coral.** A2 cited the observed encryption and access loss at E2.1. It omitted the incident attribution and the process-to-session link at E1.1 and E3.1. The encrypted/encoded-file distractor remained in the answer.
- **Moss.** A2 cited frame capture at E2.1 and omitted E3.1, which links the process to the relevant session, and E1.2, which establishes adversary control and the lack of authority.
- **Quartz.** A2 cited the asset-side privilege diff at E2.1 and omitted the authorization and attribution statements E1.2 and E3.1. The observations also leave the cloud platform premise under-specified. Excluding quartz yields **0/5 → 5/5** ID selection, **0/5 → 0/5** complete groups, and **0/11 → 5/14** relevant citations.
- **Slate.** A2 selected both expected techniques and cited one keyed statement for each. Both missed actor/session attribution E1.1. Recovery inhibition also missed evidence E4.1 of the completed purge.

In A2 the reduction in extra claims coexisted with six newly selected but incompletely grounded technique claims. On the registered claim-level definition, total unsupported findings therefore rose **12 → 16**. The comparison provides every extra technique ID, citation, and missing address. Each A1 case had zero changes in raw response text, technique IDs, citation addresses, validity or abstention compared with original v2 hybrid pass one. These five matches establish repeatability for these controls. [Full comparison](../.build/attack_diagnostics_v3_a/comparison.json)

## What this establishes and the next decision

Expected techniques entered every A2 context only through the specified candidate changes, and all six were subsequently selected. This supports reference availability as a constraint on ID selection in this setup. A2 jointly inserts relevant definitions and displaces distractors, so their individual contributions remain unresolved. The model cited exactly one appropriate statement per selected keyed technique. Every group needed more than one statement. This directly locates a residual failure in assembling the necessary evidence even with the technique supplied. The experiment cannot separate the flat answer format, attention to candidate distractors, interpretation of cross-record evidence, and model limitations. The positive-only selected cohort provides no estimate of abstention specificity.

**Proceed with B and C after separate review and authorization.** Their eight fixed-technique contrasts can test whether an explicit hypothesis with fewer competing references enables complete evidence chains and rejection of withdrawn, authorized, failed, or unattributed activity. Freeze those exact requests and thresholds before inference, report per-case errors even if binary decisions are correct, and preserve quartz as a sensitivity in A. B–E have generated zero responses. The AI-authored key and exposed synthetic cases support diagnosis within this setup.

## Reproduce the analysis from saved evidence

From the repository root, run `python -B -m eval.attack_experiment_a_analysis_v3`. This reaudits the inputs, matches the serialized request bytes to all ten frozen payload objects, recomputes each case score, and checks the existing comparison against the new computation. It sends no inference requests. The [one-shot runner](../eval/attack_experiment_a_v3.py) is retained for audit and refuses an existing run directory.

| Artifact | SHA-256 |
| --- | --- |
| Attempt ledger | `4e7cb6d9fcdbb33f7dc02cef39c4449c50a358034759012666a1f79195bc7202` |
| Authorization | `406731d1ff1ce48a8a4932fa25201967d80f88f646c096b2829e6d0315ab92c0` |
| Completion | `397b51d1708d914802a9debde5453f0e9ddb2b2e5683c0b65320f27b292c80e8` |
| Comparison | `634bc5b4b350dd00311a8a6e5266b8358c43a0c2a862e442174c79a22de34370` |
