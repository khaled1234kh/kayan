# KAYAN TrustGate — Project Proposal and Implementation Report

Revised 16 November 2026. This report follows the six TA sections in the supplied requirements mapping. The original brief was unavailable for independent comparison. Implemented behavior, recorded results and proposals are identified throughout.

## 1. System Overview & Architecture

KAYAN is a TrustGate-governed autonomous penetration-testing platform. Recon, Web-App and Network constitute its Red Team: they propose and perform bounded offensive tests against the local authorized lab. Reporting constitutes its Blue Team, assembling the evidence-based report and defensive recommendations. Planner coordinates these roles without becoming another offensive or defensive specialist. This allocation reuses the existing agents; it does not create additional execution authority.

The authorization foundation is a signed Rules of Engagement (ROE) contract. A Rust/Axum service authenticates the contract and uses Cedar policies to evaluate requested actions against enrolled roles, targets, techniques and time limits. The Python execution engine submits model and tool requests through this gate. Its executor exposes a fixed catalogue of lab operations rather than arbitrary model-selected shell commands or URLs. Supported candidate findings require a fresh second request before publication. Decisions are recorded in a hash-chained, HMAC-signed audit file; the storage remains mutable and must not be described as immutable.

The local Qwen2.5:7b model is shared across Planner, Recon, Web-App, Network and Reporting, with role-specific prompts and capability contracts. In the TA's base/helper/worker terminology, Qwen is the common inference base and the agents are specialized software workers around it. A shared model was chosen to fit the local compute and project-time budget; a distinct helper model was not implemented or evaluated. This is a design substitution, with no measured claim about a second model's capability, cost or latency. Calls are serialized within the configured local context and output budgets. A/B/C capability labels regulate context verbosity and responsibilities, rather than representing three independently trained models.

A FastAPI backend persists agent sessions and broadcasts snapshots over a WebSocket. A React Three Fiber/Three.js office presents the five workstations, current tasks, role tiers, transcripts and governance decisions. The backend and 3D client communicate through HTTP and WebSocket interfaces. The Python engine is the primary demonstration path. A separate upstream Go PentAGI integration provides a scoped enforcement comparison, with delegation limitations disclosed below. No equivalent sandbox guarantee is established for the Python process.

## 2. Required Data Inputs

The implemented optional descriptive inputs are company size (`company_size`), departments (`departments`), infrastructure summary (`infrastructure_summary`), network architecture (`network_architecture`), data storage (`data_storage`) and customer touchpoints (`customer_touchpoints`). **These six fields carry zero policy weight.** They frame Reporting's narrative and may separately be analyzed by the offline Risk Plan. They are treated as untrusted descriptions, not verified organizational facts, operator instructions or permission to test. Empty descriptive context is supported; unknown fields, invalid types and excessive lengths are rejected.

Authorization inputs are a separate tier. The signed ROE specifies targets, authorized techniques, forbidden actions and the permitted time window, alongside the role/action contract used by the gate. Descriptive context is held outside the ROE and does not enter signing, loading or Cedar authorization inputs. Keeping these tiers separate prevents a statement such as an infrastructure description from silently expanding the testing scope. Reporting's model-written narrative remains unvalidated narrative even when its input has passed structural validation.

## 3. Core Deliverables & Logic Flow

Phase 1, the Risk Plan, uses eight authored scenario rules and a pinned MITRE ATT&CK/OWASP reference index. A hypothesis requires multiple technical signals. It includes source excerpts, a potential consequence, a rationale for reference applicability and explicit assumptions. Unsupported scenarios yield an empty result. The ordering reflects scenario relevance. The system does not estimate severity, likelihood or business loss. This offline path accesses no targets and calls no model, tool or authorization endpoint.

Phase 2 offers two evidence paths. Option A, Direct Mitigation, passes Phase 1's hypotheses to Reporting's deterministic builder. It selects authored controls tied to the relevant scenario, assets and source excerpts. The result carries a hypothetical evidence basis and zero verified findings. Actual control effectiveness and analyst time savings remain unmeasured.

Option B, Pentest-to-Mitigation, uses the existing live governed assessment. Supported reproduced findings and their runtime proof/audit references feed the same mitigation structure. A saved completed report can be displayed without starting another assessment. The reporting layer checks the proof envelope supplied by the runtime; displaying the report does not independently reproduce the finding or cryptographically verify the entire execution history.

The recorded synthetic planning fixture produced three hypothetical risks, three Option A recommendations and zero findings. The separate Option B view of saved engagement `7da73508-01e6-48e9-9093-be09c5fd734d` produced two recommendations from two verified findings. These are different evidence bases, not a quality comparison between the paths. That recorded real-model rehearsal had two findings, 29 allowed decisions and one denied decision, including its deliberately tainted-input probe. The final three-path demonstration reused this saved report rather than launching a fresh live engagement. The source results are preserved in the [TA alignment record](TA_DELIVERABLES_ALIGNMENT.md) and [recorded functionality checkpoint](FUNCTIONALITY_CHECKPOINT_2026-11-01.md).

## 4. Blue Team Configuration & Pricing Logic

Reporting recommendations expose Defense in Depth and Zero Trust grouping filters, inclusion controls and additive illustrative point weights. A filter changes the visible grouping without changing inclusion. Excluding a recommendation changes the displayed total; export preserves the original recommendation evidence and records the presentation selection separately. These controls implement the mapped requirement for configurable strategic-framework presentation and cost-responsive output through a transparent relative-weight mechanism.

The exact shipped disclaimer is: **“Illustrative relative effort/cost only. Points are comparison weights, not prices, quotes or measured implementation effort.”** There is no real pricing or billing engine. The project has no measured implementation-cost dataset or calibrated commercial estimator; presenting the weights as prices would therefore create unsupported precision. This is an explicit bounded interpretation of the mapped requirement, not a claim that actual procurement pricing or mitigation effectiveness has been validated. Selecting a framework or a recommendation does not change authorization or agent execution.

## 5. LLM Training & Framework Evaluation Task

Fine-tuning was considered and rejected at the design stage because of local infrastructure and project-time constraints. No training experiment was conducted. The implemented substitution is a pretrained local Qwen2.5:7b model with role prompts, skill packets and retrieved ATT&CK/OWASP context; these additions do not change trained weights. The combined local index already contains both MITRE ATT&CK and OWASP Top 10. A query may retrieve either framework, so using the combined index does not imply that every model call receives both.

In the recorded v1 live comparison, grounding off produced one finding, 23 allows, one denial and 20% findings-based MITRE coverage. Grounding on produced zero findings, 23 allows, two denials and 0% coverage. TrustGate denied an unsupported action proposed by the grounded Web-App agent.

The later v2 comparison tied across both conditions at two findings, 29 allows, one denial and 40% coverage. Both findings reproduced. The legacy evidence rubric counted 1/2 under its own proof criteria. The coverage denominator is five lab categories. The reflection finding establishes raw reflection only.

**No grounding improvement was demonstrated in live engagements.** The [v1 comparison](../eval/reports/live_grounding_comparison.md) and [v2 comparison](../eval/reports/live_grounding_comparison_v2_bounded_retry.md) preserve the regression and tie. The small comparisons and intervening workflow changes limit causal interpretation.

The [scoped Go evaluation](../eval/reports/pentagi_go_comparison_2026-11-01.md) recorded three reproduced findings, 19 allows including verifier requests, and 15 denials. Worker failures and differing workflows limit the comparison.

The November 4 inference-only Planner benchmark passed 24/30 authored cases at first attempt and 26/30 after correction. Separately, the offline defensive study found ATT&CK mapping micro-F1 of 0.167 without references and 0.778 with lexical references on 32 authored cases. A same-model evidence screen reached 0.800 while strict exactness stayed 25/32. These results measure distinct tasks with different denominators. The [research update](RESEARCH_UPDATE.md) documents the limits and the five-checkpoint comparison. Training time, a trained-model winner and general accuracy remain unmeasured.

## 6. Pending Tasks / Future Iterations

Blue Team task allocation is resolved: Reporting owns defensive and mitigation synthesis, receiving hypotheses in Option A and reproduced findings in Option B. The remaining work concerns the limitations below rather than an undecided Blue Team role.

Upstream PentAGI/Go worker delegation and ROE revocation on completion remain open. The [November 2 asset and bundle verification](ASSET_BUNDLE_VERIFICATION_2026-11-02.md) documents the runtime FBX compatibility migration and production chunk split. Full asset re-export and broader animation fidelity were outside that check.

The original acceptance screenshots established functional task/result display but did not measure its roughly two-second task-start criterion. The pre-meeting pass supplied new rendered-frame evidence: one real deterministic fixture showed the current task, working state, tier and new transcript entry within 0.916 seconds of publication. This is a sampled local observation, not a universal latency guarantee; result rendering and expansion were checked separately. The [twelve-step closure review](CLOSURE_EVIDENCE_REVIEW_2026-11-01.md) preserves the original gap, and the [meeting-readiness record](TA_MEETING_READINESS_2026-11-01.md) documents its bounded recheck. No original checklist item is currently left unobserved within those stated limits; this does not turn sampled visual acceptance into certification of every device or camera angle.

The [cloud-ready research design](RESEARCH_UPDATE.md#proposed-cloud-ready-defensive-review) covers four inference placements for offline defensive evidence review under independent TrustGate controls. It remains a proposal. Independent human annotation, confirmatory model selection and isolated Rust/Cedar verification are open. Production readiness also requires validated identity, isolation and durable audit controls.
