# TA deliverables alignment — implemented and visually accepted 2026-11-01

Later meeting pass: [TA_PROPOSAL_REPORT.md](TA_PROPOSAL_REPORT.md) supplies the requested six-section submission prose. [TA_MEETING_READINESS_2026-11-01.md](TA_MEETING_READINESS_2026-11-01.md) records fresh checks and bounded rendered task-start timing; the [closure review](CLOSURE_EVIDENCE_REVIEW_2026-11-01.md) reconciles all twelve acceptance steps and the separate zero-denial UI runs. Historical pending statements below describe their dated earlier passes, not current instructions to bypass a browser denial or repeat a final live run.

Current status: all five mapped TA requirements, the six-step planning procedure and the final continuous three-path recording are complete within the stated scope. Direct rendered evidence, actual-model/fixture counts and recording path/hash are in [ACCEPTANCE_2026-11-01.md](ACCEPTANCE_2026-11-01.md). The original 3D procedure is also accepted; FBX re-export and bundle cleanup remain deferred. Earlier implementation-only statements below retain their historical dates.

This is the post-checkpoint addition requested in the TA-alignment instructions. The original TA brief itself was not independently supplied here; the implementation follows the user's explicit mapping and sequencing. The four functionality-checkpoint items remain closed with their stated limits. The six-step human visual walkthrough, monitor-text black patch, FBX re-export and bundle warning remain separate.

## Five-item result

| Item | Result and scope |
|---|---|
| 1. Optional engagement context | PASS: six strict bounded string fields in intake, documented as a separate descriptive section. They reach Reporting's narrative only, outside the signed ROE and gate inputs. Empty context remains supported. |
| 2. Phase 1 Risk Plan | PASS: standalone local TF-IDF over the existing pinned ATT&CK/OWASP index; up to three hypothetical matches, explicit empty/no-match outcome, relevance-based priorities and uncertainty. No model, target, tool, live orchestrator or gate call. |
| 3. Option A | PASS: alternate input to the existing Reporting agent/report builder; shared deterministic mitigation synthesis with local references. No additional model inference, live loop, target or authorization. Same mitigation shape as Option B, different explicit evidence basis. |
| 4. Labels / illustrative points | PASS for implementation, arithmetic/SSR and TypeScript/production build. Defense in Depth / Zero Trust filters, inclusion toggles, additive points and JSON export are built. UI copy explicitly rejects real pricing/effort interpretation. Direct pixel/click acceptance is now recorded in ACCEPTANCE_2026-11-01.md; earlier implementation checks remain distinct. |
| 5. Written architecture and evaluation | PASS: complete Red/Blue allocation and training-versus-grounding text are in [ARCHITECTURE.md](ARCHITECTURE.md), under their own headings. They are finished prose, not future tasks or a claim training took place. |

## Isolation by design

`pentagi/engagement_context.py` contains the six optional fields: company_size, departments, infrastructure_summary, network_architecture, data_storage and customer_touchpoints. Unknown fields/non-string values and excessive lengths are rejected. `StartRequest.engagement_context` is separated from the existing owned-lab authorization input. `LiveEngagement` holds it in `reporting_context`, never `self.roe`; only the Reporting model's task data and final narrative receive it. It is explicitly framed as untrusted descriptive data, not instructions, verified facts or authorization. Model narrative remains unvalidated narrative.

**Items 1–3 add no policy evaluation.** Context never reaches `policy.rs`, `roe.rs`, ROE canonical signing/loading, `/authorize` or Cedar. Phase 1 and Option A do not call TrustGate at all. The pre-existing Option B live engine still authorizes its model/tools as before; that existing governance is not bypassed or described as removed. No Rust, taint, signer or Go integration source was edited in this pass. `docs/ROE_CONTRACT_SCHEMA.md` describes the optional section without adding it to the Rust contract. No Cedar policy expansion was needed.

`pentagi/risk_plan.py` imports descriptive validation and the existing retrieval layer, with no live-runtime, executor, HTTP or gate dependency. It produces `hypothetical_risk_plan` with `verified=false`, `target_accessed=false`, reference IDs/source URLs/excerpts and an explicit ranking basis. The same descriptions can be analyzed offline without enrolling an engagement or changing the live scene.

`ReportingAgent.generate_direct_mitigation` reuses `generate_report`, then supplies the Risk Plan to the shared mitigation builder. This is deterministic structured reporting, not an additional LLM agent or a new autonomous engine. Its authored defensive templates are accompanied by local reference matches; a citation is not a guarantee that a recommendation is applicable or effective. Option A has zero verified findings. Option B admits mitigation inputs only with a supported verification record and audit reference supplied by the existing runtime. This reporting-layer envelope check is not independent cryptographic verification or a new reproduction run.

## Product/API use

Terminology: TA Option A (direct mitigation) / B (live testing then mitigation) are reporting paths. The older model-architecture “Option A” means shared local Qwen across roles and is a separate decision; it does not imply that offline direct mitigation calls that model.

On `http://127.0.0.1:5173/`, **New assessment** now exposes **Optional descriptive context** before the unchanged owned-lab authorization. The separate **Risk planning / mitigation** button opens an offline planning dialog; it does not start or animate a live engagement.

- `POST /planning/risk-plan` with `{"engagement_context": {...}}`: hypothetical plan only.
- `POST /planning/direct-mitigation` with the same body: recomputes the local Risk Plan and feeds Reporting directly. Client-provided findings/targets/reference URLs are not accepted.
- `GET /planning/current-mitigation`: derives a report view from the current completed actual-model assessment's saved report, with ID checks. It neither re-runs testing nor overwrites the saved historical report. Returns 409 without a completed/saved actual-model assessment.

The console backend was deliberately restarted while idle and its existing completed engagement 7da73508-01e6-48e9-9093-be09c5fd734d snapshot restored (101 transcript entries). The new endpoints returned HTTP 200 on port 8001. No browser automation was used; serving source/API success is not rendered acceptance.

The mitigation section uses the same keys for A/B: option, evidence_basis, method, reference_retrieval, verified_finding_count, hypothetical_risk_count, recommendations and limits. Each recommendation links either risk_ids or finding_ids and includes references and uncertainty. Historical model-summary recommendations remain separate unvalidated narrative. The shared new mitigation retrieval is post-report processing, distinct from the agent-grounding conditions in historical off/on runs; those saved runs and metrics were not changed.

The UI annotates recommendations with grouping tags and fixed illustrative point weights. Filters do not change inclusion; inclusion changes only the displayed sum and exported `presentation_selection`. Original recommendations and evidence remain intact. Product copy reads: **“Illustrative relative effort/cost only. Points are comparison weights, not prices, quotes or measured implementation effort.”** This is not billing, currency conversion, pricing estimation or an additional analysis engine.

## Fresh verification and preserved limits

Full Python suite: **46 passed**, 16 utcnow deprecation warnings retained. Nine TA tests cover strict/absent context, signing invariants, separation from the gate payload, Reporting-only model data, offline network/subprocess/tool/gate guards, A/B evidence shape, rejection of fake proof and planning API isolation. Mocked guards establish tested code behavior, not universal sandbox guarantees.

Actual local HTTP checks: [results](../eval/reports/ta_alignment/api_2026-11-01_v1/results.json). The synthetic six-field fixture produced **3 hypothetical risks, 3 Option A recommendations and 0 Option A findings**. A separate saved-run view produced **2 Option B recommendations from 2 previously verified findings** in engagement 7da73508…. These are not comparable finding counts or a mitigation-quality experiment. Both outputs are saved separately; neither was overwritten to favor a path. The live console snapshot and audit file hash were unchanged across the offline requests. Empty input returned insufficient context; injected top-level findings/targets were rejected with 422.

Presentation arithmetic/SSR, full 3D TypeScript/production build, 12 transport checks and session-panel checks passed. Logs are in `eval/reports/ta_alignment/2026-11-01_v1/`. Initial TypeScript failure (`replaceAll` under ES2020) was corrected without raising the target. A subsequent verification wrapper failed printing a Unicode build checkmark on a cp1252 console after the build itself exited 0; remaining checks were run separately. Both setup failures are preserved, not runtime defects. The Vite bundle warning remains. Rust/Go suites were not repeated in this pass because their source and integration behavior were unchanged; the earlier consolidated checkpoint remains their dated evidence.

At the time of the TA pass, 3D Git metadata was broken and source/hash copies were preserved for recovery. Subsequent scope-freeze repair resolved that registration and committed the frozen runtime as 300687a; see GIT_REPAIR_2026-11-01.md. Historical copies remain unchanged. No source checkout/reset/reinitialization or second handoff was created. Original v1 grounding/performance hashes are preserved. **No grounding improvement was demonstrated. Preserve this failure.** No new grounding-off/on, training-time, mitigation-effectiveness or browser-rendering claim is made by these additions.

## Reproduction

From canonical TrustGate root, with current console backend on 8001 and no concurrent engagement:

```powershell
python -B -m pytest tests -q -p no:cacheprovider
python -B -m eval.ta_alignment_check --label UNIQUE_NEW_LABEL
python -B -m pentagi.risk_plan --context eval/reports/ta_alignment/api_2026-11-01_v1/context.json --output NEW_RISK_PLAN.json
```

The API driver refuses an existing label. The CLI refuses an existing output. API samples and Markdown reports live in `eval/reports/ta_alignment/api_2026-11-01_v1/`; Option B is explicitly a derived view of saved evidence, not a fresh engagement.

From the active 3D root:

```powershell
npm run check:ta-alignment
npm run check:trustgate
npm run check:session-panel
npm run build
```

## Accepted planning-UI procedure — retained for reproduction

1. Hard-refresh `http://127.0.0.1:5173/`. Open **New assessment**, expand descriptive context and confirm all six fields and zero-policy-weight copy. Cancel without starting a run.
2. Open **Risk planning / mitigation**. Expand context and enter the saved synthetic fixture. Generate Phase 1: expect Risk 1–3, hypothetical labels/references and a relevance-ranking disclaimer. Blank input should produce insufficient context, not invented risks. The live scene should retain its existing assessment state.
3. Select **Option A · direct mitigation, no testing**: expect Option A, hypothetical evidence basis, no live/verified finding claim, recommendations and local references. Open reference details; verify text wrapping/scrolling and that Escape/Close returns to the office.
4. Reopen; load **Option B · completed assessment mitigation**: expect recommendations linked to the saved completed engagement, with verified-finding basis. Loading while a new live run is active must give the completed-assessment requirement rather than mix evidence.
5. Check All / Defense in Depth / Zero Trust grouping. A group may have no matches; filtering must not change inclusion. Toggle a recommendation: the illustrative total should change by its displayed points. Export JSON and confirm original recommendations remain and presentation_selection records selected IDs/total/disclaimer.
6. Read the visible illustrative disclaimer, test a narrow window and verify the dialog is scrollable and keyboard usable. Record discrepancies separately; SSR/build checks do not close pixel/click acceptance. This is additional planning-dialog acceptance, not completion of the existing six-step 3D live walkthrough.

Scope-freeze delivery update: implementation and direct browser acceptance are complete. The original built-in browser subsequently permitted same-origin access. All six observations above were performed with saved screenshots, an actual active-fixture guard check and inspected export JSON. The final recording uses the original saved completed report without a new assessment. Historical denials remain in BLOCKED.md; no bypass was used.
