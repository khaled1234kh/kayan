# SovereignEG matched evidence comparison

21 November 2026 · Frozen diagnostic completed

**Actual cloud result:** one successful capability probe and 12 diagnostic calls. All 12 diagnostics exhausted the frozen 512-token output budget on reasoning and returned no answer. Each cloud arm recovered 0/3 complete findings, as did the archived local direct arm. The comparison below preserves the frozen design and earlier preflight. [Execution evidence and costs](CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md)

The project owner subsequently authorized the exact frozen scope and a 20 EGP ceiling. The regenerated bundle matched. Execution remains blocked pending credential location verification, effective account-side budget evidence and provider capability and routing verification. The readiness record below describes the earlier pre-authorization checkpoint. [Owner authorization](CLOUD_PIVOT_OWNER_AUTHORIZATION_2026-11-21.md) · [Latest preflight](CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md)

## Execution preflight · 21 November 2026

The operator supplied a replacement credential file path. File metadata confirmed its presence. The credential contents were outside this check. A replacement file supplies no evidence that the exposed key was revoked. The four authorization fields in the frozen manifest are still unset, and the project records checked contain no approval for the exact request bundle or a maximum spend.

The frozen comparison manifest and request bundle matched the SHA-256 values below. All 12 drafts were present. The request envelopes carry the configured model, the expected system/user messages and schema, and addressed synthetic observations and hypotheses. Only the lexical arm adds references. The envelopes contain no authentication headers or custody approval objects. The existing adapter still requires mock transport. Provider-side routing and structured-output capability remain unverified. The preflight stopped before the capability probe. **0 provider requests sent.** A real-execution results report remains pending.

Approval evidence still needed:

- Account-owner confirmation that the previously exposed key was revoked and the replacement is active, with a dated reference and no credential value.
- Account-owner evidence of the configured spend cap and overage settings, with an approved maximum and currency.
- Provider documentation or account evidence identifying the model, approved destination, upstream routing and required structured-output capability.
- Written project-owner approval naming the exact frozen bundle SHA-256, configured destination `https://backend.sovereigneg.com/v1`, model `SovereignEG/Qwen3.8-27B-FP8`, 12 diagnostic calls, any separately allowed capability probe, permitted synthetic-only processing and maximum spend.

The supplied credential file is untracked and unignored under the repository. Store it outside the checkout before staging repository changes.

## Comparison prepared before preflight

**The real SovereignEG comparison did not run.** There is no evidence yet about whether the 27B candidate improves complete evidence-grounded findings. The offline preparation reproduced four actual archived local Qwen2.5 7B results with the frozen scorer. Local direct recovery was **0/3**. The separate authored proof control recovered **3/3**.

## Authorization and provider readiness

| Prerequisite | Evidence available at this checkpoint |
| --- | --- |
| Previously exposed credential revoked and replaced | No account-owner confirmation in the project records. The credential remains treated as compromised. |
| Bounded budget, spend limit and overage controls | No approved maximum, verified cap or overage setting. |
| Exact model and routing, including structured response support | The local configuration names `SovereignEG/Qwen3.8-27B-FP8`. Provider-side routing, model identity, output limits and support for the v2 union schema remain unverified. |
| Project approval for synthetic-only remote inference and maximum spend | No explicit authorization with an approved amount and payload scope. |
| Payload provenance and approved scope | The offline drafts derive solely from the pinned synthetic fixture originals, fixed hypotheses and pinned ATT&CK excerpts. The outgoing drafts exclude scoring keys, custody receipts, private ledgers and headers. Exact bytes and permitted egress still require project approval. |

The provider constructor accepts only the configured SovereignEG destination and an explicit mock transport. The existing experimental route remains paused. The preparation CLI creates neutral message/schema envelopes for capability and egress review. It contains no provider client or send action. Cloud requests, paid activity and live model measurements were zero. Cost, billed tokens, rate limits, provider errors and cloud latency are unmeasured. [Provider implementation](../ai/providers/sovereign.py) · [Cloud security checkpoint](CLOUD_PIVOT_SECURITY_AND_EVAL.md)

## Frozen comparison

Retain the four existing synthetic development cases and their exact hypotheses from the extraction experiment. Windows and its variants share source material. Results are diagnostic. The independent untouched evaluation cohort remains pending. [Comparison manifest](../eval/fixtures/ai/cloud_real_comparison_v1.json) · [Source dataset manifest](../eval/fixtures/ai/cloud_automatic_proof_v1.json)

| Arm | Matched inputs and status |
| --- | --- |
| A · Local Qwen2.5 7B direct | Actual archived direct responses from the extraction-v2 ledger. Byte-pinned inputs, exact original requests and reproduced scorer outputs. |
| B · SovereignEG direct | Prepared with the same instructions, observations, hypotheses and citation schema as A. Blocked. |
| C · SovereignEG with lexical references | Prepared with the same direct input plus up to five frozen FieldBM25 references from Enterprise ATT&CK 20.1. References are background material. Hypotheses remain fixed. Blocked. |
| D · SovereignEG structured v2 | Prepared with the same observations and hypotheses as B, the frozen role-specific schema and deterministic proof assembly. No extra retrieved context. Blocked. |

The drafts match the local 512-token output cap and temperature 0. Local evaluation used Qwen ChatML, a 4,096-token context and seed 391. Cloud messages use neutral system/user envelopes. Exact tokenizer, seed support, template, context handling, response format and provider-added reasoning would have to be confirmed and reported before execution. The planned cloud total is 12 calls, one per case and arm, without replacement of failed attempts. B versus A compares models plus deployment/runtime differences. C versus B tests extra retrieval context. D versus B tests the structured pipeline.

Score exact hypothesis identification as a diagnostic separate from complete groups, scoped occurrence and citation attribution. Use the existing extraction-v2 scorer and admission for proof, with role precision/recall/F1 limited to structured outputs. Count unsupported proposals, unsupported eligible items and missed supported findings against the frozen reviewed key. Keep authored proof in its own control. Empty contract-valid output counts as structural abstention. A semantic abstention requires corroborated case-specific reasoning. The direct schema provides no such rationale, and structured absence alone receives no semantic credit. Report measured usage, cost and latency separately by provider and retain refused, truncated or invalid responses.

## Replayed local result

The four local direct responses contained five existing action citations. Three proposed hypotheses matched supported occurrences. The other two were on authorized or incomplete inputs. Exact technique proposal precision was 3/5 and supported-hypothesis recall was 3/3. Complete proof and admitted supported findings were **0/3**. All five proposals lacked complete support and admission withheld all five. The two negative controls were withheld after proposal, yielding **0/2** empty abstentions. Exact role metrics are unavailable for the direct schema. Summed observed endpoint time was **8.358 seconds**, with **3,754 prompt tokens and 191 output tokens**. [Archived paired evaluation](CLOUD_PIVOT_EXTRACTION_V2_RESULTS.md)

| Case | Local action citations and reason for withholding | Lexical reference coverage in blocked arm C |
| --- | --- | --- |
| Windows | E1.1, missing cited authorization and independent attribution | T1685.005 present |
| Slate | E2.1 and E4.1, both missing authorization and attribution. Recovery also lacks cited completion. | Neither expected technique reached the top five |
| Windows incomplete | E1.1, missing authorization and attribution | Fixed hypothesis present. Unavailable corroboration remains unavailable |
| Windows authorized | E1.1, applicable contrary authorization and incomplete positive proof | Fixed hypothesis present. Retrieval contributes no incident authorization evidence |

The top-five references cover **1/3** supported occurrences across Windows and Slate. Because the correct fixed hypotheses are supplied in all arms, coverage here measures supplemental context. It should never count as recall of independently generated findings. In the archived local result, correct action observations did not supply the missing actor, authorization and outcome links. No cloud diagnosis follows.

## Reproduction and next decision

```powershell
python -B -m eval.cloud_real_comparison_prep --output .build/cloud-real-comparison-v1-replay.json
python -B -m pytest -q -p no:cacheprovider tests/test_cloud_real_comparison_prep.py tests/test_cloud_track_a.py tests/test_cloud_extraction_v2.py tests/test_ai_layer.py
```

The comparison manifest SHA-256 is `c3713861ca304a9ed7c84c3629684865eba517f650860087d2c0d700d7b7c840`. The first generated bundle is `.build/cloud-real-comparison-v1-prepared.json` with SHA-256 `7701b717960ec8806ce7eaaea1d4417825fb748d009cd6cd2d042da8b7338e53`. The second run produced identical bytes. Each case retains its replayed verdict and measured local usage separately from the draft cloud envelopes and null cloud results. **33 tests passed.** All 71 historical artifact hashes and five signed-off source hashes matched. [Offline replay implementation](../eval/cloud_real_comparison_prep.py)

The next justified experiment is the frozen diagnostic comparison, contingent on documented revocation and rotation, spend controls, model capabilities and written authorization for these exact synthetic payloads and a maximum spend. Any provider capability check that sends a request is subject to those same approvals. A later confirmatory claim requires untouched, independently labelled cases. The present evidence supports no claim about 27B quality or superiority.
