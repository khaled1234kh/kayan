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

