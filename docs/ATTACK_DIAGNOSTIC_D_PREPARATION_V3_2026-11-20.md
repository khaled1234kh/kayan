# ATT&CK v3 Experiment D · Incident facts first

**20 November 2026.** The manifest freezes 12 planned local attempts. It contains eight concrete payloads and four deterministic D3 templates. Each D3 request is finalized from its own D2 result after authorization. Zero generations were sent during preparation. Manifest SHA-256 is `c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba`. [Frozen request manifest](../eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.json)

## Design and locked request order

Both mapping arms use Qwen2.5 7B on pinned Ollama 0.40.13, raw ChatML, temperature 0, 4,096 context and the v2 response schema with a 370-token output limit. D2 uses the same model, context and temperature with a 512-token limit and an extraction schema. It receives all original addressed observations and exactly zero technique references. The schema permits zero to eight facts, each with one of seven roles, a value of at most 80 characters and one or two observation addresses.

| Case | Schedule | D1 and D3 technique references in display order | D1 / D2 / largest D3 fallback prompt bound |
| --- | --- | --- | --- |
| cedar | D1 → D2 → D3 | T1685.006, T1070.003, T1685.005, T1685.004, T1685.001 | 2,748 / 1,304 / 3,298 |
| slate | D2 → D3 → D1 | T1486, T1558, T1027.011, T1490, T1578.001 | 2,764 / 1,370 / 3,314 |
| silver | D1 → D2 → D3 | T1484, T1098.003, T1036.010, T1087.004, T1548.005 | 2,587 / 1,172 / 3,137 |
| flint | D2 → D3 → D1 | T1685.001, T1685.006, T1685.004, T1070.003, T1685.005 | 2,694 / 1,250 / 3,244 |

The order alternates the first mapping arm while always running each D2 before its D3. Cedar already had the expected ID. Slate substitutes two missing IDs using the lowest-fused-rank non-keyed display slots and exactly matches the archived A2 reference IDs. Silver and flint retain their v2 hybrid references. D1 uses the exact v2 mapping instruction. The D3 template retains identical observations, reference objects and mapping settings, then adds instructions for handling an unverified extraction. The prompt bodies omit dispositions, target labels, rubric roles, sufficient groups and analyst fixtures. [Diagnostic protocol](ATTACK_DIAGNOSTIC_PROTOCOL_V3_2026-11-20.md) · [Archived A trace](../eval/reports/attack_forensics_v3_20261120/oracle-a-requests.json)

## Extraction validation and D3 materialization

1. Preserve every D2 request, raw response, finish reason and execution failure. Validate execution and finish status before decoding the extraction. Reject malformed JSON, schema violations or any address outside that case. Preserve a valid empty extraction as a valid outcome.
2. Carry structurally valid D2 claims in `incident_fact_extraction` with the explicit status `unverified`. Serialize extracted values as data and escape raw ChatML delimiters. Every D3 receives the original addressed evidence and the same five reference objects as D1. Instructions tell D3 to verify the interpretation against the original statements and cite only those statements. Extraction has no path to the trusted facts passed to the evidence guard.
3. For an execution or truncation failure, invalid extraction, unknown address or conservative context-bound overflow, pass D3 the original evidence with an empty extraction array and the explicit failure code. Retain D2 raw output and error details separately. Execute D3 once even if D2 failed, and retain that pair in the denominator. A failed extraction and a successful empty extraction are distinguishable in the payload.
4. Hash each fully materialized D3 request and keep the corresponding D2 result alongside it. The manifest hashes the prompt template, schemas and materialization source. Concrete D3 payload hashes depend on future D2 responses.

The preparation uses conservative UTF-8 byte bounds plus the frozen token reserve. Static and fallback payloads fit with the full respective output budgets. Compact constructed successful D2 outputs also fit for all four cases. A long but schema-valid D2 result can exceed the conservative D3 bound. The explicit overflow fallback avoids silently clipping facts and is a potential constraint on the staged workflow. An existing citation address confirms only that a source statement is present. The code can enforce address and schema checks, but semantic inventions may still appear in model text. They remain unverified and never become analyst facts or execution authority. [Offline materialization and scoring code](../eval/attack_experiment_d_v3.py)

## Analysis to apply without changing the scorer

Use the same frozen v2 response schema, evidence grader and execution validation for D1 and D3. Report each arm's complete groups out of three expected technique occurrences, complete positive cases out of two, correct abstentions out of two negative cases, keyed technique selection with incomplete evidence, false mappings, unsupported citations and claims, and invalid cells. Report both `slate` impact claims separately. Report all four paired differences with their case IDs and D2 validity. A D3 fallback stays in the primary paired comparison and should be flagged in the output. Record stage latency and output tokens where available.

For each D2 fact, examine the value, cited text, and entity, event and time qualifiers. Classify supported claims, unsupported or contradicted claims, and wrong joins. Separately record critical omitted facts and failures. This semantic review uses original observations and the following frozen review anchors outside model inputs. An output can include a true mechanic and still make an unsupported inference about actor or outcome.

| Case | Critical extraction review anchors |
| --- | --- |
| cedar | E2.1 establishes completion on JUN-4 under session 6M. E3.1 ties that session to the unauthorized actor. E3.2 describes a separate, authorized session. |
| slate | E1.1 supplies actor and authorization for B19. E2.1 supports encryption and unavailability. E4.1 connects B19 to batch Z and E3.1 establishes the recovery loss. SE-3 and administrator B91 are separate. Check that extraction preserves two distinct effects. |
| silver | E1.1 records the completed Blue-tenant role grant. E2.1 explicitly authorizes the same grant and interval. E2.2 involves an unrelated same-name principal in another tenant. |
| flint | E1.1 is an allegation, E2.1 records the lack of corroboration and unavailable journal, and E3.1 retracts the conclusion. A delivery gap is no evidence of completed clearing. |

D estimates the effect of the staged workflow as a bundle on four already-exposed fictional cases. It adds a separate generation, an extraction prompt, additional output budget and D3 guidance. It cannot isolate a benefit from staging alone. Even a complete D3 finding could result from the original evidence without relying on D2. No result here establishes raw-telemetry extraction, population accuracy or independent confirmation. [B/C observed limitations](ATTACK_DIAGNOSTIC_BC_RESULTS_V3_2026-11-20.md) · [Frozen rubric](../eval/fixtures/ai/attack_mapping_v2/rubric.json)

## Existing evidence guard · offline diagnostic

The guard was tested with manually normalized fictional source statements, modeled source names and event keys. These records are review fixtures. D2 has produced no model facts and the guard never consumes D2 output in this plan.

| Guard fixture | Observed result |
| --- | --- |
| Cedar with complete action and custody | Eligible for analyst review |
| Cedar action only | Withheld for missing independent attribution and authorization |
| Slate encryption and recovery, evaluated in event-scoped inputs | Both separately eligible for analyst review |
| Slate both findings in a shared flat fact bank | Both withheld because E1.1 appears under two event identities. The current guard expands a citation to all facts on that address and requires exactly one event per claim. |
| Silver proposal omitting the signed authorization | Withheld. The same-grant authorized fact remains visible to the guard. |
| Flint retracted allegation | Withheld for missing verified completed action and mechanic. |

The shared-address behavior is a real limitation of the existing guard with this fixture representation. It does not invalidate the separate staged experiment, which uses the frozen v2 scorer. Guard eligibility concerns the normalized input and is not a measure of automatic telemetry parsing or analyst independence. [Offline fixture and complete verdicts](../eval/reports/attack_diagnostics_d_v3_20261120/offline-guard-diagnostic.json)

## Integrity and authorization

The audit regenerated the request manifest in memory and matched its exact bytes. It checked the v2 registration and archived evidence, four Experiment A run hashes, and the B/C request and three run hashes. Read-only local status matched the registered Qwen2.5 7B digest and Ollama version and showed SovereignEG disabled. The original human-gated confirmation directory was absent. The targeted preparation and existing evidence guard suites passed **32 tests**, covering malformed or truncated extraction, invalid addresses, escaped delimiters, overflow, feasible transfers, equal mapping scoring and the guard outcomes above.

```powershell
python -B -m eval.attack_experiment_d_v3 audit
```

Exact authorization request for the project owner:

> I authorize Experiment D only under `attack-diagnostics-v3.0`, bound to request-manifest SHA-256 `c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba`. Execute exactly 12 local Qwen2.5 7B attempts in manifest order after preflight passes. Send the four frozen D1 and four frozen D2 requests once each, and send the four D3 requests once each using the frozen per-case materialization rules, including explicit failed-extraction fallbacks. Use temperature 0, 4,096 context, and output limits of 370/512/370 for D1/D2/D3. Archive and hash the raw requests, outputs, failures, materialized D3 payloads and scores. Keep the frozen v2 scorer unchanged for both mapping stages. Scope ends after the exploratory report. No retries, replacements, additional experiments, external inference or live execution are authorized.
