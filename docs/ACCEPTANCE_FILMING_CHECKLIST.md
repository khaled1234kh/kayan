# Acceptance filming checklist — actions only

Current status: both procedures and the final three-path recording were subsequently accepted through legitimate direct browser inspection; see ACCEPTANCE_2026-11-01.md. This historical action-only guide is retained for reproduction, not an open delivery task. The earlier unsupported “both passed, no issues found” message was never used as evidence. The guide below describes the safer human-recording route used while browser access was blocked; no denial bypass is authorized.

Use `http://127.0.0.1:5173/`. Record the whole browser window, including the address bar. No narration or technical judgment is required. Leave each result visible for about five seconds and scroll slowly enough to read it. Keep discrepancies in the recording rather than restarting to hide them.

Start with the planning segment, while the existing completed actual-model session is still loaded. The deterministic fixtures later replace the console's current engagement. Do not click **Start assessment** for the planning segment or final demo.

## Planning segment

1. **Start recording and refresh.** Open the URL and hard-refresh. Click **New assessment**, expand **Optional descriptive context**, and scroll through its six fields and explanatory copy. Click **Cancel** without authorizing/starting an assessment.

2. **Show the empty-input outcome.** Click **Risk planning / mitigation**. With its context blank, click **1. Generate hypothetical Risk Plan**. Leave the resulting message visible.

3. **Enter the synthetic fixture.** Expand **Optional descriptive context** and enter these exact values. They are also saved in `eval/reports/ta_alignment/api_2026-11-01_v1/context.json`.

   | Field | Value |
   |---|---|
   | Company size | 25 employees (synthetic evaluation fixture) |
   | Departments | Operations and customer support |
   | Infrastructure summary | Public web application and API; review SQL injection and broken access control |
   | Network architecture | Office network and hosted application |
   | Data storage | Relational database with customer records |
   | Customer touchpoints | Customer web portal and login |

   Click **1. Generate hypothetical Risk Plan**. Scroll through the entire result, including the uncertainty, ranking explanation and references.

4. **Show Option A.** Without changing the context, click **2. Option A · direct mitigation, no testing**. Scroll through its evidence label, recommendations and illustrative disclaimer. Expand at least one **Grounding references** section. Do not change the context between Phase 1 and Option A.

5. **Show Option B and selection behavior.** Click **Option B · load completed assessment mitigation**. Scroll through its evidence label and recommendations. Change **Recommendation grouping** to **Zero Trust**, then **Defense in Depth**, then **All**. Keep the point total visible while unticking one **Include** checkbox; hold for five seconds, then tick it again. Click **Export report with illustrative selection**. Retain the downloaded JSON for inspection.

6. **Show dialog usability.** Scroll to the disclaimer. Press Escape to close the dialog, then reopen **Risk planning / mitigation**. Make the browser window narrower by dragging its edge; scroll the dialog and show its buttons. Close the dialog and restore the window size. Leave the recording running if continuing directly; otherwise save this first clip under a new filename.

## 3D segment — coordinate the paused fixtures with the agent

7. **Show the office and reset.** With the dialog closed, click **Reset view** and hold the overview. Drag on empty floor to orbit slowly around the room so all five named workstations and workers are visible. Move closer to Web-App's workstation using the scroll wheel. Orbit to show the worker-facing display, then its rear casing, then return to the worker-facing side. Click the Web-App name or monitor and hold the sidebar and physical screen in view.

8. **Pause for the agent to coordinate model evidence.** Tell the agent the recording is running and the office segment is ready. Do not start another assessment yourself. The agent will inspect the existing actual-model recording `7da73508…` against the original checklist and identify any missing model/transcript views. Anything absent remains OPEN; a deterministic fixture or a status reply must not silently substitute for evidence of a complete actual-model run. Any additional acceptance capture must be explicitly coordinated and distinguished from the final demo.

   Existing evidence review: sampled frames at 55s and 65s show Reporting working/current summary, the boundary-delivered instruction and the matching report-saved event. They do **not** establish expanded per-agent raw model output growing on screen, a selected-session status reply or the form queue receipt. These are specific evidence gaps, not a blanket claim that the full video contains no such view. The review record is `eval/reports/acceptance/2026-11-01_coordinated_v1/existing_model_evidence_review.json`.

9. **Record the ALLOW fixture.** Wait until the agent announces that the actual `tool_started` event is paused. Click **Web-App Agent** if necessary. Hold its physical monitor and sidebar in view. In **Session transcript**, expand the row beginning **Executing sql_injection_test** so the raw entry is visible. Tell the agent “ALLOW view recorded”. The agent will advance the existing terminal fixture to its actual `tool_result` pause. Expand the new result row and hold it visible, then say “ALLOW result recorded”. The agent handles the fixture terminal; you do not need to type commands.

10. **Record the active-report-view guard.** While the ALLOW fixture is paused/active, open **Risk planning / mitigation** and click **Option B · load completed assessment mitigation**. Hold the returned message visible, then close the dialog. This records what happens when the current engagement is not a completed actual-model assessment. Tell the agent when this view is recorded before it finishes the fixture.

11. **Record the DENY fixture.** Wait until the agent announces the actual denied operation is paused. Select **Web-App Agent**. Show its physical screen and sidebar, then expand the transcript denial row so its decision/audit reference is visible. Say “DENY view recorded” after holding the view. The agent will inspect the footage alongside the real audit/fixture record to determine whether the denied operation lacked an executor result. Absence of an operation is not established by a single screenshot alone. These fixtures are explicitly deterministic/no LLM inference; their baseline finding totals are not verified exploit evidence.

12. **Finish with layout and save.** Click **Reset view**, narrow the browser window again, and show the office, labels, sidebar and navigation controls. Restore its size. Stop/save the recording under a new filename. Send the full video path (or both clip paths) and the exported JSON path. The agent records the date, viewport, actual engagement IDs and per-step observations from the footage and runtime records; you do not need to decide whether either checklist passed.

## What happens after filming

The agent reports each original checklist step as **observed pass**, **observed discrepancy**, or **not observed**, with timestamps and engagement IDs where applicable. Missing/unclear footage stays open. Passing tests, generic assurances and secondhand “passed” messages do not fill gaps.

These are acceptance recordings. Only after both original checklists pass will a separate final three-path walkthrough be recorded: the same synthetic fixture → Phase 1 → Option A → Option B derived from the existing saved live report. That final recording requires no fresh live engagement. The agent must restore/check the existing saved session after fixtures before using its Option B view; no synthetic findings or replacement report may be inserted to rescue the demonstration.
