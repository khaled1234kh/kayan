# Real local-Qwen comparison v2 — bounded retry and reference framing

Checked 2026-11-01. The original failure is preserved byte-for-byte; its three artifact hashes match v1_grounding_artifact_hashes_2026-11-01.json. No grounding improvement was demonstrated. Preserve this failure.

Changes: at most two recovery retries across a specialist loop, explicit rejected-action feedback and current callable names, no duplicate/unknown dispatch, denied targets remain denied, operator instructions persist across recovery turns. Read-only reference titles/excerpts are separated from callable actions; slug-shaped skill IDs are retained in the full audit context but omitted from model-facing executable choices.

| Condition | Findings | Allowed | Denied | Existing MITRE tracker | Legacy evidence precision | Fresh-nonce reproduction |
|---|---:|---:|---:|---:|---:|---:|
| Off | 2 | 29 | 1 | 40% | 1/2 (50%) | 2/2 (100%) |
| On | 2 | 29 | 1 | 40% | 1/2 (50%) | 2/2 (100%) |

Off engagement: d71c66c6-2c0c-4678-be2b-f038e3cb74a8. On engagement: 1c7e41da-8830-408f-877c-0ad3b9ebfcff.

Both returned xss and command_injection. The command probe uses a benign echo nonce and a second independently generated nonce. The unchanged legacy evidence rubric accepts standalone whoami output for command injection; it does not recognize this echo-marker proof, so it reports 1/2 (50%). Do not hide that number or relabel fresh-nonce reproduction as blinded classification accuracy. XSS evidence is unescaped script reflection; browser execution remains unchecked.

Coverage reuses EngagementOrchestrator._compute_mitre_coverage: two observed vulnerability labels (T1190/T1059) out of five lab categories, 40%. Secondary observed-tool coverage is 5/5 catalogue labels (100%) in both; neither is all-ATT&CK coverage. Counts are all gate decisions after assessment/status response, excluding ROE load; both include one deliberately target-tainted input denial.

Model: qwen2.5:7b, temperature 0; 11 model calls per condition. Retrieved technique context: off 0, on 10. WebSocket snapshots: off 182, on 181; incremental output, five sessions, live status reply and queued delivery checks passed in each.

Neither v2 run made an invalid proposal, so live recovery was not exercised by these two samples. Nine controlled Python regression tests cover actual recovery, exhaustion, duplicates, gate denial, scope rejection, unregistered verifier calls and framing. Do not claim this single pair proves a reduced hallucination rate.

Interpretation: the original skill-ID-as-tool failure did not recur in this pair, but grounding-on did not outperform grounding-off. Changed loop/framing and the later run conditions also prevent causal comparison of v1-versus-v2 finding totals. Original artifacts remain authoritative records of their own runs.

Artifacts: live_grounding_off_v2_bounded_retry.json and live_grounding_on_v2_bounded_retry.json. The evaluator now refuses to overwrite existing labeled artifacts. This report does not certify the upstream PentAGI swap or rendered visual acceptance.
