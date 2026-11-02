# Final demo-readiness verification — 2026-11-02

The reopened Planner, functionality, interface, media-link, asset and bundle TODOs are implemented and checked. GitHub publication is tracked separately until its remote commit is verified. This is owned-lab demo readiness, not unrestricted pentesting or production-security certification.

## Final checks

`eval/reports/checkpoints/final_todo_validation_20261102_v5/results.json` records **17/17 checks passed**: 84 Python tests (27 retained deprecation warnings), 28 Rust tests, 15 top-level focused Go boundary tests including the actual Cedar profile, 15 top-level Go config tests, the explicit no-embedding provider case, 9/9 adversarial cases, TypeScript/production build and ten frontend scripts. The bundle-budget check runs after its production build, so stale chunks cannot establish a pass. This is the defined project verification profile, not every upstream Go test or every possible edge case.

Covered failure/edge cases include invalid specialist order/roster, bounded model recovery without invented fallback, specialist failures and partial Reporting coverage, Reporting/route failures, safe-boundary guidance, reconnect exhaustion/recovery, port collisions/false readiness, absent or invalid descriptive context, offline planning without execution authority, unknown tools, out-of-scope and expired ROEs, untrusted arguments and impersonation. New audit cases cover recursive key order, Unicode/nested payloads after reload, original insertion-order records, changed payloads, invalid signatures, unknown fields and malformed JSON.

## Real local-model runs

All used the unchanged shared `qwen2.5:7b`, actual signed ROEs, Rust/Cedar, owned loopback lab tools, HTTP and WebSocket. No model, tool or gate mock was used.

| Label | Engagement | Findings / allowed / denied | Status |
|---|---|---|---|
| planner_final_live_20261102_v1 | e8218896-2e19-416a-98a8-f9de35e70c28 | 2 / 29 / 1 | Coordinator passed; transcript punctuation defect observed afterward |
| planner_final_live_20261102_v2 | f5cc9c9c-9653-4416-b854-95bfb20dcabe | 2 / 29 / 1 | Corrected punctuation and coordinator passed; whole-journal hash-order defect subsequently found |
| planner_final_live_20261102_v3 | 51bba207-f4eb-4ff5-9228-92566ae06377 | 2 / 29 / 1 | Final run after audit fix; journal verification passed before and after |

Counts exclude ROE load and include the deliberate tainted-input DENY and governed operator status/instruction checks. They do not establish broader detection accuracy. Findings were fresh-nonce harness reproductions; XSS browser execution was not independently tested. Each run has its own immutable result/state/observer files. Original `7da73508…` reports, videos and all grounding comparisons remain historical, unchanged evidence.

The final observer captured **151 specialist-active frames** with Planner still working. Assignment order was Recon → Web-App → Network → Reporting; all three specialist outcomes completed, Planner completed last, incremental model output was observed, and Planner dispatched no specialist tools. Its audited actions remained inference/message coordination. These transport observations are not pixel timing measurements.

Rendered inspections showed Planner Tier A, shared Qwen, the completed hand-off, chronological assignments/outcomes and specialist-owned findings. The first live tab's accessibility state showed working Planner with working Reporting; its full scene was still loading then, so it is not claimed as a screenshot proving live monitor text. Earlier real-rendered UI and explicit controlled-fixture monitor inspections remain separately labeled in the redesign evidence. Current saved Option B resolves to the final engagement and retains its complete coverage metadata. No new final-demo recording was substituted for the original films.

## Two final defects preserved and fixed

The transcript separator was literally garbled in generated authorization text. Its focused Python test failed before the source correction and passed afterward. The correction affects newly generated text; old transcripts were not rewritten. See `text-regression-before.log` / `text-regression-after.log` under `eval/reports/final_todo_retry_20261102/`.

The initial whole-journal endpoint returned:

```json
{"valid":false,"broken_at":0,"message":"Hash mismatch at entry 0: tampering detected"}
```

Independent byte-hash checks found 82 records matching sorted-key JSON and 621 matching insertion-order JSON, with none matching neither. The verifier's serialization was order-dependent. The fix makes new hash inputs recursively key-sorted and retains exact original parsed payload order for authenticated historical verification. `serde_json` preserve-order parsing is explicit for that legacy path; arrays retain order. Legacy acceptance still requires the stored signature, exact stored hash and payload equivalence to the typed record. Unknown or unreadable records cannot silently become valid empty history. Cedar, ROE capability evaluation, taint decisions and agent authority were unchanged by this audit-only correction.

No old entry, hash or signature was repaired or deleted. A byte-identical pre-fix journal backup remains local at `output/backups/audit-before-canonical-fix-20261102.jsonl` (not uploaded). Its 553,627-byte prefix, SHA-256 `10aea34eefec032c62b8a33233a5b62da41475573d93ba1fd409a3ec0935e064`, remained unchanged. After checkpoint appends and a real service restart, verification passed for 718 records; after the final engagement it passed for all **749**. The subsequent complete publication profile ended with **779** entries verified; see publication-audit-verification.json. Full before/after evidence, a corrected initial Rust compile error and regression logs are retained. This does not make local mutable storage immutable or remove the existing development-key/production-hardening limitations.

## Startup and former Windows blocker

The normal offline Cargo retry and `Start-Kayan.ps1 -Component Gate` succeeded. The same read-only Smart App Control registry check still returned 1; no Defender exclusion, protection change, alternate build location or execution bypass was used. Why Windows permitted the new attempt is not established. Earlier error 4551 remains preserved; current success is not a promise about future host decisions.

`Start-Kayan.ps1 -Component All` subsequently verified/reused Gate 8000, lab 8888, backend 8001 and office 5173. Installed Ollama serves 11434; its installed 7b model was selected in every run. The launcher starts no assessment. For live use, start installed Ollama separately, then run All. Review remains the safe default. `-RestoreDemo` is for the original recorded session in a waiting/already-matching backend; it deliberately refuses to overwrite the different final completed session now loaded.

## Delivery boundaries

The linked sharing PDF retains all five confirmed students, public video links and dated proposal/evidence content. Original recordings remain 1 November artifacts. FBX compatibility and production chunks have their own bounded checks and preserved failures; total JavaScript grew slightly despite smaller independently cacheable chunks. No FPS or grounding benefit was invented.

Current publication omits local runtime keys/journal, bytecode, build/dependency caches and duplicate recovery/delivery exports. Original asset recovery ZIPs remain local; previous source LFS pointers are retained in Git history. The vendored upstream example/test credentials and instructional skill examples were distinguished from local provider credentials during the bounded pattern review. It was not a comprehensive secret-detection guarantee.

The publication check also made the original-FBX payload assertion portable: committed fingerprints were independently generated from the preserved original archive and matched against all four active assets. This test no longer skips when temporary candidates/backups are absent. The full Python suite was re-run afterward: 84 passed, 27 retained warnings. The application's tested behavior was unchanged.

The first GitHub push was rejected by push protection for Google OAuth-shaped strings in a vendored test fixture in the old history. The two values were changed to nonfunctional test placeholders, without changing the configuration/runtime implementation. Original development history stays local in a recovery branch/bundle; publication uses a clean initial snapshot. No scanner override or force push is used. The affected full Go config package is included in the final publication profile.

That newly included package initially failed because consolidation had removed the upstream Compose input used by TestConfig_EveryVariableReachesTheContainer. Two pre-consolidation recovery copies matched byte-for-byte. Their exact 13,742-byte template (SHA-256 b7d4eb6a4ee4b607e41874e2121352bd46068156376b9b4b38fedfbc9c946305) is restored under pkg/config/testdata and the test reads it there. It is not an active deployment. All 15 config tests passed with zero skips. The failed v4 profile remains preserved; the final v5 profile passed 17/17.

## Fresh-download and README follow-up

The clean public snapshot a542f8a was cloned from GitHub into a separate temporary verification directory. Its six current LFS model/video objects were downloaded from the remote and passed Git LFS fsck. Fresh npm ci, production build and all ten frontend scripts passed there; this did not substitute for the separately recorded real-model/pixel observations.

A new isolated Python environment installed the original declared requirements and exposed a real bootstrap failure: `ImportError: jinja2 must be installed to use Jinja2Templates`. The lab never uses that imported template helper, so the unused import was removed. Required form parsing and WebSocket packages were explicitly declared at the exercised versions, python-multipart 0.0.32 and websockets 17.1. The isolated environment then imported the lab/backend without Jinja installed, connected to the real console WebSocket, and passed all 84 Python tests (28 warnings in that environment, versus 27 in the main profile). Before/after evidence is retained in fresh-setup-before.json, fresh-setup-verification.json and fresh-environment-python.log.

README now includes five inspected actual UI screenshots, captured on 2 November from the final real session and explicitly hypothetical planning sample. No mockup or generative retouching is used. File hashes and dimensions are in readme-screenshots.json. A failed region-capture attempt was replaced by complete viewport captures before publication. Setup/review/live instructions, evidence labels, validation links, team names and proposal/video access were refreshed.

No grounding improvement was demonstrated. Preserve this failure.
