# Reusable Reporting

Open **Reporting → Archived Reporting** in the 3D console. The selector lists the pinned Slate fixture plus completed sessions from KAYAN's owned loopback lab. To grant local report writing for a selected session for 30 minutes, run:

```powershell
python -B -m console.backend.authorize_archived_reporting <assessment-id>
```

That command grants no inference permission. For Slate, omit the ID. The completed assessment's original ROE is not replaced. Its report uses a separate Reporting-only Gate identity.

## Evidence flow

The existing workflow writes tool results, decisions and specialist outcomes to the session store. When Reporting opens a completed owned-lab session, it captures those persisted records in a versioned, content-addressed snapshot under `.build/reporting-archive/evidence`. This read path starts no tools. Local hashes identify the recorded bytes. Recorded tool decisions are retained as references and attribution remains unreviewed unless separately established.

An operator can configure a separately supplied, externally stored custody catalogue through `KAYAN_REPORTING_CUSTODY_FILE` and its trusted pin in `KAYAN_REPORTING_CUSTODY_SHA256`. The catalogue is keyed by full assessment ID. Each entry carries the existing archive fields (`assessment_id`, `title`, `status`, `snapshot`, `records`, `custody`) plus `operational_evidence_sha256`. Source IDs, revisions and payload hashes must match captured, nontruncated records. Admission v2 verifies the case, current head, authority and claims. Unmatched operational hypotheses remain withheld. Available examples contain no independently issued operational custody catalogue. Fixture custody is separately labelled.

The report path binds the assessment evidence and review revision. A cloud request for a completed operational archive binds the same case and review revision and uses the existing digest-specific, one-shot opt-in. The model can select only admitted excerpts and approved controls. Cloud remains disabled by default.

## Verified in the running console

| Selected assessment | Evidence and result |
| --- | --- |
| Slate archive and recovery review | Pinned synthetic custody. T1486 admitted; T1490 withheld. Real TrustGate first denied the inference action and the mock transport received zero requests. An authorized mocked request then changed the summary and recommendations while preserving the identical verdicts. |
| Owned lab · 7da73508 | Ten recorded outcomes. No independent custody and no eligible finding. T1059 and T1190 withheld. Local reporting succeeded without cloud access. |

Both exported HTTP payloads matched the saved report bytes. The owned-lab evidence digest and artifact survived the actual backend restart. The normal console was restored with cloud disabled. No new assessment or provider request was sent. Screenshots, captured mock request and example exports are in `.build/reusable-reporting-2026-11-21/`.

149 targeted Python tests and 28 Rust tests passed. The frontend production build, session panel and 14 transport checks passed. Go `pkg/trustgate` passed. Go `pkg/tools` failed in unchanged code, including executor tests that lack required TrustGate context and argument tests that expect different decoder diagnostic names. All 71 historical artifact hashes and five admission verifier hashes matched.


## Publication and capture consistency

Reporting reloads the current archive after write authorization. Cloud mode also checks the exact approved request and complete archive after inference authorization and again before publishing the result. A changed or removed archive returns HTTP 409. If the change happens after the one permitted provider attempt has started, the attempt stays consumed. The route denies stale output without publishing it. These are checks at asynchronous boundaries. Separate processes that write custody files still need a shared transaction or trusted publication boundary for an atomic guarantee.

Five deterministic tests reproduced stale HTTP 200 results. The local test changed the pinned custody file while the mocked write decision was pending. Three mock cloud tests changed review status without changing the request digest. The fifth removed the archive. All five return HTTP 409 after the fix. Changes before inference made zero requests. A change during the response used one mock request and kept the reservation. An explicit subsequent local run produced the current invalid-custody report and withheld the previously admitted finding.

Reporting also checks the full scoped decision history before accepting a captured outcome. Decisions must agree on the actor, normalized verdict and audit reference. The chronological check still requires a matching earlier decision. Late contradictions, incompatible decision fields and wrong-agent decisions had passed six new tests incorrectly. All are now rejected. An equivalent duplicate and a decision for another task leave the valid capture intact. This corroborates transcript consistency. It leaves independent TrustGate audit-chain reconciliation open.

The candidate checkout passed 96 focused Python tests. The canonical checkout passed 224, including admission, custody and guard regressions. Four Reporting evaluations, the original saved Slate result, its pinned request, 71 historical digests and five verifier digests reproduced. The new cases used synthetic records and mocked authorization or transport.

## TrustGate audit reconciliation

In Archived Reporting, expand **Evidence coverage** and select **Check TrustGate audit** for captures. The console checks the response against the evidence snapshot it is displaying. Reporting sends only the case ID and requested audit entry IDs through loopback. TrustGate verifies its hash and HMAC chain and looks up the exact entries under one read lock. The route requires a loopback peer and rejects browser-origin requests. It returns only the case, actor, role, tool, target, verdict and entry ID. Reporting checks every returned field and keeps a missing reference, contradictory tuple, reused reference, invalid journal and unavailable service distinguishable.

This is corroboration of a recorded authorization decision. A matching denial remains a denial. The deployed TrustGate instance and its signing setup are part of the trust boundary. Independent custody, attribution and admission remain separate controls. The audit check does not write to the audit journal, send anything to a model, create an assessment report, or change a historical archive.

The real Windows Reporting client queried an isolated Rust service built and run natively in Ubuntu. A synthetic denied decision matched and a second UUID was missing. The ledger stayed at one entry before and after the read. The rendered console used a separate mocked response and displayed one match, one missing entry and missing independent custody. [Browser verification](images/archived-reporting-audit-mock-preview.jpg)

The focused Python suite passed **238** tests in the canonical checkout. The frontend panel check and production build passed. Ubuntu passed **32** Rust tests, including four reconciliation tests and one actual loopback HTTP router check. Windows Application Control blocked dependency build scripts with OS error 4551. Windows settings stayed in place. Four saved Reporting replays, the pinned Slate request, the saved Slate response, 71 historical digests and five verifier digests matched. A full signed-custody restart scenario remains open.

## Signed custody and audit restart

The cross-runtime regression uses the real Reporting and custody routes, persisted case files, the latest signed test-only receipt and the native Rust service in Ubuntu. The write decision for the local report is a test fixture. A separate live Rust decision denies an inert fixture request. Nothing dispatches or contacts any assessment target. The audit check reads the real ledger.

The exact audit sequence was verified, unavailable, verified after restart, ledger invalid after a damaged journal was loaded, and verified after restoring the original journal bytes. The test-only receipt head and downloaded report stayed identical in all five phases. T1486 stayed withheld. The one-entry ledger gained no entries during the audit checks. Repair and corruption occurred only on the temporary fixture journal.

On Windows with a native Ubuntu build of this checkout, set `KAYAN_AUDIT_RESTART_WSL_BINARY` to the absolute Linux path of that binary, leave test port 8000 free, and run `python -B -m pytest -q -s -p no:cacheprovider tests/test_reporting_signed_audit_restart.py`. The normal test run leaves this cross-runtime fixture opt-in. The first harness run detected that the Windows-side relay briefly remained after the Ubuntu process exited. The harness now waits for that listener to clear before restarting. The full lifecycle passed in 18.48 seconds.

## Specialist observation attribution

The evidence collector groups records by source ID and exact artifact digest. An identical replay counts once. When that identity has more than one valid captured version, every version is excluded and counted as an integrity failure. An unaffected specialist retains its own observation. Previously retained and verified history is checked on read.

The nine frozen synthetic cases cover role isolation, intact and projected output, empty output, denied and failed events, historical records, late contradictions, exact duplicate delivery and colliding captured versions. The baseline passed **7/9** and the correction passed **9/9**. The earlier reader incorrectly rejected an identical replay and counted one of two conflicting versions. Authored case oracles measure passive attribution. The result establishes neither finding accuracy nor specialist model accuracy.

The console shows per-role retained observations separately from reported catalogue completion. The browser fixture displayed one completed Network capture, one projected Recon capture and a Web-App capture without retained output alongside its reported completion. The historical owned-lab archive still has ten transcript-only records across Recon 3, Web-App 5 and Network 2. Reporting-mode exports bind any new role counts to the verified archive and accept legacy bytes where the count field is absent. [Rendered fixture](images/archived-specialist-attribution-preview.jpg)

Reproduce with `python -B -m eval.archived_specialist_attribution --output <new-result.json>`. The frozen fixture SHA-256 is `0dc1e4cddca602157b55676307e94184061702b6b0c4d65042f17328185bd17d`. The canonical checkout passed 278 focused tests, including the real signed-archive restart fixture. The frontend panel check and production build passed. Six saved evaluations, the historical Slate request and result, and all 76 pinned historical and signed-verifier digests matched. [Frozen oracle](../eval/fixtures/archived_specialist_attribution_v1.json) · [Baseline](../eval/reports/archived_specialist_attribution_v1_baseline.json) · [Corrected replay](../eval/reports/archived_specialist_attribution_v1_after.json)
