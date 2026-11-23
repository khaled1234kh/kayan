# ATT&CK v3 fixed-technique Experiments B and C results

**20 November 2026.** The single-reference setup produced **zero complete evidence groups in four confirmed cases** and **three correct abstentions in four negative or ambiguous cases**. The withheld findings were the withdrawn log-clear allegation, authorized role grant and rejected forwarding rule. The model still mapped an unattributed screen capture and abstained on the paired attributable capture. [Preparation and locked scoring rules](ATTACK_DIAGNOSTIC_BC_PREPARATION_V3_2026-11-20.md)

## Execution and integrity

The project owner authorized eight local generation attempts against request-file SHA-256 `fef24e05b445dcaf4c48ba362a36383487d3f8bf039c3b928ab2b4933bfe74fc`. The requested offline audit matched every request byte, the original v2 registration and archived artifacts, the four Experiment A run hashes, the registered output schema and inference settings. Read-only runtime checks matched Ollama 0.40.13 and Qwen2.5 7B digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`. SovereignEG status was disabled before and after. The local model reported a 4,096-token loaded context. The original human-gated run directory remained absent.

The ledger records one start and one result for each frozen payload in manifest order. All eight returned HTTP 200 and finished with `stop`. There were zero invalid responses, execution failures, off-target IDs, retries or substitutions. Summed request wall time was 8.57 seconds. An offline replay verified the serialized request bytes against each payload, decoded the archived server envelopes and reproduced every score using the unchanged B/C interpretation rules. [Exact request file](../eval/reports/attack_diagnostics_bc_v3_20261120/fixed-technique-requests.json) · [Raw attempt ledger](../.build/attack_diagnostics_v3_bc/attempts.jsonl) · [Completion](../.build/attack_diagnostics_v3_bc/completion.json)

## Measured results

| Metric | Result |
| --- | ---: |
| Complete positive evidence groups | 0/4 |
| Correct positive IDs with incomplete support | 3/4 |
| Positive abstentions | 1/4 |
| Correct abstentions on negative or ambiguous cases | 3/4 |
| False mappings on negative or ambiguous cases | 1/4 |
| Relevant citations | 3/4 cited statements |
| Unsupported citations | 1/4 cited statements |
| Unsupported findings | 4 distinct case-technique claims, including three incomplete positives and one false mapping |
| Invalid responses, execution failures | 0/8, 0/8 |

| Case | Fixed technique | Response | Evidence judgment |
| --- | --- | --- | --- |
| cedar | T1685.005 | E2.1 | Correct ID with the completed log-clear receipt. Missing E3.1, which links the session to the unauthorized intruder. |
| flint | T1685.005 | Abstained | Correct for the retracted allegation and unavailable source journal. The response provides no rationale. |
| birch | T1098.003 | E1.1 | Correct ID with the committed tenant role grant. Missing E2.1, which ties the principal and transaction to adversary control without owner consent. |
| silver | T1098.003 | Abstained | Correct for the authorized grant in the same tenant and time window. The response provides no rationale. |
| ochre | T1114.003 | E1.1 | Correct ID with the enabled forwarding rule. Missing E3.1, the identity and authorization statement required by either group. The alternate group also lacks E2.1, its independent record of configuration and outcome. |
| hazel | T1114.003 | Abstained | Correct because the change was rejected before commit and the revision stayed the same. The response provides no rationale. |
| moss | T1113 | Abstained | Missed the confirmed capture. The answer omitted all three required statements. E2.1 establishes action, asset and capture outcome. E1.2 establishes actor and authorization. E3.1 provides the contemporaneous PID-to-session link. |
| larch | T1113 | E1.1 | False mapping. The cited images establish capture mechanics only. Neither source resolves which active session produced them. Attribution and a link to the unauthorized session are absent from the case. |

Every positive returned finding cited a statement that established the action and outcome. Each stopped before the independent actor and authorization statement. The evidentiary gap on `moss` includes the outcome and explicit process linkage because the response was empty. The `larch` mapping had no source evidence for the conclusion that the capture was adversarial. [Frozen rubric](../eval/fixtures/ai/attack_mapping_v2/rubric.json) · [Ledger and per-statement scoring traces](../.build/attack_diagnostics_v3_bc/attempts.jsonl)

## Descriptive comparison

On the **same eight cases** in v2, BM25 selected 3/4 positive IDs, completed 0/4 groups and abstained on 1/4 negatives in each pass. Hybrid selected 2/4 IDs, completed 0/4 groups and abstained on 0/4 negatives in each pass. BM25 had 18 unsupported citations in each pass on those cases. Hybrid had 24 and 25. B/C returned one unsupported citation. Off-target references were available in v2 and the v2 prompt was open-set, so the citation totals describe the outputs under each setup. [V2 results](ATTACK_EXPLORATORY_V2_RESULTS_2026-11-20.md) · [V2 case matrix](../eval/reports/attack_forensics_v3_20261120/matrix.md)

Experiment A recovered all six expected IDs after candidate substitution and completed zero groups. Its overlap with B/C is `birch` and `moss`. A2 selected both IDs with partial evidence. B/C repeated the same single relevant citation for `birch` and abstained on `moss`. A2 supplied five references and used the open-set instruction. B/C supplied a single reference and an explicit fixed-technique decision, and used a different case schedule. These contrasts cannot isolate the effect of candidate competition alone. [Experiment A results](ATTACK_DIAGNOSTIC_A_RESULTS_V3_2026-11-20.md)

## Interpretation and limits

**Complete evidence chains were unobserved even with a single supplied technique.** The model repeatedly recognized behavior while leaving attribution and authorization ungrounded. The screen-capture pair was reversed at the decision level. It withheld the linked capture and asserted the unresolved one. The other three negative outcomes demonstrate correct abstention on the authorized, failed and withdrawn examples, with one case per category. An empty mapping gives no reason for withholding, so these observations establish behavior on the cases rather than the decision process behind it.

These four positive and four negative examples are exposed fictional cases with AI-authored labels. Each ran once. The comparison supports exploratory diagnosis within the cohort. Independent validation, general accuracy and production readiness remain unestablished. Experiments D/E have zero generations and remain pending review.

## Artifact hashes

The archived run contains the exact serialized requests, raw server bodies, finish reasons, execution errors and scores. Verify the inherited inputs with `python -B -m eval.attack_experiment_bc_v3 audit`. To verify scores offline, decode the base64 responses in the attempt ledger with the archived per-case prompt bounds and apply `interpret` from the B/C module against the frozen observations and rubric.

| Artifact | SHA-256 |
| --- | --- |
| Fixed request manifest | `fef24e05b445dcaf4c48ba362a36383487d3f8bf039c3b928ab2b4933bfe74fc` |
| Attempt ledger | `ee6f93be1ee6eeff03a730f148fdd7b6c1266bec02b514098d866a6cce88861f` |
| Authorization | `f1c0c86409238da59a0a33ff9366b05f5ae5bf7c7dc98df72f637723647d3354` |
| Completion | `0258a37149c8f7af42cc62f2c92626e5bc5febc554d81712c24271de739a3d4a` |
