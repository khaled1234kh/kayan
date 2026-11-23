# Matched SovereignEG 80-case role benchmark (isolated evaluation branch)

Branch `eval/sovereign-80-case-accuracy`, worktree `<EVAL_WORKTREE>`.
This package is evaluation-only. It does not modify production code, Cedar/TrustGate rules,
signed ROE, provenance, admission, saved reports, or the frozen reference harness.

## What is actually being compared

The original frozen KAYAN role benchmark was recovered byte-for-byte from the archived
offline-benchmark evidence bundle. It is **not** `eval/ai_benchmark.py` and **not** the
18-case ATT&CK extraction diagnostic.

- Frozen manifest: `eval/reference/role-benchmark/data/roles_frozen.json`
- SHA-256: `09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0`
- Scorer: `role_cases.py` SHA-256 `f21e5da7…8104c6`; runner `model_bench.py` SHA-256 `3a8cf412…9da484`
- 120 cases total = 80 held-out (16 per role) + 40 calibration. Only the 80 held-out are used.
- Deterministic order: `random.Random(20261112).shuffle(entries)` on manifest order.
- 9 scorer integrity tests pass. All five local arms re-score to their historical values.

This is a **retrospective matched benchmark** on authored synthetic cases. It is not a fresh
independent blinded human-adjudicated holdout and does not estimate general security accuracy.

## Frozen protocol and cloud mapping

| Frozen field | Cloud request | Status |
| --- | --- | --- |
| `system` prompt | identical text | unchanged |
| user `json.dumps({role,case}, sort_keys=True)` | identical serialization | unchanged |
| `format: <schema>` | `response_format.json_schema.strict` | remapped |
| `temperature 0` | `temperature 0` | unchanged |
| `num_predict 384` | `max_tokens 384` | remapped |
| `think false` | `reasoning_effort "none"` | remapped |
| `seed 42`, `num_ctx 4096`, `keep_alive 3m` | not sent | ignored: no documented provider equivalent |
| one structural-repair retry | same, contract errors only | unchanged |
| no transport retry | same | unchanged |

`reasoning_effort="none"` is used to honor the frozen `think: false` control, not to improve
the cloud arm. Earlier cloud diagnostics that used the provider's default reasoning exhausted
the output budget on reasoning and are a protocol mismatch, not an accuracy result.

## Metrics (unchanged definitions)

- Exact pass: all expected labels and citations, plus acceptable Planner dependency order.
- Evidence F1: item + label + source-reference triples.
- Affirmative F1: each role's affirmative class.
- Per-role exact passes, abstention F1, unsupported positives, invalid outputs, errors.
- Paired role-stratified family-cluster percentile bootstrap (5,000 replicates, seed 20261112).
- Cloud endpoint latency and token cost are recorded but never ranked against local host latency.

## Offline validation (no network calls)

```powershell
python -B -m unittest -v test_roles
# from eval/reference/role-benchmark

python -B eval/cloud_matched/score_matched.py --output .build/score-local-only-check
python -B eval/cloud_matched/make_mock_fixture.py --output .build/mock-responses-80.json
python -B eval/cloud_matched/run_matched.py --mode mock --responses .build/mock-responses-80.json --output .build/cloud-mock-validation-80
python -B eval/cloud_matched/score_matched.py --cloud .build/cloud-mock-validation-80 --output .build/score-with-mock-cloud
```

`score-local-only-check` reproduces 18/28/27/23/5 of 80 and evidence F1 .454/.693/.762/.688/.454
exactly. The mock cloud run produced 80 cases / 103 requests / 1.55281927 EGP catalogue-equivalent
and is labelled `MOCK_VALIDATION_NOT_A_MEASUREMENT`. Its score is derived from expected answers and
is never a model result.

## Live execution gate

Live mode is disabled unless all of the following hold:

1. Owner verifies on the SovereignEG dashboard that the Student allowance for
   `SovereignEG/Qwen3.8-27B-FP8` is active, automatic balance use is off, paid overage is off,
   and the current input/output rates are confirmed.
2. Owner provides a credential file outside the checkout and confirms rotation status.
3. Owner grants one explicit bounded authorization: 80 primary + at most 80 structural retries,
   destination and model pinned, no real data, no production changes, spend ceiling 10 EGP.
4. Runner is invoked with `--mode live --authorized --credential <external path>`.

The runner stops on HTTP 401/402/403/429/3xx, on any provider header indicating a dropped/mapped
parameter or clamped output, on the 160-request cap, or when the spend ceiling is exceeded. It
records every outgoing request, raw response, request ID, usage, reasoning tokens, finish reason,
latency, contract errors, retry, and catalogue-equivalent cost with credentials redacted.

## Current status

Cloud accuracy: **MEASURED - 72/80 (90.00%)** on 23 Nov 2026 under bounded owner authorization. See SUPERVISOR_REPORT_2026-11-23.md.
