# Asset compatibility and production chunks — 2026-11-02

**Later final runtime status:** normal Gate startup and actual coordinator validation passed. Final profile: 17/17 checks (84 Python, 28 Rust, focused Go/Cedar, adversarial and frontend). Audit ordering was corrected with old bytes preserved; all 779 entries verify. See DEMO_READY_2026-11-02.md. Earlier blocked statements below are historical.

The user reopened all TODOs after the earlier freeze. This pass addresses the two previously deferred compatibility/packaging items; it does not reopen agent authority, model choice or grounding claims.

## FBX: reproduced, migrated and checked

The original four active models produced the literal warnings preserved in `eval/reports/asset_bundle_20261102/before-browser-log.json`:

```text
THREE.FBXLoader: %s map is not supported in three.js, skipping texture. ShininessExponent
THREE.FBXLoader: Vertex has more than 4 skinning weights assigned to vertex. Deleting additional weights.
```

`scripts/normalize_fbx_assets.py` performs bounded binary FBX 7.5+ reserialization. It first requires an exact original-byte round trip. It preserves all other source property bytes, including embedded textures, vertices and animation. It removes only the already-ignored ShininessExponent connections, and stores the same stable top-four normalized influences that the current loader already displayed. This is a compatibility migration, **not a Blender/DCC re-export, restored lost influences or improved authoring claim**. No replacement character or software installation was used.

Original files are recoverable inside the canonical project: `output/backups/pre_normalized_fbx_20261102.zip`. The archive was reopened and all four originals matched their before-SHA256 values before active files were replaced. Before/after hashes and per-file counts are in `eval/reports/asset_bundle_20261102/normalization.json`. Keep the backup. The four originals contained 195 / 234 / 306 / 878 vertices with more than four stored influences, respectively for AIManager / AIOps / AISales / Employee. Each had one ignored map connection. These are source-data counts, not findings or new performance measurements.

Independent validation uses the actual `three-stdlib` FBXLoader used by Drei (`console/office/scripts/validate-fbx.mjs`). It checks all expanded geometry arrays, groups, bone order/inverse bind matrices, effective per-vertex weights, material colors/map presence, and all animation track times/values. Sampled deformed positions agree at 0, 4, 8 and 16 seconds (every 23rd expanded vertex, tolerance 0.00015 source units). All four candidates parsed with **zero loader warnings**. The Node check stubs texture decoding; it does not claim to render textures. Separate Python checks compare every untouched property payload, including the embedded texture bytes.

The production browser then loaded the active files, rendered all five workstations, and showed textured, seated Planner/Web-App/Reporting actors at close range. No new missing-texture, pose or joint discrepancy was observed in those views; this is bounded inspection, not every joint at every animation instant. The fresh production tab's warning/error log was empty. Original warnings and earlier imperfect views remain evidence, not erased history. Ordinary pan/zoom and Reset view were used; the overview recovered correctly. The prior development tab's accumulated log contains historical warnings across reloads, so it was not mislabeled as a fresh clean log.

## Bundle: smaller chunks, explicit tradeoff

Reproduced baseline build: one 1,120.61 kB JavaScript bundle (314.94 kB gzip) and the >500 kB warning, retained as `build-before.log` in the evidence folder.

`console/office/vite.config.ts` uses the installed Three 0.170.0 public source entry for every bare Three import. Pure shader strings and math/constants have separate chunks; executable engine, React, other office runtime and application code have stable independent cache boundaries. No dependency version, package installation, renderer feature or warning threshold changed.

Final production output (decimal kB, Vite display):

| Chunk | Minified kB | Gzip kB |
|---|---:|---:|
| Application | 76.67 | 23.41 |
| Three math | 80.18 | 23.78 |
| React | 145.96 | 47.12 |
| Shader strings | 157.24 | 33.70 |
| Office runtime | 208.82 | 67.88 |
| Three engine | 476.70 | 130.31 |

All chunks are below the unchanged 500 kB warning limit; the final build emits no oversized-chunk warning. Total JavaScript is **1,145,652 bytes**, slightly larger than the baseline due to source/module boundaries. This improves chunk/cache separation, **not total-download size, FPS or measured load time**. No such speed claim is made. `npm run check:bundle` checks the actual built files, the 100 kB application-entry budget, vendor identities and 500 kB per-chunk budget. Earlier intermediate splits still exceeded the limit; the final raw build log contains the accepted result.

## Production UI checks and exact suites

The agent-owned development server was replaced temporarily by Vite preview at the same authorized origin, `http://127.0.0.1:5173/`, to exercise actual production chunks. Screenshots and an empty warning/error log are under `eval/reports/asset_bundle_20261102/`. At 1280Ã—720 the production build rendered the office, selected Planner/Tier A/shared Qwen, displayed two coordinated findings with original specialist ownership, generated the sample's three hypothetical risks and Option A's three recommendations/four illustrative points, loaded saved Option B's two findings/two recommendations/six points, and exported its review selection. Audit displayed the original 101 transcript entries, including its tainted-input DENY. No fresh assessment or model inference was started by these actions. The saved run remains historical, not validation of the revised coordinator.

After checking production, the normal `Start-Kayan.ps1 -RestoreDemo` development launcher was restored and verified: backend reuse, office ready and original completed session already loaded. A production preview was a verification method, not a new launcher default.

Final suites: **83 Python tests passed, 27 retained deprecation warnings; ten frontend scripts passed, including 13 transport checks and built-bundle budgets.** TypeScript/production build passed. Exact raw logs, script names, runtime snapshot and export are in the evidence folder. Saved-session transcript recount: **2 findings / 29 ALLOW / 1 DENY / 101 entries**, not a fresh assessment; the separate legacy `denials` list is not the operator authorization-decision count.

Reproduction:

```powershell
python -B -m pytest tests -q
cd console/office
npm run build
npm run check:bundle
node scripts/validate-fbx.mjs ORIGINAL_FBX_DIRECTORY CANDIDATE_FBX_DIRECTORY REPORT_JSON
```

The independent loader comparison needs the preserved original files extracted to a separate temporary folder; do not compare candidates with themselves or overwrite active models while reproducing. The generator always writes candidates to a separate output directory.

Gate live validation remains blocked by Windows Application Control, error 4551. The security controls were not changed. No grounding improvement was demonstrated. Preserve this failure.
