# Archived Reporting observed-action holdout

The eight synthetic retrospective archive families were frozen in `52bf118` before inference. Their archive and request digests differ from the development set. Six were primary cases, one tested the eight-excerpt limit, and one contained only authorized activity. Preferences and expected dispositions were authored before inference without independent reviewer validation. [Cases](../eval/fixtures/ai/archived_reporting_action_holdout_v1.json) · [Frozen plan](../eval/fixtures/ai/archived_reporting_action_holdout_v1.lock.json)

All seven local Qwen2.5 7B requests returned HTTP 200 and valid selections. The authorized-only case made zero requests. Ollama 0.40.13 served the pinned Q4_K_M model on an isolated loopback port with cloud features disabled. The trace records 4,355 input tokens and 430 output tokens, with a 1.61-second median wall time per request. The dedicated service was stopped after evaluation. [Raw trace](../eval/reports/archived_reporting_action_holdout_v1.jsonl)

| Metric across six primary cases | Deterministic composer | Raw Qwen | Qwen plus verified action excerpts |
| --- | ---: | ---: | ---: |
| Occurrences cited | 8/8 | 8/8 | 8/8 |
| Occurrences with an observed-action excerpt | 8/8 | 1/8 | 8/8 |
| Preferred excerpts recovered | 8/16 | 9/16 | 16/16 |
| Preferred excerpts among excerpts returned | 8/8 | 9/12 | 16/19 |
| Correct order among comparable pairs | 2/2 | 2/3 | 14/16 |
| Exact ordered excerpt lists | 0/6 | 0/6 | 1/6 |
| Exact ordered control lists | 6/6 | 6/6 | 6/6 |

The supplement preserved the original excerpt order, exact admitted and withheld findings, and defensive controls. It met all preregistered gates, including the minimum action coverage of 90% and maximum precision and ordering losses of 10 percentage points. The comparable-pair denominators differ because the supplement adds excerpts. The two methods had only three comparable pairs in the unsupplemented model arm. [Offline scoring output](../eval/reports/archived_reporting_action_holdout_v1_summary.json)

The full selection in the nine-occurrence stress case stayed within the eight-excerpt cap. It cited 8/9 occurrences and displayed observed-action excerpts for 0/9, both before and after supplementation. The appended-excerpt policy cannot repair a full selection. Treat this as a presentation limitation. The underlying verified findings remain available. This result supports a bounded presentation change and does not establish independent accuracy, live-provider quality or production readiness.

Fixture SHA-256 is `1684e8ad27b33a288318d367456436a365d9f76c32a8d9c17a93cb6d0183c644`. Raw trace SHA-256 is `38ff96c614a92302307c80853915852e5335b7d6c598d5d98dc304165022bf90`.

Verify the request plan with `python -B -m eval.archived_reporting_local_ranking plan --fixture eval/fixtures/ai/archived_reporting_action_holdout_v1.json`. Reproduce the saved scores without inference using `python -B -m eval.archived_reporting_action_holdout`. Fresh local measurements require an isolated Ollama process on `127.0.0.1:11534` with `OLLAMA_NO_CLOUD=1` and a new output path. Run `python -B -m eval.archived_reporting_local_ranking run --fixture eval/fixtures/ai/archived_reporting_action_holdout_v1.json --lock eval/fixtures/ai/archived_reporting_action_holdout_v1.lock.json --startup-log <log> --output <new-jsonl-path>`.
