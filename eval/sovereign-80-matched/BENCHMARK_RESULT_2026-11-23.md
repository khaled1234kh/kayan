> **Scope of this figure.** 90.00% is exact contract accuracy on 80 authored synthetic cases in a
> retrospective matched benchmark. It is **not** a fresh blinded human-adjudicated holdout, not
> real-world vulnerability-detection accuracy, and not a production-readiness result.

# KAYAN TrustGate — matched 80-case cloud accuracy result

23 November 2026 · Khaled Mohamed (20231160) · isolated evaluation branch
`eval/sovereign-80-case-accuracy` · worktree `<EVAL_WORKTREE>`

## Result table (all values MEASURED from the recovered frozen benchmark)

| Model | Exact passes | Exact accuracy | Affirmative F1 | Evidence F1 | Abstention F1 | Unsupported affirmative decisions | Invalid outputs | Inference errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **SovereignEG/Qwen3.8-27B-FP8 (cloud)** | **72/80** | **90.00%** | **0.935** | **0.945** | **0.984** | **0** | **0** | **0** |
| Qwen3 8B (local) | 28/80 | 35.00% | 0.745 | 0.693 | 0.857 | 41 | 0 | 0 |
| Granite 4.2 8B (local) | 27/80 | 33.75% | 0.762 | 0.762 | 0.879 | 39 | 0 | 0 |
| Llama 3.1 8B (local) | 23/80 | 28.75% | 0.714 | 0.688 | 0.847 | 36 | 0 | 0 |
| Qwen2.5 7B (local) | 18/80 | 22.50% | 0.544 | 0.454 | 0.571 | 78 | 0 | 0 |
| Qwen2.5 1.5B (local) | 5/80 | 6.25% | 0.634 | 0.454 | 0.316 | 84 | 0 | 0 |

## Exact passes by role (out of 16 each)

| Role | Cloud 27B | Qwen3 8B | Granite 8B | Llama 8B | Qwen2.5 7B | Qwen2.5 1.5B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Planner | **11** | 3 | 7 | 0 | 3 | 1 |
| Recon | **16** | 7 | 4 | 5 | 5 | 1 |
| Web-App | **16** | 7 | 7 | 5 | 6 | 1 |
| Network | **15** | 8 | 4 | 7 | 1 | 0 |
| Reporting | **14** | 3 | 5 | 6 | 3 | 2 |

The cloud arm is equal to or better than every local checkpoint in every role. Its eight failures
were five Planner, two Reporting and one Network case; none emitted an unsupported affirmative
decision. All 80 responses were HTTP 200, `finish_reason=stop`, served the exact authorized model,
had zero reasoning tokens, and had no provider parameter-drop/map or output-clamp header.

## Paired uncertainty (cloud minus local, 5,000 role-stratified family-cluster bootstrap replicates)

| Reference arm | Exact-pass difference (pp) | 95% interval (pp) | Evidence-F1 difference | 95% interval |
| --- | ---: | ---: | ---: | ---: |
| Qwen2.5 7B | +67.50 | [+56.25, +77.50] | +0.492 | [+0.387, +0.605] |
| Qwen3 8B | +55.00 | [+45.00, +65.00] | +0.253 | [+0.201, +0.305] |
| Granite 4.2 8B | +56.25 | [+46.25, +66.25] | +0.184 | [+0.133, +0.242] |
| Llama 3.1 8B | +61.25 | [+48.75, +73.75] | +0.258 | [+0.180, +0.340] |
| Qwen2.5 1.5B | +83.75 | [+76.25, +90.00] | +0.491 | [+0.449, +0.531] |

Every interval excludes zero. These are exploratory intervals over small authored synthetic
families, not population estimates, and are unadjusted for multiple comparisons.

## Runtime, cost and execution integrity

- Measured catalogue-equivalent usage: **1.32167372 EGP** for 80 scored requests plus one
  rate-limited (429) request that was discarded and re-sent. Under the owner-confirmed
  allowance-only account setting the expected balance charge is 0 EGP; the API supplied token
  counts but no itemized charge, so this is a catalogue-rate inference.
- Input/output tokens: 35,897 / 15,155. Mean per case about 449 input / 189 output.
- Endpoint latency: p50 1.164 s, p95 1.693 s per case. Local p50/p95 were 1.12–3.57 s /
  1.56–5.04 s on the original RTX 5060 Laptop host. These are **not** a like-for-like host
  comparison and must not be used to claim the cloud model is faster in deployment.
- Wall time: 5.03 minutes including a provider 429 stop at case 21 and a resume with 4-second
  request pacing (15 starts/min, below the documented 20/min limit). The resumed run reused the
  identical frozen order, prompt, schema, model and scorer; only inter-request pacing changed.
- Authorized caps respected: 81 total requests (cap 160), 1.32 EGP (ceiling 10 EGP), frozen
  synthetic data only, no production or TrustGate/Cedar/ROE changes.
- The full redacted request ledger, scored `cases.jsonl` and final re-score outputs remain private and are **not** published (they are raw model responses/request metadata). Their integrity was checked locally: re-running the untouched scorer on the saved outputs reproduced `summary.json` and `summary.csv` byte-for-byte. Published here are the frozen inputs, harness, scorer, exact metrics and digests needed to understand and audit the claim.
  Frozen manifest SHA-256 `09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0`.

## Answers to the supervisor questions

1. **Did the cloud model outperform Qwen2.5 7B on exact accuracy?** Yes: 72/80 vs 18/80,
   +67.5 percentage points, paired 95% interval [+56.25, +77.50].
2. **Did it outperform Qwen3 8B exact accuracy?** Yes: 72/80 vs 28/80, +55.0 points,
   paired 95% interval [+45.00, +65.00].
3. **Did evidence F1 improve and unsupported claims fall?** Yes on both. Evidence F1 0.945 vs
   0.693 (Qwen3) and 0.454 (Qwen2.5 7B). Unsupported affirmative decisions were 0 versus 41 and
   78 respectively. Abstention F1 was 0.984, the highest of all arms.
4. **Which roles improved or regressed?** All five improved against every local arm: Planner
   11 vs best-local 7, Recon 16 vs 7, Web-App 16 vs 7, Network 15 vs 8, Reporting 14 vs 6.
   No role regressed. Planner remains the hardest role for the cloud model (11/16).
5. **Runtime/cost tradeoff?** The cloud arm cost about 1.32 EGP catalogue-equivalent and took
   about five minutes including a rate-limit pause, against local inference on owned hardware.
   Endpoint latency was low but not host-comparable. The 20/min rate limit requires pacing for
   any repeated run.
6. **Is this comparable to the historical local numbers?** Yes, to the recovered frozen 80-case
   role benchmark only: identical manifest, case order, prompt, schemas, scorer, temperature and
   384-token output budget, with documented remapping of Ollama `format` to strict `response_format`,
   `num_predict` to `max_tokens`, and `think: false` to `reasoning_effort: none`. `seed`, `num_ctx`
   and `keep_alive` have no documented provider equivalent and were not sent. Cloud context,
   chat templating and tokenization remain provider-specific. It is **not** comparable to the
   18-case ATT&CK extraction diagnostic, the 19-case `eval/ai_benchmark.py`, or the earlier
   live Planner-only 24/30 figure.
7. **Continue the cloud pivot?** The measured evidence supports continuing as a scoped research
   candidate: it is the first matched result showing a clear advantage on the project's own
   frozen role benchmark. It does **not** by itself justify production deployment. Next step
   should be replication on a fresh independently labelled synthetic cohort with blinded human
   adjudication, plus a provider-side check of context/template effects and repeatability. Keep
   TrustGate authorization, Cedar rules, signed ROE and admission controls unchanged.

## Limits to state explicitly

- Retrospective matched benchmark on 80 authored synthetic cases, not a fresh independent
  blinded human-adjudicated holdout. The holdout families are separate from the 40 calibration
  cases, but ground truth and contracts were authored for this pilot.
- The comparison includes deployment/runtime differences, not only model capability: provider
  tokenization, chat template and context handling cannot be matched exactly.
- Reasoning was disabled to honour the frozen `think: false` control. Earlier cloud diagnostics
  that exhausted output on reasoning used a different setting and are not accuracy results.
- One 429 event was excluded and re-sent under the same authorization; no model response was
  substituted, no prompt or rubric was changed, and no scoring key was altered.
- The key used for this run was previously exposed in chat; it must be rotated before any
  shared or public use. Its contents were never printed or written to artifacts.
