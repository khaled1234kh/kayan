# SovereignEG citation grounding v3

21 November 2026 · Frozen · Sole authorized probe completed

The Stage A v2 probe returned a visible, schema-valid mechanic with zero reasoning tokens. It used `Windows Security event` in both `anchor` and `cite`, where the supplied address was `E1.1`. The archived outgoing prompt did show E1.1 and instructed the model to use it. The schema allowed any string within the field length limit, so the provider could return prose while meeting the wire contract. Captured headers indicated no clamp or parameter remap. They do not reveal the provider's internal constrained-decoding behavior. The observed failure was selection of source text as an address. The original probe and its failed exact validation remain recorded. [Stage A v2 evidence](CLOUD_PIVOT_REASONING_BUDGET_V2.md#stage-a-result--exact-citation-check-failed)

## Correction

The v3 wire contract derives allowed IDs from the selected case's addressed evidence. Each of the eight existing extraction variants adds an enum to both `anchor` and `cite`. All other variant fields and values remain as in extraction v2. The local check parses the output and rejects any ID missing from that case's registry without rewriting it. Each case gets its own registry. An address reused in another case resolves only against the selected case's records and verified custody manifest. [Contract and local validator](../eval/cloud_citation_grounding_v3.py)

An allowed ID can still name the wrong action, occurrence or evidence role. The existing scorer checks the exact technique, anchor, role, polarity and citation tuple against reviewed evidence. It withholds candidates with unsupported core evidence, and the signed-off admission path decides whether the remaining claim is eligible. Missing roles and adverse evidence remain blockers. No model output becomes a reviewed fact. [Scorer](../eval/cloud_extraction_v2.py#L104) · [Admission sign-off](ATTACK_PROVENANCE_ADMISSION_V2_FINAL_SIGNOFF_2026-11-20.md)

## Deterministic results

| Control | Address contract | Attribution or proof outcome |
| --- | --- | --- |
| Descriptive prose, non-existent ID or removed custody record | Rejected | No assembly or admission |
| Slate uses the existing E4.1 backup action for the encryption mechanic | Valid | Wrong occurrence and role, zero review items |
| Slate cites encryption as recovery outcome or as authorization | Valid | Both affected assembled candidates withheld by the reviewed-role veto |
| Slate with complete reviewed role tuples | Valid | Two eligible items through signed-off admission |
| Authorized and incomplete Windows role sets | Valid | Zero eligible items |
| Empty extraction on the incomplete case | Valid | Abstained |

**106 tests passed**, including the new deterministic controls, v2 extraction and probe tests, and the admission suite. All **71** historical artifact hashes and **five** signed-off verifier source hashes matched. The original 12-call ledger and v2 Stage A response hashes also matched. There were zero provider requests in this pass. The new schema may improve valid address selection. Its effect on correct record attribution and complete supported findings is unmeasured.

## Frozen probe

The probe uses the existing synthetic Slate records as a JSON keyed map with four IDs. E2.1 describes archive encryption and unavailability. E4.1 describes a different action, the backup purge. E3.1 describes the resulting loss of recovery points, and E1.1 describes attribution. The fixed hypothesis is T1486. Both output fields permit all four IDs. Exact success requires one mechanic atom, with T1486, `observed` and E2.1 for both fields. The scoring answer is stored outside the outgoing request. A structured output choosing a wrong allowed address fails the exact-check gate.

The request retains `reasoning_effort="none"`, `max_tokens=1024` and temperature 0, as in the visible-answer v2 probe. The exact required answer takes 62 tokens with the pinned local Qwen2.5 tokenizer proxy. Provider tokenization and enforcement of the new nested enums still require measurement. The next authorized response must preserve the exact model, HTTP 200, nonempty answer, a normal stop, explicitly reported zero reasoning and no clamping or substitution. Record address validity, exact occurrence and citation correctness, and complete findings as separate measurements. This one-mechanic probe cannot establish complete proof or model accuracy on an independent cohort.

| Artifact | SHA-256 |
| --- | --- |
| v3 manifest | `b6ae9e1718b6d704648a99f802667ce403d5df6b3b91f6436cfcf2c5c3472e9c` |
| v3 bundle | `bf4ad17cc5794f408842c39e0d3c824771ed329a367c3df0b1b03df8f434d6d2` |
| Sole outgoing request | `c543a58a0ed2a655a03fc4504749f4d10a7bc90cd65ea1e3d8570f278c341223` |

Request digest uses compact sorted-key ASCII JSON. Bundle and manifest use indented ASCII JSON and final LF. [Frozen manifest](../eval/fixtures/ai/cloud_citation_grounding_v3.json)

## Owner authorization and preflight

On 21 November 2026 (Cairo), the project and SovereignEG account owner authorized exactly one request at the three hashes above, for the frozen synthetic probe, to `https://backend.sovereigneg.com/v1/chat/completions` on `SovereignEG/Qwen3.8-27B-FP8`. The ceiling was 1 EGP and only the Student allowance could be used. Paid balance draw was required to be zero. Approval excludes retries and Stage B.

Before execution, offline regeneration matched the manifest, bundle and outgoing request digests. The replacement credential was stored outside the Git checkout. The signed-in Plans page showed an active Student plan with 99% of today's allowance remaining, automatic balance use off and paid overages off and disabled for this exact model. The catalogue listed the sovereign routing and the input/output tariffs. The conservative published-rate bound using 92,000 input tokens at the highest listed input tariff (10.26 EGP per million) plus 1,024 output tokens (10 EGP per million) was 0.95416 EGP. [Model catalogue](https://sovereigneg.com/models/SovereignEG%2FQwen3.8-27B-FP8) · [Student plan](https://sovereigneg.com/docs/student-plan)

## Real provider result · Exact grounding failed

The single authorized request returned HTTP 200 from `SovereignEG/Qwen3.8-27B-FP8` with request ID `req_sDJiDziRXEoS1FwL1pMH1` at 12:46:55 Cairo time. The visible answer was `{"facts":[]}`. The response finished with `stop`, reported zero reasoning tokens and carried no parameter-substitution or clamping headers. The raw response reported vLLM fingerprint `vllm-0.28.0-04aa581e`.

| Measure | Result |
| --- | --- |
| Output availability and first-pass schema validity | Visible JSON, schema valid |
| Permitted address selection | Zero addresses emitted, so individual selection was untested |
| Exact technique, event and occurrence | 0/1 expected T1486 encryption mechanic at E2.1 |
| Exact citation and role | 0/1 expected citation and 0/1 expected mechanic-role tuple |
| Complete proof groups and emitted review items | 0 and 0. The mechanic-only design cannot establish a complete proof chain |
| Abstention and unsupported claims | Empty-output abstention on a supported mechanic, zero unsupported claims |
| Tokens and latency | 199 uncached input, 10 output, 209 total, 1.2244 seconds |
| Spending | 0.001095 EGP at catalogue rates before the Student allowance. Account controls disallowed paid balance draw. No charge amount was returned in the captured response headers |

The frozen validator failed with `Probe did not return the expected nonempty structured answer`. The existing scorer returned `abstained` with zero eligible review items. The enum-constrained request produced usable structured JSON, but the empty array supplies no evidence that the provider enforced the address enums or could choose the correct record from the four options. This single exposed synthetic case does not establish a comparison of grounding accuracy. The sole authorization is consumed. Stage B was not executed and remains unauthorized.

Local raw request and response with selected headers, measured latency and scorer output are in `.build/cloud-citation-grounding-v3-probe-2026-11-21.json` (SHA-256 `f75ab77efc820bb9f71ef419f243ea2c2c9e36f0df16d382ed187808f6c68963`). The four suites listed below passed again (106 tests). All 71 historical artifact digests and five signed-off verifier source digests matched. The original 12-call cloud ledger and prior Stage A v2 probe digest also matched.

## Reproduction

```powershell
python -B -m eval.cloud_citation_grounding_v3 --parent .build/cloud-reasoning-budget-v2.json --output .build/cloud-citation-grounding-v3-replay.json
Get-FileHash -Algorithm SHA256 -LiteralPath eval/fixtures/ai/cloud_citation_grounding_v3.json,.build/cloud-citation-grounding-v3-replay.json
python -B -m pytest -q -p no:cacheprovider tests/test_cloud_citation_grounding_v3.py tests/test_cloud_reasoning_budget_v2.py tests/test_cloud_extraction_v2.py tests/test_attack_evidence_admission_v2.py
```

The preparation CLI verifies the frozen sources and writes a new output file offline. Follow the previous results record for the consumed v2 probe. These are exposed synthetic fixtures, and improving field validity alone supplies no evidence of improved grounding.
