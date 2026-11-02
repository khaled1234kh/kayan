# Screenshot feedback corrections — 2026-11-01

The user supplied written feedback plus C:\Users\khale\Downloads\pdfjoiner.pdf. The four PDF pages were rendered with Poppler and inspected. They show the previous build, not the revised build. This is screenshot spot evidence, not the six-step live walkthrough. Source hashes are in eval/reports/visual_feedback/sources.json. No browser automation or permission workaround was used.

## 1. Selected-agent decision attribution — corrected and data-checked

The screenshot's Network session showed the globally latest Reporting/write_report decision. App.tsx previously passed lastDecision directly to TrustGatePanel. It now selects authorization_decision entries by the selected actor's actual backend agent ID, rejects an explicitly mismatched engagement, and never falls back to another agent when no own decision exists. With no agent selected, the global block is explicitly labeled engagement latest.

Tests cover mixed Network/Reporting records, missing own decisions, stale engagement and out-of-order entries. A read-only check of the actual console WebSocket passed with five agents/97 transcript entries: Network -> port_scan; Reporting -> write_report. The saved evidence is eval/reports/visual_feedback/agent_decision_scope_2026-11-01.json. This proves data projection/identity, not rendered pixel acceptance.

## 2. Oversized/clipped labels — source corrected; appearance pending

The old Html distanceFactor=12 magnified labels at close zoom. It is removed. Labels use the same fixed 12px card, maximum width 180px with explicit ellipsis/title, and projected positions are bounded within the canvas. The bounded-position check passes at two viewport sizes and extreme projected positions. Off-screen anchors can place cards near the edges; overlap/legibility still needs human review. The scoped, inexpensive occlusion target remains in use.

## 3. Monitor text and physical obstructions — source corrected; appearance pending

The wrapper previously stopped at maxLines without marking omitted text; a separate activity.slice(0,150) could cut a word before layout. A measured-width wrapper now handles word breaks and long tokens, fits within the display width, and adds a final-line ellipsis. Header text also fits its width before the tier badge. Tests cover short text, long reports, long single tokens and zero-width input.

The PDF also shows foreground plant/lamp geometry obscuring parts of the activity area. Tall props are now behind the display rather than in front of it, while maintaining plant/lamp/mug clearance. Geometry checks cover the new placement. The physical display remains front-only and GPU depth-tested; no mirrored rear content or floating replacement screen was introduced. Human review must confirm text and prop visibility in the new close-up.

## 4. Floor visibility — reopened, not accepted

Ambient/floor changes were implemented in the first polish pass, but the overhead PDF still shows a nearly black circulation floor. The implementation checkbox was not visual proof. Floor acceptance is explicitly reopened in TODO.md.

This revision changes floor albedo to #293642, roughness to 0.65 and metalness to 0.03, and adds one static, non-shadowed cool fill directional light at [-6,6,-4], intensity 0.55. Existing ambient 0.78, hemisphere 0.45, key light/shadow configuration and desk teal accents are retained. There is no new animation or synthetic activity. Visible success is pending a new human review; post-change performance is also pending.

## 5. Black overhead region — candidate corrected; final cause/appearance not certified

The PDF's black upper planes appear consistent with the opaque, nearly black ceiling/upper shell in close-up views. This is an inference from images plus source, not proof of a shadow-map edge. The room is now explicitly open-top, removing the opaque ceiling plane while retaining side walls, glazing and furniture.

A check using the configured key light and refreshed shadow-camera projection contains the tested room bounds (maximum absolute projected x/y 0.934). It does not reproduce a room-boundary shadow-frustum clip; the shadow bounds/map size were not guessed wider. The initial test omitted projection refresh and failed; the corrected setup matches WebGLShadowMap's projection refresh and passes. Do not report that test-setup failure as a runtime defect. A revised close-up is still required before closing the visible artifact.

## 6. Local model authorization — verified against the later user clarification

The earlier placeholder/budget requirement was followed by the user-provided clarified vision at C:\Users\khale\.codex\attachments\556c1ee3-ac5f-44cb-9bd2-624eea6d2e3a\Pasted text.txt. Its model-choice section explicitly calls for Qwen2.5-7B-Instruct (or 14B) through Ollama and a possible 1.5B compute fallback. Its tier section recommends Option A (one model plus role prompts/contracts), and instructs: “Pick one and state it.”

The agent chose Option A under that instruction; the user did not separately assign a different model to each tier. Current config/llm.json declares architecture A, local Ollama, qwen2.5:7b, context 4096, concurrency 1, num_predict 384 and a declared 1.5B fallback. config/model_tiers.json resolves A, B and C to the same qwen2.5:7b; none is currently a placeholder. Tier labels still distinguish role/capability/context behavior. The recorded compute budget is an RTX 5060 Laptop/8151 MiB VRAM and 31.2 GiB RAM, observed earlier and not remeasured for this UI pass. No paid-cloud model or API budget was silently selected. A future multi-model/cloud budget is not resolved by this local MVP choice.

## Current checks and remaining acceptance

Selected-agent SSR/data tests, real console WebSocket projection, label/text/shadow-coverage checks, workstation/monitor/prop geometry, actor picking, 12 transport/reducer checks, TypeScript and the final production build pass. The bundle-size warning remains. Backend Rust/Python/Go suites were not rerun for these frontend-only changes; earlier results retain their dates and limits.

Current profiler source revision: selected_agent_decision_and_visual_feedback_v5. The last measured pre-polish close-up sample was 131.04 FPS, max gap 25.60 ms, zero long tasks; those numbers do not measure this revision. A human-operated orbit/click export has been requested and must be compared with the preserved baseline, including viewport/DPR/path/load limits. Do not infer rendered correctness from these checks or copy prior FPS as current.

The complete six-step live walkthrough remains open. The original grounding regression and incomplete upstream Go swap remain unchanged; TA alignment implementation has not started during these fixes.

## Subsequent human feedback and current performance

The user replied "Renders; spot checks look correct" to a question naming revised labels, floor, monitor text and selected Network decision. Record: eval/reports/visual_feedback/human_spot_check_2026-11-01.json. This is successful human spot feedback for those items. It is not an agent screenshot or the full live walkthrough; the ceiling artifact was not separately named in that reply.

The current v5 export is preserved at eval/reports/performance/after_visual_feedback_v5_2026-11-01.json. Same viewport 2560x1277, DPR 1 and five completed agents: 134.59 FPS, p95 gap 8.90 ms, max gap 34.90 ms, zero long tasks. Pre-polish two-fix sample: 131.04 FPS, p95 9.60 ms, max 25.60 ms, zero long tasks. Camera paths/visible geometry and GPU co-load were not controlled. No major regression was observed in the sampled path; the worse maximum gap remains recorded. Earlier pending-measurement statements describe the state before this export, not current status.

## FBX warnings reported during this review

The user pasted Vite connected messages and these literal warnings, with no uncaught runtime error in the supplied log:

~~~text
THREE.FBXLoader: ShininessExponent map is not supported in three.js, skipping texture.
THREE.FBXLoader: Vertex has more than 4 skinning weights assigned to vertex. Deleting additional weights.
~~~

Installed three-stdlib FBXLoader source confirms the unsupported map is skipped; actor material conversion uses explicit roughness and retains supported diffuse/normal/alpha maps. Its parser retains the four largest skin weights, then createMesh normalizes them. This can affect joint deformation. These warnings occur in import/parser paths, not an animation-frame callback; multiple assets/meshes can emit them. The later user reply confirms the scene renders. No warning suppression or asset modification was used to claim a clean import.

Asset follow-up: re-export prepared models with supported maps and at most four normalized influences per vertex, then compare skin/hair, hands and elbows before adopting replacements. This was not performed; preserve the originals. The full six-step live walkthrough stays open. Subsequent functionality-checkpoint media inspection explicitly accepts the sampled Web-App ceiling view; see below.

## Subsequent consolidated checkpoint media acceptance

The human's Downloads/Screen Recording 2026-11-01 153604.mp4 at 6s supplies a Web-App close-up. Compared with original PDF page 1, the large opaque overhead ceiling plane no longer covers that workstation in the sampled view. That specific artifact is now closed on rendered evidence. A small black patch over lower monitor text remains unclassified; it is separately recorded for visual recheck, not hidden by ceiling acceptance.

A later human-operated recording, C:\Users\khale\Videos\Screen Recordings\Screen Recording 2026-11-01 155848.mp4, covers actual engagement 7da73508… through the visible report-saved event at 15:58:36 Cairo. Sampled extracted frames show actual live state changes; no browser automation occurred. See FUNCTIONALITY_CHECKPOINT_2026-11-01.md for source hashes, exact run counts and acceptance limits. This closes the recorded-rehearsal checkpoint, not all six human visual steps.
