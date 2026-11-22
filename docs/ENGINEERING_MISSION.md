# KAYAN TrustGate engineering mission

KAYAN aims for dependable coordination across Planner, Recon, Web-App, Network and Reporting, with independent enforcement and auditable evidence. The [acceptance matrix](ENGINEERING_ACCEPTANCE.json) records what each subsystem must demonstrate and the scope of its current evidence. The [proposal](TA_PROPOSAL_REPORT.md), [research update](RESEARCH_UPDATE.md) and [master handoff](../MASTER_HANDOFF.md) record the requirements and research history.

## Standing criteria

- Keep signed rules of engagement, Rust/Cedar authorization, review, evidence admission and execution independent of model output. Preserve action-specific decisions, restricted scope and auditable outcomes.
- Measure task selection, dependency correctness, recovery, loops and unnecessary operations for Planner. Measure grounded observations, attribution, coverage and false claims for specialists. Measure admitted findings, evidence-group completeness, withheld claims and recommendation fidelity for Reporting.
- Compare shared local, role-specific and hybrid configurations under a matched protocol. Measure task accuracy, safety, abstention, latency, token use, resource use and cost separately. Keep development families separate from held-out cases, preserve negative results and report uncertainty. Base decisions about training on observed failure modes.
- Prefer source verification, occurrence and attribution checks, applicable adverse evidence and explicit abstention. Admission v2 retains its signed-off authority. Preserve the distinction between verifying submitted proof and generating proof.
- Keep a local working baseline. Require bounded requests, explicit egress approval, effective spend controls and accurate provider attribution. The standing mission authorizes zero live cloud requests. Historical one-shot permissions have their own scope.
- Verify security, correctness, operational, cloud, evaluation, reliability, academic and production criteria individually. Record which evidence is synthetic, owned-lab, historical, operational or independently validated. Real telemetry still requires separate approvals and custody.

## Checkpoint

The authorized repository's Go CI branch head is `06e5f12`. [Ubuntu CI](https://github.com/khaled1234kh/kayan/actions/runs/44919189760) executed 180 tools tests and 10 TrustGate tests with zero failures and the existing live Cedar skip. The local checkout also contains unpublished Reporting, evidence, research and UI work. Keep that work intact and stage reviewed source and fixtures explicitly.

The verified local report is now saved atomically with the one-shot Archived Reporting reservation. An interrupted mocked request previously left the result and export unavailable after an application restart. Reopening the same evidence revision now recovers the local report and preserves the consumed approval. The test uses the FastAPI route with a synthetic gate and in-memory HTTP transport.

New cloud selections persist validated finish reason, input/output/reasoning tokens and measured provider latency. Malformed or out-of-budget token usage yields the existing local fallback. The full console ASGI check recovered and exported the fallback after an injected interruption, with the original Slate request digest and a single mocked attempt. Historical reports retain their original metadata.

Archived Reporting now also enforces the configured request time as a total deadline. A mocked response exceeding the deadline across individually short waits produces an exportable local fallback and consumes only one attempt.

The Reporting panel displays saved input, output and reasoning tokens, provider latency and finish reason. Rendered-HTML tests cover a measured zero, legacy partial records, unusable values and local fallback. Production build passed. Windows Computer Use ended before navigating to the fixture because it could not reliably determine Brave's current URL. Browser visual verification remains pending.

Archived Reporting now binds the console export to the SHA-256 of the exact saved JSON shown in the panel. The API returns HTTP 409 if custody changed, the report was replaced, or the viewed result is no longer available. The panel asks the operator to review the current report before exporting. Legacy API callers can still request the current report without a digest.

A reviewed synthetic Windows case exposed a false negative in Reporting. The verifier used one primary address per fact, but the report proposed the secondary logon statement as another fact and triggered an extraneous-citation rejection. Reporting now proposes primary addresses and preserves the verifier's full support in the finding. The regression admits the supported occurrence, withholds authorized activity, and fails verification if the secondary record is missing. The signed-off verifier and approved Slate request digest are intact.

The frozen Reporting projection benchmark measured nine archives. Baseline Reporting displayed 1/4 supported occurrences, while occurrence-aware Reporting displayed 4/4 with exact expected source addresses. Both runs admitted 0/6 withheld occurrences and rejected the invalid archive. The unchanged verifier agreed with all 11 authored occurrence dispositions. [Benchmark and reproduction](ARCHIVED_REPORTING_PROJECTION_BENCHMARK.md)

The new occurrence-aware selection contract passed offline tests for exact aliases, malformed and withheld choices, approval and custody changes, and one-shot reservation across independently locked app instances. The pinned Slate request and prior projection output reproduced exactly. [Selection contract and limits](ARCHIVED_REPORTING.md#occurrence-aware-selection)

The frozen Reporting selection replay matched all 14 expected outcomes. Seven replies were accepted, six used exact local fallback, and one archive made no attempt. The console and export now show occurrence and observed-action coverage so readers can see partial or weakly relevant summaries. Relevance and ranking scores use authored preferences and do not measure model accuracy. [Replay results and reproduction](ARCHIVED_REPORTING_SELECTION_REPLAY.md)

The pinned local Qwen run selected valid evidence on six frozen Reporting cases. It recovered 10/14 preferred excerpts versus 6/14 for the deterministic composer, while observed-action coverage fell from 8/8 to 2/8. A post-hoc replay adding verified action excerpts recovered 8/8 action coverage and 14/14 preferred excerpts, with 14/17 preference precision and no new inference. The approved-only case made zero requests. [Local ranking experiment, raw replies and limits](ARCHIVED_REPORTING_LOCAL_RANKING.md)

The frozen action holdout compared seven real loopback replies in eight distinct synthetic archive families. Across six primary cases, appending verified action excerpts raised observed-action coverage from 1/8 to 8/8 and preferred-excerpt recovery from 9/16 to 16/16. The full nine-occurrence case still surfaced no actions because all eight excerpt slots were occupied. The authorized-only archive made no request. [Results and scope](ARCHIVED_REPORTING_ACTION_HOLDOUT.md)

Archived Reporting now appends verified action excerpts after a valid selection, labels each deterministic addition, and preserves the request digest and finding decisions. The 3D mock preview showed the action label and correct dispositions. The downloaded JSON matched the saved bytes. [Application check](ARCHIVED_REPORTING_ACTION_HOLDOUT.md#application-verification)

The frozen full-summary comparison found that swapping references improved aggregate observed-action coverage from 9/50 to 16/50 and lost two preferred excerpts in one case. The application preserves the selected summary and discloses remaining verified actions separately, with exact occurrence-bound references in the export. The rendered mock check and byte-identical browser download passed. [Capacity results and application](ARCHIVED_REPORTING_FULL_SUMMARY.md)

Saved Reporting results now recheck their archive identity, finding decisions, citations and presentation before being served. Corrupted stored results and reserved fallback reports return HTTP 409 without rewriting their files. The saved real Slate response still passes the new check. [Reproduction and verification](ARCHIVED_REPORTING_FULL_SUMMARY.md#saved-result-verification)

Reporting now rejects archive changes across awaited write, inference and response boundaries. Passive capture also rejects late or wrong-agent contradictions in authorization history. Five stale publication cases and six capture defects reproduced before the correction. [Verification and scope](REUSABLE_REPORTING.md#publication-and-capture-consistency)

Archived Reporting can reconcile captured decisions through the Rust ledger without granting new authority or changing custody. Rust verifies and selects entries under one read lock. The client matches case, actor, role, tool, target and verdict. The real Rust-to-Python smoke observed one match and one missing reference, and the browser mock displayed both alongside missing custody. [Verification and limits](REUSABLE_REPORTING.md#trustgate-audit-reconciliation)

The opt-in signed-archive test reopened the same custody receipt and exact report through a real Ubuntu TrustGate restart, a damaged journal and restoration. Verification states moved independently of the signed custody status. [Recovery results](REUSABLE_REPORTING.md#signed-custody-and-audit-restart)

Offline Phase 1 now requires a stated relationship between an external actor and the remote access path. The frozen 16-case regression removed seven false vendor-access hypotheses and retained all eight positives. The earlier 32-case and 12-case sets stayed exact. [Planning validity and scope](PLANNING_AND_COORDINATION_2026-11-03.md#vendor-remote-access-validity--2026-11-21)

Archived Reporting now counts retained evidence per specialist. An exact replay counts once. Conflicting versions of one source are excluded and reported separately. The frozen passive attribution set moved from 7/9 to 9/9 exact, and the historical owned-lab archive kept all ten records classified as transcript-only. [Before and after results](REUSABLE_REPORTING.md#specialist-observation-attribution)

Signed Reporting now matches 7/7 frozen three-role cases, from 2/7 before the occurrence correction. Explicit, corroborated adverse review scope preserves valid siblings. Ambiguous scope keeps the broad veto. The combined run passed 293 tests, including real Rust restart coverage. [Synthetic proof and limits](REUSABLE_REPORTING.md#signed-finding-and-occurrence-attribution)

Signed Reporting now uses one snapshot for coverage and admission and checks the current source digest before adding a receipt. Two controlled source-update tests prevent mixed-revision reporting and stale receipt insertion. [Before and after checks](REUSABLE_REPORTING.md#signed-source-revision-consistency)

Signed import now rechecks the active assertions and the current authenticated custodian assignment before receipt insertion. Review publication and receipt insertion share the SQLite writer lock. Four stale imports reproduced and now leave the existing head intact. [Concurrency and scope](REUSABLE_REPORTING.md#current-review-and-enrollment-at-receipt-import)

Phase 1 now requires a stated API-to-record relationship and keeps the exact quoted interface and record together in Option A. The 16 fictional cases improved from 12 to 16 exact, retaining all eight positives. Three existing planning sets remained exact. [Evidence and limits](PLANNING_AND_COORDINATION_2026-11-03.md#api-to-record-relationships-in-phase-1)

Archived Reporting now offers opt-in local Qwen ranking of verified excerpts. One pinned-model browser smoke selected `E2.1` and two fixed controls in 5.609 s with the preview gate. The export matched the saved result and preserved both dispositions. The default report remains deterministic. [Implementation and measured scope](ARCHIVED_REPORTING_LOCAL_RANKING.md#opt-in-console-mode)

Archived Reporting now persists a deterministic fallback before local generation. The first interrupted run survives application recreation and export. An interrupted rerun preserves its prior verified report bytes. [Recovery conditions](ARCHIVED_REPORTING_LOCAL_RANKING.md#interrupted-local-requests)

Next, measure whether the report preserves enough exact proof to explain each admitted occurrence when its summary is capacity-limited. Compare the source-role and occurrence references against a frozen defensive Reporting set, and correct any disclosure gaps without changing admission.
