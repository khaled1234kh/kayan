# Cohesive workspace and office acceptance — 2026-11-03

This record closes the current bounded UI/office queue, not general aesthetic perfection, universal device support or production security. Evidence comes from actual ChatGPT in-app-browser WebGL renders, DOM observations, downloaded exports, normal process restarts, real local-model runs and the separate suites below. The older supplied office brief is preserved in design/OFFICE_OVERHAUL_2026-11-03.md; its final sentence is truncated. Nothing missing from that sentence was assumed.

## Verified implementation and reproduced defects

The shell now uses a 280px operations rail and 344px session panel (260/310 at intermediate widths), an expandable central office, compact drawers, a five-agent roster and a genuine office-focused Presentation view. New Assessment is a native modal with explicit fixed scope, descriptive-only context, validation and persistent actions. The planning profile keeps four journey stages distinct from three unnumbered profile sections; sample/draft notices are consolidated and saved Option B is integrated as an alternative evidence path. Shared model/configuration, Cedar/ROE/taint, scope and action budgets are unchanged.

| Observed discrepancy | Correction and recheck |
|---|---|
| The old skyline/backing exceeded the room footprint; deep side walls obscured desks. | Contained rear opening, continuous slab, matching wall depth, camera-near upper-wall cutaways and controlled glass. Front/isometric/side/elevated renders inspected. |
| Selected Recon/Network camera went behind the opaque rear backing. | Selected camera positions bounded inside the shell. Original black renders remain as employee-*-before-bounds.jpg; all five employee-*-bounded.jpg were inspected. |
| Unfitted manual high orbit cropped architecture. | Added a fitted Elevated preset. office-elevated-orbit.jpg retains the rejected free-orbit view; office-elevated-fitted.jpg and camera-elevated-acceptance.jpg show the supported preset. Arbitrary free orbit can still intentionally crop/occlude; Reset recovers. |
| Projected agent label intercepted profiler Export JSON (hit target was Web-App Agent). | Profiler z-index raised above labels; actual hit-test and downloaded after JSON passed. Original obstruction screenshot and both telemetry files retained. |
| Resizing assessment into tablet layout hid its rail and therefore its modal. | Portal outside the rail; modal stayed open across all six breakpoints. assessment-resize-before.json preserves failure. |
| Expanded assessment footer extended beyond dialog bottom. | Bounded flex layout and internal scrolling. assessment-footer-before.json versus responsive-assessment.json: all six final footerInside values true. |
| Scene labels/toolbar appeared on top of compact Agent Session. | Compact drawers raised above both; session-findings-narrow.jpg preserves discrepancy, session-findings-narrow-fixed.jpg and heading hit-test show correction. |
| Clearing selection left a disabled Selected workstation preset selected. | Returns preset to Overview; actual browser value recorded in deselected-camera-reset.json. |
| Reporting showed zero findings while aggregating specialist findings. | Reporting/Planner views aggregate assessment findings but retain original specialist ownership/IDs; actual two-finding views inspected and regression checked. |
| Latest raw tool output expanded the activity header excessively. | Four-line/110px activity summary, with full expandable transcript preserved. live-v2-webapp-working.jpg is before; browser computed clamp/max-height and normal final rendering checked. The transient long-output state was not recaptured after the fix; do not claim that exact after pixel pair exists. |
| Backend restart lost the current visible session; browser eventually exhausted retries. | Atomic current-session pointer and records-only restoration; persistent capped-backoff viewer reconnect. Completed session restored identically and automatically after actual outage; no manual reload/Reconnect, no new inference or authorization. Interrupted runs fail visibly instead of resuming execution. |
| Real Planner route timed out despite backend recording delivery. | General snapshot client had a 2s timeout, while message authorization may wait 8s. Only signed message routing now allows 12s response/2s connection, with no resend and an explicit ambiguous-delivery error. Real delayed-loopback tests failed against original _route and passed after correction; subsequent real runs passed. |
| Production entry exceeded unchanged 100kB budget (104,250 bytes approximately). | On-demand PlanningPanel chunk. Final entry 82,115 bytes; PlanningPanel chunk 23,835 bytes; every chunk under 500,000 bytes. Production browser planning loaded successfully. Exact byte counts in final-bundle.log. |

## Rendered acceptance matrix

All paths below are relative to ../eval/reports/ui_cohesion_20261103_v1/. Pass means the listed observations, not an unsupported broader claim.

| UI item | Result and actual evidence |
|---|---|
| 1 Sidebar | Pass: compact hierarchy, real stage states, collapse and drawer. responsive-office-*.jpg. At 720px height the rail can scroll to later roles; collapsing exposes all five roster buttons. |
| 2 Assessment | Pass: six-size expanded modal, operator focus, blank/authorization/overlimit blocking, exact retained long Unicode context, cancel/reopen resets authorization, Escape. assessment-browser-checks.json, responsive-assessment.json, setup-keyboard.json. Native Chrome briefly focuses BODY at its tab-cycle boundary, then returns to Close setup; native :modal remains active and background controls are inert. |
| 3 Screen balance | Pass: no page overflow at six dimensions, central office retained at compact widths, independent dismissible panels and five-agent access. responsive-office.json and screenshots. |
| 4 Exterior | Pass: restrained layered static architectural illustration, contained opening, no yellow-dot skyline. camera-*-acceptance.jpg and office-side-orbit.jpg. Illustration, not a photoreal city. |
| 5 Camera | Pass: fitted Overview/Isometric/Front/Elevated, all five labels; selected focus inside shell and Reset. camera-acceptance.json, bounded employee captures. Free orbit limits disclosed above. |
| 6 Office cohesion | Pass within sampled views: five seated characters, monitor/keyboard/chair alignment, retained role desk materials/props, quieter matte floor/lighting/glass and continuous construction. All five bounded employee images, camera contact sheet, monitor-rear-final.jpg. No new character asset or animation capability claimed. |
| 7 Agent Session | Pass: useful empty state, model/tier/current task, four tabs, chronological raw expansion, owner-preserving findings, coverage and decisions. session-*.jpg, network-body-decision.jpg, live captures. |
| 8 Typography | Pass: shared tokens, coherent headings/actions, readable sampled desktop/narrow/presentation views; ten token text/background contrast checks >=4.5:1. Small metadata remains smaller than body. |
| 9 Navigation/footer | Pass: active workspace navigation, actual console/Gate wording, separate Recorded demo link and Presentation control, state/white-selection legend, Reset. operations-final.jpg, presentation-final.jpg. |
| 10 Agent interactions | Pass: all five labels in intended presets, selected label/roster/rings synchronized, physical Network body/monitor selection through glass, explicit Overview recovery. network-monitor-picking.jpg, camera matrix, deselected-camera-reset.json. Extreme arbitrary angles may hide labels; roster remains the alternative. |
| 11 Planning journey | Pass: sample preview/replace/undo, six exact fields through A export, relevance/uncertainty, grouping leaves inclusion unchanged, 2 selected/3 illustrative points export, saved B retains original two findings. planning-*.jpg, browser-plan-a/b.json, planning-export-verification.json. Production empty/insufficient and clinic scenarios also inspected. |
| 12 Audit | Pass: read-only role/decision/search filters, one real DENY, honest combined-filter empty result, collapsible raw data, internal scroll and full 115-record export despite filtering. audit-*.jpg, audit-export-verification.json. Viewer does not itself verify the hash chain. |
| 13 Transitions | Pass: real camera focus status/settlement, user orbit cancels transition; reduced-motion emulation produced zero CSS transition duration and settled selection. reduced-motion.json. Emulation reset. |
| 14 Feedback | Pass: actual model planning/tool/reporting/completed/failed states, unavailable-backend error with retained inputs and successful retry, scope validation and no-selection/filtered-empty/insufficient-context views. live/error/setup/audit/production captures. Prior absent-model/readiness checks remain in earlier evidence; no unavailable model was simulated this pass. |
| 15 Responsive | Pass for requested 1920×1080,1600×900,1440×900,1280×720,1024×768,640×800 office/profile/setup renders; no page/dialog horizontal overflow and footer reachable. Compact session/audit also inspected at 640. Temporary overrides reset. Not every possible screen/state combination was sampled at every size. |
| 16 Presentation | Pass: both panels initially hide, office fills space, five-agent roster stays available, inspection opens contextual panel, Exit/Reset recover. presentation-final.jpg. |
| 17 Identity | Pass within inspected live/planning/setup/audit: restrained dark tokens, coherent type/spacing/actions, quiet accents and purposeful state rings. Contact sheets and final screenshots. Subjective user/doctor approval is not asserted. |
| 18 Performance/loading | Pass for bounded measurement and budgets, not a claimed speedup. Before/after telemetry below; no added visual dependency. Real production split/empty path loaded; no error-level logs returned by the preview. |
| 19 Full audit | Pass for listed major screens/interactions and corrected reproduced defects. This matrix explicitly states unobserved limits; tests alone did not close visual items. |

Older office O1–O15 are covered as follows: O1→UI4/6; O2→4/18; O3→5/6; O4→5/16; O5→5/6/10; O6→6/17; O7→6/8; O8/O9/O10→6; O11→6/14; O12→9/10/17 (decorative cross-floor lines removed, architectural perimeter lights subdued; thin white selection differs from colored actual-state ring); O13→10; O14→7/10; O15→7/9/14/16. Only real runtime states were used for the live inspection. Waiting for model/tool input is explained by current task/activity; this pass does not add an approval workflow or invent a new backend status.

## Functional and live results

Final full checkpoint ui_cohesion_final_20261103_v3: **17/17 groups passed**; **156 Python tests / 48 retained warnings**, **28 Rust**, **15 focused Go boundary +15 Go config + explicit no-embedding case**, **9/9 adversarial**, TypeScript/build and ten frontend scripts, including **14 transport/reducer checks**. Following the final CSS/activity-tooltip change, the session check and production build/budget were rerun successfully; the actual production browser was inspected separately. Original v1 checkpoint remains failed 16/17 because of bundle size; v2 passed 17/17 before the final route regression additions.

| Real run | Findings / allowed / denied | Outcome |
|---|---|---|
| 8f98ca43-8b05-42d7-8de9-71e3e7137f6c | 0 / 6 / 1 | Failed with literal `timed out`; routed instruction was present. Preserve this failure. |
| 62a7c952-0422-48ea-9ed5-49e211d55a5f | 2 / 30 / 1 | After route fix: accepted reviews, all specialists/Reporting completed, Planner last, no Planner tool dispatch. |
| b813d8a6-cc6f-4456-a9bc-0929249fd2a4 | 2 / 30 / 1 | Final UI recheck: same bounded assertions passed, incremental model output and governed operator/safe-boundary paths. |

Counts are Gate decisions for each ID excluding ROE load, including deliberately tainted-input DENY. final-runtime-counts.json independently cross-checks all three. Whole audit verified **1,247 entries**. Successful runs have three accepted reviews and nine execution-ledger records, with unchanged Web-App budget leaving directory traversal untested. Complete execution is not complete coverage. These runs use the shared qwen2.5:7b; they are not training, general accuracy or grounding-efficacy measurements.

Actual screenshots separately observed Planner working/assignment, Web-App working and Reporting working (live-v3-reporting-observed.jpg), then completed findings/report. Runtime records establish ordering and incremental output; screenshots establish the sampled rendered states. This was not a continuous recorded video or a universal task-to-pixel latency measurement. Original videos/PDFs and saved 7da73508… evidence remain unchanged.

## Performance comparison

One 10-second idle and one orbit sample per build, same IAB 1440×900, five completed agents, no active model/heavy suite during capture. Baseline clean checkout ce459f8; revised layout/camera differ. The other page was temporarily suspended to avoid rendering two scenes simultaneously, then resumed before download/closure. Twelve horizontal drags were attempted for each orbit interval; captured counters were 11 downs/98 moves/10 clicks before and 11/95/10 after. Idle had zero canvas input in both. Both samples were valid. Raw JSON files are performance-before.json / performance-after.json; final profiler stacking fix was verified by actual export.

| Mode | Before cadence fps / p95 gap | After cadence fps / p95 gap |
|---|---|---|
| Idle |64.97 /17.0ms|65.33 /17.0ms|
| Orbit |55.72 /21.4ms|54.69 /21.4ms|

No speedup or statistical performance/regression conclusion is established by this single pair. Renderer textures remained 50; geometries 439 before versus 444 idle / 445 orbit after. Canvas cadence is not GPU timing or input latency. The scene/picking checks and bundle measurements are separate facts. Temporary baseline/production servers on5174 were stopped and their tabs closed; normal5173 remains.

## Startup, restoration and remaining limits

Start-Kayan All reused expected Gate 8000 / lab 8888 / backend 8001 / office 5173; Ollama 11434 remains separate. Review/-RestoreDemo correctly refused a different current session with `Refusing to replace an active or different session.` Temporarily loading the original completed7da73508… allowed the matching Review/-RestoreDemo path to pass; latest real session was then restored and Gate audit stayed unchanged. No assessment was started by the launcher/replay check. Evidence: start-all-final.log, restore-demo-guard.log, launcher-review-verification.json.

Actual backend restart restored completed a16f71f5… exactly, no manual snapshot upload. A >21s outage remained Reconnecting rather than exhausting retries, then reconnected automatically without click/reload. Snapshot pointer corruption fails visibly; interrupted execution is marked failed/blocked, queued instructions not resumed. Records-only restoration does not restart inference/tools/ROE loading. Tests cover these cases; an active process was not intentionally killed mid-assessment.

**No grounding improvement was demonstrated. Preserve this failure.** No model weights/configuration, Cedar/ROE/taint, tool authority, target scope or budgets changed. Docker runtime swap, old PDFs/videos, comprehensive upstream Go behavior, production identity/isolation, immutable audit storage, development-key hardening and completion-triggered ROE revocation were not recertified or implemented here. These disclosed architectural limits are not relabeled as completed capabilities. The new image is an illustration and existing characters remain stylized. Arbitrary free-camera occlusion/clipping and unobserved device/state combinations remain possible. User aesthetic acceptance is not claimed.

Reproduce from project root:

```powershell
.\Start-Kayan.ps1 -Component All
python -B -m eval.functionality_checkpoint --label ui_cohesion_UNIQUE
python -B -m eval.planner_live_acceptance --label ui_live_UNIQUE
```

The last command starts a new signed, owned-loopback assessment and replaces the selected current session. Use a unique label; never overwrite previous evidence. For presentation only, use Review with no new assessment; -RestoreDemo is specific to the original session and refuses a different selected run.


## Publication verification

Implementation/evidence commit **695acab8f1424babd419a68863f726a6578e8443** was pushed to the authorized khaled1234kh/kayan main. Remote HEAD and a fresh downloaded source checkout matched; all 38 changed-source SHA-256 values matched. All six README JPEGs returned HTTP 200 from their commit-specific raw GitHub URLs, matched local hashes and decoded successfully.

The source-only clone initially retained LFS pointers: 151 Python passed / 5 asset checks failed/48 warnings. That failure is preserved in downloaded-python-lfs-pointers.log. Hydrating all six original assets from the existing hash-verified local LFS cache resolved those expected missing-asset failures; LFS fsck passed and downloaded-source Python rerun passed **156 tests /48 warnings**. Existing host dependencies were used. This is not a fresh isolated dependency install or fresh download of remote LFS media. publication-verification.json contains source/image hashes and the exact scope. Subsequent closure changes are documentation/evidence only.
