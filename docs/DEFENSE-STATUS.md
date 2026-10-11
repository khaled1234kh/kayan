# KAYAN — Defense Status

**Date:** 2026-10-10
**Repository:** `kayan-task-board`, branch `swarm/task-board`
**Sources:** `HANDOFF.md` (2026-10-09), `KAYAN_Project_Proposal.pdf` (submission edition, 06 Oct 2026), direct code inspection on this machine.

**One-sentence status:** The backend logic is tested and the frontend builds and runs its scripted demo, but nothing visual and nothing against a live backend or PostgreSQL has been confirmed on this machine.

**How to read this file:** Section 1 lists only features with a named test or command and a file path. Section 2 lists code that exists but has no passing run behind it here. Section 3 lists behavior that is simulated by design. Section 4 gives the exact replacement wording for claims that overstate the work.

---

## Section 1 — What is implemented and verified

| Feature | Verified by | Evidence location |
|---|---|---|
| Scripted demo order runs end to end: 43 events, TrustGate denial recorded, blocked then recovery, all five seats reach a terminal state | `npm run check:mock` — 16/16 PASS on 2026-10-10 | `kayan-3d/scripts/mock-mode-check.ts` |
| Transport behavior: command protocol, bounded reconnect, resume cursor, duplicate suppression | `npm run check:transport` — PASS on 2026-10-10 | `kayan-3d/scripts/transport-check.ts` |
| Frontend strict typecheck and production build | `npx tsc --noEmit` and `npm run build` — PASS on 2026-10-10 | `kayan-3d/tsconfig.json` |
| Task-board reducer: create lands in Todo, reassignment keeps the column and updates the assignee, start/block/complete move columns, a value-less update moves nothing, unknown ids are no-ops, existing order handling intact | Ad-hoc esbuild check — 14/14 PASS on 2026-10-10 | `C:\Users\khale\AppData\Local\Temp\opencode\task-reducer-check.ts` (folds `kayan-3d/src/state/eventReducer.ts`) |
| Backend runtime produces the same 43-event sequence as the frontend mock | `server/tests/test_runtime.py` asserts `len(events) == 43`; SQLite PASS recorded in HANDOFF on 2026-10-09, not re-run here | `server/tests/test_runtime.py:48,256,271,279` |
| Backend suite: 556 test functions across 32 test files covering event ordering, commands, the WebSocket bridge, the runtime, experiments, and P0.1–P0.5.1 (company, workforce, recommendations, contracts, lifecycle, budget, concurrency, periods) | `python -m pytest`, SQLite PASS recorded in HANDOFF on 2026-10-09, not re-run here (no Python environment on this machine) | `server/tests/test_*.py` |
| Budget enforcement: three ceilings (company, employee month, per-task), reserve-before-work, settlement with remainder release, denial recorded without charge, append-only ledger | `server/tests/test_p0_5_budget.py`, `test_p0_5_concurrency.py`, `test_p0_5_periods.py`; SQLite PASS recorded in HANDOFF on 2026-10-09 | `server/tests/test_p0_5_*.py`, `server/app/services/budget.py` |
| Company configuration: draft company plus monthly budget account in one transaction, workforce replacement with reporting-graph validation, versioned role templates, contract generation with frozen terms at activation, pause/resume | `server/tests/test_p0_2_*.py`, `test_p0_3_*.py`, `test_p0_4_*.py`, `test_p0_models.py`; SQLite PASS recorded in HANDOFF on 2026-10-09 | `server/tests/test_p0_*.py`, `server/app/services/companies.py`, `workforce.py`, `contracts.py`, `lifecycle.py`, `company_tasks.py` |
| At most one active company | Partial unique index `uq_one_active_company`, covered by model tests; SQLite PASS recorded in HANDOFF on 2026-10-09 | `server/app/models/company.py`, `server/tests/test_p0_models.py` |
| Six Alembic migrations chain from empty without drift (asserted against PostgreSQL in the migration test) | `server/tests/test_p0_migration.py`; PASS requires PostgreSQL — NOT RUN on this machine, see Section 2 | `server/alembic/versions/*.py` |

Notes on this table:

- "SQLite PASS recorded in HANDOFF" means the prior session ran the suite green against SQLite on 2026-10-09. This machine currently has no Python environment, so no backend test was re-run for this document.
- The backend function count above (556) is a direct count of `def test` in `server/tests/test_*.py`; HANDOFF records 624 executed tests from the 2026-10-09 run. The difference is parametrization: 8 `parametrize` markers expand single functions into multiple executed cases.
- The ad-hoc task-reducer check lives outside the repo (temp directory). It ran green against the committed reducer; it is not a wired npm script.

---

## Section 2 — What is implemented but unverified

Code exists for each item below. No automated test run or visual confirmation backs it on this machine.

- **Browser pass: NOT PERFORMED.** This machine has no browser (no Chrome, Edge, Firefox, Playwright, or Puppeteer). Nothing was visually confirmed and no browser console was read. This covers the 3D office, the wall-mounted task board (`TaskBoard3D`, whose 6-draw-call budget holds by construction, not by measurement), the Kanban overlay, the onboarding wizard, and the inspector, audit, and experiment views.
- **PostgreSQL tests: NOT RUN.** OS-level Application Control blocks the psycopg and PostgreSQL DLLs, so no local PostgreSQL runs here. Affected: the migration-chain tests (`test_p0_migration.py`, skipped without PostgreSQL), the trigger behavior (contract immutability trigger, append-only ledger trigger), `alembic check` no-drift, and all concurrency tests under a real database.
- **Live-backend suites: NOT RUN.** `npm run check:e2e`, `npm run check:command`, and `npm run check:experiment` drive the real transport against a running FastAPI plus PostgreSQL. The scripts exist (`kayan-3d/scripts/e2e-*.ts`) but were never executed here because the backend cannot run here.
- **Backend suite not re-runnable here.** There is no Python virtualenv on this machine, so `pytest` cannot execute. Section 1 backend rows rest on the recorded 2026-10-09 SQLite run, not on a fresh run.
- **Task-board REST integration untested.** The Kanban create/PATCH/status-move path against a live backend has no automated test; only the reducer projection is unit-checked (Section 1, row 4). The onboarding REST paths were path-fixed but never called against a live backend here.
- **Onboarding wizard end to end.** The five-step wizard exists (`kayan-3d/src/components/onboarding/`) but has no automated test and no browser confirmation.

---

## Section 3 — What is simulated, not real

These are design facts, not gaps. Each is stated in the code or the handoff.

- **The runtime is deterministic and scripted; it does not call a real LLM.** The demo order is a fixed step list (`kayan-3d/src/workflow/collabWorkflow.ts`) executed by `WorkflowSession` through `MockEventSource`. The backend dependency list contains no inference client library (`server/requirements.txt`: FastAPI, SQLAlchemy, Alembic, Pydantic, psycopg, pytest — no model provider package).
- **Cost metering uses `MockCostMeter` and produces mock amounts, not provider charges.** Prices are a hardcoded deterministic table, every output is labeled mock, and nothing is contacted over a network (`server/app/services/metering.py`: `MOCK_UNIT_PRICES`, `class MockCostMeter`).
- **Workforce recommendations use the `TemplateProvider`, not a real model.** The provider seam states "No model provider is configured in this deployment" and any model request resolves to the deterministic template fallback with a warning (`server/app/company/providers.py`).
- **CompanyTask execution is mock, not a real API call.** The pre-execution seam (`server/app/services/execution.py`) takes an injected callable; the proven property is that the callable is *not* reached when TrustGate denies or money is refused. Configured employees are not mapped to executing agents. No tool credentials exist anywhere in the call path.
- **The experiment harness compares gate conditions through the same scripted runtime.** `run_comparison` varies only `authorize_intent` versus `simulated_allow` (`server/app/security/trustgate.py:170,181`); it measures logic behavior, not model performance.
- **Mock mode is the default frontend.** Without `VITE_KAYAN_EVENT_SOURCE=backend` and a running backend, everything on screen is the local scripted prototype.

---

## Section 4 — Claims that must be softened

Use the right-hand wording in defense, slides, and demos.

| Do not claim | Say instead |
|---|---|
| "OPA/Rego is implemented" | "Policy decisions come from a Python evaluator, `authorize_intent` in `server/app/security/trustgate.py`; the browser keeps a mock-only copy in `kayan-3d/src/security/trustGate.ts`. No OPA/Rego runtime is integrated — a codebase-wide search finds no Rego policy evaluation. The proposal's Rego fragment (p. 10) is labeled there as an untested design illustration, not a complete policy." |
| "Autonomous AI agents" | "Deterministic scripted workflow. The demo order is a fixed 43-event script, asserted in `server/tests/test_runtime.py` and reproduced by `npm run check:mock`. No agent plans, reasons, or adapts." |
| "Real-time multi-tenant SaaS" | "Single-company prototype. At most one company is active at a time (`uq_one_active_company`). Events stream live over a WebSocket with replay-then-live handover, but there is no authentication — the budget-adjustment header is a dev-only shared secret that is open by default (`server/app/api/deps.py`: `verify_budget_adjustment_token`) — and no multi-tenant operation has been demonstrated." |
| "Budget accuracy" | "Budget enforcement logic with mock metering. Ceilings, reservations, settlement, and the append-only ledger are tested logic (Section 1); every amount originates from `MockCostMeter`, never from a provider charge." |

Further proposal claims that remain unproven by implementation: adaptive routing configurations B/C/D, the three cyber scenarios, the second template transfer, bilingual parity, customer validation, and any cost or market number. The proposal itself (pp. 29–30) marks these as requiring validation. Nothing in this repo measures them.
