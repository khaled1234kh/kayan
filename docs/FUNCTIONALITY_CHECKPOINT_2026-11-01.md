# Consolidated functionality checkpoint — 2026-11-01

Current source revision: `selected_agent_decision_and_visual_feedback_v5`. No TA implementation, FBX re-export or further polish was started during this checkpoint. Geometry checks ≠ rendered acceptance.

## 1. Ceiling artifact: PASS for the inspected Web-App view

An explicit Web-App close-up was found at 6 seconds of the human-supplied clip and compared with page 1 of the original feedback PDF. The large opaque overhead ceiling plane no longer covers the workstation in that view. This specific artifact check is closed on rendered evidence, not on the open-top source change or geometry tests. The camera positions are comparable views of the same workstation/overhead area, not an identical recorded camera transform. This does not certify every camera angle or complete the six-step human walkthrough.

Rendered evidence: [Web-App close-up from the human clip](../eval/reports/checkpoints/functionality_20261101_v1/media/provided_clip_06s.png), compared with [original feedback page 1](../eval/reports/checkpoints/functionality_20261101_v1/media/original_feedback_page1.png). A small black patch is also visible over the monitor's lower activity line in the current clip; its cause is unverified and separate from the large overhead plane. Do not interpret this ceiling acceptance as acceptance of that patch or of all monitor rendering.

The supplied filename was found at `C:\Users\khale\Downloads\Screen Recording 2026-11-01 153604.mp4`, rather than the originally mentioned Videos path. ffprobe reports 25.3333 seconds, 2560×1392, 30 fps and creation time 13:35:39 UTC / 15:35:39 Cairo. Frames at 1, 6, 12 and 24 seconds were extracted and actually inspected under `eval/reports/checkpoints/functionality_20261101_v1/media/`. They show an older completed session; the Network decision visibly contains engagement prefix `b8729a4c-69c4-4bb8-a314-bc966f0e5be6`, role Network, action port_scan and Tier C on its physical monitor. This is useful rendered spot evidence, including the Web-App close-up, but not the new rehearsal recording.

Any separately saved still can corroborate the close-up; its path has been requested. No browser automation was used to obtain these frames.

## 2. Combined regression: PASS

One consolidated run, 13:37:28–13:38:05 UTC / 15:37:28–15:38:05 Cairo. All **13 check groups passed**. Commands, cwd, exit status and complete logs are in [results.json](../eval/reports/checkpoints/functionality_20261101_v1/results.json).

| Group | Fresh result |
|---|---|
| Rust isolated-target offline tests | 20 passed, 0 failed; compiler warnings retained |
| Python orchestrator/backend tests | 37 passed; 6 utcnow deprecation warnings retained |
| Go boundary | 15 top-level focused tests passed across trustgate/tools/providers; actual Rust/Cedar `TestCedarLiveProfile` passed |
| Go no-embedder | Selected `none` provider test passed |
| 3D TypeScript + production build | `npm run build` passed (`tsc --noEmit` then Vite); bundle-size warning retained |
| 2D fallback production build | Passed |
| 3D transport/reducer | 12 checks passed |
| Session panel | SSR and selected-agent scoping checks passed |
| Office | Geometry checks passed |
| Actor picking | Proxy geometry checks passed |
| Visual-feedback checks | Label bounds, monitor text and actual key-light room coverage checks passed |
| Performance metric math | Synthetic calculations passed; no new browser FPS measurement |
| Adversarial scope harness | 9/9 expected denials passed against the running gate |

These are focused Go boundary tests, not the entire upstream Go suite. Full host Go/Docker builds and container source hashes were last verified in the earlier 2026-11-01 boundary pass, not rebuilt by this checkpoint. Frontend builds/SSR/data checks do not establish pixel acceptance.

Reproduce from the canonical root with live TrustGate on 8000:

```powershell
python -B -m eval.functionality_checkpoint --label UNIQUE_NEW_LABEL
```

The harness refuses an existing label and starts no engagement. Check listeners and actual health first. This pass initially attempted duplicate service starts after an incomplete listener snapshot; the attempts correctly failed with address-in-use errors. Existing servers were then checked with netstat and HTTP. They were not killed or replaced, and this setup diagnostic is not recorded as a runtime regression. Confirmed ports: TrustGate 8000, console backend 8001, lab 8888, 3D 5173, Ollama 11434; Go API 8443.

## 3. Real live rehearsal: PASS, matching saved recording inspected

The first fresh rehearsal below completed successfully and the human confirmed live updates, but initially identified an older 25-second clip. That clip was correctly rejected as proof of that run. The first runtime evidence/report remain preserved. To obtain a matching recording, one new rehearsal was started only after a second explicit human “Recording running now” acknowledgement. No results were overwritten or selected away.

### Recorded rehearsal — current demonstration evidence

Engagement **7da73508-01e6-48e9-9093-be09c5fd734d**, 2026-11-01 **15:57:57–15:58:36 Cairo** (13:57:57–13:58:36 UTC), actual Python/Ollama qwen2.5:7b with grounding on. The human-operated recording is `C:\Users\khale\Videos\Screen Recordings\Screen Recording 2026-11-01 155848.mp4`, 77,261,135 bytes, 69.966633 seconds, 2560×1392 at 30 fps. Its path, SHA-256 and ffprobe metadata are preserved in `eval/reports/checkpoints/functionality_20261101_v1/media/recorded_v2_metadata.json`. MP4 creation metadata is not treated as exact wall-clock alignment; visible event times and engagement ID match the run.

Extracted frames at 20, 24, 40, 55 and 65 seconds were actually inspected. At 20s the scene shows the prior completed session before the new run. At 24s the visible activity shows the new Planner/status/queued-instruction setup at 15:58:00–01. At 40s the scene is active with Web-App inference and the new engagement prefix `7da73508…`. At 55s Reporting's physical screen shows working/current summary text, while activity records the delivered instruction. At 65s the scene returns to New assessment and visibly shows **“Verified-finding report saved” at 15:58:36**, with Reporting/write_report and the matching engagement ID. These are rendered human-recording observations, not an inference from WebSocket checks. They do not certify every frame, every agent close-up, narration audio or the six-step visual walkthrough. The agent narrated live through chat; audio was not transcribed/verified.

| Cairo time | New recorded run |
|---|---|
| 15:57:57–15:58:00 | Assessment created; signed ROE loaded and compiled with 13 rules; five roles ready |
| 15:58:00–10 | Planner inference and specialist assignments |
| 15:58:11–15 | Recon HTTP probe, endpoint discovery and scoped port scan |
| 15:58:16–22 | Web-App tests and independent fresh-nonce reproduction of both accepted findings |
| 15:58:23–28 | Network scoped port/service scans |
| 15:58:29–36 | Reporting boundary-delivered instruction, local inference and saved final report; all five roles completed |

Result: **2 findings / 29 allowed / 1 denied**, 11 actual model calls, 10 retrieval-context calls, 189 WebSocket snapshots, verified incremental output and 101 chronological entries across five sessions. Governed live status, queued instruction delivery and tainted-input HTTP 403 passed. Coverage remains 40%, legacy precision 50% and fresh-nonce reproduction 100%, with the same denominator/evidence limits below. No invalid live proposal occurred. A grounded repeat does not demonstrate grounding improvement.

Evidence: [runtime result](../eval/reports/live_grounding_on_functionality_rehearsal_recorded_20261101_v2.json), [phase/transcript observations](../eval/reports/checkpoints/functionality_20261101_v1/rehearsal_events_recorded_v2.jsonl), [final JSON](../reports/report_7da73508.json), [final Markdown](../reports/report_7da73508.md), [working Reporting frame](../eval/reports/checkpoints/functionality_20261101_v1/media/recorded_v2_055s.png), [report-saved frame](../eval/reports/checkpoints/functionality_20261101_v1/media/recorded_v2_065s.png). The full video stays at the human-supplied absolute path above; its content hash is recorded rather than committing the 77 MB media to Git.

### First rehearsal — preserved, recording did not match

Actual engine: Python + local Ollama `qwen2.5:7b`, grounding enabled, owned lab `http://127.0.0.1:8888`. Engagement **88209191-9503-4df3-960e-fe4afcb8f8ec**. Run 13:40:54–13:41:22 UTC / **15:40:54–15:41:22 Cairo**.

| Cairo time | Observed behavior |
|---|---|
| 15:40:54–56 | New engagement created; signed ROE loaded/compiled with 13 rules; five roles enrolled and ready |
| 15:40:56–15:41:03 | Planner performed actual local-model inference and finished specialist assignments |
| 15:41:04–07 | Recon performed HTTP probe, endpoint discovery and scoped port scan |
| 15:41:07–11 | Web-App executed tests; raw script reflection and benign command echo each reproduced with an independent fresh nonce; SQL injection yielded no accepted finding |
| 15:41:12–16 | Network performed scoped port and service scans |
| 15:41:16–22 | Reporting received the queued instruction at a task boundary, performed model summarization and saved the final JSON/Markdown report; all five agents completed |

Fresh result: **2 findings / 29 allowed / 1 denied**. Counts exclude ROE load and include the deliberately tainted operator input denial. Eleven actual model calls, ten retrieval-context calls, 176 observed WebSocket snapshots and incremental output verification. Five sessions had Recon 31, Web-App 38, Network 18, Reporting 10 and Planner 4 transcript entries. Governed status reply, queued instruction delivery and tainted-input HTTP 403 all passed.

Coverage remains 40% on the established five-label findings-based denominator. Independent fresh-nonce reproduction is 2/2 (100%); unchanged legacy evidence precision is 1/2 (50%), since its command criterion requires whoami rather than benign nonce echo. These are distinct metrics. XSS is reflected script text; browser execution and blinded classification accuracy were not checked. No invalid live tool proposal occurred, so live retry recovery was not exercised.

Evidence:

- [Immutable runtime result](../eval/reports/live_grounding_on_functionality_rehearsal_20261101_v1.json)
- [Timestamped phase/transcript observation](../eval/reports/checkpoints/functionality_20261101_v1/rehearsal_events.jsonl) — transport data, not pixels
- [Final report JSON](../reports/report_88209191.json) and [Markdown](../reports/report_88209191.md)
- Human live-update confirmation; the initially supplied clip did not record this first run. The subsequent recorded rehearsal above closes the recording requirement.

Reproduce only when the human has recording running, using a new label and with no concurrent engagement:

```powershell
python -B -m eval.rehearsal_watch --output eval/reports/checkpoints/UNIQUE_EXISTING_CHECKPOINT/rehearsal_events_NEW.jsonl
# In another terminal, after the observer is watching:
python -B -m eval.live_runtime_check --grounding on --label UNIQUE_NEW_LABEL
```

## 4. Go integration reporting stance: CLOSED as a scoped evaluation

PentAGI integration is functionally connected and policy-enforced within the recorded signed-menu profile. A fresh offline comparison of the preserved raw audit/toolcall records against that profile found all five actual terminal dispatches matched their role, endpoint, hardened approved template and unique one-use intent: **zero observed unauthorized environment dispatches relative to those recorded menus**, not a universal zero-false-allow claim. Three malformed/unapproved terminal proposals and nine repeated intents were denied. Upstream worker handoffs dropped approved commands or re-delegated completed checks; fixing that delegation behavior is outside the current demonstration scope. Three denied `subtask_patch` calls are an explicitly unmapped **local adapter** limitation, not an upstream defect. The custom Python orchestrator remains the primary verified demonstration path. The Go result is a completed second-framework boundary evaluation with limitations disclosed; autonomous clean completion, per-model-call Go authorization and upstream five-role console migration are not claimed or required to close that scoped evaluation.

Saved Go totals remain **3 findings / 19 allowed / 15 denied**, including three independent verifier ALLOWs; Go-only **16 allowed / 15 denied**. The three upstream flows entered waiting and were explicitly stopped. Their failures remain in the artifacts.

[Fresh offline profile consistency result](../eval/reports/checkpoints/functionality_20261101_v1/go_recorded_profile.json) confirms the saved raw SHA-256 still matches the verifier artifact. This consistency check is not a new model engagement or a full cryptographic audit-chain validation.

Docker was rechecked during this pass: daemon 29.9.2 reachable, `kayan-pentagi-local` running at `127.0.0.1:8443 -> 8080`. The retained final worker error remains the literal `subtask_patch` adapter refusal in [BLOCKED.md](BLOCKED.md); no new Docker connection error occurred. No upstream flow was rerun or delegation workaround added.

## Sequencing and preserved evidence

All four checkpoint items are complete within the stated bounds: sampled ceiling artifact check, combined regression, actual model rehearsal with matching inspected human recording, and finalized scoped Go stance. TA alignment can follow after this completion is reported. No TA implementation, FBX re-export or bundle cleanup was included in this checkpoint. The separate six-step human visual walkthrough remains open. The small monitor patch is recorded separately for a later visual recheck.

Original v1 grounding regression and unchanged v2 outcomes remain authoritative. **No grounding improvement was demonstrated. Preserve this failure.** This single grounded rehearsal is not another off/on comparison and does not revise that conclusion. Earlier failed Go attempts, intermediate performance regressions and the rejected polish screenshots remain preserved.
