# KAYAN TrustGate

One project containing the Rust/Cedar gate, Python agents, 3D console, local references, tests and scoped Go integration. The previous external office source is retired. All active source now lives under this folder.

## Start locally

Install Git LFS and fetch the real model/video assets after cloning, then install Python requirements and office dependencies:

```powershell
git lfs pull
python -m pip install -r requirements.txt
npm --prefix console/office ci
.\Start-Kayan.ps1 -RestoreDemo
```

Open **http://127.0.0.1:5173/**. The launcher leaves existing listeners unchanged; inspect them before starting duplicates. The default is safe Review mode: Python and Node are required. Rust/MSVC and Ollama are additional prerequisites for live execution; use `-Component All` only when the gate is allowed to build/run. Start Ollama separately with the existing authorized `qwen2.5:7b` model for real-model assessments. The launcher does not start an assessment or alter Docker. Saved reports can be viewed without model inference.

**Final verified readiness (2026-11-02):** 17/17 consolidated checks passed, including 84 Python tests, 28 Rust tests, focused Go/Cedar, adversarial and frontend cases. The final actual shared-Qwen run returned **2 findings / 29 allowed / 1 denied**, with full-journal integrity verified. See [final readiness](docs/DEMO_READY_2026-11-02.md). Earlier Windows error 4551 did not recur on the normal retry; no protection was changed. Start installed Ollama separately, then for live operation:

```powershell
.\Start-Kayan.ps1 -Component All
```

All starts/reuses the Gate, owned lab, backend and office; it starts no assessment. Review remains the safe default. `-RestoreDemo` restores the historical recorded session only into a waiting/already-matching backend and refuses to overwrite a different session. Current completed live session: 51bba207...; the original recordings remain separately labeled historical evidence. Exact old errors and final retry results: `docs/BLOCKED.md`.

For the verified recorded-evidence presentation, open **http://127.0.0.1:5173/review.html**, or click **PRESENTATION** in the console. It includes both recordings, the PDF, evidence table and saved report. Their hashes are in `console/office/public/review/manifest.json`. `python -B scripts/prepare_review.py` validates/prepares those existing artifacts; it starts no assessment.

| Component | Source | Port |
|---|---|---|
| Signed-ROE Rust/Cedar gate | `trustgate/service/` | 8000 |
| Python local-model agents | `pentagi/` | Uses the gate/lab/model |
| Sessions/planning backend | `console/backend/` | 8001 |
| React Three Fiber office | `console/office/` | 5173 |
| Intentionally vulnerable owned lab | `lab/` | 8888 |
| Local inference | Installed Ollama | 11434 |
| Optional scoped Go backend | `pentagi_upstream/backend/` | Existing Docker profile: 8443 |

Source consolidation preserves the HTTP/WebSocket boundaries. It does not merge processes or move policy enforcement into the browser. The Go backend is vendored source, with licensing retained, rather than a separately fetched submodule. Its delegation limitations remain; Python is the primary demonstration.

## Review

- `output/pdf/KAYAN_Evidence_Presentation.pdf`: small sharing PDF with both public Drive video links, the proposal, five confirmed students and the evidence appendix.
- `output/pdf/KAYAN_Evidence_Presentation_With_Videos.pdf`: same clickable video links plus the original embedded MP4 attachments.
- `docs/UI_REDESIGN_2026-11-02.md`: current design, actual rendered acceptance and limits.
- `output/pdf/KAYAN_TrustGate_Proposal.pdf`: original eight-page proposal retained unchanged.
- `MASTER_HANDOFF.md`: canonical state, commands, dated evidence and limits.
- `docs/PROJECT_CONSOLIDATION_2026-11-02.md`: consolidation, recovery and verification record.
- `docs/TA_DELIVERABLES_ALIGNMENT.md`: hypothetical planning and the two mitigation paths.
- `TODO.md`: bounded completed product/demo work and separately verified GitHub delivery.

Descriptive organization inputs carry zero policy weight. Phase 1 and Option A are offline hypotheses, not findings. The live engine authorizes bounded actions against a signed ROE and requires independent reproduction for supported candidate findings. Audit records are hash-chained/HMAC-signed in **mutable** local storage. General semantic taint tracking, production identity/isolation and completion-triggered ROE revocation are not established.

**No grounding improvement was demonstrated. Preserve this failure.** Original regressions, equal v2 outcomes and scoped Go errors remain in the dated evidence.

## Verification

```powershell
python -B -m eval.functionality_checkpoint --label UNIQUE_LABEL
npm --prefix console/office run check:trustgate:live
```

The checkpoint starts no assessment and covers the focused Go boundary profile, not all upstream Go tests. Browser rendering is separate evidence. `CARGO_TARGET_DIR` can select an existing build cache; otherwise the service uses its local target directory.

Runtime keys and sessions stay local/ignored. Do not touch KAYAN-video's unrelated Remotion project, sibling old `server/` or abandoned pre-pivot handoff. The completed FBX/chunk compatibility pass, original asset backup and measured build tradeoff are documented in docs/ASSET_BUNDLE_VERIFICATION_2026-11-02.md. Final normal Gate startup and actual coordinator/audit validation passed; earlier Application Control failures remain historical.
