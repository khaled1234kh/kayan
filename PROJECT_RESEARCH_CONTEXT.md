# KAYAN TrustGate: Research Context

Prepared 12 November 2026 from the checked-out repository and its retained evidence. This is a context inventory for a research agent. It is not new research, an architecture recommendation, or a fresh validation. No assessment was run and no source/configuration/policy/model file was changed.

## Evidence labels

- **Verified implementation (source):** behavior visible in source/config files read for this document; source inspection alone does not prove runtime behavior.
- **Historical result:** dated evaluation or checkpoint retained in the repository; not rerun for this document.
- **Proposal / backlog:** described as planned or unchecked in docs/TODO; not an implemented capability.
- **Unverified:** handoff/history claim not independently confirmed here, or not established by the checked evidence.

The master handoff is dated 4 November 2026 and contains multiple superseding historical sections. Use the newest explicitly dated section for each subject and retain older results as history. Its current top-level section reports the latest Planner baseline; its architecture/limitations sections summarize the project. This document cross-checks selected claims against source and the dated benchmark report; it does not refresh runtime state.

## 1. Current agents and responsibilities

**Verified in source.** The live path constructs five roles: Planner, Recon, Web-App, Network, and Reporting. `pentagi/live_engagement.py` uses four schema-constrained assignments for Recon, Web-App, Network, and Reporting; the Planner itself does not appear in that executor assignment list. `ReasoningAgent.run()` raises to prevent an independent ungoverned agent execution path. A shared `OllamaClient` is attached to participants. Each model call first requests TrustGate authorization for `llm_inference`.

The role-to-technique mapping and source terms identify Planner as planning, Recon as recon, Web-App as web-app, Network as network, and Reporting as reporting. Source-level responsibilities, corroborated by `docs/ARCHITECTURE.md` and the top section of `MASTER_HANDOFF.md`:

| Role | Responsibility in the live workflow | Boundary |
|---|---|---|
| Planner | Proposes fixed specialist assignments, reviews specialist outcomes, prioritizes allowed next tools, decides continue vs disclose partial, and coordinates the Reporting handoff | Coordinator only; no specialist tool execution assignment |
| Recon | Bounded reconnaissance against the owned loopback lab | Role-specific tool catalogue, TrustGate decisions, small action budget |
| Web-App | Bounded web application checks against the lab | Role-specific tool catalogue, TrustGate decisions, small action budget |
| Network | Bounded network/service checks against the lab | Role-specific tool catalogue, TrustGate decisions, small action budget |
| Reporting | Synthesizes findings/evidence and recommendations | Last specialist assignment; not intended to perform evidence-collection commands |

The Red/Blue label mapping in architecture/TA docs is Recon + Web-App + Network as Red Team, Reporting as Blue Team, with Planner coordinating. This label mapping does not create new privilege boundaries.

## 2. Orchestration and execution order

**Verified in source:** `LiveEngagement.create_engagement()` rejects targets other than exactly `127.0.0.1`, creates the governed roles, loads descriptive context separately, and initializes per-agent console state. `_model_call()` authorizes inference, records a streaming transcript event, supplies role/tier context, and records output/timing/token metadata. `_route()` signs Planner/operator messages and uses a bounded timeout; ambiguous delivery errors explicitly do not trigger automatic resend. `_instructions()` retrieves and acknowledges queued instructions.

The implementation and handoff describe the fixed order as **Planner plan → Recon → Web-App → Network → Reporting → Planner completion**. Planner reviews occur at specialist boundaries; a review names the next role, allowed priority tools, evidence IDs, and continue/disclose-partial action. Specialist output is constrained by the role's catalogue and bounded actions/retries; failures are meant to flow forward as coverage gaps rather than fabricated success. Reporting receives the evidence after the specialists. The deterministic baseline is `pentagi/orchestrator.py`; the live Qwen path is `pentagi/live_engagement.py`.

**Historical behavioral support, not rerun here:** handoff reports completed actual-model runs with correct order, Planner last, no Planner specialist-tool dispatch, Reporting handoff, and controlled denied requests. These dated runs do not prove every failure/recovery branch works now.

## 3. LLM configuration and hardware assumptions

**Verified configuration files:** `config/llm.json` specifies local Ollama at `http://127.0.0.1:11434`, primary `qwen2.5:7b`, fallback `qwen2.5:1.5b`, context `4096`, prediction limit `384`, and concurrency `1`. It records a maximum of 3 actions per specialist and up to 2 action retries. `config/model_tiers.json` maps A, B, and C to the same `qwen2.5:7b`. Tier is a capability/context budget label, not a distinct model assignment. Planner is not a second inference model; no fine-tuning is claimed.

The config records hardware observations/assumptions of an NVIDIA GeForce RTX 5060 Laptop GPU, 8,151 MiB observed total VRAM, and 31.2 GiB system RAM. Its own note warns that actual model VRAM residency must be measured and that 3D graphics share the GPU. These fields are configuration metadata, not a fresh hardware or resource measurement. The 1.5B fallback's actual selection/availability during present runs is **unverified here**.

## 4. TrustGate security and communication boundaries

**Verified in source/config:** `trustgate/service/src/main.rs` exposes health, authorization, ROE-load, audit, and audit-verification routes and builds its Cedar policy engine and audit log. `live_engagement.py` routes inference and tool actions through `trustgate.authorize(...)`; the live MVP fixes the only accepted target to loopback. The signed bridge (`integration/bridge_signing.py`) binds inter-agent messages to engagement/sender/recipient/text payloads. Model-produced assignments and decisions are structured with Pydantic schemas that forbid extra fields in the shown definitions. Role-specific tools live in `pentagi/lab_tools.py`.

**Important limits from source/docs:** the Axum service binds `0.0.0.0:8000`, and its source currently applies `CorsLayer::permissive()`. Therefore the loopback target restriction is not equivalent to network-interface isolation, and permissive CORS is not an origin allow-list. The handoff explicitly discloses local mutable hash-chain/HMAC audit storage, nonproduction identity/isolation limitations, incomplete upstream Go parity/delegation, and limits to universal semantic taint/provenance guarantees. These are architectural constraints, not solved merely by passing a bounded lab assessment. Inspect `trustgate/service/src/{authorize,policy,roe,taint,audit}.rs` and `integration/` before making detailed security claims.

Operator interaction is documented as status requests handled live and task-changing instructions queued for safe boundaries. Handoff says backend restoration reloads records only; active execution is not resumed. These are dated implementation/acceptance claims, not runtime checks made for this inventory.

## 5. MITRE ATT&CK and evaluations

**Verified implementation (source):** `pentagi/orchestrator.py` contains a static ATT&CK coverage mapping including `T1059` (Command and Scripting Interpreter) and associates observed technique labels with results. `pentagi/lab_tools.py` defines the bounded tool catalogue and its MITRE/finding mappings. The handoff says `grounding/` contains a pinned local index incorporating ATT&CK and OWASP material and describes local retrieval as TF-IDF; `pentagi/risk_plan.py` calls the local index and explicitly states its outputs are unverified hypotheses, not findings, and that it contacts no target. `grounding/` and its source/index/licenses are reference/retrieval material, not proof of technique execution. Coverage is bounded by available tools, supplied lab evidence, and test budget; a coverage percentage is not real-world ATT&CK coverage.

**Historical latest Planner benchmark (4 November 2026):** `docs/PLANNER_ACCURACY_2026-11-04.md` records 30 authored synthetic closed-world Planner cases: 24/30 (80.0%) first-attempt contract pass and 26/30 (86.7%) after the existing deployed validation/correction path. This is not vulnerability-detection accuracy, broad semantic accuracy, nor a random/representative sample. There were four final failures: P04 generation abort on token repeat limit; P08 unsupported curl/evidence-collection task assigned to Reporting and accepted by validator; R07/R08 rationales omitting supplied failure/verification gaps. The report also documents unscored invented flags/ports/arguments and unsupported narrative specificity. Thirty-two actual Planner inference requests and 33 Gate allows are reported; it was inference-only, with no specialist dispatch or target requests.

**Historical live engagement results in MASTER_HANDOFF:** the latest office/functionality section reports two separate actual-model runs (including `b813d8a6-cc6f-4456-a9bc-0929249fd2a4`) at 2 findings / 30 allowed / 1 denied each, with one directory-traversal check explicitly untested due to the unchanged budget. These are bounded owned-loopback runs and counts from retained records, not a general detection rate. No engagement was run for this document.

**Grounding evaluation, negative result preserved:** the handoff records earlier grounding-on/off comparisons with different bounded counts and explicitly states: **“No grounding improvement was demonstrated. Preserve this failure.”** The result is dated historical evidence, not a new experiment. It must not be recast as an improvement or generalized beyond the recorded comparisons.

## 6. Limitations, failures, and unresolved problems

- Latest Planner benchmark retains P04, P08, R07, and R08 failures. P08 is particularly relevant to boundary design: validator acceptance of a task string did not mean the command executed, but it exposed a gap in semantic task validation.
- Narrative fidelity, unsupported technical details, and the quality of generated risk reasoning are not captured by the 86.7% contract score.
- Live lab assessments have deliberately bounded tools/budgets. “Completed” does not mean comprehensive coverage; directory traversal is named as untested in a latest run.
- No grounding improvement was demonstrated. Keep the original regression and comparison evidence.
- One shared local model creates serial inference (`concurrency: 1`) and shares laptop GPU resources with the 3D UI. Actual VRAM residency/performance is not established by the config.
- Local mutable audit storage, runtime identity/isolation, universal provenance/taint semantics, and upstream Go worker delegation/completion remain disclosed limits in the handoff.
- Handoff records earlier host/Application Control failures and later successful normal builds/runs while noting that why the host behavior changed is unexplained. Those historical host outcomes were not reproduced here.
- Handoff says latest bounded implementation TODOs are checked but lists unresolved Planner quality cases and production architecture limitations. Do not translate “TODOs checked” into “all architectural problems solved.”
- Current service/process/container state, the installed model's presence, and current audit integrity were not checked for this context-only task.

## 7. Source and reference map

| Path | Responsibility / research value |
|---|---|
| `MASTER_HANDOFF.md` | Dated project state, superseding checkpoints, system map, recorded evaluations, limitations and startup notes. Read newest dated section per topic. |
| `pentagi/live_engagement.py` | Live Planner/specialist/Reporting flow, structured contracts, inference calls, TrustGate routing, signed message flow, target restriction. |
| `pentagi/orchestrator.py` | Deterministic orchestration baseline, role setup, counts and static MITRE coverage mapping. |
| `pentagi/agents/base_agent.py` | Agent identity, capabilities, tier and base boundary definitions. |
| `pentagi/lab_tools.py` | Tool catalogues by role, local lab operations and evidence/finding/technique mappings. |
| `pentagi/ollama_client.py` | Local Ollama request/response and generation handling. |
| `pentagi/inference_context.py`, `pentagi/call_context.py` | Role/tier prompt and evidence/context assembly. |
| `pentagi/engagement_context.py`, `pentagi/risk_plan.py` | Descriptive-only company context and deterministic offline Phase 1 hypotheses. |
| `trustgate/service/src/main.rs` | Rust/Axum routes, service binding, policy/audit state and CORS setup. |
| `trustgate/service/src/authorize.rs`, `policy.rs`, `roe.rs`, `taint.rs`, `audit.rs` | Authorization decision path, Cedar policy, rules of engagement, taint handling, audit persistence. |
| `integration/bridge_signing.py` and `integration/` | Signed inter-service/agent message binding, clients and bridge code. |
| `config/llm.json`, `config/model_tiers.json` | Actual declared provider/model/token/action/concurrency/hardware metadata and A/B/C mapping. |
| `grounding/build_index.py`, `grounding/retrieval.py`, `grounding/index.json`, `grounding/licenses/` | Local index construction, retrieval implementation, indexed material and source licenses. |
| `docs/ARCHITECTURE.md` | Human-readable roles, security boundaries and architecture description. |
| `docs/PLANNER_ACCURACY_2026-11-04.md` | Frozen Planner benchmark method, score, retained failure cases, metric limits and reproduction. |
| `eval/reports/planner_accuracy_20261104_v1/` | Raw benchmark outputs, frozen data, audit evidence, manifests and post-run semantic review referenced by the report. Historical; do not rerun. |
| `docs/BLOCKED.md` | Exact prior environment/tool blockers and outcomes. Historical errors need dates/context. |
| `TODO.md` | Open Planner quality items and visual/backlog state; checkboxes are not proof of broader capability. |

## Scope boundary for the next research agent

This context note is not an architecture recommendation and does not propose experiments. Before designing research, distinguish deterministic Phase 1 rules from the Qwen Planner; distinguish model output/schema acceptance from independently verified evidence; and distinguish dated benchmark/engagement records from current runtime facts. The user explicitly prohibited assessments for this task.
