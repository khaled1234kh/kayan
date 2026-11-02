# Browser performance evidence — 2026-11-01

Human-operated exports from the opt-in 3D dev profiler. No browser automation, screenshot or rendered acceptance is claimed. Raw exports are preserved; do not replace poor or contaminated samples with later results.

Initial export: baseline_initial_2026-11-01.json, copied byte-for-byte from the user's kayan-performance-2026-11-01T12-10-16-380Z.json in Downloads. Five agents, completed engagement, TrustGate connected, visible tab, viewport 2560x1277, DPR 1, continuous rendering, antialias and shadows enabled.

| Label in export | FPS | p95 frame gap | Max frame gap | Long tasks | Interpretation |
|---|---:|---:|---:|---:|---|
| idle (sample 1) | 145.95 | 7.60 ms | 96.50 ms | 2 / 149 ms total | 183 canvas pointer moves; contaminated, not a clean idle baseline. |
| orbit-click (sample 2) | 101.58 | 10.20 ms | 112.90 ms | 20 / 1772 ms total | 277 moves, 3 pointer downs; no click/wheel recorded. Orbit evidence, not proof of selection responsiveness. |
| idle (sample 3) | 65.31 | 98.90 ms | 237.80 ms | 50 / 4932 ms total | 419 moves, 3 pointer downs, 8 wheel events, 1 click; contaminated, not an idle baseline. |

All three samples recorded zero store updates, actor-array replacements and scene React commits. They do not support a store-update explanation for this completed-engagement interaction lag. They do not rule out store cost during a live engagement. About 451–454 visible draw calls were observed; rendering alone was not yet isolated as a dominant cost. Actual historical GPU/model co-load is not recorded by this export and must not be inferred from workflow_running=false.

Source inspection found whole-scene Html occlusion and recursive event picking through detailed skinned characters. This is a hypothesis, not yet a measured attribution. The profiler now times scene-occlusion batches and individual pointer-picking raycasts. A second diagnostic export has been requested before selecting an optimization. No renderer settings, raycast behavior or scenery were changed at this point.

## Follow-up attribution and selected change

The paragraph above describes the initial state, before attribution. diagnostic_second_2026-11-01.json contains a valid clean idle sample: 152.17 FPS, zero canvas inputs, zero long tasks. Its orbit-labelled sample also has zero input and zero raycasts, so its 151.88 FPS is static rendering, not interaction evidence. The human replaced the original Downloads filename when saving this export; the original bytes had already been preserved separately.

diagnostic_orbit_2026-11-01.json is the subsequent genuine interaction sample: 389 moves, 5 pointer downs, 6 wheel events, 2 clicks; 43.80 FPS; p95 gap 80.40 ms; maximum gap 351 ms; 30 long tasks totaling 4872 ms. Scene React commits and store updates remain zero. Whole-scene label occlusion: 2055 calls, 6575.60 ms (63.44% of the 10364.60 ms sample), worst call 96.10 ms. Pointer picking: 6120 calls, 188.10 ms (1.81%), worst call 62.40 ms. This directly identifies label occlusion as the dominant measured cost in this sample; no store/renderer rewrite is justified by it.

One change was selected: name-tag occlusion now targets an explicit static room/furniture group instead of the complete scene containing detailed employee meshes. Employee rendering/picking, physical monitor front/rear depth, shadows, DPR, antialiasing and frameloop are unchanged. This preserves room/furniture occlusion for labels; labels no longer use employees/workstation props as occluders. Human acceptance must check that label visibility remains appropriate. The profiler recognizes the scoped group as scene_occlusion for comparable cost accounting.

Type/geometry/session checks pass. A same-viewport after-fix idle/orbit export has been requested; no performance improvement is claimed until that export is read. Source version is recorded as static_room_occlusion_v1 in new sample metadata. artifact_hashes.json records the preserved raw captures and timestamps; recompute existing hashes to check integrity, never rewrite their bytes.

## First fix measured; remaining close-up hitch preserved

after_static_occlusion_2026-11-01.json contains three samples. Its first idle label has 22 pointer moves (contaminated); its second is clean: 151.48 FPS, zero input/long tasks, max gap 10 ms. Interaction: 86.32 FPS, p95 gap 10.40 ms, max gap **557 ms**, 24 long tasks totaling 3076 ms. The worst hitch worsened; do not hide it behind the higher average FPS.

Scoped label occlusion cost fell to 176.40 ms across 3005 calls (about 0.059 ms/call versus 3.200 ms/call before), while detailed pointer picking took 2951.80 ms across 10830 calls. The manual path had 652 moves, 22 wheel events and 3 clicks, versus 389/6/2 in the diagnostic baseline, and the camera viewed different geometry. The FPS ratio is descriptive, not a controlled identical-path speedup. Viewport/DPR/five completed agents match; model/GPU co-load was not continuously sampled. Four store updates changed no actor arrays; three scene commits totaled 30.40 ms. A wholesale store rewrite remains unsupported by this evidence.

The second selected change uses a single posed, invisible actor hit box instead of triangle-level picking through detailed skinned meshes. Rendered employee geometry/materials, physical monitor depth and static-label occlusion remain unchanged. Proxy padding is two native FBX units; all workstation transforms still apply. A geometry check confirms a rotated/scaled proxy receives hits without calling detailed mesh raycasts. It is not rendered acceptance. A new idle/close-up orbit-and-selection export is pending, with profile_revision static_room_occlusion_and_actor_proxy_v2. No further speculative renderer/store changes are planned.

Keep a clean visible-tab idle sample, comparable orbit/click path and viewport/model conditions for before/after comparisons. Canvas cadence is not GPU timing, input latency or visual acceptance. Metric arithmetic tests use synthetic input and provide no real FPS measurement.

## Second fix measured — performance stage reported before polish

after_actor_proxy_2026-11-01.json preserves the user's 12:29 UTC capture with source revision static_room_occlusion_and_actor_proxy_v2. FPS was recomputed from raw frame counts and wall durations and matches the exported summary. Same 2560x1277 viewport, DPR 1, five completed agents, visible tab, TrustGate connected; exact manual paths and continuous GPU/model co-load were not controlled.

| Recorded stage | Clean idle FPS | Interaction FPS | Interaction p95 gap | Interaction max gap | Long tasks |
|---|---:|---:|---:|---:|---:|
| Diagnostic baseline | 152.17 | 43.80 | 80.40 ms | 351 ms | 30 / 4872 ms total |
| Static label occlusion only | 151.48 | 86.32 | 10.40 ms | 557 ms | 24 / 3076 ms total |
| Label occlusion + actor picking proxy | 150.22 | 131.04 | 9.60 ms | 25.60 ms | 0 / 0 ms |

The final interaction contains 779 moves, 10 pointer downs, 27 wheel events and 6 clicks. Picking: 12675 calls / 159.80 ms total / 0.40 ms maximum, versus 10830 / 2951.80 / 92.10 after the first fix. Occlusion: 5645 calls / 353.40 ms / 0.60 ms maximum. Three store updates replaced no actor arrays; two scene commits totaled 20.10 ms. Clean idle had no input, raycasts or long tasks. Idle draw calls/triangles stayed 454/273958; five invisible proxy geometries were added, without extra visible detail.

These recorded samples support the two targeted changes and show the observed close-up hitch was removed in this pass. They do not prove every camera path, live-inference load, input latency or future frame is hitch-free. Do not call this a controlled threefold benchmark gain, a store optimization, or rendered visual acceptance. Preserve the first-fix 557 ms regression and all contaminated samples. No DPR/shadow/AA/render-loop rewrite was made. Static polish starts only after this performance result was reported.

## Screenshot-feedback revision measured

after_visual_feedback_v5_2026-11-01.json is the human's current-revision orbit/click export (selected_agent_decision_and_visual_feedback_v5), captured 13:10:19 UTC on 2026-11-01. It includes selected-agent decision scoping, fixed-size bounded labels, explicit monitor ellipses, tall props behind the screen, revised floor plus a non-shadowed fill light, and the open-top shell. Raw FPS arithmetic and all prior capture hashes were verified before saving it.

| Recorded comparison | Interaction FPS | p95 frame gap | Max frame gap | Long tasks |
|---|---:|---:|---:|---:|
| Diagnostic before raycast fixes | 43.80 | 80.40 ms | 351 ms | 30 |
| Two raycast fixes, before polish | 131.04 | 9.60 ms | 25.60 ms | 0 |
| Current visual-feedback revision | 134.59 | 8.90 ms | 34.90 ms | 0 |

Same 2560x1277 viewport, DPR 1, five completed agents and visible tab. Current input: 1027 moves, 12 pointer downs, 25 wheel events, 6 clicks. Four store updates replaced no actor arrays; two scene commits totaled 21.60 ms. Label occlusion: 5069 calls / 288.40 ms / 0.90 ms max; picking: 16320 / 197.10 ms / 0.60 ms max. No major interaction-performance regression is observed in this sample. The maximum gap is worse than the pre-polish sample and remains preserved. Camera path/visible geometry and continuous GPU/model co-load were not controlled; do not present the small average-FPS change as a causal polish speedup. No new idle result is claimed.

Separately, the user reported that the revised scene renders and the requested label/floor/monitor/Network-decision spot checks look correct. That text feedback is not a screenshot captured by the agent or the full live walkthrough. FBX material/skinning import warnings remain known asset limitations; see docs/VISUAL_FEEDBACK_2026-11-01.md.
