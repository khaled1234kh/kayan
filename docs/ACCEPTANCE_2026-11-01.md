# Browser acceptance — observed 2026-11-01

**Current meeting readiness:** the [twelve-step closure review](CLOSURE_EVIDENCE_REVIEW_2026-11-01.md) reconciles the separate 2/25/0 acceptance run and the final video using original `7da73508…` (2/29/1). The earlier timing gap is preserved and now has a bounded rendered task-start recheck within 916.031 ms. [TA_MEETING_READINESS_2026-11-01.md](TA_MEETING_READINESS_2026-11-01.md) records fresh regression, actual UI checks and the saved-report rehearsal; [TA_PROPOSAL_REPORT.md](TA_PROPOSAL_REPORT.md) is the requested six-section submission prose. Existing archives remain dated snapshots/on review hold and were not opened or updated in this pass. Blender was closed by user instruction, not verified as a download. FBX/bundle backlog stays deferred.

Both six-step visual procedures passed in the original built-in ChatGPT browser (`iab`) after legitimate origin access became available. This is direct rendered inspection, not a test-suite or secondhand acceptance claim. Default screenshots are 1244 × 1244; the narrow checks use 640 × 900. The temporary viewport override was reset. Evidence directory: `eval/reports/acceptance/2026-11-01_browser_v2/`.

## Original 3D procedure

| Step | Actual observation / evidence |
|---|---|
| 1. Office and workers | Five named workstations are visible in `01-office-overview.jpg` and the reset/narrow views. Workers, desks, keyboards and single monitors remain aligned. Completed-worker hands remain in their resting pose across the inspected close-ups; active fixture views show changing typing poses. This is sampled visual acceptance, not an animation benchmark. |
| 2. Web-App front/rear and selection | `14-monitor-front-close.jpg`, `15-monitor-support-fixed.jpg`, `17-webapp-rear-casing.jpg` show the worker-facing display and solid rear casing/vents without mirrored text. `33-monitor-click-selection.jpg` shows a physical Web-App monitor click switching the sidebar from Network to Web-App. The label-selection defect found during this pass was fixed and retested. |
| 3. Actual ALLOW fixture | Engagement `378b47e3-dbe2-4dd7-83ca-ee1987d34e98`: `18`–`22` screenshots show working/sql_injection_test/Tier A, an expanded actual tool entry, then a live result append and cleared current task without reload. The UI explicitly says deterministic baseline/no LLM inference. Result says vulnerable=false and preserves the lab error. Live delivery is observed; an exact two-second latency bound was not benchmarked. |
| 4. Actual DENY fixture | Engagement `b4f8296e-3491-4c58-963c-2333d22b6e93`: `23-deny-paused.jpg` shows blocked state, red denial, Tier A and audit reference `7b3a03bf-67b6-4504-9108-017724ce9c1c`. That reference matches the saved audit. Both the paused and complete saved transcripts lack SQLi tool_started/tool_result. The screenshot alone is not the absence proof. |
| 5. Actual model/session interaction | Full actual-model engagements completed; exact results are below. `28-instruction-queued-live.jpg` records the queue receipt in `9982a60b…`; its saved state records delivered_at_task_boundary. `27-status-reply.jpg` and the first completed state record a governed status reply in `2bdf9d1d…`. `30-visible-stream-02.jpg` and `31-visible-stream-completed.jpg`, with the two output JSON records, establish the same actual Planner entry `d04002222022482794fae0d32484c478` in `546daa0c…` growing from partial output to completed output. A status-only call or deterministic fixture is not substituted for this actual assessment. |
| 6. Reset and narrow layout | `32-office-narrow.jpg` shows five labels, Reset view and a separate scrollable sidebar at 640 × 900. Reset restores the overview after orbit/pan/zoom. Intake, navigation and legend stay above projected labels after the observed overlap corrections. |

## Planning-dialog procedure

| Step | Actual observation / evidence |
|---|---|
| 1. Context intake | `02-assessment-context.jpg` preserves the original overlap; `11-assessment-context-after-overlap-fix.jpg` is the retest. Six optional fields and the zero-policy-weight warning are present. Cancel returns without starting an assessment. |
| 2. Phase 1 | Blank context returned insufficient description/no reference matches (`03`). The documented six-field synthetic fixture returned three explicitly hypothetical risks with relevance/uncertainty copy (`04`); the existing live scene retained its completed session. |
| 3. Option A | The unchanged fixture produced three recommendations, five illustrative points, hypothetical evidence and no verified-finding claim. Expanded local references wrap and scroll (`05`). Escape closes the dialog. |
| 4. Option B | The saved `7da73508…` assessment produced two recommendations with verified-finding IDs and no new-testing claim (`06`). While the actual ALLOW fixture was active, the dialog returned “A completed actual-model assessment is required for Option B” (`20`). |
| 5. Grouping/selection/export | Zero Trust explicitly had no matches; Defense in Depth and All showed the two saved-run recommendations. Filtering kept six points. Unticking one three-point recommendation changed the total to three (`07`–`08`). The downloaded `exported-selection.json` retains both original recommendations, one selected ID, total=3 and the disclaimer; these assertions were rerun. Rechecking restored six points. |
| 6. Disclaimer/keyboard/narrow layout | The illustrative-only disclaimer is visible in desktop/narrow views. `09`–`10` show a scrollable dialog at 640 × 900, visible controls and keyboard focus; Tab moves focus and Escape closes it. The viewport override was reset. |

## Corrections and passing checks

The inspected defects were label clicks being cleared by canvas empty-click handling, labels covering intake/navigation controls, long decision values overflowing the sidebar, the monitor support crossing the lower display, and expanded streaming output being followed by a large input payload. The fixes isolate label clicks, keep overlays above labels, wrap constrained grid values, rear-mount the monitor neck, and place output last in the expanded raw record without dropping fields. Five 3D source paths are committed as `e4a1519` on `kayan-trustgate-console`.

Final office geometry, session-panel, visual-feedback and TA presentation checks plus TypeScript/production build all exited 0; logs and `final-checks.json` are saved. The bundle warning remains. No Rust/Go/grounding comparison or FPS benchmark was rerun for these UI fixes. Geometry checks ≠ rendered acceptance; the preceding tables are the separate actual visual evidence.

Vite initially retained the old LiveAgentPanel module despite the source edit. The pre-restart `29` screenshots establish DOM output growth but do not establish visible output at the bottom of the panel. That failure is preserved. Vite was restarted, its served helper checked, the page reloaded, and the `30`/`31` screenshots then verified output visibility. The same entry's observed output lengths were 85, 113, 151, 169, 215, 245, 277, 327 and 349 characters; the final saved entry has streaming=false.

## Fresh engagement breakdowns

| Run | Findings | Allowed | Denied | Limit |
|---|---:|---:|---:|---|
| Deterministic ALLOW fixture, 378b47e3… | 9 reported | 9 | 0 | Baseline detectors have known overclaims; not nine verified exploits. |
| Deterministic DENY fixture, b4f8296e… | 8 reported | 8 | 1 | Same baseline caveat; denied SQLi lacked execution entries. |
| Actual model acceptance, 2bdf9d1d… | 2 | 28 | 0 | Includes three additional authorizations for the post-run status exchange; not identical to the earlier adversarial harness. |
| Actual model acceptance, 9982a60b… | 2 | 26 | 0 | Includes the queued instruction authorization and actual boundary delivery. |
| Actual model acceptance, cc795340… | 2 | 25 | 0 | Pre-reload output-visibility check. |
| Actual model acceptance, 546daa0c… | 2 | 25 | 0 | Post-reload visible partial/completed output check. |

Actual-model totals come from saved complete transcripts and match their actual audit decisions, excluding ROE-load records. Findings come from each saved report. These runs add acceptance evidence; they do not replace the earlier off/on or adversarial results. Four runs were retained because successive checks missed the queue window or exposed the stale-module/output-visibility problem. No failed or incomplete capture was discarded to imply first-try success.

**No grounding improvement was demonstrated. Preserve this failure.** No mitigation effectiveness, general classification accuracy or new grounding benefit is claimed.

## Recording status

The first browser video attempt stopped after two frames with `Error: Browser Use could not read requirements.` It is incomplete (`model-capture-attempt.json`), not a full model-run recording. A bounded capture inside one active browser operation subsequently recorded 40 frames with no capture/action error (`capture-probe/frames.json`).

Both visual procedures and the separate continuous final three-path recording are accepted. The delivered recording is `C:\Users\khale\Downloads\KAYAN-final-three-path-2026-11-01_v2.mp4`: 35.44 seconds, 1244 × 700 encoded content viewport from a 1280 × 720 source, 589 captured frames, no audio/browser chrome, and no capture/action error. It uses original frame timestamp intervals, with no cuts. SHA-256: `884600dc39805af0b2ca3ed00f58f49107378353e9b24adbbf488839121d56f0`.

Eight encoded-video frames were inspected: synthetic fields at 3.466/5.999s, Phase 1 at 9.272s, Option A at 14.078s, Option B at 23.898s, empty filter at 27.992s, exclusion at 31.705s and restored selection at 34.085s. Exact observations are in `v2-review-frames.json`; not every frame was manually inspected. The audit SHA-256 and original completed `7da73508…` engagement/101 entries were unchanged through both recordings. No new live assessment was run for them.

The first 31.08-second version is retained as `KAYAN-final-three-path-2026-11-01_v1.mp4`, with its metadata in `final-recording-v1.json`. Its Option A heading scrolled past too quickly, so it was superseded for presentation clarity. Earlier incomplete capture/error and all acceptance retries remain preserved. Capture frame rate is not an FPS benchmark.
