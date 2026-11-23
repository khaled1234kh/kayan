# ATT&CK v3 fixed-technique Experiments B and C

**20 November 2026.** Eight requests are frozen for review. No model generations have been sent. Request-file SHA-256 is `fef24e05b445dcaf4c48ba362a36383487d3f8bf039c3b928ab2b4933bfe74fc`. [Exact request file](../eval/reports/attack_diagnostics_bc_v3_20261120/fixed-technique-requests.json) · [Existing diagnostic protocol](ATTACK_DIAGNOSTIC_PROTOCOL_V3_2026-11-20.md)

## Payload and scope

The schedule follows the protocol's paired order. The labels and capacities in this table are reviewer metadata outside the model prompt. Each model request contains all original addressed observation text for that case and the single pinned Enterprise ATT&CK 20.1 reference, using the v2 ID, title and first 220 description characters. The same reference text appears in both cases of each pair. The v2 open-shortlist instruction was removed and a common fixed-technique adjudication question was added. The request format, settings and JSON response schema come from the frozen registration. [V2 registration](../eval/reports/attack_mapping_v2_20261120/registration.json)

| Order | Case | Fixed technique | Contrast | Conservative prompt token bound | Feasible witness output bound |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | cedar | T1685.005 | Completed and attributed | 1,842 | 98 |
| 2 | flint | T1685.005 | Withdrawn allegation | 1,788 | 19 |
| 3 | birch | T1098.003 | Adversarial role grant | 1,745 | 98 |
| 4 | silver | T1098.003 | Authorized grant | 1,708 | 19 |
| 5 | ochre | T1114.003 | Completed forwarding with alternate support | 1,888 | 98 |
| 6 | hazel | T1114.003 | Rejected before commit | 1,705 | 19 |
| 7 | moss | T1113 | Attributable capture | 1,855 | 126 |
| 8 | larch | T1113 | Capture with unresolved attribution | 1,720 | 19 |

The 38 addressed observations were checked against the frozen input. Each prompt body has only observations and one reference. Dispositions, expected responses, roles, evidence groups, grader annotations and keyed witnesses are excluded. The largest conservative input bound is 1,888. Reserving all 370 output tokens gives 2,258 against the 4,096-token context. The largest proven sufficient compact response fits within 126 tokens. These are byte-based upper bounds with the registered boundary reserve. No generation lengths have been measured.

## Interpretation rules locked before inference

Use the archived v2 scorer for citation judgments and the separate B/C interpreter for the fixed-ID constraint. Keep the original four scheduled cases in each primary denominator. Treat transport failure, malformed JSON, truncation, duplicate pairs or any off-target ID as invalid. For a structurally parseable off-target reply, retain the original trace and count unsupported IDs and citations descriptively. Exclude that reply from primary success. An invalid reply cannot count as abstention.

| Metric | Rule |
| --- | --- |
| Complete positive evidence groups | Complete positive cases out of four. Credit a valid fixed-ID response with every addressed statement from at least one sufficient group. Report any unsupported extra citations alongside a completed group. |
| Correct abstentions | Valid empty responses out of the four negative or inconclusive cases. |
| False mappings | Valid fixed-ID findings on the four negative or inconclusive cases, shown separately from invalid responses. Report each case and the cited evidence. |
| Correct ID with incomplete evidence | Valid positive responses that select the fixed ID and omit a required statement from every alternative group. Report out of four, alongside valid positive abstentions and invalid cells. |
| Unsupported citations and claims | Count citation rows by the v2 trace, including wrong addresses, unsupported references and explicit negative evidence. Count distinct unsupported technique claims per case, separating an incompletely grounded fixed claim from additional IDs. Report totals and denominators for structurally interpretable replies. |
| Missing evidence dimensions | For each positive, report missing statements, records and roles by sufficient alternative. Include action, attribution, authorization, asset, outcome and explicit linkage when keyed. On negatives, distinguish the known reason for withholding a finding from evidence the reply actually cited. |
| Invalid responses | Count out of eight and split by cause. Retain wire status, output body, finish reason and parse errors when available. |

In `moss`, the explicit linkage requirement is E3.1, the contemporaneous PID-to-session binding. In `cedar`, `birch` and `ochre`, identity correlation is encoded in the evidence group across records. The role key supplies no distinct link atom for those cases. `ochre` permits either E1.1 plus E3.1 or E2.1 plus E3.1, and the reply has to satisfy only one. Negative cases separately represent retracted evidence, successful authorized activity, action blocked before commit, and observed activity with uncertain actor linkage. [Frozen rubric](../eval/fixtures/ai/attack_mapping_v2/rubric.json) · [Original case matrix](../eval/reports/attack_forensics_v3_20261120/matrix.md)

## Integrity and interpretation limits

The offline audit reran the original v2 registration validation, verified the historical manifests, raw v2 ledger and v2 run hashes, and matched all four Experiment A artifact hashes to their recorded values. Read-only local status checks matched Ollama 0.40.13, Qwen2.5 7B digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, and disabled SovereignEG status. The human-gated run directory remained absent. The B/C interpreter passed 61 checks on constructed responses covering all four positives, both `ochre` alternatives, four negative abstentions and false mappings, missing linkage, wrong IDs, duplicates, malformed output and truncation. [Experiment A audit anchors](ATTACK_DIAGNOSTIC_A_RESULTS_V3_2026-11-20.md)

The technique is supplied by construction. Selection therefore measures acceptance of a named hypothesis in this prompt. Complete groups and correct abstention are the harder outcomes. B/C change both the candidate set and the instruction, so comparison with Experiment A remains descriptive. The JSON contract exposes citations or an empty array, so a correct abstention cannot reveal the model's reason for abstaining. The four matched contrasts use exposed fictional cases with AI-authored labels. These outcomes have exploratory value within the cohort. No protocol conflict requires a design decision before authorization. Authorization remains an explicit separate decision.

From the repository root, run the offline audit command below. It regenerates the manifest in memory, compares exact bytes and prints all verified bounds.

```powershell
python -B -m eval.attack_experiment_bc_v3 audit
```

## Exact authorization request for review

> As KAYAN project owner, I authorize exactly eight local Qwen2.5 7B generation attempts for Experiments B and C under `attack-diagnostics-v3.0`, bound to request-file SHA-256 `fef24e05b445dcaf4c48ba362a36383487d3f8bf039c3b928ab2b4933bfe74fc`. Execute the eight frozen payloads once, in manifest order, on the registered local Ollama runtime with temperature 0, 4,096 context and a 370-token output limit. Verify the request hash, frozen inputs, local model identity and paused route status before inference. Preserve each request, raw response, score and failure. Stop if preflight fails. Scope ends after the eight attempts and the exploratory report. Retries, replacements, cloud inference, fine-tuning, other experiments and execution through TrustGate are outside this authorization.
