# ATT&CK confirmation handoff

**Historical release workflow, 2026-11-20, Africa/Cairo.** The original comparison remains sealed. The 24 observations have since been reviewed by an AI, with separate provisional judgments and zero model-evaluation requests. They no longer qualify for an AI-unseen confirmation claim. The workflow and prerequisites below preserve the original preregistration. A new independent study needs a fresh cohort and a versioned protocol. [AI research review](ATTACK_PROFESSIONAL_RESEARCH_REVIEW_2026-11-20.md) · [Historical comparison](ATTACK_MAPPING_ABLATION_2026-11-20.md)

## Coordinator and reviewer materials

Give the two qualified reviewers the files below in separate private messages, together with the reviewer instructions and the pinned Enterprise ATT&CK 20.1 taxonomy. The coordinator should first confirm that each reviewer is a real person with relevant defensive telemetry or ATT&CK experience and has no access to author labels, model answers, scores, or the other person's review. Keep the reviewers' identities or qualified pseudonyms and qualifications in private receipts.

| Reviewer | Diagnostic packet | Confirmation packet |
| --- | --- | --- |
| A | [32 cases](../eval/reports/ai_mapping_ablation_20261120/review/diagnostic-reviewer-a.json) | [24 cases](../eval/reports/ai_mapping_ablation_20261120/review/confirmation-reviewer-a.json) |
| B | [32 cases](../eval/reports/ai_mapping_ablation_20261120/review/diagnostic-reviewer-b.json) | [24 cases](../eval/reports/ai_mapping_ablation_20261120/review/confirmation-reviewer-b.json) |

Supply the exact `enterprise-attack-20.1.json` archive member configured in `config/ai.json`. Its SHA-256 is `539a843a7b53ed9749740b2123dddae3726b1a4831841c32aca740b011b910b5`. Do not give either reviewer this handoff, the research report or the experiment lock.

### Coordinator checklist

- [ ] Confirm qualifications and independence for two distinct reviewers. Assign the same person to each slot across both cohorts and send each only their own forms, the taxonomy and the [reviewer instructions](ATTACK_BLINDED_REVIEWER_INSTRUCTIONS.md).
- [ ] Collect all four returned originals privately. Record each reviewer's identity or qualified pseudonym, relevant experience, completion date and attestation of independence. Keep the files byte for byte as `reviewer-a.json` and `reviewer-b.json` in each cohort folder under `.build/attack_confirmation/inputs/`.
- [ ] Verify SHA-256 for the issued forms and returned originals. Record the packet, taxonomy, issued-form and returned-file digests and the coordinator's identity in each cohort's [receipt](../eval/reports/ai_mapping_confirmation_preparation_20261120/receipt-template.json). Let the validator check the case IDs, unchanged observations and complete fields. Only the coordinator can verify the reviewers' authenticity.
- [ ] Generate an agreement report and adjudication draft for each cohort. Collect the completed, versioned adjudications and obtain signed-off stakeholder approval bound to both adjudication hashes and the protocol hash.

```powershell
python -B -m eval.ai_mapping_confirmation agreement diagnostic
python -B -m eval.ai_mapping_confirmation adjudication-draft diagnostic
python -B -m eval.ai_mapping_confirmation agreement confirmation
python -B -m eval.ai_mapping_confirmation adjudication-draft confirmation
```

The agreement report gives raw agreement on disposition, any mapping, exact technique sets and exact technique–record pairs. It computes Cohen's kappa for disposition and any mapping when both reviewers vary. Set-valued judgments use exact agreement and macro Jaccard. The report flags disagreements and every row flagged ambiguous by either reviewer. It does not use the original author's answers.

## Adjudicator instructions

Work from the source records, original reviewer submissions, agreement file and pinned taxonomy. Complete a versioned copy of each `adjudication-draft.json` as `adjudication.json`. Record who adjudicated and when, the reasoning for every resolved case, changes from each reviewer where applicable, and any remaining ambiguity. The rubric version, packet digest and agreement digest are prefilled in the draft. Preserve the older author labels and every original return.

- Use a most-specific active ATT&CK ID only when the evidence establishes the completed behavior and an adversary context. Resolve parent versus child, local versus remote mailbox collection, existing log deletion versus stopping future logging, host shutdown versus service stop, and authorized versus malicious account use where applicable.
- `resolution: "score"` with an empty `evidence_sets` object means the defensible answer is abstention. `resolution: "exclude_ambiguous"` with an empty object means the adjudicator cannot establish a fair expected answer. Exclusions must be justified before inference. Excluded cases remain in the attempt ledger and schema/citation counts, with no accuracy or cost credit.
- For a confirmed, scorable incident, group the smallest sufficient sets of records for each technique. Example syntax using placeholder technique and record IDs follows.

```json
{"T0000": [["E1", "E2"], ["E3"]]}
```

Here E1 and E2 are jointly required for the first alternative, while E3 is independently sufficient. Each alternative must be minimal and supported by the records. The adjudicator decides which alternatives genuinely establish the technique, using the full observations. An authorized, prevented, unconfirmed, insufficient, contradictory, or simulated case cannot carry an expected mapping.

### Versioned scoring

The model keeps the existing one-record-per-entry schema. Multiple entries for the same technique can supply a joint group. The scorer first checks active IDs and verbatim binding to the nominated observation. It then checks complete evidence groups against the adjudication.

| Submission for the example above | Correct / unsupported / missed pairs |
| --- | --- |
| E1 + E2 | 2 / 0 / 0 |
| E3 | 1 / 0 / 0 |
| E1 only | 0 / 1 / 2 |
| E1 + E2 + E3 | 2 / 0 / 0 |
| E3 + unrelated E4 | 1 / 1 / 0 |
| Valid abstention | 0 / 0 / 1 |

One complete group earns credit. If multiple groups are complete, the largest group wins, then record ID order breaks ties. Additional citations from other complete alternatives receive no extra credit and no penalty. Submissions without a complete group earn zero credit for that technique. The scorer chooses the missed group with greatest eligible evidence overlap, then fewest records, then record ID order, and counts all its records as missed. Unsupported submitted pairs, including partial-only groups and invalid citations, count as false positives. Duplicate technique–record pairs count once. A malformed response or execution failure cannot earn abstention credit. A valid empty response on a supported case incurs missing pairs, and on a scored negative case earns abstention credit.

### Reporting checklist

Report the following three levels side by side for each arm after the authorized run, using the same scorable adjudicated cases. These are descriptive breakdowns from the existing ledger and labels. The preregistered scoring and stakeholder decision rule stay as recorded.

| Level | What to report |
| --- | --- |
| Technique selection | Compare the distinct technique IDs in each result's `attempted_pairs` against the adjudicated technique IDs. Report expected IDs selected, unexpected IDs selected and expected IDs missed. A correct ID can count here with incomplete or invalid citations. |
| Evidence-group completeness | Report expected techniques with a complete approved evidence set using `satisfied_techniques`, over all expected techniques. Also report this fraction among correctly selected IDs so missed technique selection and incomplete evidence can be distinguished. |
| Technique–record pairs | Use the preregistered `tp`, `fp` and `fn`, with pair precision, recall and F1. Report literal quote-binding failures separately. |

For example, naming the right technique and citing only E1 from the required E1 + E2 group counts as a correct technique selection, zero complete evidence groups and 0 / 1 / 2 on pair scoring. Report exact cases, positive-case recall and negative specificity separately. Exclude unresolved cases from the three accuracy denominators, retain them in the attempt ledger and count malformed or failed responses as errors. A valid empty response is the only way to earn negative-case abstention credit. The earlier uncorroborated log-clearing case illustrates why a literal quotation alone cannot establish evidence support.

## Stakeholder approval

The project owner or authorized stakeholder must approve and sign off on the rubric and the following application choices before any confirmation predictions exist. Record them in `.build/attack_confirmation/inputs/approval.json` using the [blank approval template](../eval/reports/ai_mapping_confirmation_preparation_20261120/approval-template.json). Bind the protocol file hash and both completed adjudication hashes. Use a real approver, date, and reason.

| Decision | Required response |
| --- | --- |
| Cost of an unsupported pair and a missed pair | Two positive weights. An example for discussion is 2 and 1. |
| Minimum useful gain | Positive decrease in weighted errors per scored case, on the chosen weight scale. |
| Allowed negative-specificity loss | Maximum fraction, with zero meaning no regression. |
| Required uncertainty bound | `above_zero` requires the lower bound above zero and the point estimate above or at the agreed margin. `meets_margin` also requires the lower bound to meet the margin. |

The report computes baseline minus challenger weighted error per scored case. An unmet rule, incomplete or malformed execution, or an interval including zero keeps the challenger experimental. The 12 family pairs constrain the strength of the result. Even a research-rule pass is a case for more validation before deployment.

## Preregistered run

The [protocol manifest](../eval/reports/ai_mapping_confirmation_preparation_20261120/protocol.json) pins the inputs, source hashes, dependency versions, Enterprise corpus, E5 snapshot and 192-token cap, exact reference format and k=5, both base prompts, JSON schema, Qwen2.5 7B digest and Ollama version. The run explicitly requests a 4,096-token context, up to 370 generated tokens and temperature 0. Both arms run once per case. Cases are sorted within sorted families and the starting arm alternates by family. Temperature 0 does not guarantee repeatable model output.

The runner checks the frozen study and the human evidence before contacting the server for a run. It also verifies the loopback model/version and paused experimental routes, reserves one local output directory, and writes a durable start and raw result for each attempt. The evaluation makes no retries or selective replays. Transport/contract failures count against the relevant metrics. An interrupted evaluation keeps its partial ledger, consumes its single attempt and cannot publish a valid complete comparison. Do not delete its output to repeat the same cohort. The report describes paired family uncertainty, index time, CPU and resident memory, reported model VRAM, latency and token counts.

After every human release item is complete, run from the repository root:

```powershell
$snapshot = "$env:USERPROFILE/.cache/huggingface/hub/models--intfloat--e5-small-v2/snapshots/ffb93f3bd4047442299a41ebb6fa998a38507c52"
python -B -m eval.ai_mapping_confirmation run --e5-snapshot $snapshot
```

Keep review receipts and raw private run files in the ignored `.build/` directory. Publish any future report with deidentified review provenance, versioned labels/digests and the paired results. The final 48-request run remains untested on the real cohort. SovereignEG stays paused, fine-tuning stays deferred, and neither TrustGate permissions nor the five-agent runtime changed.

## Verification this pass

All four blinded forms matched independently reconstructed empty forms. The fresh packet hash and all 22 previous artifact checksums matched. The 12 new tests used only mock observations, mock reviewer files, or mock HTTP responses. The targeted suites passed 48 tests and the full Python suite passed 217 tests with 81 existing warnings. All three experimental console routes returned HTTP 503 and the selected engagement's response digest matched before and after. No fresh confirmation requests ran. Rust, Go and frontend suites were outside this offline pass. [Verification record](../eval/reports/ai_mapping_confirmation_preparation_20261120/verification.json)
