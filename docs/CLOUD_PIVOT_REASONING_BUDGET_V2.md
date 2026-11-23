# SovereignEG reasoning budget correction

21 November 2026 · Frozen offline design and Stage A execution record

## Stage A owner authorization

On 21 November 2026 the project and SovereignEG account owner authorized exactly one Stage A request for the manifest, bundle and request digests in this report. The owner approved a combined 12 EGP ceiling across Stage A and any later approved Stage B, with zero paid balance draw. Destination, model and all frozen parameters were approved. Stage B requires its own authorization. The signed-in Plans page showed an active Student plan, about 3.8 million tokens remaining, automatic balance use off, and paid requests over plan limits off and disabled for Qwen3.8-27B-FP8. The current public catalogue identifies the approved model and endpoint and lists 5 EGP per million input tokens, 10 per million output and 10.26 per million cache-write tokens. The original catalogue estimate below remains part of the frozen preparation record. [Provider catalogue](https://sovereigneg.com/models/SovereignEG%2FQwen3.8-27B-FP8)

## Stage A result · Exact citation check failed

One approved probe was sent on 21 November 2026 at 12:38 Cairo time. SovereignEG returned HTTP 200 and the exact model `SovereignEG/Qwen3.8-27B-FP8`. The response was visible and schema-valid, with `finish_reason="stop"`, 84 input tokens, 75 output tokens, explicitly reported zero reasoning tokens and 1.734 seconds of endpoint time. The captured headers showed no clamp or parameter substitution. Request ID `req_Vd9cK0Vq3oIqsC3YRqHmi`. The rate-limit header reported 20 requests per minute, with 19 remaining.

The expected mechanic atom required `E1.1` in both `anchor` and `cite`. The model returned `"Windows Security event"` in both fields. Technique `T1685.005`, role `mechanic` and value `observed` matched. Those fields accept strings at schema validation, so the response passed JSON Schema and failed the exact-answer test in the existing `check_probe`. The corrected configuration produced a usable answer and removed the measured reasoning-token exhaustion on this probe. Exact citation and occurrence grounding failed. No retry or Stage B request was sent. **Stage B is not ready for authorization under the frozen criterion.**

At the current public rates the probe used **0.00117 EGP** of catalogue-equivalent usage. The verified allowance-only controls imply zero paid balance draw. The response did not return an itemized charge header. Raw evidence is in `.build/cloud-reasoning-budget-v2-stage-a-2026-11-21.json` with SHA-256 `271544c978063f25ade957e988dd2657f6a3c4e47054d71ddf5e86ebc93f6b86`. The record contains no authorization header or credential.

## Frozen design

The first run exhausted 512 output tokens on reasoning in all 12 calls. The new diagnostic changes exactly two generation parameters, `reasoning_effort="none"` and `max_tokens=1024`. Temperature remains 0. The 12 requests retain the original case and arm order, model, messages, observations, hypotheses, lexical references and exact schemas. Scoring and signed-off admission stay the same. The original probe, benchmark ledger and approvals remain historical. [Original run](CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md) · [Offline preparer and probe validator](../eval/cloud_reasoning_budget_v2.py)

## Frozen identities

| Artifact | SHA-256 |
| --- | --- |
| v2 manifest | `ba6261262fb374fab7d724cafdcaee3148d5b3234ec7a9b9f8532857e0816d21` |
| v2 bundle | `18a6c76752ed8a95cd235c4a7c1383e6585396dce27f7b62b119008265715dbf` |
| Stage A request | `5052fcf7de5e45d51acc70e73d38704a898f5b074f9b2a2990fa175f6fd31113` |
| Parent manifest | `c3713861ca304a9ed7c84c3629684865eba517f650860087d2c0d700d7b7c840` |
| Parent bundle | `7701b717960ec8806ce7eaaea1d4417825fb748d009cd6cd2d042da8b7338e53` |

Each diagnostic has an individual digest in the manifest, computed from sorted-key compact ASCII JSON. The bundle uses the repository's indented ASCII JSON serializer with a final LF. It stores the Stage A expected answer separately from its request. The expected answer is never part of the transmitted payload. [Manifest and per-request hashes](../eval/fixtures/ai/cloud_reasoning_budget_v2.json)

## Provider behavior and answer capacity

The Chat Completions documentation lists `reasoning_effort`, `max_tokens` and `temperature`. For the sovereign Qwen3.8 family, it states that `none` passes through unchanged and disables reasoning. It documents `X-Dropped-Params` and `X-Mapped-Params` for gateway changes, and `X-Output-Clamped` and `X-Plan-Output-Cap` for output restrictions. The previous live probe accepted the exact schema but did not test a nonempty answer with reasoning disabled. The exact v2 behavior remains a Stage A measurement. [Chat Completions documentation](https://dev.sovereigneg.com/docs/chat-completions)

I validated role-key answer witnesses against the exact extraction-v2 schema and counted tokens using the installed Qwen2.5-7B tokenizer as a proxy. The tokenizer digest and counts are in the manifest. The largest required witness is Slate with eight atoms and 264 compact or 421 indented tokens. The 1,024-token cap leaves 603 proxy tokens above the largest indented required witness. A schema-only stress case with 18 optional quote-bearing atoms reaches 2,502 proxy tokens. The cap fits the required proof witnesses under this proxy. It cannot guarantee space for every schema-permitted output or predict the provider's exact encoding.

## Original proposed approval scope

- **Provider and model** — SovereignEG, `SovereignEG/Qwen3.8-27B-FP8`, `https://backend.sovereigneg.com/v1/chat/completions`.
- **Exact payload scope** — the v2 manifest and bundle hashes above. Synthetic-only Stage A input and the already exposed synthetic diagnostic records. Keep credentials, private telemetry, scoring keys and custody material outside generation inputs and ledgers.
- **Stage A authorization** — exactly one capability and answer request with the exact structured schema and a nonempty expected mechanic atom. Approved 21 November 2026 and consumed by the recorded probe.
- **Stage B authorization** — exactly 12 diagnostic calls, conditional on recorded Stage A success and a subsequent explicit owner approval against the same hashes. Owner approval/date ___.
- **Total ceiling approved 21 November 2026** — **12 EGP across Stage A and any separately approved Stage B**, with **zero paid balance draw** under the Student allowance. No retries, credit purchases or paid overages.

At public model rates of 8.41 EGP per million input tokens and 67.29 EGP per million output tokens, reserving 92,000 input and 1,024 output tokens per call gives 10.95412448 EGP of catalogue-equivalent use across all 13 calls. The 92,000 input allowance is a conservative per-call estimate from the documented Student context setting. This is a secondary estimate. Effective enforcement requires observing the signed-in account with this exact model covered, adequate allowance available, and both automatic balance use and paid requests over plan limits off. The earlier account check is historical. Reverify those controls and current prices immediately before each approved stage. [Model pricing](https://sovereigneg.com/models/SovereignEG%2FQwen3.8-27B-FP8) · [Plan context guidance](https://sovereigneg.com/docs/opencode) · [Allowance rules](https://sovereigneg.com/docs/student-plan)

## Execution and results record

1. Regenerate to a new path and verify the output hash. The preparation module is offline.

   ```powershell
   python -B -m eval.cloud_reasoning_budget_v2 --parent .build/cloud-real-comparison-v1-prepared.json --output .build/cloud-reasoning-budget-v2-replay.json
   Get-FileHash -Algorithm SHA256 -LiteralPath eval/fixtures/ai/cloud_reasoning_budget_v2.json,.build/cloud-reasoning-budget-v2-replay.json
   python -B -m pytest -q -p no:cacheprovider tests/test_cloud_reasoning_budget_v2.py tests/test_cloud_real_comparison_prep.py tests/test_cloud_extraction_v2.py
   ```

2. After Stage A approval and the account check, submit only `stage_a.request` once to the approved endpoint. Record HTTP status, served model, finish reason, reasoning-token usage, request ID and relevant adjustment/clamp headers without credentials. Use the offline `check_probe` function on the recorded response. It requires HTTP 200, exact model, a visible schema-valid answer matching the expected atom, `stop`, explicitly reported zero reasoning tokens, and no indicated clamp or change to temperature or reasoning effort. Empty, invalid, missing-metadata or adjusted replies stop the experiment.
3. After Stage A success and separate Stage B approval, submit the 12 `stage_b` requests sequentially under provider limits. Preserve every request and response once in a fresh ledger. Stop upon unexpected routing, spend or parameter changes or allowance exhaustion. Reuse the existing scorer and admission verifier. Report visible answers and truncation, first-pass schema validity, technique and occurrence correctness, evidence roles, complete supported findings, unsupported claims, appropriate abstentions, latency, tokens and cost. Preserve missing or invalid answers as failures and the authored oracle as a separate control.

**Verification:** 11 focused tests passed. All 71 historical artifact hashes, five signed-off source hashes and the original cloud ledger and probe hashes matched. The design tests answer availability by changing two generation settings together. It does not isolate their individual effects. The exposed development cohort supplies no independent validation.
