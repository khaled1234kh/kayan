# Bounded live authorization request — matched 80-case cloud arm

Status: **AWAITING OWNER AUTHORIZATION. NO LIVE REQUEST HAS BEEN SENT.**

## Exact frozen scope

| Item | Value |
| --- | --- |
| Destination | `https://backend.sovereigneg.com/v1/chat/completions` |
| Model | `SovereignEG/Qwen3.8-27B-FP8` (served model must match exactly) |
| Manifest | `roles_frozen.json` SHA-256 `09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0` |
| Cases | 80 held-out cases, 16 per role; order fixed by `Random(20261112)` |
| Request body | frozen system prompt + frozen case JSON + frozen per-case schema, temperature 0, max_tokens 384, reasoning_effort none, stream false, strict JSON schema |
| Primary requests | 80 |
| Structural retries | at most 1 per case (contract rejection only), 80 maximum |
| **Total request cap** | **160** |
| Transport retries | 0 |
| Data | frozen synthetic cases only; no real telemetry, credentials, private records or scoring keys |
| Output | new exclusive-create directory; full redacted ledger; hashes of manifest and all artifacts |
| Ceiling requested | **10 EGP** catalogue-equivalent |

## Cost estimate (catalogue rates from 21 Nov 2026 record: 8.41 EGP/M input, 67.29 EGP/M output)

| Scenario | Input tokens | Output tokens | Catalogue-equivalent |
| --- | ---: | ---: | ---: |
| 80 primaries at local-observed usage (445 in / 134 out) | 35,577 | 10,735 | 1.02156072 EGP |
| 160 requests at frozen 384-token output cap | 71,200 | 61,440 | 4.73308960 EGP |
| 160 requests at conservative 512-token output | 71,200 | 81,920 | 6.11118880 EGP |

The 10 EGP ceiling covers the conservative case. Under the previously verified allowance-only
account setting the expected balance charge is 0 EGP; this remains to be reconfirmed by the owner.
The API does not return an itemized charge, so the reported cost is a catalogue-rate inference.

## Stop conditions built into the runner

- HTTP 401/402/403/429 or any 3xx response: stop immediately.
- Response header `X-Dropped-Params`, `X-Mapped-Params` or `X-Output-Clamped`: stop immediately.
- Served model differs from the authorized ID: stop that case and record.
- 160 requests reached or spend ceiling exceeded: stop.
- Transport error: record and continue (no bill is assumed), matching frozen runner behavior.
- Malformed or empty response: record as failed contract, no substitution, no replacement model.

## Owner checks required before the single live run

1. Student allowance for `SovereignEG/Qwen3.8-27B-FP8` is active with sufficient remaining tokens.
2. Automatic balance use is disabled and paid requests above plan limits are disabled.
3. Current input/output catalogue rates are as stated or lower.
4. Credential file is outside the checkout, not staged, and is a rotated replacement.
5. This exact scope, 160-request cap and 10 EGP ceiling are approved in one authorization.

## What will be reported

A supervisor-ready table with MEASURED values or NOT MEASURED, per-role exact passes, evidence F1,
affirmative F1, unsupported claims, latency/cost tradeoff, paired uncertainty against each local
arm, and an explicit statement that this is a retrospective matched synthetic benchmark rather
than a fresh independent blinded human-adjudicated holdout. If fewer than 80 cases complete, the
run is reported as incomplete with the exact completed count and no extrapolation.
