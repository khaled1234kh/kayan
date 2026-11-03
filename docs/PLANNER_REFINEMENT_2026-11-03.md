# Planner refinement — 3 November 2026, Africa/Cairo

This pass reopens bounded Planner functionality work after the 2 November publication. It refines prompts, validation and execution accounting; it does **not** train model weights, change the shared qwen2.5:7b/configuration, add another model, or expand execution authority. Cedar, signed ROE and taint policy source were untouched.

## Reproduced defects and corrections

| Reproduced behavior | Correction and bounded verification |
|---|---|
| A specialist immediately choosing finish or reaching the action budget had no explicit untested-tool record. A caught executor error could still be reported as a completed assessment. | Return observations plus catalogue coverage: successful/attempted/untested/denied tools, execution errors, verification issues and stop reason. A completed loop is distinct from complete catalogue coverage. Failed-specialist progress survives in outcomes; other specialists and Reporting continue through their normal governed paths. |
| Model Reporting could omit verified IDs or repeat them; only unknown IDs were rejected. | Require the exact full verified-ID set once each. One governed correction is permitted; a still-invalid summary prevents report publication. This validates IDs, not the truth of arbitrary generated prose. |
| Blank task text/unknown plan fields could pass; a malformed boundary revision had no correction opportunity. | Strip task whitespace, forbid extra plan fields, allow one correction at every plan boundary, preserve completed assignments exactly. Denied inference/network/runtime errors are not treated as schema-retry opportunities. Historical model input/context snapshots are copied before feedback mutation. |
| Real run f7013ffe… assigned http_probe to Web-App and discover_endpoints to Network. Specialists stayed inside their own callable catalogues, but task descriptions were wrong. | Validate known tool references against each specialist role. Provide short role-specific task examples. Reporting may mention observed tool names as evidence; it gains no execution path. The expanded acceptance harness checks semantic assignment-to-catalogue consistency. |
| A finished engine could run again with old findings/engagement state. | Require ready state from a fresh signed engagement before another run; reject reuse before creating tools or dispatching work. |
| A string-valued supported flag could count as successful observation; conflicting/error-bearing proof envelopes could become findings. | Require literal boolean support for candidate/verification success, reject error-bearing proofs, and record malformed support as an execution-result error. Negative boolean results remain observations, not vulnerabilities. |

Before-fix artifacts are retained in `eval/reports/planner_refinement_20261103/`: `before.log` (13 failed / 25 passed), `cross-role-before.log` (3 failed), `overview-before.log` (incomplete report wrongly labeled saved completed assessment), and `final-edges-before.log` (2 failed / 1 passed). Intermediate successful and failed full profiles remain separately named. These controlled reproductions use synthetic proposals and are not actual-model evidence.

## Final automated profile

Command from the canonical root:

```powershell
python -B -m eval.functionality_checkpoint --label planner_refinement_20261103_v3
```

Artifact: `eval/reports/checkpoints/planner_refinement_20261103_v3/results.json`.

**14/17 groups passed; overall profile status is failed.** Three Go groups could not finish because Windows Application Control blocked their generated executables. They are not skipped or counted as passes. Yesterday's 17/17 result remains dated historical evidence.

| Group | Fresh result |
|---|---|
| Python | **115 passed, 32 deprecation warnings** |
| Rust | **28 passed** |
| Adversarial authorization | **9/9 passed** |
| Frontend | TypeScript/production build and all ten scripts passed; largest JS chunk 476.70 kB, no oversized-chunk warning |
| Focused Go boundary | Group failed on host execution policy; 11 top-level tests completed before other package binaries were blocked. Do not call the whole boundary profile passed. |
| Go configuration | Generated test executable blocked |
| Go no-embedding provider | Generated test executable blocked |

Literal current Go errors and retry path are in `docs/BLOCKED.md`. No protection setting, exception, alternate execution path or bypass was used. No claim that every upstream Go test was run.

## Actual model and actual Gate

The owned-loopback lab, actual Ollama Qwen, signed ROE, native Rust/Cedar and HTTP/WebSocket paths were exercised. No model/tool/Gate mock or simulated fallback was used for these engagements:

| Run | Engagement | Findings / allowed / denied | Result |
|---|---|---|---|
| v1 | f7013ffe-9f32-4324-968b-34d04792fd28 | **2 / 29 / 1** | Preserved wrong-role task descriptions. Its older harness passed transport/order checks before semantic validation was added; it does not prove correct assignment content. |
| v2 | 28490c2e-4770-4971-89f6-8a7d7bb60786 | **2 / 29 / 1** | Expanded assignment/coverage/report-ID checks passed; rendered planning and export checks used this session. |
| final v3 | **035e7ee6-0a7b-4bfc-84a1-c3e7b51b81ae** | **2 / 29 / 1** | Final source after edge corrections, fresh backend process, expanded checks passed. **142** observed specialist-active frames kept Planner working. Planner completed last and dispatched no specialist tools. |

Reproduction (starts a new actual owned-lab engagement, not an offline video review):

```powershell
.\Start-Kayan.ps1 -Component All
python -B -m eval.planner_live_acceptance --label YOUR_UNIQUE_LIVE_LABEL
```

All three include the deliberate target-origin tainted-message DENY. Counts exclude ROE load and include harness operator interaction. Final audit verification was valid at **934 entries**, following a valid 903-entry pre-run check. Existing historical recordings/reports were not replaced. Final session remains loaded; `-RestoreDemo` deliberately refuses to overwrite a different session.

Each actual run exercised three Web-App actions under the unchanged three-action budget, leaving **directory_traversal untested**. Reports now explicitly say `execution_complete: true`, `complete: false` for catalogue coverage. Increasing the budget to make a green label would conceal the issue; it was not done. This is registered-catalogue accounting, not comprehensive coverage or an absence-of-risk claim. Findings remain independently reproduced lab evidence; general accuracy and browser-executed XSS are not established.

## Small real-model contract evaluation

```powershell
python -B -m eval.planner_model_scenarios --label YOUR_UNIQUE_SCENARIO_LABEL
```

Version-1 dataset: `eval/planner_model_scenarios.py`; results/transcript: `eval/reports/planner_model_scenarios_20261103_v1/`. Engagement **400d8832-3a90-42d9-8d77-1df08d58e059** used **seven real authorized inference calls**, verified in Gate audit, with **zero specialist dispatches**. The fixtures are explicitly synthetic task/finding records; they were not saved as real findings or an assessment report and did not replace the console session.

**7/7 first-attempt structured-contract passes; 7/7 accepted after validation, no corrections required**: normal role assignments, cross-role pressure, reference-slug pressure, exact completed-prefix preservation, failed-specialist hand-off ordering, complete fixture-ID reporting, and an empty-ID report with a synthetic failure. Role/schema/ID checks do not prove every narrative sentence is correct. The failure-report prose, for example, adds a broad scanning-frame description absent from its minimal synthetic records. Preserve that limitation; do not report 100% general Planner accuracy or validated mitigation quality. No paired pre/post benchmark or causal prompt-improvement percentage was measured.

## Rendered UI and startup

Actual built-in-browser inspection, separate from SSR/builds:

| Observation | Evidence / limit |
|---|---|
| Planner during a real run | Observed working current task and Tier A/shared Qwen while specialists executed; final report/gap warning was inspected separately. No new close-up monitor pixel-timing measurement. |
| Planner coverage panel | `planner-coverage-after.jpg`, `planner-final.jpg`: Web-App action-budget stop and untested directory_traversal, correct no-safety wording; collapsible coverage details preserve transcript access. |
| Overview | Before-fix assertion reproduced wrong “Saved completed assessment” label. Final view says “Assessment finished · incomplete coverage”; loop stages still show terminal execution state. |
| Phase 1 → Option A | Used explicitly hypothetical sample, generated three local-retrieval hypotheses, then three offline recommendations; actual UI labels no testing. `option-a-after.jpg`. No policy/model/target call was added to this path. |
| Saved Option B → review/export | Correct v2 report, two verified findings, coverage gaps, two recommendations / six illustrative points; actual browser download parsed and retained as `browser-export.json`, including source ID/coverage/selection. `option-b-coverage-after.jpg`. |
| Narrow review | Temporary 640×800 viewport, no page horizontal overflow (DOM page width 625); readable scrollable review and reachable export. `review-narrow.jpg`. The immediately-after-resize capture was visibly inconsistent and is retained as `review-narrow-initial-capture.jpg`, excluded from acceptance; subsequent actual screenshot was inspected. Default 1159×764 viewport restored. |
| Browser errors | `rendered-check.json`: zero captured error-level logs in that inspected tab. This is bounded to this session, not a universal guarantee. |
| Startup | `startup.log` and `startup-final.log`: all four components started and later reused expected services via Start-Kayan; installed Ollama started separately. Review page returned HTTP 200. No different current engagement was overwritten to demonstrate RestoreDemo. |

These are bounded checks of changed functionality. They do not re-certify the original twelve-step video checklist, every camera angle/device, or new FPS. Screenshots are actual unretouched captures. The prior data/error-page tab rejected binding to its data URL; opening the authorized ordinary HTTP URL succeeded, with no origin-policy workaround.

## Remaining

The only new unchecked TODO is ordinary re-execution of the three Go groups after the host permits their test binaries. Python demo/live Planner works despite that separate test-host limitation. Production hardening, full Go runtime replacement and framework efficacy limits remain unchanged.

**No grounding improvement was demonstrated. Preserve this failure.** The negative comparison and historical artifacts were not softened or replaced. This pass establishes specific fixes and their bounded checks, not model training or a general detection improvement.
