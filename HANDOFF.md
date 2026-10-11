# KAYAN — Engineering Handoff

**Date:** 2026-10-09
**Scope:** Tasks 07–10 delivered in this session (backend foundation, event bridge, backend runtime, backend experiment harness), on top of the existing frontend (Tasks 01–06).
**State:** backend and frontend both green. No commit was made (see *Git*).

---

## 1. What this system is

KAYAN is a 3D office visualisation over an agent collaboration workflow, with a
security demonstration: an agent forms an intent, a policy gate decides
pre-execution, and the office shows what happened.

The frontend is a visualisation + interaction layer. The Python backend owns
business state and is becoming the authority:

```
React / Three.js  ──commands──▶  FastAPI  ──▶  KAYAN Runtime  ──▶  TrustGate
      ▲                                │                              │
      └──── WebSocket events ◀─────────┴──── EventBus ◀── PostgreSQL ◀─┘
                │                                        (persist → commit → publish)
                └── existing reducer → existing UI (3D + panels + audit)
```

The browser decides **nothing** in backend mode. It sends one of two commands
and renders the events that come back.

### Repository layout

```
KAYAN-final/
  kayan-3d/            frontend (React 18, Vite 5, three, zustand)
    src/
      experiments/     local mock harness + backend experiment client
      transport/       FastApiEventSource (WebSocket) + source selection
      state/           Zustand store, event reducer, MockEventSource
      workflow/        TypeScript workflow (mock mode only)
      security/        mock TrustGate (mock mode only)
      components/      3D scene, panels, AuditView, ExperimentView
    scripts/           headless check scripts (node, via esbuild)
  server/              backend (FastAPI, SQLAlchemy, PostgreSQL)
    app/
      runtime/         the authoritative business workflow
      security/        the authoritative TrustGate evaluator
      events/          ordering, publication, wire projections
      services/        queries, EventService, company/workforce/catalog/contracts,
                 recommendations, contracts, company lifecycle, budget, metering
      models/          typed ORM models
      company/         template catalogue, provider seam + template provider,
                        recommendation/contract validation, contract hash, supported
                        permission vocabulary, budget arithmetic, reporting
                        validator, errors
      schemas/         Pydantic API + command contracts
      api/             HTTP routes + the /ws/events bridge
      db/              engine/session, seed, role template seed
      scripts/         devdb.py (local PostgreSQL), init_db.py
    tests/             624 tests (600 P0.1–P0.5 + 24 P0.5.1 hardening)
    alembic/           initial schema, P0 company/workforce/contract/budget,
                       P0.2 employee responsibilities, P0.3 recommendations,
                       P0.4 contract role version + escalation,
                       P0.5 company tasks + append-only ledger
```

---

## 2. Run it

Three terminals. All commands are PowerShell from
`C:\Users\khale\Downloads\KAYAN-video\KAYAN-final`.

**1 — database**
```powershell
cd server
..\.venv\Scripts\python.exe -m app.scripts.devdb start --data-dir .pgdata --db kayan --port 54321
```

**2 — backend** (first run only: `alembic upgrade head`, then `init_db --demo`)
```powershell
cd server
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.scripts.init_db --demo
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

**3 — frontend**
```powershell
cd kayan-3d
npm run dev            # mock mode (default, needs no backend)
```

Backend mode:
```powershell
cd kayan-3d
Copy-Item .env.backend.example .env.local     # sets VITE_KAYAN_EVENT_SOURCE=backend
npm run dev                                    # restart dev server after copying
```

Open <http://localhost:5173>. API docs at <http://127.0.0.1:8000/docs>.

Stop: Ctrl+C in terminals 2–3, then `python -m app.scripts.devdb stop` (data kept).

### Configuration

`server/.env` (gitignored; `.env.example` documents every key):

| Key | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | sqlite file | Use `postgresql+psycopg://…` |
| `APP_ENV` | `development` | `production` unmounts `/api/dev/*` and disables experiments |
| `ENABLE_DEV_ENDPOINTS` | `false` | Mounts the development event publisher |
| `ENABLE_EXPERIMENTS` | `false` | Enables the `run_comparison` command |
| `RUNTIME_PACE_MS` | `0` | Scales step delays when you want to watch a run |

Frontend `.env.local` (Vite only exposes `VITE_`-prefixed vars):
`VITE_KAYAN_EVENT_SOURCE` (`mock` | `backend`), `VITE_KAYAN_API_URL`,
`VITE_KAYAN_STREAM`.

---

## 3. What each task delivered

### Task 07 — backend foundation
FastAPI + PostgreSQL + SQLAlchemy 2.0 + Pydantic. Entities: Agent, Task,
Message, Handoff, Event, ExperimentRun/WorkflowRun, CommandRequest. Engine/session
in one place, Alembic for migrations, env-only credentials. Read-only REST API.
Deterministic seed of the five canonical agents plus a demo order. Event
ordering by a per-stream monotonic `sequence` (not wall clock).

### Task 08 — WebSocket event bridge
`GET /ws/events?stream=main[&afterSequence=N]`. Replays persisted events in
sequence order, then tails live. The replay→live handover subscribes **before**
reading history and flushes the buffer after, so no committed event is missed and
none is delivered twice. Multiple independent clients. `FastApiEventSource`
implements the existing `KayanEventSource`; it is a pure transport (no Zustand, no
reducer logic, no business rules). Resume cursor + bounded reconnect with backoff.
Source selection defaults to mock; backend is opt-in.

### Task 09 — backend runtime + first command
`KayanRuntime().request_order(session, order_id=…, request_id=…)` executes the
whole workflow with no browser, producing the same 43-event sequence as the
verified frontend mock (asserted by test). Messages, handoffs, intents, task
transitions and events are owned by the runtime and persisted through the service
layer. The authoritative TrustGate is ported to `app/security/trustgate.py`.
Command `request_order` added with `command_ack`, idempotency by `requestId`, one
active run per order.

### Task 10 — backend experiment harness
Command `run_comparison` runs both conditions through the **same** runtime and
workflow; the only variable is the gate (`authorize_intent` vs `simulated_allow`).
Each trial is a persisted `workflow_runs` row linked by `experiment_id`,
`condition`, `seed`, `run_index`, with every metric derived from its own events.
Aggregates are computed on read. `ExperimentView` gained a backend path that
submits the command, polls persisted status and renders backend records; the mock
path is untouched.

### P0.1 — company configuration schema
The foundation for configuring a real company, staged so nothing in the running
system changes behaviour yet. Eight new tables (`server/app/models/company.py`):
`companies`, `role_templates`, `company_employees`, `contracts`, `budget_accounts`,
`budget_reservations`, `budget_ledger_entries`, plus `events.clock_offset_ms`.
Migration `90c90b1427fa` (revision `17252b923d8c` → `90c90b1427fa`), verified
against a database created empty.

Decisions worth keeping:

- **`CompanyEmployee` is configuration only.** It never becomes an `Agent` row and
  never reuses a canonical demo id; ids carry an `emp_` prefix. Execution mapping
  (employee → active contract → agent) is a later phase, not this one.
- **At most one active company**, enforced by the partial unique index
  `uq_one_active_company`; drafts are unlimited and a paused company does not
  consume the slot, so pause/resume stays reversible.
- **Contract terms freeze at activation.** A PostgreSQL trigger rejects any change
  to a material column of an activated contract while still allowing the lifecycle
  transition to `superseded`, and refuses to delete it. A partial unique index keeps
  one active contract per employee.
- **Role templates are versioned seed data.** `(key, config_version)` is the primary
  key, so redefining a role adds a version and a contract generated from an older
  one stays explainable. Seeded at startup by `app/db/seed_roles.py` from
  `app/company/templates.py`; the catalogue carries structured default scopes, not
  just prose.
- **Governance event vocabulary** added to the backend *and* frontend catalogues
  (17 types, category `governance`, plus an Audit filter). Parity between the two
  catalogues is asserted by test, so they cannot drift.
- **No wizard, no new commands, no runtime mapping.** The command protocol is still
  `request_order` and `run_comparison`; the office still shows the canonical five.

### P0.2 — company and workforce APIs
Draft companies and their employees can now be configured over HTTP. The eight
endpoints are under the existing `/api` router; nothing about the running demo
changed — the canonical five agents, the runtime, TrustGate and the experiment
harness are untouched, and there is still no WebSocket write path.

- **Company** — `POST /api/companies` creates a draft company *and* its initial
  monthly `BudgetAccount` in one transaction, then returns the configuration.
  `PATCH` applies partial draft edits and keeps the company and its budget account
  consistent. A PATCH that changes nothing is a read: it returns 200 and emits no
  event, because reporting a change that did not happen would make the audit trail
  lie. Only drafts are editable; activation is a later stage, so a non-draft
  company is 409 and `status` is not a writable field.
- **Workforce** — `PUT /api/companies/{id}/workforce` states the complete desired
  workforce. It is a replacement, not a merge: anything absent is removed. New
  seats get backend-generated `emp_` ids; supplied ids must already belong to this
  company, so a request can never touch another company's roster. Employees stay in
  `draft` and are never inserted into `agents`.
- **Reporting lines** — `app/company/reporting.py` validates the hierarchy as a
  graph over the *proposed* workforce, so seats may reference each other regardless
  of request order. Self-reference, missing targets, cross-company targets and
  cycles of any length are rejected before a single row is written. A flat
  workforce is allowed; a diamond is not a cycle.
- **Catalogue** — `/api/setup/templates` and `/api/setup/roles` serve the seeded,
  versioned `role_templates` rows (only the current `config_version` of each key),
  ordered deterministically. An unknown `template_key` is 422 rather than a silently
  unfiltered list.

Design decisions worth keeping:

- **One transaction for the change and its event.** `EventService` gained a narrow
  `stage()` / `commit_and_publish()` pair so a domain mutation and its governance
  event commit together and publish only afterwards. `record()` is unchanged and is
  now expressed in terms of them.
- **Strict inbound schemas.** `extra="forbid"` means a client sending `status` or
  `activeContractId` is told plainly instead of having it ignored. Read-only fields
  that appear in responses (`companyId`, `status`) are accepted on input but
  validated, so a client can read a workforce and send it straight back.
- **`Decimal` all the way.** JSON numbers are converted through their decimal
  string form, `NaN`/infinity are refused, and more precision than `Numeric(18, 6)`
  holds is rejected rather than rounded. A currency change is refused, never
  converted.
- **One migration.** `05f09d5e2ace` adds `company_employees.responsibilities` with a
  temporary server default so the upgrade is safe on a populated table (verified by
  test). The already-applied migrations were not touched.

### P0.3 — workforce recommendation service
The backend can propose a workforce for a draft company, validate the proposal,
store it and audit it — without changing the company at all.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/setup/recommendations` | Generate a proposal (201) |
| `GET` | `/api/setup/recommendations/{id}` | Retrieve a stored proposal |

- **A proposal is inert.** Generation creates a `recommendations` row and nothing
  else: no `CompanyEmployee`, no `Contract`, no budget movement, not even a company
  `revision` bump. The owner's roster only changes when they submit a workforce,
  which is a P0.2 operation.
- **Only the company identifies the request.** Budget, currency, template and target
  are read from the saved company. Restating them is refused, because a proposal
  built on a stale copy of the ceiling is a proposal against money that does not
  exist.
- **Provider seam, no provider beyond the template.** `RecommendationProvider` is a
  protocol with a registry, a selection policy and an explicit fallback rule.
  `TemplateProvider` is deterministic and needs no credentials. **No model provider
  is configured**: the backend declares no inference dependency and holds no
  inference credentials, so `RECOMMENDATION_PROVIDER=model` resolves to the template
  fallback and says so in the response's warnings. Requesting a model provider never
  fabricates a call and never mislabels the result.
- **Provider output is untrusted input.** Every proposal — template or model — is
  re-derived against the catalogue before it can be stored: every role key and
  version must exist, the role must be offered by the company's template, the seat
  kind must match, scopes must parse as structured grants, responsibilities must be
  stated, and the reporting graph is checked by the same P0.2 validator. A provider
  cannot define executable permissions by asserting them.
- **Money is apportioned, not estimated.** Shares are weighted by role and
  *truncated* (never rounded) before the remainder is handed out one unit at a
  time, so `sum(monthly) <= ceiling` holds exactly in `Decimal` and no seat absorbs
  an arbitrary rounding remainder. Each seat's per-task ceiling is at most half its
  monthly allocation, and the unallocated remainder is reported explicitly.
- **Deterministic and bounded.** The same company, preferences and catalogue version
  produce byte-identical proposals. A request for 20 seats returns the 6 distinct
  roles the template can justify and explains that more seats would repeat existing
  work — adding people is not treated as automatically better.
- **Snapshots stand alone.** The stored proposal includes each role's
  `config_version`, scopes and rationale, so a later catalogue revision cannot
  change what was recommended. Money is persisted as decimal strings, never floats.
- **Announced only after storage.** The record commits with
  `recommendation_generated` in one transaction, published afterwards. A provider
  that fails, or returns something invalid, produces no record and no event.

### P0.4 — contracts, activation and company lifecycle
A configured company can now be given contracts, reviewed, activated, paused and
resumed, with activated terms immutable.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/companies/{id}/contracts/generate` | One draft contract per employee (201) |
| `GET` | `/api/companies/{id}/contracts` | Every version |
| `GET` | `/api/contracts/{id}` | One contract with its metadata |
| `PATCH` | `/api/contracts/{id}` | Edit a **draft** only |
| `POST` | `/api/contracts/{id}/versions` | Draft successor to an activated contract (201) |
| `POST` | `/api/companies/{id}/activate` | Atomic activation |
| `POST` | `/api/companies/{id}/pause` | Pause an active company |
| `POST` | `/api/companies/{id}/resume` | Resume, optionally activating reviewed successors |

Decisions worth keeping:

- **Budgets are requested, never invented.** `CompanyEmployee` does not retain a
  draft allocation, so `generate` takes one per employee and refuses the request
  unless the set exactly covers the workforce: no unknown ids, no duplicates, no
  cross-company references, per-task within per-month, total within the ceiling.
- **Terms are derived least-privilege.** Scopes come from the role's catalogue
  defaults, a catalogue restriction that forbids finalising without approval becomes
  an executable approval rule, and communication defaults to "may talk to my
  manager". `role` stores the role **key**, not its label.
- **The permission vocabulary is derived, not restated.**
  `app/company/permissions.py` reads supported resources, tools, operations,
  restrictions and task categories out of the seeded catalogue, so a second
  hand-written list cannot drift from it. An unfamiliar tool is refused, never
  widened.
- **The hash covers the whole contract.** Canonical JSON, sorted keys, `Decimal` as a
  plain decimal string, SHA-256 over every material term including budgets and the
  reporting line. `5000` and `5000.00` hash identically; any material change changes
  the digest; a lifecycle change does not. Activation **recomputes** it and refuses a
  contract whose terms no longer match.
- **Validation is over the whole contract, not the patch.** A PATCH that fixes one
  field is still refused if another field is invalid, and a no-op PATCH returns 200
  without an event.
- **Two new event types, not misused ones.** A draft edit emits `contract_updated`
  and a successor draft emits `contract_version_created`. `contract_superseded` is
  reserved for the moment a predecessor actually stops being effective, which is
  during resume — creating a successor supersedes nothing.
- **Activation re-verifies instead of trusting.** Role versions, scopes, reporting
  graph, communication targets, approval rules, budgets and hashes are checked again
  at activation, so a contract edited behind the service, or a catalogue revised
  since generation, is caught before it becomes live authority.
- **Atomicity is one commit, not one flush.** Resume issues two flushes so a
  predecessor is superseded *in the database* before its successor activates — the
  partial unique index is evaluated per statement — and still commits once.
- **Two schema gaps closed by one migration.** `contracts.role_config_version` and
  `contracts.requires_human_escalation` did not exist. The migration adds both with
  temporary server defaults (safe on a populated table) and **replaces** the
  immutability trigger so the database protects the same terms the hash does. The
  applied P0.1 migration was not rewritten.
- **One consequence worth knowing:** because the trigger refuses to delete an
  activated contract, deleting a company that has activated contracts now fails at
  the database. That is the intended reading - contract history is not disposable -
  and P0 exposes no company-delete endpoint anyway.

### P0.5 — budget enforcement, reservations and cost metering
Money is now committed, reconciled and audited. The company ceiling is a hard
maximum, and the service is the only authority for that.

- **Three ceilings, tightest wins.** For a company period, for an employee's month
  (from their active contract) and for one employee on one task,
  `available = limit - spend - outstanding`. A request must fit all three; fitting
  the company budget while breaching the employee's allocation is still refused.
- **Reserve before execution.** No billable work starts without a successful
  reservation, and the amount committed is the *maximum* cost, not the expected one.
- **A denial is a result, not an exception.** It is recorded in the ledger and
  committed as `budget_reservation_denied`, creates no active reservation, and
  returns an explicit refused result. Rolling back the evidence with an exception
  would leave a refusal with no record.
- **Nothing is trusted from the caller.** Ceilings, contract state, balances and
  contract hashes are resolved from persisted records; the request carries no limits
  at all, and supplying them is rejected rather than ignored.
- **Contract is the source of an employee's limits.** They are read from the active
  contract each time, never copied into an authorization field that could drift, and
  the contract's integrity hash is re-verified before it may authorise money.
- **Counting rules.** Actual spend comes from ledger entries whose category counts as
  spend; outstanding commitments come from the reservation table. Counting a
  reservation as spend too would deduct the same money twice.
- **Concurrency is a database guarantee.** Reservations lock the company period's
  `BudgetAccount` `FOR UPDATE`, so two requests that each fit alone cannot both be
  approved. A racing duplicate idempotency key loses the unique constraint and
  replays the winner's reservation instead of erroring.
- **Settlement reconciles, it does not assume.** The actual charge is recorded, the
  unused remainder released, and a settlement above the reservation is an explicit
  reconciliation failure that leaves the reservation committed - so the discrepancy
  cannot be spent past.
- **The ledger is append-only.** A PostgreSQL trigger refuses UPDATE and DELETE;
  corrections are new `refund_or_adjustment` entries. Money crosses the API as
  decimal strings, never floats.
- **Adjustments are absolute and audited.** The canonical form is "the ceiling is now
  X"; a delta would need a sign convention callers get wrong. A reduction below
  committed money or below active contract allocations is refused.
- **Metering is mocked and labelled.** No inference provider is configured, so
  `MockCostMeter` is the only meter and everything it produces is marked `mock`. A
  communication and the model call behind it are recorded but charged once.
- **Three endpoints, deliberately.** `GET .../budget`, `GET .../budget/ledger` and
  `POST .../budget/adjustments`. Reserve, settle and release are *not* HTTP
  endpoints: they are trusted backend operations, and exposing them would let any
  client move a company's money.
- **`budget_limit_reached` event emitted on exhaustion.** When a ceiling's available
  amount reaches exactly zero, a `budget_limit_reached` event is published with
  `level` (`company` | `employee` | `task`), the `limitAmount`, `currency`, and
  the affected `employeeId`/`taskId` where applicable. A mere denial with funds
  still available does **not** emit it.
- **Exhaustion is deduplicated by state, not by request.** A marker ledger entry
  (`BudgetLedgerCategory.BUDGET_LIMIT_REACHED`, amount zero) records the
  transition. A later release, refund, or ceiling increase restores capacity; the
  next zero transition is a new event. This uses the append-only ledger as the
  state machine - no new table.
- **Injectable UTC accounting clock.** `BudgetService(session, clock=...)` and
  `current_account(now=...)` accept an explicit instant for deterministic
  month-boundary tests. Production defaults to the real UTC clock; naive datetimes
  are rejected.
- **Two known gaps, both deliberate.** The adjustment endpoint is unauthenticated -
  KAYAN has no auth in this phase, so it inherits the local/development posture of
  the other write endpoints. And `CompanyEmployee` is still not mapped to an
  executing agent, so the pre-execution seam is exercised directly rather than by
  the runtime.

---
---

## 4. Architecture decisions you should know

**One run record.** `ExperimentRun` and `WorkflowRun` overlapped, so
`ExperimentRun` was removed. A commanded order and an experimental trial are both
`workflow_runs`; a trial just carries `experiment_id`/`condition`/`seed`/
`run_index`. `events.run_id` is a real foreign key again. One concept, one table.

**Persist → commit → publish.** `EventService.record()` commits before it
publishes to the `EventBus`. A failed commit publishes nothing, so a client can
never observe unrecorded state. The WebSocket only subscribes.

**One timestamp convention (corrected in P0.1).** A persisted `events.timestamp` is
**always real UTC**. The workflow's reproducible position travels separately in the
nullable `events.clock_offset_ms`, derived from the authored step delays. Experiment
timing and `duration_ms` are computed from those offsets, and `wall_clock_ms` still
records real elapsed time. Nothing sleeps to inflate a number.

This replaced an earlier design where the workflow stamped events on a fixed virtual
clock (`VIRTUAL_EPOCH`, 2026-03-14). That had two defects: the activity feed showed
the same 2026-03-14 date for every run, and real configuration changes had to share
one stream with synthetic times. `sequence` remains the authoritative stream order,
and the 43-event sequence and workflow semantics are unchanged.

**Read-only bridge.** The socket carries business events server→client and two
commands client→server (`request_order`, `run_comparison`). Inbound non-command
frames are refused with a protocol error. There is no browser-side business write.

**Isolation.** Trial evidence is read per run
(`GET /api/experiments/runs/{runId}/events`), not by filtering the live `main`
stream — so the stream's ordering guarantees are untouched and one trial's audit
can never mix with another's.

**Trusted decisions live in one place.** `app/security/trustgate.py` is the only
evaluator in backend mode. The frontend mock (`src/security/trustGate.ts`) is
retained solely for mock mode.

---

## 5. Tests and verification

**Backend — 624 tests. SQLite: PASS. PostgreSQL: NOT RUN — blocked by local OS environment (Smart App Control blocking psycopg and postgres DLLs).**
```powershell
cd server
..\.venv\Scripts\python.exe -m pytest
$env:KAYAN_TEST_DATABASE_URL="postgresql+psycopg://postgres:@127.0.0.1:54321/kayan_test"
..\.venv\Scripts\python.exe -m pytest
```
Covers: health, DB connection, agent/task/message/handoff/event/run persistence,
message threading, per-stream event ordering, the WebSocket bridge (replay, live,
ordering, multiple clients, disconnect, resume, no missed events), the command
protocol (valid/duplicate/unknown/malformed, concurrency), the runtime (both
conditions, collaboration directions, TrustGate, failure honesty), experiments
(per-condition semantics, aggregation integrity, isolation, exports), and API
serialisation.

P0.1 added 76 tests, P0.2 added 93, P0.3 added 61, P0.4 added 122,
P0.5 added 70:

- `tests/test_p0_models.py` (50) — configuration-only identity, single-active-company,
  role-template versioning and seed idempotency, contract/budget constraints, the
  governance catalogue (including frontend parity), and the timestamp convention.
  Two are worth calling out: `test_two_runs_report_the_same_duration_despite_real_time`
  fails if timing ever starts depending on wall-clock again, and
  `test_configured_employees_never_enter_the_agent_table` fails if a configured seat
  ever inherits demo privileges.
- `tests/test_p0_migration.py` (26) — builds a throwaway PostgreSQL database, runs
  the real Alembic chain from empty, and asserts the schema *and* behaviour: trigger
  installed, every material column immutable after activation, lifecycle transition
  still allowed, activated contract undeletable, one active contract per employee,
  money stored as exact decimal, and `alembic check` reporting no drift between the
  models and the migration. Skipped unless `KAYAN_TEST_DATABASE_URL` is PostgreSQL.

P0.2 added 93 tests across five modules:

- `tests/test_p0_2_companies.py` (29) — creation, retrieval, cross-session
  persistence, partial updates, budget consistency, multiple drafts, and the full
  rejection matrix (empty name, unknown template, bad currency, non-positive
  budget, over-precision, malformed targets, non-draft edit, unknown field).
- `tests/test_p0_2_workforce.py` (23) — 25-employee workforce, editing by stable id,
  add/remove replacement semantics, duplicate and foreign ids, unknown roles, roles
  outside the company's template, refusal once not draft, and three atomicity tests
  proving a rejected replacement leaves the previous workforce completely intact.
- `tests/test_p0_2_reporting.py` (16) — the validator as a unit: flat, chain,
  forward reference, diamond and 40-deep chain accepted; self-reference, missing
  target, cross-company, and 2/3/4-person cycles plus a cycle hidden behind a valid
  prefix rejected, with the cycle path in the error details.
- `tests/test_p0_2_catalog.py` (8) — template and role shape, roles served from the
  database with only the current version exposed, template filtering, the documented
  error for an unknown template, and deterministic ordering.
- `tests/test_p0_2_events.py` (16) — the right events emitted with the right
  payloads, no event for a no-op PATCH or a re-sent budget, nothing published when a
  transaction fails, configuration events carrying no run and no logical offset, and
  a subscriber that reads the company through its own session at publication time —
  which fails if publication ever precedes the commit.

P0.3 added 61 tests across two modules:

- `tests/test_p0_3_recommendations.py` (36) — the template provider against all three
  templates, determinism for identical input, preference handling (counts, no-human,
  no-HR, notes), the refusal matrix for malformed preferences, lifecycle errors,
  reporting structure, targeted communication, scope carriage, per-seat rationale, and
  the budget rules (totals within the ceiling, per-task within monthly, decimal
  precision end to end, a tiny ceiling, and no budget record moved).
- `tests/test_p0_3_audit.py` (25) — retrieval by id, survival of a new session, a
  snapshot that still describes the proposal after the catalogue role is revised,
  history accumulation, `proposed` never becoming `accepted`, the event payload shape
  (no prompts), the subscriber probe proving persistence precedes publication, and —
  most importantly — the negative cases: a provider that raises, invents a role,
  overspends, injects a role the template does not offer, or creates a reporting
  cycle is rejected with nothing persisted and no event emitted. Plus four assertions
  that generation touches no employee, no contract, no company status and no
  canonical agent.
- P0.4 added 122 tests across two modules plus the PostgreSQL trigger:
  `tests/test_p0_4_contracts.py` (70) covers generation, allocation validation
  through the API, regeneration, hash canonicality and coverage of every material
  column, and draft editing including the whole-contract validation rule;
  `tests/test_p0_4_lifecycle.py` (51) covers atomic activation, its eight refusal
  cases, a mid-activation failure that rolls everything back, the single-active-company
  constraint, versioning, pause and resume; and `test_p0_migration.py` gained a check
  that the replaced trigger really does cover the two new columns while still allowing
  the lifecycle transition.
- P0.5 added 70 tests across three modules:
  `tests/test_p0_5_budget.py` (49) covers every ceiling refusing a request that fits
  the others, lifecycle and contract guards, caller-supplied limits being rejected,
  reservation/settlement/release idempotency and conflicts, the refusal path leaving
  evidence without leaving a charge, derived summaries, paginated ledgers,
  adjustments and their safeguards, and the pre-execution seam proving the callable
  is never reached when money is refused; `tests/test_p0_5_concurrency.py` (5) uses
  independent sessions and threads to prove the company ceiling, the task ceiling and
  a duplicate idempotency key all hold under a race, plus account creation under
  concurrency; `tests/test_p0_5_periods.py` (15) covers period rollover, ceilings
  carried forward, earlier periods left alone, reservations staying with the period
  that approved them, and the metering abstraction. `test_p0_migration.py` gained the
  append-only ledger check against real PostgreSQL.

**Frontend — typecheck, build, and five headless suites.**
```powershell
cd kayan-3d
npx tsc --noEmit
npm run build
npm run check:transport   # transport unit checks (fake socket, injected timers)
npm run check:mock        # mock-mode regression: the scripted order still runs
npm run check:e2e          # live bridge vs a running backend
npm run check:command      # backend mode: request_order → events → UI state
npm run check:experiment   # backend mode: run_comparison → results → per-trial audit
```
The three E2E suites drive the real transport, the real Zustand store and the
real reducer in Node against a live FastAPI/PostgreSQL. They need the backend
running (and `ENABLE_EXPERIMENTS=true` for the experiment suite).

**Browser verification: NOT PERFORMED.** This machine has no browser (no Chrome,
Edge, Firefox, puppeteer or playwright), so nothing was visually confirmed and no
browser console was read. All non-browser end-to-end checks were done instead, as
listed above. A visual pass on a machine with a browser is still outstanding.

---

## 6. Environment quirks (this machine)

These cost real time and will bite anyone who touches the setup:

- **Application Control blocks compiled extensions.** `sqlalchemy>=2.1` and the
  `psycopg` binary wheel cannot load their `.pyd`/DLLs.
  - SQLAlchemy is pinned `>=2.0,<2.1` (2.0 has a pure-Python fallback).
  - psycopg falls back to its pure-Python implementation and needs libpq on
    `PATH`; `app/core/config.py` adds the `pgserver`-bundled binaries automatically
    (best-effort shim). No manual `PATH` editing is needed.
- **Local PostgreSQL** is a real server from the `pgserver` wheel, driven with
  `pg_ctl`, cluster initialised `--encoding=UTF8` (the host default is a Windows
  codepage that cannot store the JSONB payloads).
- **`devdb start` from a script** works interactively; if launched detached, start
  `pg_ctl` through the same mechanism the session uses or the process tree will
  be torn down with the shell.
- **`package.json` must stay BOM-free.** A UTF-8 BOM in it breaks Vite's JSON
  loader with a confusing error.

---

## 7. Known limitations (intentional, not bugs)

- **Replay is history, not a rerun.** The backend serves recorded event history;
  it does not re-execute a workflow. The frontend "replay" control re-emits local
  mock history only.
- **Experiments are opt-in** (`ENABLE_EXPERIMENTS=true`, never in production).
- **Two commands only.** No `send_message`, `approve`, `reject`, agent creation
  or generic command framework.
- **No auth, no LLM/agent models, no cloud, no queueing/Redis/Kafka.** The
  collaboration runtime is deterministic and scripted — the experiment is a
  reproducible logic demonstration, not a model-performance benchmark.
- **Runs at full speed by default**; `RUNTIME_PACE_MS` makes a run watchable.
- **20k+ events in the `main` stream** after a few 10×10 experiments; per-run
  history endpoints are the intended way to read a single trial.

---

## 8. Suggested next steps

P0 is staged; each stage is meant to be reviewable on its own.

1. **P0.6 - onboarding wizard and dynamic roster.** Replace the canonical five with
   the configured roster when a company is active, demo office otherwise. Activation,
   contracts and a budget summary now exist, so the wizard has a real end state.
2. **P0.7 - runtime mapping.** Employee to active contract to execution, through the
   pre-execution seam in `app/services/execution.py`, which already refuses work that
   TrustGate denies or that money cannot cover.
3. **A real meter**, if one is ever wanted: implement the CostMeter protocol and
   register it; source already distinguishes provider charges from mock ones.
4. **A real model provider**, if one is ever wanted: implement the
   RecommendationProvider protocol, register it, and the selection policy,
   labelling and fallback already behave correctly.
5. **Authentication.** The budget adjustment endpoint is unauthenticated by design at
   this stage; owner identity and production exposure are a separate phase.

Carried over from before P0:

- **Browser pass** — this machine has no browser; confirm the office renders and the
  console is clean on a machine that has one.
- **Replay from backend history** — let the audit view replay a *backend* trial from
  `GET /api/experiments/runs/{id}/events`.
- **Harden the run guard** — the in-process per-order lock is single-process.
- **Auth on the command channel** — anyone who can reach `/ws/events` can request work.

---

---

## 9. Git

No commit was made. The enclosing repository is C:\Users\khale (the whole user
profile) and KAYAN-final/ is untracked inside it, so staging or committing from
here risks capturing unrelated files. Decide on the intended repository (or add a
.gitignore for the profile-level repo) before committing.
