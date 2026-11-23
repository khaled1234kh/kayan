# Can KAYAN justify an ATT&CK mapping from several records?

**Engineering decision, 20 November 2026.** Keep field-weighted BM25 @ 5 as the reference and hybrid E5-192 @ 5 as the challenger. The v2 study can now reject unanswerable cases before inference, identify citations to irrelevant statements within the right record, and score claims that depend on joining independent sources. The checks below measure properties of the benchmark. Model accuracy on v2 remains unknown. [Frozen registration](../eval/reports/attack_mapping_v2_20261120/registration.json) · [Verification record](../eval/reports/attack_mapping_v2_20261120/engineering-verification.json)

## What broke and what changed

| Reproduced condition | Historical behavior | V2 regression result |
| --- | --- | --- |
| Five techniques each require two citations | The adjudication validator accepted all five. The response schema rejected the ten-entry answer. | The preflight rejects that key. When two techniques have independently sufficient one-entry alternatives, it exhibits a valid eight-entry answer and checks it with the scoring function. |
| A citation is literal and from the correct record, but describes keyboard servicing | The historical scorer gave exact credit with zero binding blocks on the synthetic positive. | The correct technique still receives selection credit. One of two citations has keyed support, the group remains incomplete, and the other citation is identified as topical. Exact credit is false. |
| The source in historical `fresh-22` says the examiner found no corroboration | The historical negative label already penalized the false finding. Its verbatim-quote check accepted the citation. | A regression using the original observation marks the quoted statement as unresolved, records one unsupported technique and gives zero completed groups. The new cohort includes a separate withdrawn-allegation case, `flint`. |
| A suitable alternate source exists, or a prediction cites only part of the evidence | Pair counts alone make these cases hard to interpret. | Either complete alternative satisfies the finding. A partial citation retains individual support and can earn record-pair credit, while leaving the technique unsubstantiated. |
| A run returns malformed JSON, truncates, or cannot verify the model's loaded context | An old residency check could accept an empty list. | Invalid model cells retain their failure and cannot count as successful abstentions. An empty residency report withholds the study summary and preserves the ledger in the tested mock run. |

The original capacity defect crossed three components. The adjudicator checked the validity and minimality of each technique's evidence groups in isolation, the prediction class capped the whole response at eight mappings, and the runner had a separate 370-token ceiling. None tested a single complete answer against all three constraints. The original quotation binder verified record identity and verbatim text. It did not inspect which proposition the quotation supported. [Original validator](../eval/ai_confirmation_review.py) · [Original scorer](../eval/ai_confirmation_scoring.py) · [Original runner](../eval/ai_mapping_confirmation.py) · [Before-and-after tests](../tests/test_attack_evidence_v2.py)

## The v2 response contract and capacity proof

Each observation has immutable numbered source statements. A prediction supplies an active technique and a statement address such as `E2.1`. The scorer resolves the exact quotation from the observation. The model sees every statement and its address, plus public ATT&CK references. The answer key, evidence roles, disposition, family, feasibility witnesses and scoring exceptions stay out of the prompt. This design measures **selection of supporting statements**. Free-text explanations and arbitrary quotation boundaries fall outside its scope.

The eight-citation ceiling, 370 generated tokens and 4,096-token context are retained. For each technique, the validator tries its alternative sufficient groups. Across techniques it retains the cheapest compact answer for each feasible entry count. A technique shared across records needs multiple citations. A record used for two techniques consumes a citation for each. The validator then serializes a witness, validates the response schema and requires the scorer to accept it as exact. If the proof fails, registration stops.

The token bound uses the byte length of the complete compact answer plus four tokens for boundaries. The pinned local GGUF header identifies Qwen2 preprocessing and GPT-2-style BPE. Its vocabulary contains all 256 byte-alphabet symbols. Byte length therefore gives a conservative upper bound for these raw ASCII-serialized prompts and witnesses. A separate input bound uses the five largest serialized references from the actual catalogue, including escaping and framing. The runner checks the actual prompt again. A conservative rejection may exclude an answer that a tokenizer could compress. A passing witness establishes expressibility even if the model chooses a longer rendering and truncates.

All **18 cases** passed. The largest witness uses **five citations** and has an upper bound of **198 output tokens**. The largest prompt bound with any distinct five references is **2,929 tokens**, leaving room for all 370 generated tokens. These are upper bounds, not measured generation lengths. [Scorer and capacity proof](../eval/attack_evidence_v2.py) · [Case-level witnesses](../eval/reports/attack_mapping_v2_20261120/registration.json)

## Evidence-support rubric

A positive key names explicit source statements and assigns roles covering action, affected asset, outcome, actor and authorization. Some keys also require a link such as process-to-session identity. A sufficient group is a conjunction of statements. Several groups for one technique are alternatives. A prediction must contain every statement in at least one group. Extra unsupported citations remain visible and incur a cost even when the technique has a complete group.

| What a statement establishes | Scoring treatment |
| --- | --- |
| A keyed fact about action, identity, scope or outcome | Counts as individually supported. A group may still be incomplete. |
| Additional corroboration identified in the key | Counts toward citation relevance. It cannot substitute for a required statement. |
| A topic, alert title or proposal | Topical only. No evidentiary credit for the finding. |
| Action without attributable adversary control | A partial atom when attribution exists elsewhere in a positive case. An action-only or unresolved citation where attribution is unknown. |
| A contradiction, withdrawn allegation, authorized lookalike or fact about another asset/session | Explicit reason in the citation trace when annotated for that technique. The finding needs other admissible evidence. |
| A valid address with no keyed support for that technique | Reported as unkeyed. Unknown technique IDs and addresses have their own failure categories. |

The scorer verifies alignment with the authored key. It cannot establish that the key is complete, that a source is truthful, or that an unlisted interpretation is wrong. This matters especially for the penalty on unkeyed citations. The raw response, resolved quotations, roles and failure reasons let a reviewer inspect those judgments. Any subsequently accepted alternate interpretation belongs in a separately versioned analysis. [Frozen scoring key and per-case rationales](../eval/fixtures/ai/attack_mapping_v2/rubric.json)

## Cohort and construction limits

The new cases were written as fictional retrospective SOC records for Enterprise ATT&CK 20.1. The observation packet and the AI-authored key were stored separately before any model calls. The pinned catalogue loaded **706 active techniques**. Eighteen cases cover six families, with three cases per family. The authored dispositions are **nine confirmed, four benign, two failed actions and three inconclusive**. The inference prompt omits the family and disposition. Cases mix positive and negative outcomes in irregular order.

| Family | Evidence distinction exercised |
| --- | --- |
| Windows audit logs | A committed local clear, a relay delay with a continuous local sequence, and a withdrawn clearing allegation. |
| Cloud identity | A granted role and control of its beneficiary, with tenant, authorization and time-window lookalikes. |
| Mail forwarding | A committed rule and attribution, independent alternative records for the same rule, and a rejected request. |
| Screen capture | Desktop frames, PID reuse, concurrent operator sessions and an unrelated archived helpdesk image. |
| System recovery | Recovery-point inventory, a session-bound purge, legitimate expiration and an unsuccessful deletion. |
| File availability | Evidence of encryption and attribution, ambiguous corruption, and one incident with distinct encryption and recovery-inhibition claims. |

In `moss`, one record identifies the unauthorized session, another records desktop frames and the process that produced them, and a third links that process to the session at the relevant time. In `ochre`, either of two independent configuration records can establish the mail rule, but both alternatives require session attribution. In `slate`, a common session anchors two distinct findings, each with its own outcome evidence.

The nine positive cases contain **ten expected technique occurrences and eleven sufficient groups**. Under the frozen key, all **26** checks using the available support from just one source failed to complete the corresponding technique. Removing each required statement in turn broke the selected group in **27/27** checks. These are structural tests of the key. They do not show that a model can join sources or that human examiners would agree with every choice. The study has only one multiple-technique case and one case with alternative sufficient groups. The normalized statements, English prose, small technique selection, and shared AI authorship limit generalization to operational telemetry. [Observation packet](../eval/fixtures/ai/attack_mapping_v2/observations.json) · [Measured coverage](../eval/reports/attack_mapping_v2_20261120/engineering-verification.json)

## Registered comparison

| Decision | Frozen choice |
| --- | --- |
| Models and retrieval | Local Qwen2.5 7B, Ollama 0.40.13, temperature zero. The baseline uses the existing field-weighted BM25. The challenger fuses it with pinned E5-small-v2 at 192 tokens. Both get five public references in the same deterministic ordering scheme. |
| Context presentation | Both arms receive the same raw ChatML instructions and statement addresses. Reference excerpts use the first 220 description characters, allowing the conservative context proof. V1 used a different prompt, 400-character excerpts and a free-quotation schema. Cross-version scores would confound these changes. |
| Primary endpoint | Pass-one mean cost. Each unsupported technique claim costs 2, each missed supported behavior costs 1, each bad citation costs 1, and each invalid response costs 3. A correct ID with incomplete support can incur both unsupported and missed costs. These are explicit exploratory research weights. Operational risk owners have not calibrated them. |
| Secondary endpoints | Technique-selection micro-F1, completed-group recall, citation relevance, unsupported claims and bad citations, missed grounded behaviors, record-pair micro-F1, known-negative specificity, abstention on inconclusive cases, overall abstention and contract failures. Counts accompany ratios. A ratio with zero denominator is undefined. |
| Uncertainty | Resample six families with replacement as paired clusters for 10,000 draws, seed 391. Report the pass-one baseline-minus-challenger cost difference, percentile interval and per-family differences. Six clusters give weak interval precision. No deployment decision follows automatically. |
| Repeatability | Two full passes, 18 cases × two arms × two passes = **72 local generation requests**. Starting-arm order reverses between adjacent families and between passes. Reuse each case/arm's exact prompt. Report both pass summaries and same-arm agreement on raw answer, technique set and citation set among valid pairs, with both-valid counts. |
| Failures | One attempt per scheduled cell. Reserve one output directory exclusively. Log the request before transmission and retain the response bytes, references and scoring trace. An interruption leaves a partial ledger. A failed ending runtime check withholds the summary. |

Technique F1 counts a correctly *named* technique even if its evidence is incomplete. Completed-group recall counts a technique once when any sufficient group is satisfied. Citation relevance measures accepted supporting and corroborating citations over all submitted citations. Pair F1 uses one reference group per technique, credits supported records within it and treats additional keyed alternative records as neutral. A wrong statement in an otherwise correctly cited record can lower citation relevance without lowering pair F1. Known-negative specificity uses the six benign/failed cases. The three inconclusive cases have a separate abstention denominator. [Registered parameters, source hashes and metrics](../eval/reports/attack_mapping_v2_20261120/registration.json) · [Isolated runner](../eval/attack_experiment_v2.py)

## Verification, interpretation and authorization

The targeted Python suite passed **76 tests in 7.75 seconds**. The full repository Python test directory passed **245 tests in 21.37 seconds with 81 deprecation warnings**. Tests include mock transport, reversed second-pass ordering, missing authorization, tampered registration, impossible output and input budgets, ambiguous negatives, alternate groups, duplicate submissions within a response, and refusal to reuse a run directory. Novel cohort checks used constructed responses only. [Targeted log](../eval/reports/attack_mapping_v2_20261120/pytest-targeted.txt) · [Full log](../eval/reports/attack_mapping_v2_20261120/pytest-full.txt)

Integrity checks matched **40 historical artifact hashes** across four bundles and all ten source hashes in the original confirmation registration. The old confirmation runner remains sealed. The console status endpoint returned HTTP 200 with `enabled=false`. The model tag digest, Ollama version and three local E5 snapshot files matched the registration. No cloud request, fine-tuning, live assessment or v2 model generation was performed. No model-generated v2 accuracy figure exists. The preparatory test run used mock model responses; its pass count measures engineering behavior.

The historical diagnostic still reads **22/32 exact for BM25 and 26/32 for hybrid**, with an exact-rate gain of 12.5 percentage points and a paired interval of **0 to 25 points**. The earlier hybrid scored **24/32**. These observations support keeping a challenger in the study. They do not demonstrate repeatable superiority. A comparison on these 18 AI-labelled cases would remain exploratory even if every case favored the same arm. Genuine independent annotation and a separate cohort remain necessary for confirmatory claims. [Historical ablation](ATTACK_MAPPING_ABLATION_2026-11-20.md) · [Preserved AI review](ATTACK_PROFESSIONAL_RESEARCH_REVIEW_2026-11-20.md)

**Next decision for Khaled.** Authorize the **72 local generation requests** and local E5 encoding on this specified fictional v2 cohort, under the registered exploratory weights and repeat policy, if the comparison should proceed. Bind the authorization to SHA-256 `66254d7c5fa4128faac5749bf78ae3a5ba8de324ee232b505098e462d955d8c3`. The runner requires the study ID, this digest, the stakeholder's name, approval date and an explicit true value for `authorize_local_two_pass_comparison`. No approval file has been issued by this engineering pass.

Recheck the registration offline from the repository root:

```powershell
python -B -m eval.attack_experiment_v2 audit
```

After genuine authorization is recorded, the dedicated v2 runner accepts `run --e5-snapshot <pinned-local-snapshot> --authorization <dated-stakeholder-json>`. The authorization file uses `study`, `registration_sha256`, `stakeholder`, `approved_on` (YYYY-MM-DD) and `authorize_local_two_pass_comparison`. The coordinator retains the original stakeholder message with the file. This local authorization record is an operational control and has no digital signature. Attempts and any resulting summary are written under `.build/attack_exploratory_v2/run`.

