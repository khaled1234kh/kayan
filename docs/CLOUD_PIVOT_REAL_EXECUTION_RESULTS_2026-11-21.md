# SovereignEG execution results · Output budget exhausted

21 November 2026 · **12/12 diagnostic requests executed once. The separately authorized probe also executed once.** Every diagnostic response returned HTTP 200 and the exact requested model ID. All 12 ended with `finish_reason=length`. The provider reported 512 reasoning tokens per response and returned no visible answer. **Complete grounded findings were 0/3 in each cloud arm and 0/3 in the archived local direct arm.** The cloud run establishes an output-availability failure under the frozen settings. Model accuracy conditional on a usable answer remains unmeasured. [Owner authorization](CLOUD_PIVOT_OWNER_AUTHORIZATION_2026-11-21.md)

## Preflight that cleared execution

- The signed-in dashboard showed the Student allowance active for Qwen3.8-27B-FP8, with about 3.8 million tokens available. Automatic balance use was off, and paid requests over plan limits were disabled. The default personal project exposed no separate benchmark budget. The verified account-side allowance-only behavior provided a zero-balance-charge limit for this model. The key page showed one active key out of three total and a key created on 21 November. The owner's dated attestation supplies the specific revocation confirmation. The replacement was located outside the Git checkout and read only when authenticating. [Student plan behavior](https://preprod.sovereigneg.com/docs/student-plan)
- The provider catalogue documents the exact model and destination and identifies this model as Egypt-hosted. The allowance documentation describes service on SovereignEG's own GPUs. The API reported the exact model identifier and a 20-request-per-minute limit. The preserved response headers contain no independent host attestation. [Model catalogue](https://sovereigneg.com/models/SovereignEG%2FQwen3.8-27B-FP8) · [Provider error and allowance routing documentation](https://dev.sovereigneg.com/docs/errors)
- The one separate probe used neutral synthetic text and the exact extraction-v2 schema. It returned HTTP 200, a schema-valid empty facts array, the requested model ID and `stop`. Usage was 33 prompt and 78 completion tokens. The probe establishes acceptance of the wire schema on that input. It is excluded from the accuracy comparison.
- Both hashes matched the owner authorization. The network runner projected the frozen messages, schemas and model into provider request fields, using temperature 0 and `max_tokens=512`. It ran sequentially at a minimum 3.2-second interval between starts, reserved at most **10.50624224 EGP** of catalogue-equivalent use for all 13 calls, and enforced a once-only execution marker. Cloud context, chat templating and reasoning are provider-specific. The archived local arm used local ChatML and a seed. The cloud requests used the provider's default reasoning setting.

## Matched results

| Arm | Attempts / HTTP successes | Usable contracts | Complete findings | Missed supported findings | Input / output tokens | Summed endpoint seconds |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| A · Archived local direct | 4/4 | 4/4 | 0/3 | 3/3 | 3,754 / 191 | 8.358 |
| B · Cloud direct | 4/4 | 0/4 | 0/3 | 3/3 | 2,912 / 2,048 | 19.014 |
| C · Cloud lexical | 4/4 | 0/4 | 0/3 | 3/3 | 4,390 / 2,048 | 16.407 |
| D · Cloud structured v2 | 4/4 | 0/4 | 0/3 | 3/3 | 3,056 / 2,048 | 16.453 |
| Separate human-authored proof | — | 4/4 fixture proposals | 3/3 | 0/3 | — | — |

Cloud recorded **0/12 visible answers and 12/12 truncations**, with no retries or substitutions. There were zero cloud unsupported proposals, eligible items, semantic abstentions or empty-output abstentions. Empty content under a length termination is a failed response. The denominator for precision among emitted claims, role accuracy conditional on a structured answer, and citation attribution among emitted citations is zero. The archived local arm proposed three matching action hypotheses plus two control claims. All five lacked complete support and were withheld. [Matched local results and evidence](CLOUD_PIVOT_REAL_MODEL_COMPARISON.md)

| Previously exposed synthetic case | Oracle positives | B / C / D endpoint seconds | Observed blocker |
| --- | ---: | --- | --- |
| Windows | 1 | 3.921 / 3.985 / 4.547 | All 512 output tokens consumed by reasoning in each arm. No occurrence, citation or role output. |
| Slate | 2 | 3.797 / 3.546 / 4.000 | Same truncation for both hypotheses across all arms. |
| Windows incomplete | 0 | 4.484 / 4.797 / 4.016 | Same truncation. No observable withholding rationale. |
| Windows authorized | 0 | 6.812 / 4.079 / 3.890 | Same truncation. No observable authorization judgement. |

The 12 calls used **10,358 input tokens and 6,144 output tokens**, all 6,144 reported as reasoning, over **51.874 summed endpoint seconds**. Including the probe, reported token use was 10,391 input and 6,222 output. The public catalogue rates of 8.41 EGP per million input and 67.29 EGP per million output imply **0.50606669 EGP** before the free allowance. Under the verified allowance-only setting, expected balance charge is **0 EGP**. This is a billing inference from the account setting. The API returned token counts without an itemized charge, and no post-run invoice was verified. [Pricing](https://sovereigneg.com/models/SovereignEG%2FQwen3.8-27B-FP8)

## Artifacts and verification

The owner-approved manifest and bundle hashes matched. The dated ledger `.build/sovereigneg-diagnostic-2026-11-21/requests.jsonl` has SHA-256 `ee395377b6cdb2982682643c11db60602dedd8d376d522ecea7fd4d509adb923`. The separate probe record `.build/sovereigneg-capability-probe-2026-11-21.json` has SHA-256 `0a212ae1f48c3f30256b91564f4df133b22bb20967490348cac951b1bb25f73d`. The ledger keeps outgoing synthetic requests, exact response bodies, request IDs and usage. Authentication headers are excluded. Offline inspection matched all 12 attempts to the approved case/arm schedule and frozen envelope conversion. The existing 33 focused tests passed. All 71 historical artifact hashes and five signed-off verifier hashes matched.

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath .build/sovereigneg-diagnostic-2026-11-21/requests.jsonl,.build/sovereigneg-capability-probe-2026-11-21.json
python -B -m pytest -q -p no:cacheprovider tests/test_cloud_real_comparison_prep.py tests/test_cloud_track_a.py tests/test_cloud_extraction_v2.py tests/test_ai_layer.py
```

The recorded network entry point is `eval.cloud_frozen_diagnostic`. Its one-run marker prevents repeating this authorization. Every observed cloud failure occurred before the evidence scorer received a citation or role. This comparison demonstrates **no improvement under the frozen 512-token settings**. It cannot rank extraction or retrieval quality among the cloud arms. The four exposed development cases support no independent or population-level claim. Any future comparison aimed at grounding would first need an approved test that reserves output for the structured answer. The current experiment is closed. [Isolated network runner](../eval/cloud_frozen_diagnostic.py)

## Earlier preflight record

21 November 2026 · **0/12 diagnostic requests attempted. 0/1 possible probe attempted.** The project owner authorized the frozen comparison with a 20 EGP maximum. Required operational checks remain open. [Recorded owner authorization](CLOUD_PIVOT_OWNER_AUTHORIZATION_2026-11-21.md)

| Check | Observed evidence and disposition |
| --- | --- |
| Revocation and replacement | The owner supplied dated confirmation. The original repo-local path is absent, and Git's staged file list is empty. The replacement's current absolute path was unavailable in the supplied authorization and was not found by filename in the top-level Downloads and user configuration locations checked. Credential contents stayed unread. |
| Spend and overages | The owner authorized 20 EGP and attested that caps are configured and automatic balance usage is disabled. No independently accessible account evidence established the effective numeric cap, allowance depletion behavior or current applicable pricing. The maximum cost and account-side enforcement could not be verified. A local ledger cannot clear this gate. |
| Model, routing and structured output | The repo config supplies the exact approved identifier and destination. Current upstream routing, effective context/output limits and acceptance of the exact extraction-v2 union schema remain unverified. The adapter remains mock-only. An authenticated capability check was gated on the unresolved preflight. |
| Exact bundle | Regenerated byte for byte from the offline entry point. Both approved digests matched. All four previously exposed synthetic development cases had B, C and D drafts with null cloud results. The synthetic observations, hypotheses and lexical references are pinned by the approved bundle. |

## Measurements

| Configuration | Result |
| --- | --- |
| A · Archived local Qwen2.5 7B direct | **0/3** complete supported findings. The archived per-case reasons and observed usage are retained in the comparison report. |
| B · SovereignEG direct | Blocked. |
| C · SovereignEG with frozen lexical references | Blocked. |
| D · SovereignEG role-constrained extraction v2 | Blocked. |
| Human-authored diagnostic proof | **3/3**, kept separate from model performance. |

There are no cloud per-case responses, findings, token measurements, provider errors, latency observations or charges from this preflight. The evidence cannot determine whether the 27B model improves grounding.

## Offline reproduction

```powershell
python -B -m eval.cloud_real_comparison_prep --output .build/cloud-real-comparison-owner-preflight-replay.json
Get-FileHash -Algorithm SHA256 -LiteralPath eval/fixtures/ai/cloud_real_comparison_v1.json,.build/cloud-real-comparison-owner-preflight-replay.json
python -B -m pytest -q -p no:cacheprovider tests/test_cloud_real_comparison_prep.py tests/test_cloud_track_a.py tests/test_cloud_extraction_v2.py tests/test_ai_layer.py
```

The regenerated preflight bundle is `.build/cloud-real-comparison-owner-preflight-2026-11-21.json`, SHA-256 `7701b717960ec8806ce7eaaea1d4417825fb748d009cd6cd2d042da8b7338e53`. The manifest hash is `c3713861ca304a9ed7c84c3629684865eba517f650860087d2c0d700d7b7c840`. **33 focused tests passed.** All **71** historical artifact hashes and **five** signed-off source hashes matched. The execution ledger and timestamped provider artifacts await a cleared preflight. [Matched design and per-case local evidence](CLOUD_PIVOT_REAL_MODEL_COMPARISON.md) · [Historical digest command](ATTACK_PROVENANCE_V1_P1_CUSTODY_2026-11-20.md#verification-and-reproduction)
