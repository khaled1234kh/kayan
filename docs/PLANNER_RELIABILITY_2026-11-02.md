# Planner reliability and demo readiness — 2026-11-02

**Later final runtime status:** normal Gate startup and actual shared-Qwen coordinator validation passed, including final engagement 51bba207... (2 findings / 29 allowed / 1 denied). The audit ordering fix preserves old bytes and verifies all 779 entries. Final profile: 17/17 checks, including 84 Python and 28 Rust tests. See DEMO_READY_2026-11-02.md. Earlier blocked/queued statements below are historical.

This user-authorized functional pass reopens the old freeze within a bounded coordinator/startup/UI scope. The subsequent user request makes the larger redesign an explicit blocker; current minor changes do not satisfy that design acceptance.

## Reproduced defects and fixes

Controlled before-fix coordinator checks: 4 failed / 2 passed. Planner prematurely completed before specialists; a reversed Recon dependency was accepted; specialist failure aborted Reporting; Reporting failure left Planner completed. Additional red tests reproduced missing Markdown partial-coverage warnings, invalid-plan recovery, boundary guidance consumption and Planner session findings. Launcher mock checks reproduced acceptance of a foreign occupied port. Raw before/after logs: eval/reports/planner_20261102/.

Planner now validates exact Recon/Web-App/Network/Reporting order with one bounded corrective model attempt, never a fabricated plan. It stays working through assignment, outcome and Reporting hand-off. Specialist exceptions are recorded as blocked/failed outcomes; remaining specialists still require their normal gate paths. Reporting receives outcomes and independently reproduced findings, and labels partial coverage explicitly in JSON, Markdown and saved Option B views. A Reporting/dispatch failure fails the coordinator. Queued guidance is consumed at safe specialist boundaries; revisions cannot change the roster/order or completed assignments. No extra executor, model, role contract or Cedar change.

The Planner session endpoint and sidebar expose coordinated findings while preserving original specialist attribution. Activity, current task and Tier A are visible. Existing live monitor uses the same actor state; its geometry/texture path was not changed.

Launcher verifies HTTP identity/readiness before reusing ports, waits for startup health and refuses an unhealthy/foreign listener. Review mode and -RestoreDemo were exercised twice, then the agent-owned backend was restarted to load the updated API and the original saved 7da73508... session was restored again. Final direct HTTP check: completed, 101 entries, Planner session coordinated_assessment with two findings; viewer HTTP 200. No fresh assessment started.

## Exact results

- Python tests: **63 passed, 27 deprecation warnings**, including 14 coordinator/API/report tests and 3 controlled PowerShell launcher tests. No real model/gate service is exercised by those unit tests.
- **12 transport/reducer checks passed**; session-panel and TA presentation checks passed with new Planner ownership/activity and partial-report assertions.
- TypeScript + production build passed. Existing >500 kB chunk warning remains; no bundle optimization claimed.
- Fresh Gate launcher retry failed building generic-array v0.14.7: `An Application Control policy has blocked this file. (os error 4551)`. Full log retained. No bypass/settings change. New live end-to-end gate/model acceptance remains OPEN.

## Actual rendered observations and bounds

Original built-in browser used legitimately. Saved 7da73508... Planner panel showed Tier A, shared Qwen, transcript and two specialist-owned findings. Actual Phase 1 input returned three explicitly hypothetical matches; Option A returned three recommendations/four illustrative points; Option B loaded the original two findings/two recommendations/six points. These are separate evidence paths, not a quality comparison. At 640×900, document scroll width was 640 and dialog width about 601.6; intake overflow visible and header sticky. Actual lower Option B cards/Export/Close were inspected. Nested intake scrolling was observed before correction and replaced with one dialog scroll region. Screenshots in the evidence folder. No contrast certification or full multi-viewport redesign acceptance yet.

An explicitly labeled controlled coordinator fixture (no model, gate or target calls) was temporarily published through the actual backend/WebSocket to inspect Planner working/current-task/Tier A and failed-specialist transcript state. It was then replaced by the exact original saved completed session, 101 entries. Fixture payload and before snapshot are preserved separately; never cite it as a real engagement. In-scene monitor was viewed at a closer angle, but exact full texture text/tier pixel legibility was not conclusively established at that perspective; retain this as a redesign verification item, not a rendered pass. Screenshots planner-working-fixture.png / planner-monitor-fixture.png reflect this limitation.

The new doctor-facing design brief/reference are copied under docs/design/. The full three-zone/stepper/token redesign is queued, not implemented. Show layout and planning screenshots before detail polish. User expectation is professional presentation, not more arbitrary scene decoration.

No grounding improvement was demonstrated. Preserve this failure.
