# Project consolidation — 2026-11-02

All active source is now under **C:\Users\khale\Downloads\kayan-trustgate\**. The frontend is `console/office/`; its dependencies are physically installed there, not linked to KAYAN-video. The former `kayan-company-office/kayan-3d/` contains no files. Runtime components still communicate through HTTP/WebSocket. This is source consolidation, not a new policy architecture.

## Retained

Rust/Cedar service; Python agents and bounded lab tools; console backend; prepared 3D geometry and all four FBX files; live session/operator/planning/reporting controls; local ATT&CK/OWASP and skill references; tests; scoped Go backend; third-party licensing; curated positive/negative evidence; local ignored keys/sessions; and the verified eight-page proposal PDF with five confirmed students.

The Go backend is native vendored source rather than a gitlink. Its original LICENSE/EULA/NOTICE/contributors/licenses directory and both local backend Docker profiles remain. No Cedar/ROE/taint, live Python agent or Go enforcement/worker logic was changed.

## Retired from the active project

- The redundant 2D frontend and Python authorization prototype/unused policy JSON fixtures.
- Forty-four unneeded frontend source/check/scratch files, identified from the TypeScript dependency graph: old company onboarding/tasks, business mock workflows, old transport/experiments and their unused UI/code paths. No simulated fallback remains in the live frontend.
- Unused upstream frontend, examples, observability/editor/CI files and obsolete root baseline outputs.
- Untracked scratch captures and temporary PDF renders. Curated inspected evidence, original failure reports and the final PDF remain.

The bounded retirement manifest records **1,671 moved items** (some are directories). This is not a claim that 1,671 independent source files were removed. Frontend dependency pruning has its own 44-file manifest. Caches/dependencies needed locally remain ignored rather than being included as source.

AUDIT now displays the real console transcript, role filtering, actual backend audit IDs, collapsed raw entries and complete JSON export. It does not authorize operations or verify the backend audit chain. The previous broad business-event audit UI was retired with its dependencies.

## Recovery

**C:\Users\khale\Downloads\KAYAN-recovery-2026-11-01-consolidation\** contains pre-change project/office copies, three Git-history bundles, saved index/working patches, dependency-pruning and retirement manifests, and retired files. Private runtime material in that local backup must not be published. Root history and the old shared office Git metadata were not deleted. Remotion, sibling old `server/` and abandoned handoff contents were not edited or imported.

Windows initially blocked moving the old office directory itself because a process held it open. Its children were then moved individually to `retired-active-office/`; the old directory is empty. No unrelated process was killed and no directory outside the checked source/recovery boundaries was removed.

## Verified results

`eval/reports/checkpoints/consolidated_20261101_v1/results.json` records **14/14 groups passed** at 22:35 Cairo on 2026-11-01: Rust 20, Python 46, focused Go 15 top-level including real Cedar, embedding-none, frontend build/transport/session/audit/TA/geometry/picking/text/metric checks, and 9/9 intended adversarial denials. This dated result is not a claim that a fresh native build succeeds under the current Windows policy.

On 2026-11-02, the relocated frontend and console/lab endpoints returned HTTP 200. The real WebSocket check recovered original completed engagement `7da73508-01e6-48e9-9093-be09c5fd734d`, five agents and **101 entries**. Direct browser inspection confirmed Web-App selection, office rendering, the audit's 101 entries, a 38-entry Web-App filter, and export retaining all 101 entries. Saved Option B loaded without a new assessment. Browser error-level log returned no entries. Screenshots/metadata: `eval/reports/consolidation/2026-11-02/`. The four FBX hashes match their pre-consolidation copies.

The original 2/29/1 saved result and grounding comparisons were not rerun or replaced. No fresh actual-model engagement, grounding improvement, FPS gain, FBX fidelity fix or full Go replacement is claimed. **No grounding improvement was demonstrated. Preserve this failure.**

## Current runtime blocker

Rust startup/fresh build is blocked by Windows Application Control. Both cached build locations first produced `error[E0463]: can't find crate` diagnostics. A fresh project-local target then failed executing generated build scripts with:

```text
An Application Control policy has blocked this file. (os error 4551)
```

The previously built executable was also refused by the same policy. Gate port 8000 was unavailable in the current check. The relationship between earlier cache diagnostics and this policy was not independently established. No policy bypass, alternate execution platform or security-setting change was attempted. Full clean-build output is retained in `rust-clean-build.log`.

Retry after the machine permits the trusted build/runtime through its normal controls:

```powershell
cargo build --offline --manifest-path trustgate/service/Cargo.toml --target-dir .build/rust
.\Start-Kayan.ps1 -Component Gate
```

For the working offline review path, use:

```powershell
.\Start-Kayan.ps1 -Component Review -RestoreDemo
```

This starts/reuses the backend and 3D viewer and loads the actual saved completed demo only into an empty waiting session. It refuses to replace an active/different session. The command was exercised against the current completed session and left it intact. It starts no assessment. Ollama and optional Go/Docker availability are not established by this review-mode check; neither is required for offline planning or viewing saved results. Live governed execution cannot be called ready while the gate is unavailable.

## Remaining scope

Source consolidation and proposal preparation are complete. Gate build/startup remains an explicit environment blocker, requiring an external policy change by the machine's owner/administrator. Deferred FBX/bundle work and the previously disclosed Go delegation, completion-revocation and production-security limitations remain open. The dated delivery archives were not opened or repackaged.
