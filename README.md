# KAYAN TrustGate

**A governed security-assessment platform with a live 3D operations console.**

KAYAN coordinates a local-model assessment of an owned lab through signed Rules of Engagement and Rust/Cedar authorization. The console makes assignments, decisions, model activity and independently reproduced findings visible. Planner coordinates Recon, Web-App, Network and Reporting; all roles share the local `qwen2.5:7b`. Planner is a coordinator, not a second model or an extra tool executor.

![KAYAN operations console showing five agent workstations and the completed real assessment](docs/images/operations-console.jpg)

[Project proposal PDF](output/pdf/KAYAN_TrustGate_Proposal.pdf) · [Evidence PDF with video links](output/pdf/KAYAN_Evidence_Presentation.pdf) · [Three-path demonstration](https://drive.google.com/file/d/1cBt1aRcKtT3EulSUwK-y9ayTv1UNfWkJ/view?usp=sharing) · [Recorded live assessment](https://drive.google.com/file/d/1SRUVpJtSssnN1zlT0g4Z_ZI4jXg3xfNb/view?usp=sharing)

The guided-profile screenshot below was captured on 3 November 2026; the office and older result screenshots were captured on 2 November. The videos retain their earlier interface and original engagement evidence.

## What you can demonstrate

| Path | What happens | Evidence basis |
|---|---|---|
| Phase 1: Risk Plan | Authored applicability rules link described technical details to pinned ATT&CK/OWASP references, source excerpts and uncertainty. | Offline hypotheses; context relevance is not severity. No target access or authorization call. |
| Option A: Direct mitigation | Reporting turns the Risk Plan into a mitigation plan. | Offline recommendations; zero verified findings. |
| Option B: Assessment to mitigation | Planner coordinates the governed specialists, then Reporting synthesizes reproduced findings. A saved completed report can also be reviewed. | Live signed-scope assessment or its explicitly labeled saved evidence. |

Organization context carries **zero policy weight**. Defense in Depth / Zero Trust labels and recommendation selection are presentation features. Effort points are illustrative comparison weights, not prices or measured implementation costs.

### Organization profile and planning

![Guided organization profile with three sections, explicit sample replacement and two readable editors](docs/images/organization-profile.jpg)

The six-field profile preserves full entered descriptions within explicit limits. Preview fictional samples before replacement, review the exact context, then move through **Organization → Hypotheses → Mitigation → Review & Export**. Recommendations use bounded authored scenario controls, not model-generated risk judgments. Weak text-only matches are excluded; insufficient context can produce no supported hypotheses. [Before/after evaluation and actual browser/export evidence](docs/PLANNING_AND_COORDINATION_2026-11-03.md).

The older risk screenshot below documents the previous result presentation:

![Risk Plan workspace with three explicitly hypothetical risks and ATT&CK references](docs/images/risk-plan.jpg)

### Mitigation from a completed assessment

![Option B showing two verified findings, selectable recommendations and the illustrative-effort disclaimer](docs/images/assessment-mitigation.jpg)

<details>
<summary>More screenshots: Planner activity and offline mitigation</summary>

The Planner panel shows its shared model, capability tier, assignment sequence and chronological activity. Findings retain their specialist ownership.

![Planner session and the prepared agent workstations](docs/images/planner-session.jpg)

Option A remains visibly hypothetical and performs no live testing.

![Option A direct-mitigation workspace](docs/images/direct-mitigation.jpg)

</details>

## Run the recorded review

Prerequisites: Python, Node.js and Git LFS. Live execution additionally needs the Rust/MSVC build tools and installed Ollama with `qwen2.5:7b`. The verified host uses Windows and Python 3.12.

```powershell
git clone https://github.com/khaled1234kh/kayan
cd kayan
git lfs pull
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm --prefix console/office ci
.\Start-Kayan.ps1 -RestoreDemo
```

Open **http://127.0.0.1:5173/** for the console or **http://127.0.0.1:5173/review.html** for the recorded presentation. Review is the safe launcher default: it starts the backend and office, without starting an assessment, model inference or Docker.

`-RestoreDemo` loads the original completed `7da73508…` session into a waiting/already-matching backend. It deliberately refuses to overwrite another session. Omit that switch when continuing an already loaded assessment.

## Run a live owned-lab assessment

Start the installed Ollama server in its own terminal and ensure `qwen2.5:7b` is installed. Then, from the activated project terminal:

```powershell
.\Start-Kayan.ps1 -Component All
```

All verifies/reuses the Gate, lab, backend and office; it does not start an assessment. In the console, choose **New assessment**, review the owned-loopback authorization and start it. Each action still requires backend authorization; a connected console or responding Gate grants no authority by itself.

| Component | Source | Port |
|---|---|---:|
| Signed-ROE Rust/Cedar Gate | `trustgate/service/` | 8000 |
| Sessions, operator interaction and planning API | `console/backend/` | 8001 |
| React Three Fiber office | `console/office/` | 5173 |
| Intentionally vulnerable owned lab | `lab/` | 8888 |
| Local model server | Installed Ollama | 11434 |

## Verified results

The [3 November planning/coordination pass](docs/PLANNING_AND_COORDINATION_2026-11-03.md) adds evidence-referenced real-model outcome reviews, bounded next-specialist priorities, attributed observation reuse and exact-context offline planning. Shared local `qwen2.5:7b`, scope and action budgets remain unchanged. Planner has no specialist tool authority and is not a second model. Fixed role order remains; this is not a general dynamic scheduler.

The [final checkpoint](eval/reports/checkpoints/planner_context_final_20261103_v4/results.json) passed **17/17 groups**:

| Check | Result |
|---|---|
| Python | 145 passed; 46 retained deprecation warnings |
| Rust | 28 passed |
| Go | 15 focused boundary tests, 15 config tests and the explicit no-embedding case passed |
| Adversarial authorization | 9/9 passed |
| Frontend | Ten scripts plus TypeScript/production build passed |

Latest real coordinator engagement **a16f71f5-f9b3-4518-a17b-52a908358aba** produced **2 findings / 30 allowed / 1 denied**, three accepted outcome reviews and nine executed-action records. The denied decision is the deliberate tainted-input test. Coverage is explicitly incomplete: the unchanged Web-App action budget leaves directory traversal untested. Signed service-scan denial returned **2 / 25 / 2**; actual lab outage returned **0 / 24 / 1**, with no invented findings. Different harness inputs mean these allowed totals are not equivalent workloads. Full engagement IDs and count bases are in the linked record. Type-specific saved-report mitigation improvements were tested/browser-checked after the last live run; no new live finding claim is made for those templates.

Five fictional offline before/after cases demonstrate different scenario/control sets for retailer, clinic and manufacturing, plus honest empty results for insufficient/explicit-absence descriptions. Those are deterministic authored-rule checks, **not general model accuracy or a grounding efficacy improvement**. Actual downloaded A JSON preserved all six exact context fields; saved B retained its original reviews, ledger, finding IDs and partial coverage. Sampled profile layouts were inspected at six sizes from 1920×1080 to 640×800, with keyboard/contrast checks. The broader 19-item UI/office redesign remains open in [TODO.md](TODO.md).

Earlier host-blocked Go failures remain preserved. Normal retries now pass without security changes; why host behavior changed is unknown. The latest quiet audit check verified **1,130 entries** without rewriting the journal. Backend restart still opens with no active session although snapshots persist; automatic current-session resume remains an operational limitation. Review/-RestoreDemo preserves its original-session overwrite guard.

To repeat the defined checks against running prerequisites:

```powershell
python -B -m eval.functionality_checkpoint --label YOUR_UNIQUE_LABEL
```

The full profile additionally requires Go and the Rust toolchain; the Python demo itself does not require Go or Docker. It starts no model assessment. The published ce459f8 source was downloaded into the clean verification checkout, matched all 26 recorded source hashes and passed 145 Python tests / 46 warnings using installed host dependencies. This was not a new isolated dependency install. The earlier 2 November isolated-install result remains historical. Actual-model acceptance is separate and documented in the readiness report. Test-suite and geometry checks do not substitute for rendered UI acceptance or measured FPS.

## Scope and honest limits

**No grounding improvement was demonstrated. Preserve this failure.** The original regression and later comparisons remain in the evidence; retrieval combines ATT&CK and OWASP without a claimed accuracy advantage. Fine-tuning and a separate helper inference model are documented design substitutions, not completed training experiments.

Python is the primary demo engine. The vendored Go/PentAGI work is a scoped enforcement evaluation, not a completed autonomous runtime replacement. Production identity/isolation, immutable audit storage, development-key hardening and completion-triggered ROE revocation remain disclosed limits. Earlier Windows execution failures are preserved; the final normal build/start succeeded without weakening protections. No universal visual, security or performance guarantee is claimed.

## Project guide

- [Architecture and Red/Blue allocation](docs/ARCHITECTURE.md)
- [TA deliverables mapping](docs/TA_DELIVERABLES_ALIGNMENT.md)
- [Current planning, coordination and browser evidence](docs/PLANNING_AND_COORDINATION_2026-11-03.md)
- [Earlier readiness](docs/DEMO_READY_2026-11-02.md)
- [Canonical handoff](MASTER_HANDOFF.md) and [TODO record](TODO.md)
- [Publication provenance and local recovery history](docs/GITHUB_DELIVERY_2026-11-02.md)

All active source is in this repository. The previous external 3D folder, unrelated Remotion video project and old sibling server are not runtime dependencies. Only clean `main` is published; the original development ancestry and recovery bundle stay local.

## Team

Khaled Mohamed · Youssef Montasser · Ahmed Ali Moustafa Badawi · Mahmoud Ahmed Fathy Ashry · Talal Yousif Norelhuda Elhag

The proposal PDF contains the five confirmed students and their IDs.
