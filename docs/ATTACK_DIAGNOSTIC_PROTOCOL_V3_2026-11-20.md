# ATT&CK v3 causal diagnostics on the exposed v2 cohort

**Protocol v3.0 · 20 November 2026 · awaiting separate authorization for generation.** This protocol uses fictional cases that have already been examined. The offline forensic replay was completed with the pinned E5 encoder and retained v2 responses. There are zero new generative outputs for A–E. Model inputs may include deliberately selected public technique definitions. They exclude the scorer, expected disposition, evidence groups, role annotations and witness answers.

## Shared execution settings

Use the local Qwen2.5:7b digest and Ollama version pinned in the v2 registration, temperature 0, 4,096 context, raw ChatML, structured responses and public Enterprise ATT&CK 20.1 definitions. Reuse the registered 370-token output cap for v2-shaped answers. Conditions D2 and D3 have distinct contracts below. Schedule once in the written case order, reverse the first arm on alternating cases, retain raw inputs and outputs and count every malformed or truncated response as an invalid attempt. Record SHA-256 of the fully materialized request list before execution, including verbatim prompts, schemas, and controlled reference excerpts. Show each paired outcome with denominators. The small case sets support descriptive contrasts. [V2 registration and model identity](../eval/reports/attack_mapping_v2_20261120/registration.json)

## A. Candidate availability · 10 requests · first decision

Use the hybrid pass-one requests from the ledger for `birch`, `coral`, `moss`, `quartz`, and `slate` in that order. For A1 use the identical logged payload. For A2 replace the lowest-fused-rank shown non-keyed candidates with the missing expected techniques, ordered by technique ID, in those entries' existing display slots. Replace two for slate and one for each other case. Use the v2 220-character reference renderer and change only the reference objects. The ten exact requests were generated and checked offline. Their SHA-256 is `634372410ae089de674f3ea1c3e4b7b4150a6f046ea3087c1124c874eabe3ecc`. Treat quartz's cloud premise as a label sensitivity in the interpretation. [Exact payloads](../eval/reports/attack_forensics_v3_20261120/oracle-a-requests.json)

Report expected-ID selection, complete groups, relevant and unsupported citations, unsupported techniques, and invalid responses by case and condition. The replay control estimates variation for this exposure. An ID-only gain isolates an availability contribution to selection while leaving evidence use unresolved. More complete groups support an availability contribution under this substitution. Changes remain conditional on the removed distractors.

## B and C. Fixed technique and adversarial status · eight requests

Ask whether the specified technique satisfies the completed, attributable adversarial-behavior criterion. Give each case only the named reference and all original addressed observations. Use the v2 answer schema, with an extra client-side check that every returned ID equals the fixed ID. The candidate family is held approximately constant across each positive/negative contrast. This probes evidence and abstention given an explicit technique and makes no claim about open-set performance.

| Case order | Fixed technique | Contrast |
| --- | --- | --- |
| cedar | T1685.005 | Completed and attributed |
| flint | T1685.005 | Withdrawn allegation |
| birch | T1098.003 | Adversarial grant |
| silver | T1098.003 | Authorized grant |
| ochre | T1114.003 | Completed and attributed, alternatives |
| hazel | T1114.003 | Rejected before commit |
| moss | T1113 | Attributable capture |
| larch | T1113 | Captured content with unresolved source |

Report positive groups completed out of four, false mappings separately for the four negative/ambiguous cases, and per-case attribution, authorization, asset and link roles missed. A correct binary decision can coexist with incomplete citations.

## D. Incident facts first · 12 requests

Use `cedar`, `slate`, `silver`, and `flint` with the same concept-matched candidate reference objects for both final conditions. For cedar and slate, reuse the candidate substitution rule in A, inserting missing expected IDs into the lowest-ranked slots. For silver and flint retain the original hybrid shortlist.

- D1 uses the v2 prompt and response contract with those candidates. Four calls.
- D2 extracts up to eight structured observations from original records without ATT&CK references. Four calls. Each item is a role drawn from action, asset, actor, link, authorization, outcome or contradiction, a concise value no longer than 80 characters, and one or two resolvable observation addresses. Empty lists are valid. This stage has a 512-token limit.
- D3 uses D1 candidates and the identical raw observations plus D2 output clearly identified as unverified. Four calls. The model returns the v2 mapping schema. Where D2 fails, pass an explicit extraction error and an empty list to D3, preserving the failure in the denominator.

Score D1 and D3 with the same evidence criteria. Log D2's point at which it missed or invented the incident fact. The comparison estimates the effect of this workflow bundle, including the extra budget. D2 output carries no verification authority. A schema-valid narrative cannot supply a missing independently grounded fact.

## E. Candidate contamination · eight requests

Use `flint`, `silver`, `hazel`, and `larch`. E1 replays the original hybrid pass-one requests. E2 preserves the slot count and order, replacing the two candidates most directly related to the incident's misleading claim with canonically active technique excerpts from unrelated families. Select the E2 substitutions with two explicit rules before any inference. Remove a candidate if it names the alleged positive action or the nearest related behavior, otherwise remove the earliest remaining candidate as displayed. Replace with the first two active techniques unused in the case from lexicographically sorted ATT&CK IDs whose platform and tactic differ from the removed candidates and whose visible excerpts have no incident vocabulary other than English stopwords. Save the exact IDs and displacement reasons after manual review. If the fixed two-slot procedure cannot identify unrelated matched definitions, leave E unrun until the condition is explicitly revised. Report any-finding rate out of four, unsupported claims and use of supplied IDs, and preserve output differences even when contamination appears smaller. An effect would support shortlist sensitivity, conditional on the particular replacements.

## Authorization and interpretation

The first authorization request is exactly **10 local Qwen2.5 7B predictions for A**, with the registered model, unchanged settings, five original hybrid prompts and their candidate-only counterparts. Persist the exact payload hashes, retained v2 hashes and model identity before the first request. Preserve each unsuccessful cell and attempt none twice. B–E are separate proposals totaling 28 calls beyond A. Their actual prompts and substitutions require materialization before execution. Treat all outcomes as diagnostic. Independent adjudication and a fresh cohort are required for confirmatory claims.
