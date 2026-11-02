# Governed local execution adapter — checked 2026-11-01

The earlier copy/paste interception example is superseded by the implemented source. Do not reintroduce hardcoded targets/roles, use a flow ID as the ROE ID, or mark raw model/target arguments trusted.

- server/router.go verifies X-Kayan-Governance; controller/flows.go binds it to the authenticated user and persists the verified context.
- tools.NewFlowToolsExecutor requires that signed context, rejects external function registrations, and creates a shared trustgate.Session. Reloaded flows record unknown prior dispatch history and fail closed for environment tools.
- customExecutor.Execute requires actual upstream actor context, attaches actual flow/task/subtask identifiers, and calls AuthorizeResolved before handler dispatch.
- governance.go authenticates the context with TRUSTGATE_BRIDGE_KEY_FILE and performs the flow-start gate preflight. This is not per-model-call Go authorization.
- materialization.go retains raw proposals/source lineage as untrusted data. Only exact signed owned-lab templates select newly constructed execution arguments. Supported commands are bounded curl probes, with curlrc/proxy/redirect hardening; the small nmap grammar is not enabled by the current curl-only runtime menu.
- Signed execution intent is one-use across upstream actors with the same security role. Unsupported proposals and repeats stay denied. The shared state is not generalized semantic taint tracking.
- Explicit workflow capability permits non-executing metadata bodies as untrusted data; child effects still require their own gate ALLOW. The workflow map is incomplete (subtask_patch remains denied).
- providers/governance_prompts.go carries the verified command menu into rendered worker prompts so model delegation cannot silently lose the constraints.

Runtime: local Ollama, supported embedding none, host 127.0.0.1:8443 -> container 8080, image kayan-pentagi:governed-local. The ignored private key must be mounted; there is no published default key. See the canonical kayan-trustgate/MASTER_HANDOFF.md and integration/pentagi_local.py for exact commands.

Actual scoped Go comparison: 3 independently reproduced findings / 19 allowed / 15 denied including verifier calls (Go-only 16 / 15). All three flows waited after worker failures and were stopped. This proves bounded dispatch/evidence paths, not a completed upstream swap. Source, raw audit and comparison limits are recorded in eval/reports/pentagi_go_comparison_2026-11-01.md in the canonical repo.

Focused tests in pkg/trustgate, pkg/tools and pkg/providers pass; TestCedarLiveProfile is opt-in with TRUSTGATE_TEST_REAL=1 and a running local Rust gate/key file. Controlled handler tests and actual API/model runs are separate evidence.
