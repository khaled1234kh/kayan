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

The small set supports a within-fixture comparison only. It cannot establish live provider quality, general ranking superiority or operational readiness. The action supplement needs a separate held-out evaluation before an application decision.
