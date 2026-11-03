# Planning context and outcome-aware coordination — 3 November 2026

This record covers the new guided profile, deterministic Phase 1/Option A and the separate real-Qwen coordinator pass. It supersedes the earlier same-day 115-test/blocked-Go status for current verification. It does not close the broader 19-item UI/office workstream in TODO.md.

## Input integrity: what was actually established

The supplied `kayan-mitigation-8080414c-34d7-4abd-a161-ceb2eb24a384.json` was inspected locally. Company size contains exactly 120 characters, matching the old HTML limit. Infrastructure still contains the sample description. Storage contains sample fragments surrounding inserted text. The context copies inside that export agree: JSON serialization was not shown to be the concatenation source. The original edit-event sequence is unavailable; the precise cause of every overwrite/concatenation remains unproven. Lost original text cannot be reconstructed. That user-provided context is not a public fixture or included in this commit.

The old silent input clipping is removed. Company size accepts 2,000 Unicode codepoints, departments 4,000 and each remaining field 12,000. Longer text stays editable and visible, with an explicit submission error; it is not silently cut. Nonblank text, whitespace and newlines are preserved through validation. Blank optional fields are omitted. A sorted, compact UTF-8 JSON SHA-256 and per-field counts describe the submitted context, not a security/risk score.

The profile shows two fields at a time in Organization, Technical environment and Data & customers. Completion indicators count supplied fields only. Examples are fictional. Sample preview changes no inputs; explicit replacement updates all six fields atomically, with an immediate restore option. Drafts remain in this browser tab's sessionStorage, with Clear draft and a retention notice. Reports are regenerated when reopened; drafts are not durable account storage. No credentials should be entered as descriptive company context.

The complete journey is Organization → Hypotheses → Mitigation → Review & Export. Option B is a separate, collapsed saved-assessment path. Loading B does not start an assessment or transfer the current Option A draft into its source evidence.

## Offline applicability and controls

Phase 1 now uses eight authored scenario rules over the existing pinned ATT&CK/OWASP index. Each requires multiple named technical signals, records exact source field/excerpt offsets, explains the potential consequence and reference applicability, and states unverified assumptions. Company size/department labels alone cannot establish technical applicability. Simple explicit-negation handling rejects the checked absence examples. This is bounded lexical matching with authored controls, not general language understanding or Qwen inference.

Up to three applicable scenarios are displayed, ordered by **context relevance**. Additional supported areas are disclosed separately, not classified as lower severity. Text-only TF-IDF matches that lack required applicability evidence are diagnostic exclusions, not filler risk cards. Severity, impact, likelihood and mitigation urgency are all `not_assessed`. No risk/accuracy percentage is fabricated.

Option A carries scenario-specific controls, source excerpts, assets/signal labels and later validation actions. It explicitly records `inference_used=false`, `target_accessed=false` and zero findings. Actions are authored templates selected by evidence, not bespoke generated security advice. The actual applicability and effectiveness of any control still need review.

### Controlled fictional before/after comparison

Both runs use `eval/fixtures/planning_contexts_v2.json`; full outputs and dataset hashes are retained in `eval/reports/planning_context_before_20261103_v1/` and `planning_context_after_20261103_v4/`. No targets or model calls occur. The intermediate v1 failure (obsolete OWASP IDs filtered by the active index) and subsequent v2/v3 outputs remain preserved.

| Fictional description | Before: references / distinct action texts | After: references / distinct action texts |
|---|---|---|
| E-commerce | T1213.004, T1505.001, T1597.001 / 1 | T1490, T1133, A01:2025 / 3 |
| Clinic | T1070.005, T1217, T1593.003 / 2 | T1490, A07:2025 / 2 |
| Manufacturing | T1070.005, T1584.008, T1135 / 1 | T1021, A03:2025, T1133 / 3 |
| Insufficient technical description | T1609, T1593.001, T1651 / 1 | No supported scenario / 0 |
| Explicit absence of tested technologies | T1530, T1619, T1505.001 / 2 | No supported scenario / 0 |

All five final cases preserve their exact contexts and have zero verified findings. The three substantive organizations select different scenario/control sets. Recovery controls appropriately overlap between retailer and clinic. These five authored examples and regression assertions establish those differences, not general accuracy or recall. Rules are English-focused and negation is intentionally limited; unfamiliar technology or phrasing can be missed. None of this measures live-agent grounding efficacy. **No grounding improvement was demonstrated. Preserve this failure.**

## Actual browser acceptance for the planning redesign

Inspected in the ChatGPT in-app browser at `http://127.0.0.1:5173/`. Evidence base: `eval/reports/planner_outcomes_20261103/`. No browser permission bypass was used. These checks concern the redesigned profile/planning flow, not universal whole-application visual acceptance.

| Check | Observed result / evidence |
|---|---|
| Before/after layout | Six stacked fields replaced by section navigation and two editors. `planning-profile-before.jpg` includes intermediate character counters; it is not an untouched screenshot of the originally published build. Final captures are `profile-{width}x{height}.jpg`. |
| Six fields and section navigation | Full fictional values entered across all three sections; values preserved when switching. Actual expected input is `browser-context-input.json`. |
| Typing/selected paste | Storage replaced with Ctrl+A/paste; exact beginning/end and 1,783 codepoints confirmed, including Arabic and emoji. Company size retained 232 characters, exceeding the old 120 limit. |
| Sample safety | Preview left inputs unchanged; explicit clinic replacement updated fields; Restore previous inputs recovered the exact long storage value. |
| Close/reopen | Full company-size draft retained; input exactness then checked in the final export. Tab-session retention is disclosed. |
| Over-limit state | 12,001-character storage remained present, showed an error and disabled generation. Restoring the intended 1,783 characters enabled it. |
| Keyboard and contrast | Actual Tab moved Company size → Departments with a solid 2px outline (`profile-keyboard.json`). Computed sampled text/input/navigation contrast ranges 8.03–16.27:1 (`profile-contrast.json`); this is not a full accessibility certification. |
| Responsive layout | Actual screenshots/DOM checks at 1920×1080, 1600×900, 1440×900, 1280×720, 1024×768 and 640×800. Generate reachable, first editor visible, 16px editor font, no horizontal content overflow, background scroll locked. `profile-responsive.json`. Temporary overrides reset. |
| Observed layout correction | The first responsive pass pushed inputs below the fold on smaller laptops. Its `profile-before-compact-*` screenshots/JSON remain. Compact intro, collapsed B explanation and background scroll lock were rechecked in the final captures. Short/narrow windows retain a modal-content scroll and scrollable long editors. |
| Context → hypotheses → A | Actual requests produced recovery, vendor-access and API-authorization hypotheses, source excerpts/assumptions and distinct controls. `contextual-hypotheses-after.jpg`, `contextual-mitigations-after.jpg`. |
| Actual A export | Downloaded through the UI. All six strings equal the expected input in both `narrative_context` and `risk_plan.context`; fingerprint matches. `browser-option-a-export.json`, `browser-export-verification.json`, `context-export-review.jpg`. |
| Actual B and export | Existing a16f71f5… report loaded, three Planner reviews and partial coverage visible. Actual export retains original review/ledger/governance/model-summary/coverage records and both finding IDs. `saved-option-b-after.jpg`, `browser-option-b-export.json`, `browser-option-b-verification.json`. No new assessment. |

The final sampled browser error log was empty. This is an observed log sample, not proof that every interaction has no error. The original office scene, exterior and camera were not redesigned in this bounded profile pass. All 19 broader workstream items stay open for their own acceptance.

### Extra defect found during B inspection

The rendered saved report gave command injection and XSS identical generic mitigation paragraphs. The new `saved_verified_findings` regression failed before correction (`saved-mitigation-before.log`). Reporting now distinguishes SQL parameterization, shell removal, output encoding and filesystem containment. The focused check passed after correction; the browser showed distinct command-injection/XSS recommendations, including the raw-reflection-versus-browser-execution limitation. Historical source reports were not overwritten; the saved-report view uses the new templates while preserving original findings, provenance and partial coverage. Effort points remain illustrative title-based presentation weights, not measured urgency/cost.

## Real Qwen Planner: independently tested

`pentagi/live_engagement.py` now requests a governed outcome review after each specialist. The model must cite real outcome/evidence IDs, keep the fixed next role, choose only permitted priorities and disclose partial coverage. Invalid structured/schema reviews receive one governed correction; still-invalid reviews are explicitly degraded and retain the validated original plan. Runtime/authorization denials are not bypassed by schema retries. The next specialist receives the validated priorities.

Only a successful, attributed Recon port observation for the same engagement/target and exact lab-port scope can be reused by Network within 60 seconds. Reuse retains its original authorization audit ID and is displayed separately from newly executed tools. Stale, foreign, failed or unattributed observations cannot be reused. Malformed specialist JSON now consumes the existing bounded rejection budget rather than aborting immediately or executing invented fallback work.

Planner remains active through Reporting, uses shared local `qwen2.5:7b` at tier A, and has no specialist executor authority. Configuration/model weights, Cedar, ROE and taint semantics are unchanged. This is bounded next-step prioritization and honest partial reporting, not general dynamic scheduling. Fixed Recon → Web-App → Network → Reporting order remains; unavailable-lab work still proceeds through bounded later specialists and discloses their failures rather than automatically skipping every dependent task.

Execution ledgers capture actual tool-result records and source authorization IDs. Planner explanations are labeled model-generated and do not override those records. Reports/Option B retain coordination reviews, execution ledger, governance, model summary and coverage. Live Reporting receives capped descriptive excerpts with explicit omitted-field notices; full context stays in the report. The offline Phase 1 evaluation is completely separate.

| Real test | Engagement ID | Findings / allowed / denied | Outcome |
|---|---|---|---|
| Initial normal after outcome reviews | 2e03dc5f-e54e-4720-af81-e781566ac259 | 2 / 30 / 1 | Expanded harness passed; overly long model explanations observed and preserved, then prompts shortened. |
| Signed `service_scan` denial | 424aaa23-c8f8-4bf8-8189-dfdd7b815b26 | 2 / 25 / 2 | Forbidden tool never dispatched; reporting preserved denial/partial coverage. |
| Actually stopped owned lab | 8bc7a01d-f24d-4173-af89-43b4a0070804 | 0 / 24 / 1 | Real connection failures; no invented findings, partial report. Lab restored afterward. |
| Final normal coordinator run | a16f71f5-f9b3-4518-a17b-52a908358aba | 2 / 30 / 1 | Three accepted outcome reviews, nine execution-ledger records, attributed port reuse, exact verified IDs, Planner completed last. |

Evidence folders respectively: `planner_outcomes_live_20261103_v2`, `planner_outcomes_denied_20261103_v1`, `planner_outcomes_unavailable_20261103_v1`, `planner_context_live_20261103_v3` under eval/reports. All use actual model/Gate/lab conditions, not mocked tool outputs. Counts exclude ROE loading. Normal harness also exercises operator status/instruction; edge harnesses do not, so absolute allowed counts have different inputs. Each includes a deliberately tainted inference DENY. Final run audit verified 1,085 entries. The later regression/quiet offline check verified 1,130, with no journal rewriting.

The latest real coordinator run preceded the final offline type-specific mitigation-template correction; that correction was verified by tests and the actual saved-report browser export, not presented as another live run. `visual_verification=false` in the live harness means its transport checks are not pixel evidence; separate screenshots above provide the bounded rendered observations.

## Startup, regression results and remaining limits

The reproduced missing-model defect accepted HTTP 202, changed the current session and later failed with `[WinError 10061] No connection could be made because the target machine actively refused it`. The backend now checks installed Ollama models read-only before changing session/ROE state; unavailable service returns HTTP 503: `Local model service is unavailable. Start Ollama and retry; no assessment was started.` The old session remained exact. Evidence: `model-unavailable-before.json`, `model-unavailable-after.json`. Cold Ollama startup correctly produced the retained failed live-v1 readiness attempt; later normal run succeeded. No model configuration changed.

Final source checkpoint `planner_context_final_20261103_v4`: **17/17 groups passed** — **145 Python tests / 46 retained deprecation warnings**, **28 Rust tests**, **15 top-level focused Go boundary tests including real Cedar**, **15 Go config tests**, explicit no-embedding case, **9/9 adversarial cases**, TypeScript/production build and ten frontend scripts. These are focused Go tests, not the whole upstream Go suite. Largest generated chunk is 476.70 kB as reported by Vite; no measured FPS or load-time gain is claimed.

Earlier Application Control Go failures and intermediate failing tests remain preserved. The ordinary final retries succeeded without security/exclusion changes; the reason the host later permitted those executables is unknown. Do not bypass endpoint protections if the block returns.

`Start-Kayan.ps1 -Component All` and `-Component Review` both verified/reused expected services: Gate 8000, lab 8888, backend 8001, office 5173. Installed Ollama remains separate on 11434. Evidence: `startup-final-all.log`, `startup-final-review.log`. Offline planning requests left both the current session and Gate audit unchanged (`offline-no-authority-check.json`).

Backend restart currently starts with an empty active session, although individual snapshots persist. Option B then correctly returns `A completed actual-model assessment is required for Option B`. For this recheck the exact persisted, completed a16f71f5… snapshot was restored only into a waiting backend (`restored-after-backend-restart.json`); no engagement or tool call was started. Automatic current-session resume is a remaining operational limitation. `-RestoreDemo` is specifically for original 7da73508… and must refuse a different active session. Do not overwrite the current run merely to use that switch. Historical review media/PDFs were not regenerated or recertified here.

### Reproduction

From the canonical project with prerequisites installed:

```powershell
.\Start-Kayan.ps1 -Component All
python -B -m eval.functionality_checkpoint --label UNIQUE_CHECKPOINT
python -B -m eval.planning_context_eval --label UNIQUE_OFFLINE_COMPARISON
python -B -m eval.planner_live_acceptance --help
python -B -m eval.planner_live_edges --help
```

Use a new safe label for every evidence run. The live acceptance/edge CLIs create new governed lab engagements; do not invoke them just to replay existing demo footage. The unavailable-lab CLI requires the owned lab already be unavailable and never stops a service itself. For a presentation using existing recordings, start Review and open `/review.html` instead. New broad UI tasks and automatic resume remain disclosed; no “all TODOs done”, visual perfection, model training or general accuracy claim is warranted.

## Publication verification

Implementation/evidence commit `ce459f8ae74cecd864cb4b580a8ee0c62c3e032c` was pushed to the authorized GitHub main and matched remote HEAD. An existing clean downloaded verification checkout was fast-forwarded to that commit; all 26 recorded source hashes matched, and its Python suite passed **145 tests / 46 warnings** using the installed host dependencies. It remained clean afterward. This is a downloaded-source recheck, not a new isolated dependency installation. `publication-verification.json` and `published-copy-python.log` in the evidence base retain the result. The closure commit is documentation/evidence only; earlier real-model, suite and screenshot records are not relabeled as new runs.
