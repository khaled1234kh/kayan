Written 2026-11-04 and updated 2026-11-22 (Africa/Cairo). Supersedes _ARCHIVE_PRE_PIVOT_HANDOFF.md, which describes an abandoned pre-pivot version of this project and should not be used.

# KAYAN TrustGate - canonical master handoff

## Current checkpoint · Matched 80-case cloud accuracy and public release — 2026-11-23
**Final publication state (23 November 2026).** PR #1
(https://github.com/khaled1234kh/kayan/pull/1) was opened from
`release/cloud-pivot-accuracy-2026-11-23` (`b6869051d072c9f0f47f6ee146fc2bd4dedb1e43`) into `main`
(`eb6d1f34aac11a5983995b76100ddd2684d6d681`) and merged with merge commit
`2da8b19646e68804738b999ccf290e8b2561016c`; `main` now contains the complete validated project.
GitHub Actions run https://github.com/khaled1234kh/kayan/actions/runs/45153228641 passed: 180
`pkg/tools` tests and 10 `pkg/trustgate` tests passed, with the single expected `TestCedarLiveProfile`
skip. Branch protection reported no required reviews, so no approval was bypassed.


The complete validated project is published on branch `release/cloud-pivot-accuracy-2026-11-23`
from the verified chain tip `1f63244` (39 commits ahead of remote `main` `eb6d1f3`, which is a
clean ancestor). This branch integrates the uncommitted source/documentation work in the primary
checkout (curated: 186 primary files + 20 sanitized benchmark files), preserves the Go CI
checkpoint `06e5f12` history and all negative results, and excludes raw `.build` output, request
ledgers, model responses, runtime logs, private assessment records and personal working paths.

Recovered original frozen 80-case harness SHA-256
`09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0`; the offline re-score of the
saved outputs using the untouched scorer reproduced `summary.json` and `summary.csv`
**byte-for-byte** and produced SovereignEG/Qwen3.8-27B-FP8 **72/80 = 90.00% exact** with local
arms 18/28/27/23/5. This is exact role-contract accuracy on authored synthetic cases in a
retrospective matched benchmark, not a fresh blinded human-adjudicated holdout or real-world
vulnerability-detection accuracy. All five historical cloud/lab negatives are preserved. No new
live cloud call was made for this publication; credentials stayed outside the checkout and the
production mock-only guard was not bypassed. The previously exposed SovereignEG key must be
rotated before any shared use.

Published materials: `eval/sovereign-80-matched/` (harness, scorer, frozen inputs, protocol,
result, consolidated findings, digests). Reports/docs updated: `README.md`, this handoff,
`TODO.md`, `docs/ENGINEERING_MISSION.md`, `docs/ENGINEERING_ACCEPTANCE.json`. Security controls,
signed bindings, admission v2, scope checks, reviewer independence and Go/Rust checks are
unchanged. Cloud remains optional and disabled by default.

## Current checkpoint · Archived Reporting recovery and telemetry — 2026-11-21

Ubuntu Go CI passed on `06e5f12` with 180 tools tests, 10 TrustGate tests and one existing live Cedar skip. The Reporting API saves a recoverable local report when reserving a one-shot cloud attempt. The saved fallback survives an interrupted mocked request and app recreation, keeps T1486 admitted and T1490 withheld in the Slate fixture, and rejects replay. Mocked total-deadline expiry also falls back without retry. New verified cloud selections preserve finish reason and token usage in saved exports. [Engineering mission and next coding task](docs/ENGINEERING_MISSION.md) · [Acceptance criteria and limits](docs/ENGINEERING_ACCEPTANCE.json)

Local checkpoint `ccee732` on `work/reporting-recovery` contains the selected Reporting source, console integration and synthetic fixtures. The isolated checkout passed 36 tests plus frontend typecheck, session-panel checks and build. The main development checkout passed 164 focused Python tests and verified 71 historical artifact hashes and five signed-off verifier hashes. The console recovery check used mock transport and synthetic Gate decisions.

Local follow-up `4223c24` displays saved cloud usage, latency and finish reason in Archived Reporting. The session-panel checks and production build passed. Browser inspection remains open because Windows Computer Use could not identify the current Brave URL.

Local follow-ups `f9f9692` and `fe6ae8c` bind exports to the exact displayed bytes and correct false withholding of multi-statement evidence. The console API refused stale exports after a custody change or rerun. In the signed synthetic Windows fixture, Reporting now displays the supported occurrence and its secondary record. Authorized activity stays withheld, and a missing secondary record fails verification. The isolated Reporting suite passed 40 tests and the development checkout passed 168 focused tests. The pinned Slate request, 71 historical artifacts and five verifier hashes matched. Verification used synthetic cases and mocked transport.

Local commits `15419d2` and `a235f1e` freeze and run the nine-archive Reporting occurrence benchmark. The repeated-technique fix recovered 4/4 supported occurrences from 1/4, admitted 0/6 withheld occurrences, and rejected the invalid archive. Repeated-technique reports use the local composer. The isolated Reporting suite passed 44 tests, the development checkout passed 172 focused tests and the frontend build passed. All 71 historical artifact hashes and five verifier hashes matched. This measures synthetic projection, with zero provider calls. [Benchmark and reproduction](docs/ARCHIVED_REPORTING_PROJECTION_BENCHMARK.md)

Local commit `2894314` adds scoped aliases for selecting evidence from repeated techniques and rechecks the exact grant and custody revision before provider setup and before result publication. Tests rejected stale scope, duplicate fields and withheld aliases. Two independently locked app instances sharing a directory made one mock request. The isolated Reporting suite passed 58 tests and the development checkout passed 186 focused tests. The approved Slate digest and the frozen projection output reproduced exactly. The new selection format has no live-provider result or authorization. [Selection contract and limits](docs/ARCHIVED_REPORTING.md#occurrence-aware-selection)

Local commits `3c85ca9` and `83850e7` freeze and run 14 authored Reporting selection replays. All outcomes matched expectations and preserved the exact findings and withheld claims. The console and export now show occurrence coverage and observed-action coverage separately. The isolated Reporting suite passed 59 tests, the development checkout passed 187 focused tests and the frontend build passed. The replay and projection artifacts reproduced exactly, and all 71 historical and five verifier hashes matched. The host has a `qwen2.5:7b` manifest with six blobs at their declared sizes. Its loopback service was stopped during this check. [Replay methods and limits](docs/ARCHIVED_REPORTING_SELECTION_REPLAY.md)

Local commits `db01ab6` and `8fa10db` freeze and run the synthetic Qwen2.5 Reporting ranking comparison. Six local requests selected valid evidence and the approved-only case made zero requests. Qwen recovered 10/14 preferred excerpts versus 6/14 for deterministic composition, with observed-action coverage of 2/8 versus 8/8. A post-hoc replay appending verified action excerpts recovered 8/8 action coverage and 14/14 preferred excerpts at 14/17 preference precision. All findings and withheld claims matched, and the dedicated local process was stopped after measurement. The isolated suite passed 64 tests and the development checkout passed 192 focused tests. The raw trace, pinned Slate request, 71 historical and five verifier digests matched. [Methods, results and exact scope](docs/ARCHIVED_REPORTING_LOCAL_RANKING.md)

Local commits `52bf118` and `1222499` froze and evaluated the observed-action holdout. All seven local requests returned valid selections, and the authorized-only case made zero requests. Across six primary cases, the supplement raised action coverage from 1/8 to 8/8 and preferred-excerpt recovery from 9/16 to 16/16. It preserved findings, withheld claims and controls. The full eight-excerpt selection still displayed zero actions across nine occurrences. [Frozen scope and results](docs/ARCHIVED_REPORTING_ACTION_HOLDOUT.md)

Local commit `344aa44` integrated the append-only supplement. The rendered 3D console showed the action label and retained T1486 supported and T1490 withheld with a synthetic Gate and mocked provider response. The browser export matched the exact saved bytes. The isolated suite passed 70 tests and the canonical suite passed 198. The frontend panel test and build passed. Three archived Reporting evaluations, the pinned Slate request, 71 historical hashes and five verifier hashes matched. No external provider request was made. [Application verification](docs/ARCHIVED_REPORTING_ACTION_HOLDOUT.md#application-verification)

Local commits `f287c7a` and `c2be916` froze and evaluated six full-summary cases. Swapping excerpts increased action coverage from 9/50 to 16/50 and lost two preferred excerpts in one case. The console now preserves the selected eight-excerpt summary and displays remaining verified actions separately. In the rendered mock case, seven additional actions appeared, the ninth occurrence stayed withheld and the downloaded JSON matched the saved bytes. [Capacity results and browser evidence](docs/ARCHIVED_REPORTING_FULL_SUMMARY.md)

Local commit `4436ca9` verifies stored report findings, sources and presentation before reading or export. Nine altered fixtures returned HTTP 409. The saved real Slate response passed offline without rewriting. The isolated suite passed 83 tests and the canonical suite passed 211. The latest frontend panel check and build passed. Four saved Reporting evaluations, the pinned Slate request, 71 historical digests and five verifier digests matched. Next, test local source changes during the asynchronous write decision. [Saved result verification](docs/ARCHIVED_REPORTING_FULL_SUMMARY.md#saved-result-verification)

Local commit `d9273a8` rejects stale archive publication after asynchronous authorization and detects contradictions in the full scoped decision history before accepting captured evidence. Five stale HTTP 200 fixtures and six contradictory capture fixtures reproduced before the correction. The corrected controls performed zero requests for pre-inference changes and consumed one mock attempt for a change during response. The isolated suite passed 96 tests and the canonical suite passed 224. Four Reporting replays, the saved Slate response, its pinned request, 71 historical digests and five verifier digests matched. Independent TrustGate audit-chain reconciliation and interprocess atomic custody publication remain open. [Before and after results](docs/REUSABLE_REPORTING.md#publication-and-capture-consistency)

Local commit `3da40c2` adds read-only reconciliation with the verified Rust audit ledger and exposes the result under Reporting evidence coverage. The Windows Python client matched one real Rust denial and found one missing reference. The isolated ledger stayed at one entry before and after reconciliation. The rendered console mock displayed both statuses while custody remained missing. The canonical suite passed 238 Python tests and Ubuntu passed 32 Rust tests. The frontend check and build passed. Windows Application Control blocked Rust dependency build scripts. The pinned Slate request, saved response, four Reporting replays, 71 historical digests and five verifier digests matched. The test service was stopped. [Verification and limits](docs/REUSABLE_REPORTING.md#trustgate-audit-reconciliation)

Local commit `bcb3437` adds the opt-in cross-runtime signed-archive recovery test. Real Rust journal checks went from verified to unavailable, verified after restart, invalid on damaged journal load and verified after restoring the fixture. The same signed test-only receipt and exact saved export survived all five checks, with T1486 withheld. The report write grant was mocked. The isolated fixture sent no model requests. [Recovery and reproduction](docs/REUSABLE_REPORTING.md#signed-custody-and-audit-restart)

Local commits `cff6fbe` and `d86d480` froze and fixed offline vendor-access planning on a dedicated branch. The new 16-case result improved from 9/16 to 16/16, removing seven false vendor hypotheses and retaining all eight valid matches. The historical validity and transfer suites stayed at 32/32 and 12/12. Exact input spans and Option A mitigation links passed. The canonical checkout passed 266 focused Python tests, including the live Rust restart fixture. Four Reporting replays, the new planning replay, the saved Slate result and all 76 historical/verifier digests reproduced. [Result and limits](docs/PLANNING_AND_COORDINATION_2026-11-03.md#vendor-remote-access-validity--2026-11-21)

Local commits `66fe9f0` and `47d2ff7` froze and corrected saved specialist attribution. The nine-case passive replay moved from 7/9 to 9/9. An exact duplicate counts once, and conflicting captured versions are excluded from the role totals. The browser showed retained evidence separately from declared catalogue completion. The known owned-lab archive remained transcript-only across all ten records. The canonical checkout passed 278 focused tests, the frontend build and panel check passed, and six saved replays, the Slate record and all 76 evidence digests matched. [Evidence and limits](docs/REUSABLE_REPORTING.md#specialist-observation-attribution)

Local commits `ef44d29` and `52a35c0` froze and verified signed occurrence attribution across all three specialist roles. The frozen cases moved from 2/7 to 7/7. Exact adverse occurrence scoping now preserves supported siblings while keeping ambiguous reviews fail-closed. Eight additional scope and intake controls passed. The canonical checkout passed 293 focused tests, seven saved evaluations reproduced, and all 76 pinned digests and the saved Slate result verified. The scope field is available through the review API. The round trip used test-only identities and source records. [Verification and remaining limits](docs/REUSABLE_REPORTING.md#signed-finding-and-occurrence-attribution)

Local commit `6787adb` binds signed custody, admission and coverage to a single captured revision and checks the current source digest before advancing receipt history. The mixed two-record and three-record report is now withheld, and the stale import returns HTTP 409. The canonical suite passed 295 tests, including the isolated Rust restart. Seven saved evaluations, all 76 pinned digests and the saved Slate result verified. Next, exercise concurrent reviewer or enrollment changes at receipt import. [Regression and reproduction](docs/REUSABLE_REPORTING.md#signed-source-revision-consistency)

Local commit `c11c85f` serializes review publication with receipt insertion and rechecks the active reviewer decisions and custodian assignment immediately before insertion. Four stale test-only imports now return 409 with the preceding receipt intact. A separate app instance could publish its review as soon as the receipt transaction ended. The canonical suite passed 301 tests, including the Rust restart. Seven saved evaluations, the Slate result and all 76 pinned digests verified. Next, test exact API-to-record relationships in offline Phase 1. [Before and after checks](docs/REUSABLE_REPORTING.md#current-review-and-enrollment-at-receipt-import)

Local commits `3761046` and `6b90abc` freeze and verify a Phase 1 API-to-record applicability correction. Exact results improved from 12/16 to 16/16 by removing four false hypotheses. All eight expected hypotheses remained, with Option A preserving the precise relationship excerpts. Three existing planning sets stayed exact. The canonical checkout passed 303 tests, eight saved evaluations reproduced and all 76 pins and the Slate result verified. The new cases are fictional, with no inference or target access. Next, evaluate opt-in local model ranking of verified Archived Reporting excerpts under independent authorization. [Results and limits](docs/PLANNING_AND_COORDINATION_2026-11-03.md#api-to-record-relationships-in-phase-1)

Local commit `8021236` adds opt-in Qwen2.5 7B selection of admitted excerpts in Archived Reporting. One actual local Ollama call through a synthetic preview gate rendered E2.1 with 221 input tokens, 52 output tokens and 5.609 s provider latency. The export matched all 2,623 bytes and retained T1486 supported and T1490 withheld. An independent isolated Rust/Cedar run denied writes without signed scope, denied inference under write-only scope, and allowed a single mocked selection under Reporting-only scope. The canonical checkout passed 321 tests, the console build and panel check passed, and eight saved evaluations and all 76 pinned digests matched. Next, test backend interruption recovery during local ranking. [Operational settings and evidence](docs/ARCHIVED_REPORTING_LOCAL_RANKING.md#opt-in-console-mode)

Local commit `9a0efe7` recovers deterministic Reporting after interruption at local generation. The first-run case moved from HTTP 404 to an exact saved fallback. The existing-selection case retains the earlier report. Export after app recreation made zero inference requests. All 323 focused tests passed, including the isolated Rust cases. Eight saved evaluations, 76 digests and the saved Slate cloud result verified. Next, measure full proof disclosure in capacity-limited Reporting, separately from summary ranking. [Recovery and regression](docs/ARCHIVED_REPORTING_LOCAL_RANKING.md#interrupted-local-requests)

Local commits `2d1b1d2` and `182e6ce` freeze and verify full reviewed proof per admitted occurrence. Exact role-to-source links improved from 212/215 to 215/215 and complete disclosures from 50/53 to 53/53, with unchanged summary coverage and admission. The rendered synthetic Windows finding showed joint support E1.1 and E1.2 and exported all 2,789 saved bytes. The canonical checkout passed 328 tests including isolated Rust, and the panel check and build passed. Nine saved evaluations, 76 digests and historical Slate cloud evidence verified. Next, test Phase 1 cloud storage links against unrelated asset mentions. [Proof disclosure and limits](docs/ARCHIVED_REPORTING_FULL_SUMMARY.md#full-reviewed-proof)

## Current checkpoint · Signed Reporting review — 2026-11-21

The saved owned-lab diagnostic exercised authenticated review, canonical package export, Ed25519 receipt signing in a separate test process, custodian import, admission v2 and report export in the rendered console. Admission evaluated the test-only receipt and withheld the candidate. The same receipt and report were readable after backend restart. No real reviewer or custodian was enrolled. The standard console has been restored. [Enrollment and commands](docs/SIGNED_REPORTING_REVIEW.md)

## Previous checkpoint · Tool evidence and scoped review — 2026-11-21

The owned-lab Python executor records privacy-filtered outcomes before emitting the transcript event. The artifact binds case, task, agent, tool, audit reference and outcome digest. Reporting validates the link and distinguishes execution captures from historical transcript records. A separate pinned enrolment file scopes reviewer access. The human review endpoint saves append-only submissions. New-capture admission requires an externally signed catalogue, submitted-review digest bindings and unchanged admission v2. No operational independent authority was provisioned.

The browser exercised a real allowed loopback readiness request and Gate denial, both captured, then saved a test-only unresolved review and exported zero admitted findings. Disk evidence, review and export survived a backend restart. No pentest workflow or cloud request was run. Evidence is under `.build/evidence-sprint/`. 112 Python tests, frontend typecheck and session panel checks, Go TrustGate and three Go governance tests passed. The full Go tools package had 16 failing top-level tests. Normal console restored.

## Previous checkpoint · Reusable Reporting — 2026-11-21

The console now selects completed owned-lab assessments as well as the pinned Slate fixture. Reporting stores versioned evidence and withholds claims without separately pinned independent custody. The browser exercised mock Slate and local 7da73508 reports. Exports matched and the operational evidence snapshot survived backend restart. No cloud calls or new assessment were run. [Implementation and verified outcomes](docs/REUSABLE_REPORTING.md)

## Previous checkpoint · Archived Reporting — 2026-11-21

The Reporting panel now runs or reopens a local review of the pinned Slate archive. The full cloud path was exercised in the rendered console with the real Rust gate and mocked SovereignEG HTTP transport. The saved report shows one admitted finding and one withheld hypothesis. The results are exportable. The separately authorized live smoke test returned a valid model selection and the browser export matched the saved result. The one-call approval is consumed and local mode has been restored. [Launch and verification](docs/ARCHIVED_REPORTING.md)

## Previous checkpoint · Citation grounding v3 probe completed — 2026-11-21

The one authorized SovereignEG probe returned HTTP 200 from the approved model, with visible schema-valid JSON, a normal stop and zero reasoning tokens. It returned an empty facts array instead of the expected T1486 mechanic with E2.1 as anchor and citation. Exact grounding failed. No addresses, complete groups or review items were produced. The 106 regression tests passed and the 71 historical, five verifier and two prior cloud evidence digests matched. The one-call approval is consumed. Stage B remains unauthorized. [Probe and supporting evidence](docs/CLOUD_PIVOT_CITATION_GROUNDING_V3.md#real-provider-result--exact-grounding-failed)

## Previous checkpoint · Cloud reasoning budget v2 probe complete — 2026-11-21

The single authorized Stage A probe returned a visible schema-valid answer with zero reasoning tokens. It failed exact validation because both citation fields contained an event description instead of E1.1. Stage B remains blocked and zero diagnostic calls were sent. [Probe evidence and frozen contract](docs/CLOUD_PIVOT_REASONING_BUDGET_V2.md)

## Previous checkpoint · Frozen SovereignEG diagnostic executed — 2026-11-21

One capability probe and all 12 approved diagnostic calls completed. The probe accepted the exact schema. All diagnostics consumed the 512-token output cap in reasoning and returned no answer. Every model arm recovered 0/3 complete findings. The authored control recovered 3/3. The run used the verified Student allowance-only setting. [Results and artifact hashes](docs/CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md)

## Previous checkpoint · Owner-authorized SovereignEG preflight — 2026-11-21

The owner authorized the exact frozen 12-call diagnostic and up to one capability probe within 20 EGP. The regenerated bundle matched its approved hash. Zero requests were attempted. Credential location, effective account cap, applicable pricing, provider routing and exact structured-output support remain unresolved. [Authorization](docs/CLOUD_PIVOT_OWNER_AUTHORIZATION_2026-11-21.md) · [Execution status](docs/CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md)

## Previous checkpoint · Real cloud comparison readiness — 2026-11-21

The offline matched request bundle is frozen. Four archived local direct responses replayed at 0/3 complete findings, and the separate authored control recovered 3/3. SovereignEG results remain unavailable pending documented credential rotation, spend limits, routing and capability confirmation, and written egress authorization with maximum spend. [Readiness and comparison plan](docs/CLOUD_PIVOT_REAL_MODEL_COMPARISON.md)

## Previous checkpoint · Role-constrained evidence extraction v2 — 2026-11-21

In 12 actual local Qwen2.5 7B requests, structured contract validity rose from 0/4 to 2/4 and raw keyed role F1 from 5.3% to 17.6%. All automatic arms recovered 0/3 complete findings, while authored proof recovered 3/3. Stop tuning the exposed cases. Independent evaluation and cloud approval are pending. [Paired results and stopping decision](docs/CLOUD_PIVOT_EXTRACTION_V2_RESULTS.md)

## Previous checkpoint · Automatic evidence construction — 2026-11-20

The fixed-hypothesis local Qwen2.5 7B comparison completed eight requests on exposed synthetic development material. Direct and structured each reached 0/3 complete admitted findings. All four structured replies failed role/value validation. Authored proof groups reached 3/3. The focused suite passed 121 tests and the historical and signed-off source hashes matched. Independent evaluation and SovereignEG remain pending. [Frozen design, results and decisions](docs/CLOUD_PIVOT_AUTOMATIC_PROOF_EXPERIMENT.md)

## Previous checkpoint · Offline Track A evidence checkpoint — 2026-11-20

The frozen Track A runner replayed 72 archived local replies and reproduced zero complete groups. Three cloud configurations ran only through mock transport. A separate paired synthetic proof-group experiment admitted 4/4 expected items after assembly versus 0/4 without assembly. This measures supplied proof assembly, with no model improvement claim. The focused suite passed 137 tests and historical and sign-off hashes matched. The cloud candidate remains blocked pending the account and egress approvals. [Results and commands](docs/CLOUD_PIVOT_ACCURACY_CHECKPOINT.md)

## Previous checkpoint · Admission feasibility study preparation — 2026-11-20

Independent engineering sign-off passed for the bounded offline v2 contract. The feasibility package is ready for stakeholder review. Intake and study execution remain unauthorized pending approved data scope and privacy and ethics determinations, external custody evidence, independent reviewer arrangements and a frozen evaluation plan. [Engineering sign-off](docs/ATTACK_PROVENANCE_ADMISSION_V2_FINAL_SIGNOFF_2026-11-20.md) · [Readiness memo](docs/ATTACK_ADMISSION_FEASIBILITY_READINESS.md) · [Protocol](docs/ATTACK_ADMISSION_FEASIBILITY_PROTOCOL.md) · [Custody and approvals](docs/ATTACK_ADMISSION_FEASIBILITY_CUSTODY_AND_APPROVALS.md) · [Review and adjudication](docs/ATTACK_ADMISSION_FEASIBILITY_REVIEWER_PACKET.md) · [Draft preregistration](docs/ATTACK_ADMISSION_FEASIBILITY_PREREGISTRATION.md)

## Previous checkpoint · Offline admission v2 sign-off remediation — 2026-11-20

The remediation binds explicit external ancestry attestations to the assigned case and head, and scopes negative process/session assertions to the reviewed relationship. The 31 new regressions, 54 existing admission tests and 228 historical tests passed (313 total). The pinned demo and D revision 2 audit passed and all 71 historical hashes matched. [Verdict matrix and commands](docs/ATTACK_PROVENANCE_ADMISSION_V2_REMEDIATION_2026-11-20.md)

## Previous checkpoint · Offline evidence admission v2 — 2026-11-20

The v2 offline admission contract requires affirmative reviewed process/session proof, exact uncertainty keys and externally attested explicit collector ancestry. Its custody gate checks the byte pin before parsing and retains history validation for matching pins. The 54 focused and 228 historical offline tests passed together (282). The pinned demo and D revision 2 audit passed and all 71 historical SHA-256 values matched. Real-telemetry intake remains NO-GO pending separate engineering and operational sign-off. [Contract, verdict matrix and commands](docs/ATTACK_PROVENANCE_ADMISSION_V2_2026-11-20.md)

## Previous checkpoint · Offline session correlation and synthetic custody — 2026-11-20

Both P1 session defects are corrected. The separate custody gate tests active roster completeness, history and continuity, trusted time and exact case assignment. The combined suite passed 228 tests, the pinned demo and Experiment D revision 2 audit passed, and all 71 historical SHA-256 values matched. Real-telemetry feasibility remains NO-GO pending independently controlled human, source and operational custody gates. [Implementation, matrix and commands](docs/ATTACK_PROVENANCE_V1_P1_CUSTODY_2026-11-20.md)

## Previous checkpoint · Offline provenance P0 remediation — 2026-11-20

The adapter now preserves conflicting reviewed process/session links, treats explicitly disputed identity or time as unknown and withholds attribution where collector ancestry is disputed. The combined offline suite passed 187 tests, the pinned demo reproduced and all 71 historical digests matched. Real-telemetry feasibility remains NO-GO pending the two candidate fixes and independent custody and review gates. [Remediation evidence and next decision](docs/ATTACK_PROVENANCE_V1_P0_REMEDIATION_2026-11-20.md)

## Previous checkpoint · Offline trusted fact provenance v1 — 2026-11-20

The synthetic registry, Windows 1102/4624 normalizer and v4 adapter passed 74 focused and 167 combined offline tests. The demo produced an eligible Windows claim, a withheld Windows claim and a mixed slate batch with exactly one review item. The revision 2 audit passed and 71 historical digests matched. Fixture receipts test the trust boundary under authored assumptions. Real reviewer enrollment, production integration and further experiments remain separate decisions. Experiment E is deferred. [Implementation, demo and acceptance evidence](docs/ATTACK_TRUSTED_FACT_PROVENANCE_V1_RESULTS_2026-11-20.md)

## Previous checkpoint · Trusted fact provenance proposal — 2026-11-20

The next P0 proposal specifies a versioned offline registry, a bounded Windows Security Event XML profile and a v4 adapter with explicit mixed-batch semantics. The implementation assignment awaits approval. Experiment E remains deferred. [Provenance and normalization proposal](docs/ATTACK_TRUSTED_FACT_PROVENANCE_V1_PROPOSAL_2026-11-20.md)

## Previous checkpoint · Offline event-scoped evidence guard v4 — 2026-11-20

The approved v4 sibling guard resolves a cited mechanic to one reviewed case and event. Both slate claims pass together, and removing either shared attribution association withholds only its claim. The focused suite passed 28 tests and the combined offline suite passed 93. The revision 2 audit passed and 39 historical hashes matched. The v4 interface relies on independently reviewed facts. Raw identity, time and source-lineage validation remain separate work. Production integration and subsequent workstreams require separate approval. Experiment E remains deferred. [Implementation and acceptance evidence](docs/ATTACK_EVIDENCE_GUARD_V4_2026-11-20.md)

## Previous checkpoint · Post-diagnostic architecture review — 2026-11-20

The architectural review recounted the archived v2 and A–D responses against the frozen evidence groups. Neither positive case in D received an extraction. The first proposed implementation is a versioned offline guard correction for shared attribution in slate, pending owner approval. Experiment E is deferred. [Decision, validation gates and Sol Medium assignment](docs/ATTACK_POST_DIAGNOSTIC_ARCHITECTURE_REVIEW_2026-11-20.md)

## Previous checkpoint · ATT&CK v3 Experiment D revision 2 completed — 2026-11-20

All 12 authorized local attempts completed with valid responses. Complete evidence groups stayed 0/3 from D1 to D3. D3 correctly abstained once versus zero for D1, on flint after the empty extraction fallback. The conservative D3 context bound caused three of four fallbacks. The only fact-fed case, silver, gained an unsupported claim. All request hashes, fallbacks and mapping scores reproduced offline. The original manifest integrity failure is retained. Event-scoped treatment of slate's shared attribution is a separately proposed guard correction. Review these exploratory results before further work. [Experiment D report](docs/ATTACK_DIAGNOSTIC_D_RESULTS_V3_2026-11-20.md)

## Previous checkpoint · ATT&CK v3 Experiments B and C completed — 2026-11-20

All eight authorized single-reference requests returned valid responses. Complete evidence groups were 0/4, with three correct positive IDs backed by only partial evidence. Correct abstentions were 3/4 on negative or ambiguous cases. The model withheld findings on withdrawn, authorized and failed activity, mapped the unattributed capture in larch, and missed the attributable capture in moss. The ledger and all scores reproduced offline. This is an exploratory result on exposed fictional cases. Review the findings before any further experiments or architecture work. [B/C results and evidence](docs/ATTACK_DIAGNOSTIC_BC_RESULTS_V3_2026-11-20.md)

## Previous checkpoint · ATT&CK v3 Experiment A completed — 2026-11-20

The authorized ten-request candidate substitution recovered 6/6 keyed technique IDs versus 0/6 for the repeated controls. Complete evidence groups remained 0/6 in both conditions. All ten responses were valid and all five controls reproduced the original raw answer text exactly. The result also holds excluding quartz's conditional cloud label. [Experiment A results and evidence](docs/ATTACK_DIAGNOSTIC_A_RESULTS_V3_2026-11-20.md)

## Previous checkpoint · ATT&CK v2 forensics completed — 2026-11-20

The authorized v2 run completed all 72 cells. The offline replay verified 85 source statements, 219 citation entries, all model scores and all 72 ordered shortlists. Neither arm completed any keyed evidence group. Per pass BM25 missed five expected references and hybrid missed six. Every expected ID in a shortlist was selected without a complete chain. The separate v3 scorer projection corrects numeric metadata leaking into counts, and an offline guard verifies scoped, independently supplied evidence before analyst review. The full suite passed 265 tests with 81 warnings. [Root-cause report](docs/ATTACK_ROOT_CAUSE_V3_2026-11-20.md) · [Case matrix](eval/reports/attack_forensics_v3_20261120/matrix.md)

The forensic replay prepared the ten exact Experiment A payloads on five already-exposed cases. The original human-gated confirmation remains sealed. [Diagnostic protocol](docs/ATTACK_DIAGNOSTIC_PROTOCOL_V3_2026-11-20.md)

## Previous checkpoint · Joint-evidence experiment v2 — 2026-11-20

The new offline study evaluates whether a retrospective ATT&CK finding has enough evidence across sources. Its 18 AI-authored cases contain nine positives, six benign/failed actions and three inconclusive cases. Every one of the ten expected technique mappings needs at least two records under the authored rubric. V2 verifies a complete answer fits both budgets and grades individual cited statements, technique selection and completed evidence groups separately. All 18 capacity proofs passed. The relevant Python suites passed 76 tests and the full Python suite passed 245 with 81 warnings. [Engineering report and regression evidence](docs/ATTACK_EVIDENCE_EXPERIMENT_V2_2026-11-20.md)

The registered comparison completed 72 local Qwen generations under the project owner's explicit authorization. Exact group completion was zero across both arms and passes. The primary mean cost difference was −1.333 per case for BM25 minus hybrid, with a paired interval of [−2.944, +0.778]. [Registration](eval/reports/attack_mapping_v2_20261120/registration.json) · [Frozen run results](docs/ATTACK_EXPLORATORY_V2_RESULTS_2026-11-20.md)

## Prior checkpoint · Professional AI evidence review — 2026-11-20

Completed an observation-first review of all 56 fictional cases against pinned Enterprise ATT&CK 20.1. Across both cohorts the AI analyst recorded 26 supported mappings, 28 abstentions and two ambiguous cases. The diagnostic review agrees with 30/32 original decisions and disputes the forced positives on `fresh-01/E2` and `fresh-05/E2` because actor authorization or account control is unresolved. The two proposed changes remain separate from the frozen author labels. The 24 original confirmation observations were reviewed by the AI and now have a separate provisional judgment file. They are no longer AI-unseen. [Research review](docs/ATTACK_PROFESSIONAL_RESEARCH_REVIEW_2026-11-20.md) · [Case table](eval/reports/ai_professional_review_20261120/case_review.md)

Keep the existing human-gated protocol sealed. No genuine human validations or approvals were supplied and no new model-evaluation requests ran. BM25 remains the reference and hybrid E5-192 the research challenger. A mock adjudication exposed a schema capacity mismatch, and a literal but irrelevant citation reproduced the documented semantic scoring limitation. Plan a new independently reviewed cohort for confirmatory claims. Any AI-labeled follow-up requires its own protocol. SovereignEG remains paused, fine-tuning deferred and the live workflow and policy remain as recorded. [Prioritized corrections](docs/ATTACK_RESEARCH_CORRECTIVE_ACTIONS_2026-11-20.md)

## Previous checkpoint · Independent ATT&CK review preparation — 2026-11-20

At the preparation checkpoint the diagnostic cohort was closed for optimization and the 24 cases were frozen without labels or predictions. The separate evaluation runner verifies pinned inputs and rejects missing reviewer originals, adjudication or stakeholder approval before opening model transport. The versioned scorer handles jointly required records, acceptable alternatives, abstention and unresolved ambiguity. [Review and confirmation handoff](docs/ATTACK_CONFIRMATION_HANDOFF_2026-11-20.md)

Prior to final inference, recruit two qualified independent reviewers, give each only their own two blinded forms and pinned taxonomy, then retain all four returned originals. The coordinator verifies independence and records hashes. An adjudicator resolves the evidence groups for both cohorts. The stakeholder approves false-positive and missed-pair weights, minimum useful improvement, allowable specificity loss and the uncertainty rule. Keep SovereignEG paused, fine-tuning deferred and existing agent permissions and workflow intact. [Preregistered comparison](eval/reports/ai_mapping_confirmation_preparation_20261120/protocol.json)

## Previous offline ATT&CK mapping checkpoint — 2026-11-20

Keep field-weighted BM25 @ 5 as the offline comparator and carry hybrid E5-192 @ 5 forward as the single challenger. In 224 loopback Qwen2.5 7B evaluations on the previously inspected 32 fictional cases, BM25 produced 22/32 exact with 8 correct, 6 unsupported and 8 missed technique–record pairs. Hybrid produced 26/32 exact with 11 correct, 3 unsupported and 5 missed. The matched exact-case interval includes zero [0, +25] percentage points. The earlier hybrid result stays 24/32 with 9 / 4 / 7. Identical reference context and prompts did not reproduce every output. Dense E5-512 improved standalone recall while its hybrid performed worse than E5-192. The interpretation prompt halved unsupported mappings and lost one correct pair. [Full results and reproducibility](docs/ATTACK_MAPPING_ABLATION_2026-11-20.md)

TrustGate and the live assessment path were untouched. The local cloud experiment submit, poll and reindex routes returned HTTP 503, and the selected engagement `0d6ebb9f-02d6-49db-aa74-25ed78eb0f27` kept the same status and response hash. Python passed 205 tests (201 before changes). The case trace preserves failures where valid quoted text proved neither the named behavior nor adversary action. [Case-level evidence](eval/reports/ai_mapping_ablation_20261120/case-trace.json)

**Next**: Give only their separate blinded packets to two independent reviewers. Finalize adjudicated labels and the false-positive versus missed-event decision rule before running the locked comparison once on the 24 fresh fictional observations. Those observations have been frozen without labels and were never sent to the model. Keep cloud inference paused and fine-tuning deferred. [Review protocol](docs/ATTACK_LABEL_REVIEW_AND_CONFIRMATION_2026-11-20.md)

## Earlier ATT&CK retrieval and evidence mapping — 2026-11-20

The frozen fictional benchmark selected hybrid BM25 and local E5 on the 16-case development set. On a separate 32-case cohort, the hybrid recovered 14/16 expected techniques in its top five, versus 11/16 for TF-IDF. Local Qwen2.5 7B recovered 9/16 evidence pairs with hybrid references and 10/16 with the oracle. The experimental endpoints still return HTTP 503, and direct SovereignEG adapter construction requires a mock transport. The live five-agent path remains separate. Full Python suite: 201 passed. Independent label adjudication and a fresh confirmation remain open. [Report and evidence](docs/ATTACK_RETRIEVAL_AND_EVIDENCE_MAPPING_2026-11-20.md)

## Cloud pivot security and evidence benchmark — 2026-11-20

The experimental cloud job, polling and reindex endpoints now return HTTP 503. Status reads configuration without creating a provider. The analysis layer no longer signs ROEs or borrows legacy role identities. The console restart preserved its selected session. See [verified changes and offline results](docs/CLOUD_PIVOT_SECURITY_AND_EVAL.md) for current behavior, the provider credential blocker and the benchmark decision.

The pinned local Enterprise 20.1 index retrieved 2/9 expected technique occurrences. Local Qwen2.5 7B scored 7/16 exact with and without lexical context in the original run. The structured 7B follow-up gained one exact case with an interval spanning zero. The structured 1.5B arm regressed with retrieval. Cloud comparison and fine-tuning remain open. The implementation notes below record the earlier checkpoint.

## Historical cloud/parallel AI layer and training proposal — 2026-11-20

**Historical record.** This section preserves the original additive experiment and its proposals. Decisions at the top of this file supersede the historical steps below. SovereignEG is paused and fine-tuning is deferred. Preserve the governed `pentagi/` runtime history, Gate/audit records, grounding regression and disclosed limits.

### 1. What changed in this pass (implemented and verified)

The user asked to start using SovereignEG `SovereignEG/Qwen3.8-27B-FP8`, build parallel agents, use MITRE ATT&CK as RAG, keep TrustGate authoritative, respect the Student Plan (2 concurrent / 20 requests per minute), and defer fine-tuning. All of that was implemented as an **additive** layer; the legacy assessment path was not rewired.

| Area | Files | What it does |
|---|---|---|
| Config/secrets | `config/ai.json`, `.env` (git-ignored), `.gitignore`, `ai/config.py` | Non-secret provider/model/limit settings in JSON; key only via `SOVEREIGNEG_API_KEY` in local `.env`; minimal env loader; API exposes only `api_key_configured: bool` |
| Providers | `ai/providers/{base,sovereign,ollama,registry}.py` | OpenAI-compatible chat + embeddings, reasoning-token handling, retries, Ollama fallback, usage accounting, 2-request semaphore and 20/min sliding-window limiter |
| MITRE RAG | `ai/mitre/{stix,rag}.py` | Downloads official Enterprise STIX, keeps 706 non-revoked techniques, embedded `.npz` cache under ignored `data/mitre/`, TF-IDF fallback, cosine retrieval, deterministic removal of unverified technique IDs |
| Parallel agents | `ai/orchestrator/{state,schemas,agents,graph}.py` | LangGraph `prepare → security/research/risk/operations (concurrent) → aggregate`, additive state reducers, strict Pydantic schemas, defensive JSON parsing, deduplicated findings/limitations |
| TrustGate | `ai/trustgate/client.py` | Reuses `integration.trustgate_client`; signs a narrow analysis-only ROE per engagement; canonical `planner_agent`/`planning`/`llm_inference` and `reporting_agent`/`reporting`/`write_report`; tainted args and denials block inference (fail closed) |
| HTTP API | `ai/api.py`, `console/backend/main.py` | `/ai/status`, `/ai/usage`, `/ai/mitre/reindex`, async `/ai/assess` + `/ai/assess/{job_id}` added alongside existing routes |
| Tests/docs | `tests/test_ai_layer.py`, `docs/AI_ARCHITECTURE.md`, `README.md`, `requirements.txt` | 8 offline tests (mocked provider + fake Gate); architecture doc linked from README; added `langgraph`, `numpy`, `scikit-learn` |

Verification (20 November 2026): compile/imports clean; **full suite 173 passed, 4 skipped** (8 new tests); PowerShell PowerShell-e2e query retrieved `T1059.001` first from 706 techniques; full HTTP `/ai/assess` returned 4 agents, 5 TrustGate ALLOW decisions (4 inference + 1 report write) and 15 validated MITRE findings (4 chat requests / 8,412 completion tokens / 3,719 reasoning tokens / 132 embedding tokens). TrustGate denied tainted and unscoped requests. Secret scan: key absent from candidate sources; `.env` confirmed ignored. **No accuracy or grounding gain over local baselines is claimed.**

**Security note:** the API key was pasted in chat during setup. It must be **rotated before any shared/public use**; rotation means updating only the local `.env`, no source change. Never print, commit or stage it.

### 2. The new plan — RAG first, then measured fine-tuning

Phase A (done): cloud 27B as an inference provider + MITRE RAG + parallel analysis agents + unchanged TrustGate. This is the baseline for comparison, not the final answer.

Phase B was proposed as a conditional local fine-tuning study. It was never started and remains deferred by the current decision.

Why local: SovereignEG is an **inference-only** API (no training/fine-tuning endpoint was found or used). The zip `<LOCAL_USER>\Downloads\attack-stix-data-master.zip` (252 MB) is already the same source family the RAG downloads: it contains Enterprise/Mobile/ICS bundles for versions 1.0–20.1; the current RAG uses Enterprise 20.1 (`enterprise-attack-20.1.json`, 53,982 KB, identical size to the fetched `enterprise-attack.json`). Use version-pinned files from the zip, not the moving `master` URL, for any training dataset.

Hardware reality checked this pass: **NVIDIA GeForce RTX 5060 with 8,151 MiB VRAM is present**, but installed torch is `2.6.0+cpu` with `cuda_available=False`. A CUDA-enabled torch plus `bitsandbytes`/`peft`/`trl` must be installed before QLoRA; 4-bit QLoRA of a 7–8B model is the realistic ceiling on 8 GB, with small per-device batch and gradient accumulation. Do not attempt full fine-tuning of 27B locally or claim the cloud 27B was trained.

Training must be **instruction-style**, not raw document dumping: derive prompt/completion pairs from STIX objects (technique ID + name + description + detection + mitigations + tactics), hold out a disjoint technique-ID test split, include negative/uncertainty cases, and keep RAG in the loop because ATT&CK changes quarterly. Fine-tuning is only justified if a controlled comparison shows a need; record the reason either way.

Full step-by-step training/continuation plan: [docs/AI_TRAINING_CONTINUATION_2026-11-20.md](docs/AI_TRAINING_CONTINUATION_2026-11-20.md). Read it before starting Phase B.

### 3. Original sequence retained for historical reference

1. Read `docs/AI_ARCHITECTURE.md`, then `docs/AI_TRAINING_CONTINUATION_2026-11-20.md`, then this section. Preserve the legacy results and negative grounding evidence in the rest of this handoff.
2. Confirm services still start (Gate 8000 / backend 8001 / lab 8888 / office 5173; Ollama 11434 separate). Backend must be restarted after `ai/` code changes to load new routes. Re-run `python -B -m pytest tests -q -p no:cacheprovider` before any new change.
3. **Rotate the SovereignEG key** with the user, update only `.env`, and re-check `/ai/status` shows `api_key_configured: true` without exposing the value.
4. Extract or read the STIX zip from `<LOCAL_USER>\Downloads\attack-stix-data-master.zip`. Add a config option to `config/ai.json` + `ai/config.py` for a **local version-pinned STIX path** so RAG no longer depends on a network download (keep the URL as fallback; record version + file hash).
5. Build the dataset builder (`ai/training/build_dataset.py`): parse STIX `attack-pattern`, `course-of-action`, `relationship` objects; emit JSONL instruction pairs with provenance (version, STIX ID, source URL), a technique-disjoint train/val/test split, and a held-out evaluation set. Do not invent labels or silently drop revoked/deprecated objects.
6. Define the evaluation harness (`eval/ai_benchmark.py`) **before** training: same cases and scorer for `qwen2.5:7b`, `qwen3:8b`, `granite-4.2-8b`, `SovereignEG/Qwen3.8-27B-FP8`, RAG-only and any fine-tuned candidate. Track accuracy (contract pass, technique-ID exact/F1, evidence-mapping F1), latency and token cost separately. The prior external numbers (Qwen2.5 7B 22.5% exact contract, Qwen3 8B 35%, Granite 4.2 8B 0.762 evidence F1) measure different things — do not merge them into one ranking.
7. Install CUDA torch + QLoRA dependencies, verify `torch.cuda.is_available()` is True, then train a 7–8B 4-bit QLoRA candidate on the generated dataset (PEFT adapters, checked into an ignored/local model dir, not published). Keep batch/sequence lengths inside 8 GB.
8. Compare with the frozen harness; adopt a fine-tuned model **only** if it improves the measured metrics without breaking schema/TrustGate boundaries. If it does not, keep RAG-first and record the negative result honestly.
9. Update `MASTER_HANDOFF.md`, `TODO.md`, `docs/AI_ARCHITECTURE.md`, evidence under `eval/reports/` and the benchmark numbers after real runs. Never write a result number without a fresh run or an explicit historical label.

### 4. Rules that still apply to the new work

- TrustGate stays authoritative. Fine-tuning, prompts or agent output never grant permission; every sensitive action still needs an independent ALLOW. No model gets tool/scope/approval authority.
- Human approval remains required for destructive/high-impact actions; this layer performs analysis only.
- Keep secrets out of datasets, prompts, logs, reports and git. Check `git status` before staging. `data/mitre/` and `.env` are ignored.
- Preserve the documented "no grounding improvement was demonstrated" result and all historical failures. The new RAG sanity check is not a grounding benchmark.
- Do not claim the 27B was trained, that a local model beat it, or that training improved accuracy without the controlled harness results.




## Fresh Planner benchmark — 2026-11-04

A user-requested actual-Qwen, real-Gate inference-only evaluation completed all 30 authored Planner-only cases: **24/30 (80.0%) first attempt, 26/30 (86.7%) after the deployed validation/correction path**. These are bounded contract pass rates, not general or complete semantic accuracy. The old 7/7 mixed five Planner and two Reporting cases and is not comparable to this harder dataset. Source prompts, model weights/configuration and executor/authorization code were not changed to obtain this result.

Four final cases failed: P04 token-repeat generation abort, P08 an unsupported curl task assigned to Reporting and accepted by the plan validator, and R07/R08 rationales omitting recorded failure/verification gaps despite correct partial-coverage fields. Additional passing plans invent unsupported CLI options/ports/arguments; these unscored concerns are recorded without modifying the frozen score. Do not describe Planner as fully accurate or all functional issues as closed on the basis of earlier checkpoints. No specialist tools were dispatched or console session replaced. Audit verified 1,247 → 1,280 entries; 32 Planner inference requests plus ROE load, all allowed. This was not a fresh pentest and produced no real findings.

Full rubric, limitations, raw failures, reproduction and doctor-facing wording: [PLANNER_ACCURACY_2026-11-04.md](docs/PLANNER_ACCURACY_2026-11-04.md). Evidence: `eval/reports/planner_accuracy_20261104_v1/`. New follow-ups are disclosed in TODO; no Planner defect was fixed during this baseline pass.


## Current office/functionality checkpoint — 2026-11-03

This section supersedes older same-day “19 UI tasks open”, “restart loses session” and test-count statements below. Current source/evidence and per-item acceptance: [UI_OFFICE_ACCEPTANCE_2026-11-03.md](docs/UI_OFFICE_ACCEPTANCE_2026-11-03.md). The current bounded implementation queue is accepted against that matrix; subjective doctor/user approval and perfect behavior at every camera/device/state are not claimed. The supplied older office brief was merged as O1–O15, preserving its truncated final sentence.

Implemented: collapsible operations rail and compact drawers, native assessment modal outside the rail with bounded internal scrolling, coherent four-stage planning/three-section profile hierarchy, integrated saved Option B, improved agent panel/keyboard tabs/transcript following, owner-preserving Planner/Reporting findings, read-only filtered audit and complete export. The real five-seat office has a contained illustrated exterior/window assembly, matching continuous shell/slab, camera-near wall cutaways, quieter materials/lighting/glass, fitted Overview/Isometric/Front/Elevated and bounded selected-workstation cameras. Decorative cross-floor lines are removed; white selection differs from actual colored state. Existing character assets remain stylized. Rear monitor casing was directly inspected blank; all five intended workstation focus views were inspected. Free orbit may crop or occlude; Reset/roster remain available.

Separate reliability task complete: atomic selected-session pointer and automatic **records-only** backend restoration. Interrupted active executions become failed/blocked; queued instructions never resume. Corrupt pointers fail visibly. A real >21s backend outage reconnected the viewer automatically via capped persistent backoff, without reload/Reconnect, while preserving completed session evidence. No inference, tool execution or ROE loading occurs on restoration. Review/-RestoreDemo still refuses a different current session; matching original7da73508… was temporarily checked, then the current real session restored with unchanged Gate audit.

Reproduced real Planner failure8f98ca43…: literal `timed out`,0 findings /6 allowed /1 denied; the signed message was actually recorded delivered. The generic snapshot HTTP client had a 2s timeout versus the backend's up-to-8s authorization path. Only signed message routing now uses a 12s response/2s connection timeout and fails explicitly on ambiguous delivery with **no automatic resend**. Delayed real-loopback regression failed against the original implementation and passed after correction. Shared qwen2.5:7b/configuration, Cedar/ROE/taint, target scope, tools and action budgets remain unchanged; Planner has no added execution authority and is not a second model.

Final full automated checkpoint **ui_cohesion_final_20261103_v3: 17/17 groups passed**: **156 Python /48 retained warnings, 28 Rust, 15 focused Go boundary +15 Go config +explicit no-embedding case, 9/9 adversarial, TypeScript/build and ten frontend scripts (14 transport/reducer checks)**. Final activity CSS/tooltip then passed session check/build/budget and production-browser inspection separately. First checkpoint's bundle failure is preserved; planning is now on demand with 82,115-byte entry and every JS chunk below 500,000bytes, unchanged budgets.

Fresh actual-model runs62a7c952-0422-48ea-9ed5-49e211d55a5f and **b813d8a6-cc6f-4456-a9bc-0929249fd2a4** each returned **2 findings /30 allowed /1 denied**, excluding ROE load and including deliberate tainted-input denial. Both passed ordering, three accepted reviews, nine execution-ledger records, incremental output, governed status/queued guidance, Reporting hand-off and Planner completed last/no specialist dispatch. Web-App directory traversal remains untested under unchanged budget; finished is not full coverage. Current audit verified **1,247 entries**. Final b813d8a6… is selected. Actual browser screenshots separately observed Planner/Web-App/Reporting working and completed states; no new continuous video was made.

Actual browser acceptance covers the six requested office/profile/setup dimensions1920×1080 through640×800, compact session/audit, keyboard/native-modal behavior, reduced motion, sample undo, full exact six-field A export and saved B export, filters/inclusion, insufficient/empty production results, backend error/retry and actual body/monitor picking. Temporary viewport/media overrides were reset; temporary5174 servers/tabs closed. The long-output activity correction has browser computed-clamp proof and final normal rendering; the exact transient long-output after image was not recaptured. No universal visual/performance claim. One matched before/after cadence pair showed p95gap17ms idle/21.4ms orbit in both; it establishes no speedup or statistical regression conclusion.

**No grounding improvement was demonstrated. Preserve this failure.** This pass did not retrain/change Qwen or recertify old PDFs/videos/Docker swap. Production identity/isolation, immutable audit storage, development-key hardening, completion-triggered ROE revocation and complete upstream Go delegation remain disclosed architectural limits. Existing proposal/video links remain historical evidence. No unrelated Remotion/old server source was touched.

Startup remains `Start-Kayan.ps1 -Component All` for expected Gate 8000 / lab 8888 / backend 8001 / office 5173, with installed Ollama 11434 separate; Review starts no assessment. Omit -RestoreDemo when continuing a different saved session. For a cold start, read the acceptance matrix and README, rehearse the saved result, and only run `python -B -m eval.planner_live_acceptance --label UNIQUE` when intentionally starting a fresh authorized owned-lab test. It replaces the current selection and creates new evidence. Published source/evidence commit 695acab8f1424babd419a68863f726a6578e8443 matched remote and a clean downloaded source copy. All 38 changed-source hashes and six raw GitHub README images matched. Downloaded source passed 156 Python /48 warnings using installed host dependencies and hash-verified local LFS assets (not a new isolated install or fresh remote media download); six LFS objects passed fsck. Initial unhydrated pointer-only asset failures remain preserved. Publication proof: eval/reports/ui_cohesion_20261103_v1/publication-verification.json. All current bounded TODOs are checked; this following closure commit changes documentation/evidence only.

## Historical planning/coordination checkpoint — earlier on 2026-11-03

This section supersedes all earlier same-day/historical test counts and completion statements below. Full source/evidence/reproduction record: [PLANNING_AND_COORDINATION_2026-11-03.md](docs/PLANNING_AND_COORDINATION_2026-11-03.md).

Implemented and rendered: guided Organization / Technical environment / Data & customers profile, two editors at a time, real supplied-field counts, fictional sample preview and explicit replacement/restore, tab-session drafts, exact-context review and four-stage context → hypotheses → mitigation → export journey. Bounds: company size 2,000, departments 4,000, other fields 12,000 codepoints each; overlong input stays visible and blocks submission. Actual downloaded A JSON retained all six exact fields, including 232-character company size and 1,783-character Unicode/multiline storage. Source user export was inspected privately: matching context copies do not prove a serializer concatenation bug; the original edit sequence remains unknown. No user company text is published.

Offline Phase 1 now uses eight authored applicability rules over pinned framework references, exact context evidence and explicit assumptions; unsupported TF-IDF matches do not fill cards. Context relevance is distinct from severity/likelihood/impact/urgency, which remain unassessed. Five repeatable fictional before/after cases show different organization-specific scenario/control sets and no supported risks for the two insufficient/explicit-absence cases. This is deterministic lexical/template behavior, not Qwen Planner intelligence, general accuracy or model training. Option A performs no inference, target access or authorization call. Quiet API checks preserved current session and the complete audit result exactly.

The real shared-Qwen Planner now performs governed evidence-referenced reviews after each specialist, validates the fixed next role/priorities/partial disclosure, and exposes explanations separately from execution records. Only attributed same-engagement/target Recon port observations within 60 seconds can be reused by Network, without another scan. Malformed specialist JSON consumes the existing rejection budget. Reviews do not introduce new tools, order, authority or action budgets. Configuration, model weights, Cedar/ROE/taint remain unchanged. No second inference model. Unavailable-lab handling still follows bounded later roles and reports failures; this is not a general dynamic scheduler.

Final actual-model coordinator engagement **a16f71f5-f9b3-4518-a17b-52a908358aba: 2 findings / 30 allowed / 1 denied**, three accepted reviews, nine execution-ledger records, Planner completed last, explicit untested directory_traversal due to unchanged Web-App budget. Signed service-scan denial **424aaa23…: 2 / 25 / 2**; actual lab outage **8bc7a01d…: 0 / 24 / 1**. See full IDs/count bases in the new record. The outage lab was restored. The final coordinator run preceded the last type-specific offline mitigation-template correction; that correction passed tests and actual saved-report/export inspection without another live assessment. Historical report JSON/Markdown and videos remain unchanged.

**Final current automated result: 17/17 groups passed**, checkpoint `planner_context_final_20261103_v4`: **145 Python / 46 retained warnings**, **28 Rust**, **15 focused Go boundary + 15 Go config + explicit no-embedding case**, **9/9 adversarial**, TypeScript/build and ten frontend scripts. Prior host-blocked Go errors remain preserved; ordinary retries now pass without protection changes. Why the host changed behavior is unknown. Current audit verified **1,130 entries**. These checks do not imply comprehensive upstream Go coverage or a general security guarantee.

Actual browser acceptance covered context editing/sample/length/reopen/keyboard/contrast, A and saved B exports, six profile viewport sizes (1920×1080 through 640×800), no horizontal form overflow and reachable actions. Earlier compact-layout failures are retained. Default viewport restored; latest screenshot `docs/images/organization-profile.jpg`. Geometry/build are not visual acceptance. **All 19 broader UI/office tasks remain open** in TODO.md for their own implementation/acceptance. The prepared 3D environment/exterior/camera were not redesigned here. No FPS gain, user aesthetic approval or perfection is claimed.

Operational state: expected Gate 8000, lab 8888, backend 8001 and office 5173 were freshly checked by All/Review; installed Ollama is separate on 11434. Startup now rejects missing-model assessments with HTTP 503 before changing the session. Backend restart still opens with a waiting active state, although saved snapshots persist. For B inspection the exact completed a16f71f5… snapshot was restored only into waiting state, with no new engagement. Automatic active-session resume remains a limitation; `-RestoreDemo` is specifically the original 7da73508… and must refuse to replace another session. Do not overwrite the current engagement merely to use it. Docker/PentAGI swap and historical PDFs/videos were not re-evaluated in this pass.

**No grounding improvement was demonstrated. Preserve this failure.** The new offline rule evaluation is not a rerun of the live grounding comparison. Next priority: work through the open P0 sidebar/setup/layout/exterior/camera/office tasks in TODO.md with fresh rendered evidence; also address current-session resume deliberately rather than claiming startup automatically restores it.

Published implementation/evidence: `ce459f8ae74cecd864cb4b580a8ee0c62c3e032c`, verified against remote main and a clean downloaded copy. All 26 recorded source hashes matched; the downloaded copy passed 145 Python tests / 46 warnings using the same installed host environment (not a new isolated dependency install). Publication evidence: `eval/reports/planner_outcomes_20261103/publication-verification.json`. The following closure commit changes documentation/evidence only. Unrelated mutable runtime output remains local and was not staged.

## Historical development pass — earlier on 2026-11-03

The user reopened Planner/functionality improvement after publication. This section supersedes the historical “no implementation TODO remains” statements below. Shared qwen2.5:7b weights/configuration remain unchanged: this is prompt, contract-validation and coordination refinement, not model training or a second inference model.

Implemented: explicit per-specialist tool-catalogue coverage (early finish, action budget, denied/untested tools, execution errors and unsuccessful independent verification); exact verified-ID inclusion in the model summary with one governed correction; bounded correction of invalid boundary revisions; rejection of cross-role tool references/blank assignments/unknown plan fields; guard against re-running a finished engine under its old engagement. No Cedar/ROE/taint changes or new execution authority. A completed loop and complete catalogue coverage are now distinct facts.

The actual-model v1 run f7013ffe-9f32-4324-968b-34d04792fd28 exposed wrong-role task descriptions despite correct specialist execution boundaries. Preserve it as pre-correction evidence; its old harness “passed” does not certify semantic assignment correctness. Revised v2 run 28490c2e-4770-4971-89f6-8a7d7bb60786 passed the expanded checks with **2 findings / 29 allowed / 1 denied**, correct assignments, Planner completing last, exact report IDs and explicit untested directory_traversal due to the unchanged three-action Web-App budget. This is incomplete catalogue coverage, not an unsuccessful coordinator hand-off.

Real-Qwen synthetic task-record evaluation: **7/7 structured-contract cases passed first attempt**, zero specialist dispatches, real Gate inference authorization. These are small coordination/ID-set checks, not a general accuracy benchmark; model prose remains generated narrative. Framework grounding efficacy was not re-evaluated. **No grounding improvement was demonstrated. Preserve this failure.**

Actual rendered browser checks covered the Planner coverage disclosure, accurate incomplete-coverage overview, Phase 1 → Option A → saved Option B, actual JSON export preserving coverage, and narrow review; default viewport restored. Original five-seat office/model/tier remain. No new FPS or universal visual-acceptance claim. Final counts, current Go host blocker, evidence and commands: docs/PLANNER_REFINEMENT_2026-11-03.md. The earlier 17/17 result is historical; it must not be represented as today's full-profile result.

**Final current results:** profile planner_refinement_20261103_v3 is **14/17 groups passed, overall failed**: **115 Python tests / 32 retained deprecation warnings**, **28 Rust**, **9/9 adversarial**, TypeScript/build and ten frontend scripts passed; three Go groups are blocked by host Application Control. Exact errors/retry command: docs/BLOCKED.md. Final actual-model engagement **035e7ee6-0a7b-4bfc-84a1-c3e7b51b81ae** returned **2 findings / 29 allowed / 1 denied**, with **142** specialist-active frames preserving Planner working state, correct assignments/report IDs and no Planner tool dispatch. Audit verified **934 entries**. All four application services were reused successfully by Start-Kayan, with Ollama separate.

**Next concrete task:** retry the three Go groups via the normal consolidated command only after the host permits their ordinary executables. The new implementation/rendered/delivery tasks are complete, but that revalidation remains unchecked. Do not change security protections or describe today's full profile as green. Current UI holds final 035e7ee6...; screenshot/export checks used separately preserved v2 28490c2e... . The original 7da73508... recordings/PDF remain dated historical evidence.

Publication: implementation/evidence commit **e90298973b8ea75a84204a0bc50ef3eb1ce8093b** was pushed successfully. The user selected the existing GitHub account in Git Credential Manager; the agent did not operate the authentication dialog. Remote main subsequently matched local documentation commit **0cb7fed4e3e656da009cd18cb51b338b36c3b710**. The final publication-status edit is documentation only. Publication is complete; the only new unchecked task is Go host revalidation.

## Latest verified delivery — final retry, 2026-11-02

**17/17 consolidated checks passed:** 84 Python tests (27 retained warnings), 28 Rust tests, 15 top-level focused Go boundary tests plus the no-embedding case, 9 adversarial cases, production build and ten frontend scripts. Three actual shared-Qwen assessments each returned **2 findings / 29 allowed / 1 denied**. Final engagement: **51bba207-f4eb-4ff5-9228-92566ae06377**, with Planner active through specialists/Reporting and completed last; no specialist tools were dispatched by Planner.

Gate now builds/starts on the normal path. Smart App Control still reports 1; no security setting or bypass changed, and why execution is now permitted is unknown. A final audit serialization defect was reproduced and corrected: all **779 existing entries** verify after a process restart and live run, with the original 703-entry byte prefix unchanged. No old hashes/signatures were repaired. Exact checks, defects, edge cases and limits: **docs/DEMO_READY_2026-11-02.md** and eval/reports/checkpoints/final_todo_validation_20261102_v3/.

Current services: Gate 8000, lab 8888, backend 8001, office 5173, installed Ollama 11434. All-component startup verified/reused the four application services. Use `Start-Kayan.ps1 -Component All` for live operation after starting installed Ollama. Review remains the safe default. The final completed session is now loaded; `-RestoreDemo` deliberately refuses to replace a different session. Historical 7da73508... media/reports and all grounding failures remain unchanged.

All listed TODOs, including GitHub delivery, are checked. Published source/README commit 532a4871769a03013ffb81ffe1f02943388131e6 matched remote main and a fresh downloaded clone. All six current LFS assets passed fsck; the clone passed fresh frontend install/build/ten scripts and 84 isolated-environment Python tests. Five actual README screenshots were inspected on GitHub and decoded successfully. A final documentation-only closure commit follows that tested source. Publication excludes working journal/keys, bytecode, caches and duplicate local exports. Original recovery ZIPs and development history remain local; public main has clean delivery ancestry.

The isolated-install follow-up fixed an unused Jinja template import and declared required multipart/WebSocket dependencies. Both runtime imports and a real WebSocket handshake passed in the fresh environment. README contains review/live commands, screenshots, evidence distinctions, exact results, team and proposal/video links. See docs/GITHUB_DELIVERY_2026-11-02.md and github-verification.json for publication proof.

## Earlier delivery checkpoint — before the successful final retry

The user reopened Planner/functionality work and prioritized a professional doctor-facing UI. That bounded implementation is now built and agent-observed at the requested viewports; the previous rejected layout is superseded. See docs/PLANNER_RELIABILITY_2026-11-02.md and docs/UI_REDESIGN_2026-11-02.md, with raw results/screenshots under eval/reports/planner_20261102/ and ui_redesign_20261102/. Actual latest checks: **83 Python tests passed / 27 deprecation warnings; ten frontend scripts passed, including 13 transport checks and the built-bundle budget; production build passed without the oversized-chunk warning.** Subsequent asset/chunk evidence: docs/ASSET_BUNDLE_VERIFICATION_2026-11-02.md and eval/reports/asset_bundle_20261102/. No new actual-model, Rust/Go or FPS result is claimed.

Planner remains a shared-Qwen coordinator with no new executor authority. It stays active through validated assignments/outcomes/Reporting, handles specialist failures as explicit partial coverage, consumes boundary guidance safely and fails on Reporting/coordination errors. A labeled controlled UI fixture was inspected then removed from the active view; original completed 7da73508.../101 entries restored.

The three-zone console, real stage states, tabbed agent panel, tokens, contrast checks, planning stepper, selection/export, error/empty/loading states and projector mode have bounded rendered evidence. Layout and planning screenshots were shown before detail polish. This is not a claim that every camera angle, device or subjective appearance is perfect. Low outside-wall camera occlusion and before-capture size limitations are disclosed. The normal Reset view recovers the overview.

Both user-supplied Google Drive videos were verified as public viewers and played through. Use **output/pdf/KAYAN_Evidence_Presentation.pdf** for sharing (about 1.1 MB, clickable links); the attachment edition has the same public links plus original MP4s. PDF local-only navigation is removed. Exact URLs/hashes/QA are in docs/proposal/. Older recordings/proposal results remain dated historical evidence.

**Remaining:** host Application Control still blocks the native Gate; a real gated run of the revised coordinator cannot be certified. The earlier FBX compatibility and bundle backlog is resolved by a validated binary migration and production chunk split; this was not a Blender/DCC re-export or a measured FPS improvement. Originals remain backed up inside output/backups/. No security setting or policy bypass was performed. Review mode is running and is now the launcher default; use `Start-Kayan.ps1 -RestoreDemo`. Do not describe the entire TODO file as closed.

## 1. Project identity and earlier checkpoint history

Canonical project: **<REPO_ROOT>\**. This document replaces the previously mixed historical/current handoff. Dated evidence remains in docs/ and eval/reports/; do not erase it or interpret its old paths as current startup instructions.

Implementation, TA mapping, consolidation, Planner reliability, the redesigned interface, public-video PDF, asset/chunk work and live coordinator validation are complete within the documented limits. The final normal Gate retry supersedes the earlier blocked state. Review starts no assessment or model inference. Current exact results and startup details are at the top of this document and in docs/DEMO_READY_2026-11-02.md.

**Next concrete task:** rehearse the existing bounded demo using README and the final readiness document. No listed implementation or publication TODO remains open. Original 7da73508... recordings remain separate from the final new live assessment; preserve both. Future work must respect the disclosed production/Go/grounding limits rather than relabel them as completed capabilities.

## 2. Project locations and consolidation

- All active source now lives in kayan-trustgate, including the sole frontend at `console/office/`.
- Historical 3D location: `<LOCAL_USER>\Downloads\KAYAN-video\kayan-company-office\kayan-3d\`. It is not an active source/startup location. The consolidation record reports its children retired; that historical absence was not rechecked in this pass.
- Previously two repos communicating over HTTP/WebSocket, the components now share one canonical repository while retaining separate processes and those runtime interfaces.
- Pre-delivery baseline HEAD was `29e72b6`; the final tested source/evidence has its own publication commit. Do not stage current private keys, mutable runtime journals or unrelated outputs wholesale.
- `pentagi_upstream/` contains vendored Go backend source and licensing, not an upstream frontend or Git submodule.
- Recovery location recorded in `docs/PROJECT_CONSOLIDATION_2026-11-02.md`: `<LOCAL_USER>\Downloads\KAYAN-recovery-2026-11-01-consolidation\`, including history bundles, patches and retired source. Its current contents were not inventoried again here.
- KAYAN-video's Remotion/video project and old sibling `server/` are unrelated to the current runtime. Do not modify them as part of TrustGate work.

Folder retirement advice was given, not executed: other KAYAN folders are not active runtime dependencies, but old video/planner work, recovery copies and two unused CEO FBX variants can be unique. Back them up before discarding. Four used FBX source files were previously hash-matched to physical copies in `console/office/public/models/`. No deletion was performed by that advice or this documentation pass.

## 3. Pivot and actual architecture

KAYAN is a TrustGate-governed autonomous pentesting platform for a bounded owned lab: signed Rules of Engagement, Rust/Cedar authorization, local-model agents, independently reproduced findings, a live 3D operations console and offline planning/mitigation. The clarified security-testing direction replaced the original sales-agent concept; old sales material is abandoned context, not implementation guidance. Python remains the primary demo engine. The Go/PentAGI work is a scoped enforcement evaluation, not a completed autonomous runtime replacement.

Directory contents below were listed in this pass. Working status refers to retained dated verification, not a new execution test.

| Directory | Actual contents / technology | Current status |
|---|---|---|
| trustgate/service/ | Rust/Axum/Cedar gate, ROE, authorization, taint and audit implementation | Final native build/start, 28 Rust tests and full-journal restart verification passed |
| pentagi/ | Python agents, live_engagement.py, ollama_client.py, bounded lab_tools.py, call/inference context, engagement_context.py, standalone risk_plan.py; deterministic orchestrator.py baseline | Implemented and previously exercised; no fresh model run this pass |
| pentagi_upstream/ | Go backend/, local Docker profiles, vendor/license notices and licenses/ | Scoped comparison complete; autonomous delegation/completion limitations remain |
| integration/ | Python gate/ROE/bridge clients, signed binding, local Docker helper and executor_patch/ | Implemented; previous scoped evidence retained |
| lab/ | FastAPI vulnerable_app.py, reset.py, fixtures/, services/ | Owned intentionally vulnerable target; not started/rechecked in the latest Review pass |
| console/backend/ | Python FastAPI sessions, live/operator API, WebSocket and offline planning API | Responding on 8001; Planner session findings, planning and read-only gate availability are checked |
| console/office/src/ | React 18, TypeScript, Vite 5, Three/R3F/drei, Zustand; agents, transport, scene/UI, audit, workflow, profiler | Sole frontend on 5173; new three-zone/stepper/tabbed UI has bounded current rendered evidence |
| grounding/ | Python build_index.py/retrieval.py, flat index.json, licenses/ | Local ATT&CK + OWASP TF-IDF grounding; effectiveness gain not established |
| skills/ | Curated recon/web-app/network/reporting packets, library_index.json and license | Reference context, not executable authority |
| eval/ | Checkpoint, runtime, coverage, scope, manual fixture, TA and Go evidence harnesses plus reports/ | Historical results retained; no suites rerun here |
| docs/ | Architecture, blockers, per-step acceptance, consolidation, TA mapping/proposal, proposal builders and roster | Canonical evidence/navigation records |
| config/ | Local inference, model tiers and integration configuration | Shared authorized local model; see below |
| reports/, output/ | Saved reports, proposal PDFs, portable presentation ZIP and separate MP4 exports | Files present; delivery details below |

Retired from active source: redundant 2D frontend, Python authorization prototype, upstream UI/dev extras and unused business/mock frontend paths. Do not restore their startup instructions (Gradio/7860 or old 2D/5174).

**Model configuration checked now:** `config/llm.json` uses local Ollama `qwen2.5:7b`, concurrency 1, context 4096, prediction budget 384; declares `qwen2.5:1.5b` fallback. `config/model_tiers.json` maps A/B/C to the same authorized 7B. This follows later authorized model selection, superseding the earlier placeholder requirement. Tier labels still control capability/context budgets. There is no separate helper inference model and no fine-tuning experiment. Do not represent Planner as a second model. TA Option A/B (mitigation paths) are distinct from the older model-architecture Option A terminology.

## 4. Implemented behavior and TA requirements

The dated architecture, TA alignment and acceptance records establish:

- Five roles/seats: Planner, Recon, Web-App, Network, Reporting. Recon/Web-App/Network form Red Team; Reporting forms Blue Team; Planner coordinates.
- Signed scope/action/target/time checks; bounded lab tools; recorded allow/deny audit references and independently reproduced supported findings.
- Session endpoint `GET /agents/{agent_id}/session?engagement_id=...`, current task, transcript/findings and initial plus subsequent WebSocket updates. Detail panel has collapsible raw entries, tier badge, allow/deny styling and findings with MITRE tags.
- Governed operator interaction: **status live; task-changing instructions queued at safe boundaries**. Serialized inference may queue status work too; completed agents reject new instructions.
- In-scene screens show actual task/activity/tier. Monitor front/rear, selection, support-neck black patch, labels, narrow layout and Reset corrections have dated rendered evidence. Geometry checks alone do not establish rendered acceptance.
- Six optional organization-context fields are descriptive only and carry **zero policy weight**.
- Phase 1 creates hypothetical risks through local retrieval, without model/tool/target/gate calls. TA Option A passes hypotheses into Reporting's deterministic mitigation builder, without live findings or testing. TA Option B derives mitigation from a saved/live governed assessment.
- Defense in Depth/Zero Trust grouping, selection/export and additive illustrative effort points are presentation features, not real prices or validated estimates.
- All six proposal sections exist in `docs/TA_PROPOSAL_REPORT.md`: architecture, inputs, deliverable flow, Blue Team/pricing, training/framework evaluation, future work. Literal training and a distinct helper model are disclosed substitutions, not completed original requirements.

Primary explanations: `docs/ARCHITECTURE.md`, `docs/TA_DELIVERABLES_ALIGNMENT.md`, `docs/TA_PROPOSAL_REPORT.md`. Source/runtime/security boundaries were not changed for this handoff update.

## 5. Evidence and verified-versus-historical results

**Latest functional/UI results are listed above and were freshly executed.** The older test/engagement/grounding results below retain their dates; these comparisons, Rust/Go suites and FPS samples were not rerun in the redesign pass.

- `eval/reports/checkpoints/consolidated_20261101_v1/results.json`: 14 groups passed on 2026-11-01; Rust 20, Python 46, focused Go 15 top-level, embedding-none, frontend/transport/session/TA/audit/geometry/picking/text/metrics and 9/9 intended adversarial denials. File inspected now; it is not proof a fresh Rust build currently succeeds.
- Recorded real rehearsal `7da73508-01e6-48e9-9093-be09c5fd734d`: **2 findings / 29 allowed / 1 denied**, with deliberate tainted-input test and 101 saved transcript entries. No fresh run created for the final three-path video.
- Separate actual-model UI acceptance run `546daa0c...`: 2/25/0, reconciled in the closure review; it is not the standard tainted-input rehearsal, grounding comparison or final video source. Excluded from formal proposal comparison.
- Original grounding v1: off 1/23/1, on 0/23/2; coverage 20% versus 0%. Python v2: both 2/29/1, 40% five-label lab coverage, legacy evidence precision 50%, fresh-nonce reproduction 100%. Scoped Go: 3/19/15 including three verifier allows (Go-only 16/15), 40% coverage, legacy precision 33.33%, reproduction 100%; flows waited after worker failures. These are not general classification accuracy or causal engine comparisons.

**No grounding improvement was demonstrated. Preserve this failure.** Do not soften the original regression, replace it with equal v2 outcomes or invent training-time/mitigation-effectiveness figures.

Detailed sources: `eval/reports/live_grounding_comparison_v2_bounded_retry.md`, `eval/reports/pentagi_go_comparison_2026-11-01.md`, original comparison artifacts and `docs/FUNCTIONALITY_CHECKPOINT_2026-11-01.md`.

**Rendered acceptance:** the twelve original steps are individually recorded in `docs/CLOSURE_EVIDENCE_REVIEW_2026-11-01.md`, with screenshots, timestamps, IDs, discrepancy/recheck status and limits. `docs/ACCEPTANCE_2026-11-01.md` retains full observations. Original ALLOW screenshots did not measure the roughly-two-second criterion; later bounded rendered task-start was within 916.031 ms, as recorded in `docs/TA_MEETING_READINESS_2026-11-01.md`. No universal pixel/result latency guarantee. Desktop sizes differ between distinct passes; do not merge them into one viewport claim. Historical browser permission denials were resolved through legitimate access, not a bypass. No fresh rendered acceptance occurred here.

Historical performance and intermediate regressions remain in `eval/reports/performance/README.md` and `docs/VISUAL_FEEDBACK_2026-11-01.md`. Do not attribute old samples to a new render/build or treat user spot feedback as a complete new checklist.

## 6. Delivery files, team and public video links

| File relative to root | Purpose / status |
|---|---|
| output/pdf/KAYAN_Evidence_Presentation.pdf | Preferred sharing copy: twelve pages, about 1.1 MB, two clickable public Drive links, original proposal and evidence appendix; no MP4 payloads |
| output/pdf/KAYAN_Evidence_Presentation_With_Videos.pdf | Same linked pages plus both hash-checked original video attachments, about 79.9 MB; inline PDF playback is not required/claimed |
| output/pdf/KAYAN_TrustGate_Proposal.pdf | Original eight-page proposal retained unchanged |
| output/packages/KAYAN_Offline_Presentation.zip | Extract fully and open index.html for loose local-video playback; includes the sharing PDF; presentation package, not a full source backup |
| output/videos/KAYAN_Three_Path_Demo.mp4 | Original separate MP4 export; 1,497,340 bytes / 35.44 seconds |
| output/videos/KAYAN_Recorded_Live_Assessment_7da73508.mp4 | Original separate rehearsal export; 77,261,135 bytes / 69.966633 seconds |
| console/office/public/review.html and review/ | Local review page, videos, saved report, evidence, manifest and identical served sharing PDF |
| docs/proposal/build_review_export.py | Rebuilds both PDF editions and portable ZIP; reads video_links.json |
| docs/proposal/review_export_verification.json | Current hashes, actual URI annotations, video attachment/ZIP validation and render/browser QA |

The original localhost-click failure is resolved in the new PDF navigation. The first supplied URL opens KAYAN_Three_Path_Demo.mp4; the second initially required sign-in, then after the user update opened KAYAN_Recorded_Live_Assessment_7da73508.mp4. Both public players reached their displayed ends. Public viewer access and filename/playback identity are verified; remote byte hashes were not downloaded/verified. Drive's rounded/transcoded player durations do not replace local metadata. Do not claim the TA has watched them. The PDF explicitly dates the older recorded interface separately from the new UI.

Confirmed roster in docs/proposal/students.json (all Cybersecurity; Eslam excluded): Khaled Mohamed 20231160; Youssef Montasser 20236209; Ahmed Ali Moustafa Badawi 20230524; Mahmoud Ahmed Fathy Ashry 20230249; Talal Yousif Norelhuda Elhag 20236211. All five names/IDs remain in the original proposal pages.

Historical delivery/frozen-review ZIPs in Downloads are not current source backups. No deletion was performed. Do not publish ignored keys, tokens, runtime data or the recovery folder wholesale.

## 7. Resolved blockers and retained architecture limits

The earlier native-blocker entry below is historical and was superseded by the final successful build/start and real coordinator/audit validation. There is no current native-Gate delivery blocker in the final observed pass. Current readiness is bounded to the owned lab, not the wider production capabilities excluded in item 5.

1. **Resolved: remote PDF video links.** Both public viewers and clickable PDF navigation are checked; use the small sharing edition.
2. **Resolved on final normal retry:** earlier native execution failed with `An Application Control policy has blocked this file. (os error 4551)`. The exact prior events, logs and unsuccessful retries remain in docs/BLOCKED.md. Final native build/start, 28 Rust tests and real coordinator validation succeeded without protection changes; Smart App Control still reports 1 and its changed execution behavior is unexplained. Whole-journal verification now passes after the audit ordering fix, with original bytes retained.
3. **Review and live lab available:** final startup verified/reused all four application services, and actual inference used installed qwen2.5:7b. Review alone still does not start lab/model/Gate. The current session is the final new completed assessment, separate from the historical recorded demo. No current browser permission blocker was encountered.
4. **Resolved after scope reopened:** four active FBXs were conservatively reserialized to the loader-equivalent top-four normalized influences, removing only ignored map connections. Original bytes are backed up; loader equivalence, payload identity, regression tests and rendered production close-ups passed. Production chunks now remain below the unchanged 500 kB limit. See docs/ASSET_BUNDLE_VERIFICATION_2026-11-02.md for exact counts, tradeoffs and limits; no DCC re-export or universal animation-fidelity claim.
5. **Disclosed architecture limits, not completed tasks:** Go delegation/worker completion and per-model-call parity; completion-triggered ROE revocation; production human identity, runtime isolation and immutable audit storage. Raw model narrative is not verified evidence. Caller provenance/general semantic taint propagation is not universally proven. Audit is mutable local hash-chain/HMAC storage. Single shared model is a disclosed TA design substitution; no trained helper or measured training comparison.

Last retained Go adapter error (historical, not retried here):

```text
failed to exec function 'subtask_patch': reached max retries to call function: TrustGate/adapter refused: Tainted arguments detected: ["execution_args", "target"]
```

Docker was previously restored with `docker desktop start --detach`; existing `kayan-pentagi-local` used 127.0.0.1:8443 -> 8080. Current Docker daemon/container state was not checked here; no listener appeared on 8443. Last missing-pipe and worker errors remain exact in `docs/BLOCKED.md`. Do not claim an active Docker swap or grant raw shells to make failed workflows pass.

Blender inquiry was closed by the user's explicit instruction to skip; no verified download/purpose or asset re-export should be inferred.

## 8. Reproduction / recovery commands

Run from `<REPO_ROOT>`. Review/default startup was exercised. Default Component is now Review, not All. The launcher verifies expected HTTP identity before reusing a listener and waits for readiness after launching; it never stops an unrelated owner. Gate retry remains conditional on normal host controls. Lab commands are retained source-checked examples, not a claim the lab was restarted this pass.

```powershell
Set-Location <REPO_ROOT>
# If dependencies need installation:
python -m pip install -r requirements.txt
npm --prefix console/office ci

# Recorded review / planning, without starting gate, lab, model or assessment:
.\Start-Kayan.ps1 -Component Review -RestoreDemo
# http://127.0.0.1:5173/review.html or http://127.0.0.1:5173/

# Individual components:
.\Start-Kayan.ps1 -Component Backend  # 8001
.\Start-Kayan.ps1 -Component Office   # 5173, strict port
.\Start-Kayan.ps1 -Component Lab      # 8888

# Gate retry ONLY after normal host controls permit it:
cargo build --offline --manifest-path trustgate/service/Cargo.toml --target-dir .build/rust
.\Start-Kayan.ps1 -Component Gate     # 8000
```

`-RestoreDemo` loads only original completed `7da73508...` into a waiting backend, leaves an identical completed session alone and refuses an active/different session. Saved source: `eval/reports/checkpoints/ta_meeting_20261101_preflight/before-state.json`. It starts no assessment. Start Ollama separately for authorized live work (11434); review does not need inference.

Equivalent lab/backend commands, from project root:

```powershell
python -m uvicorn lab.vulnerable_app:app --host 127.0.0.1 --port 8888
python -m uvicorn console.backend.main:app --host 127.0.0.1 --port 8001
npm --prefix console/office run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Optional Go diagnostics (not executed this pass): `docker version`; `docker ps -a`; `docker logs --tail 35 --timestamps kayan-pentagi-local`. Do not auto-create a new flow during presentation recovery. No cloud keys or Docker TCP exposure are needed for the retained local profile.

For later regression, use `python -B -m eval.functionality_checkpoint --label UNIQUE_LABEL` and frontend scripts in `console/office/package.json`. Resolve environmental prerequisites first. The final current profile passed; the old native failures remain historical. Pixel acceptance and measured FPS require their own observations; suites cannot substitute for them.

## 9. Rules for the next agent

- Public-video delivery, bounded UI, asset/chunk work and actual live-coordinator/audit-restart validation are complete. Use the final readiness document and preserve older checkpoint failures as history.
- The latest user explicitly authorized Planner/functionality fixes and the professional UI redesign. Keep those bounded to their current TODO acceptance criteria; no new agents, policy/model redesign or unrequested fresh final-demo engagement.
- **2026-11-20 override:** the user subsequently requested the additive cloud/parallel `ai/` layer and still wants ATT&CK STIX training. The newest section at the top of this handoff and `docs/AI_TRAINING_CONTINUATION_2026-11-20.md` now define the next work; the older "no new agents/model redesign" limit applies only to the legacy 3 November scope, not to the documented AI experiment.
- Do not call the project perfect, universally tested, production-ready or improved by grounding. Report the actual unchecked count and bounded owned-lab readiness separately from disclosed architecture limits.
- Do not touch unrelated Remotion/video or legacy server/, resurrect archived sales handoffs, or use historical external office paths as dependencies.
- Do not bypass Windows/browser policy, expose Docker TCP, choose cloud credentials or broaden tool authority to remove a failure.
- Do not delete source, historical evidence, unique old assets or recovery material without the user's explicit deletion scope and checked backup boundaries. The previous keep/delete list was advice only.
- Preserve raw failures, negative grounding results, exact audit/result shapes, per-step acceptance limits and original artifact hashes. No new result number without a fresh run or an explicit historical label.
- Do not commit private keys/runtime tokens or unrelated mutable audit outputs. Check git status before staging.
