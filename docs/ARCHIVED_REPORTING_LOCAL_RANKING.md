# Archived Reporting local ranking experiment

The frozen set contains seven new synthetic retrospective archive cases. Six contain eight admitted finding occurrences in total. The approved-only case contains zero admitted occurrences and made zero requests. The preferred excerpt and control lists were authored before inference. They are a development oracle without independent reviewer agreement. [Cases and oracle](../eval/fixtures/ai/archived_reporting_local_ranking_v1.json) · [Frozen request plan](../eval/fixtures/ai/archived_reporting_local_ranking_v1.lock.json)

The experiment used an isolated loopback Ollama 0.40.13 process and `qwen2.5:7b` Q4_K_M. The API model digest and the installation manifest were pinned separately. All six local blobs matched their full SHA-256 hashes. The runner reused Reporting's messages and JSON schema, with seed 19, temperature 0, a 4,096-token context and an output limit of 192 tokens. The process log confirmed cloud features were off. [Ollama local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features) · [Chat API](https://docs.ollama.com/api/chat)

Six requests returned valid selections. All eight admitted occurrences were cited, and every case preserved the exact admitted findings and withheld claims. Across the six requests, Ollama reported 2,396 input and 345 output tokens. Measured wall time totaled 13.04 seconds, with a 1.56-second median and a 5.39-second first request. A post-run sample reported 4,755,397,016 bytes of model allocation in VRAM. These are observations on this host. The evaluation made zero cloud or paid-provider requests. [Raw responses and measurements](../eval/reports/archived_reporting_local_ranking_v1.jsonl)

| Metric | Deterministic composer | Qwen replies | Qwen replies plus action excerpts |
| --- | ---: | ---: | ---: |
| Preferred excerpts among excerpts returned | 6/8 | 10/11 | 14/17 |
| Preferred excerpts recovered | 6/14 | 10/14 | 14/14 |
| Exact ordered excerpt lists | 0/6 | 0/6 | 2/6 |
| Correct order among comparable excerpt pairs | N/A | 0/4 | 6/10 |
| Admitted occurrences with observed-action excerpts | 8/8 | 2/8 | 8/8 |
| Exact ordered recommendations | 4/6 | 4/6 | 4/6 |

The post-hoc replay appended the first verified action excerpt for each occurrence missing one, within the existing eight-excerpt limit. It kept the model's original order, findings and recommendations. That recovered the missing actions on this set and reduced preferred-reference precision from 10/11 to 14/17. The test with an already-full selection demonstrates that the limit can still leave an occurrence uncovered. The supplement remains an offline development candidate. [Reproducible ablation](../eval/reports/archived_reporting_action_coverage_ablation_v1.json)

Check the frozen plan with `python -B -m eval.archived_reporting_local_ranking plan`. To repeat the measurement, run Ollama separately on `127.0.0.1:11534` with `OLLAMA_NO_CLOUD=1` and capture its startup log. Then run `python -B -m eval.archived_reporting_local_ranking run --startup-log <log> --output <new-jsonl-path>`. Score the saved original replies without inference using `python -B -m eval.archived_reporting_action_coverage_ablation`.

## Opt-in console mode

The deterministic **Local evidence report** is the default. For **Local Qwen · rank verified excerpts**, use an operator-controlled Ollama process on `127.0.0.1:11534` with `OLLAMA_NO_CLOUD=1` and confirm the startup log shows cloud disabled. Set `KAYAN_REPORTING_LOCAL_RANKING=1` for the Reporting backend. A signed Reporting-only rule of engagement must authorize both report writing and inference for the relevant archive. The existing local operator helper grants report writing only. The application records the destination, model pin and request digest in the inference decision request. Rust/Cedar checks the role, action, scope and time window. [Ollama local-only setup](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)

The adapter checks the pinned Qwen2.5 7B digest and quantization on the dedicated loopback endpoint. It allows one generation attempt per run, with a 3,072-byte request limit, 4,096-token context, 192-token output and 60-second total deadline. Only admitted excerpts and fixed control options enter the prompt. The result can select and order those IDs. When local inference is denied, the endpoint is unreachable, or the response fails validation, Reporting returns the deterministic evidence report. An archive or enablement change during inference prevents publication. [Ollama model metadata](https://docs.ollama.com/api/tags) · [Structured chat contract](https://docs.ollama.com/api/chat)

On 21 November, one actual browser-triggered local request through a synthetic preview gate selected `E2.1`, with 221 input tokens, 52 output tokens, finish reason `stop` and provider latency 5.609 s. The reopened compact console showed T1486 supported and T1490 withheld. Its browser export matched all 2,623 saved bytes. The saved result SHA-256 is `a2ce6646a67fb9a14649057c403b3735934f4396bce69083edf9800dd4949c10`. Local evidence and logs are under `.build/reporting-local-preview/`. This smoke checks selection and presentation on one synthetic archive. The original ranking experiments above provide the measured comparison.

On 22 November, an isolated Rust/Cedar instance verified the signed test-only Reporting scopes. With no scope, report writing returned 403. With a write-only scope, inference was denied and the deterministic report remained exportable. With both actions permitted, one mocked selection was saved and exported. The valid Rust ledger contained the exact request digest in both inference decisions. The focused Reporting set passed 61 tests and the combined set passed 321, including this Rust check and signed-archive restart. The frontend session check and build passed. Eight saved evaluations, 76 pinned digests, the historical Slate cloud request and the saved cloud result verified offline.

## Interrupted local requests

A first run cancelled after local preflight previously left the result endpoint at HTTP 404. The backend now saves the deterministic fallback atomically immediately before the generation request. An existing report for the same revision stays readable if a later request is interrupted. A reopened app reads the saved bytes and verifies the current evidence before making them available for display or export. Reopening and exporting make zero inference attempts. An archive that changed during the interrupted request returns HTTP 409 when its earlier bytes no longer match.

Reproduce both first-run and prior-report cases with `python -B -m pytest -q -p no:cacheprovider tests/test_archived_reporting_ollama.py -k interrupted_local_ranking`. The fixture cancels a mocked response and recreates the backend over the original output directory. After the correction, the focused set passed 63 tests and the canonical set passed 323. Eight saved evaluations, 76 pins and the previously saved Slate cloud result verified again.

The small set supports a within-fixture comparison only. It cannot establish live provider quality, general ranking superiority or operational readiness. The action supplement needs a separate held-out evaluation before an application decision.
