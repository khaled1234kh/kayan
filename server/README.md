# KAYAN Backend

FastAPI + PostgreSQL foundation. This service is becoming the authoritative store
for KAYAN domain state: agents, tasks, messages, handoffs, events, policy
decisions and experiment runs.

**The frontend is unchanged.** `kayan-3d` still runs entirely on `MockEventSource`
and its local TrustGate. Nothing in the frontend points at this service yet, so
the working prototype is untouched. There is no second state machine and no
second policy engine here — this task is persistence plus read-only API.

---

## Quick start (Windows / macOS / Linux, no Docker)

```bash
# 1. environment
python -m venv .venv
.venv\Scripts\activate            # Windows: .\.venv\Scripts\Activate.ps1

pip install -r server/requirements.txt

# 2. start a real local PostgreSQL (downloads nothing; binaries ship in a wheel)
cd server
python -m app.scripts.devdb start          # prints DATABASE_URL
# -> DATABASE_URL=postgresql+psycopg://postgres:@127.0.0.1:54321/kayan

# 3. create the schema and seed
python -m app.scripts.init_db --demo

# 4. run
python -m uvicorn app.main:app --reload --port 8000
```

Docs: <http://127.0.0.1:8000/docs> · Health: <http://127.0.0.1:8000/api/health>

Stop the database with `python -m app.scripts.devdb stop` (data in `.pgdata/`
is preserved).

### Using an existing PostgreSQL instead

```bash
cp server/.env.example server/.env
# set DATABASE_URL=postgresql+psycopg://user:password@host:5432/kayan
cd server
python -m alembic upgrade head      # schema from migrations
python -m app.scripts.init_db       # seed the five agents
```

Credentials come only from the environment. `.env` is gitignored.

---

## Tests

```bash
cd server
python -m pytest                                  # SQLite (no service needed)
KAYAN_TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest   # real PostgreSQL
```

68 tests cover health, database connectivity, agent/task/message/handoff/event
persistence, message threading, deterministic event ordering, experiment-run
persistence and metric derivation, and API serialisation.

---

## Layout

```
server/
  app/
    main.py              FastAPI app factory, lifespan (create_all + seed), db probe
    api/                 read-only routes; every response is a Pydantic schema
    core/                settings from the environment
    db/                  declarative base, engine/session, seed
    models/              typed ORM models
    schemas/             explicit API contracts
    services/            domain queries + event persistence + metric derivation
    events/              event vocabulary, sequence allocation, publish bus
    agents/              canonical agent profiles
    security/            policy-decision shape only (no evaluator)
    scripts/             devdb.py (local PostgreSQL), init_db.py
  alembic/               migrations
  tests/
```

---

## Architecture notes

### One engine, one session factory

`app/db/session.py` owns the engine and session factory for the process.
Services never build their own and never issue raw SQL.

### Event ordering

Every event carries a monotonic `sequence` **per stream**, allocated inside the
same transaction as the insert (`app/events/ordering.py`), with
`(stream_id, sequence)` unique. Ordering therefore never depends on wall-clock
resolution — a scripted run emits many events inside the same millisecond, and a
late-arriving earlier timestamp cannot reorder the stream. Replay and audit order
by `sequence`.

### Persist, then publish

`EventService.record()` commits the event and only then calls
`EventBus.publish()`. If the commit fails, nothing is published, so a client can
never observe state the backend failed to record. `record_many()` publishes the
whole batch after the batch commits.

`EventBus` is the seam the WebSocket bridge subscribes to. It is transport-free
and gets no say in durability.

### The command channel

One write command exists:

```json
{"kind":"command","command":"request_order","requestId":"...","orderId":"1042"}
```

The two directions stay separate. The client sends protocol frames; the server
sends business events in the existing event contract. A command is never an event,
and command metadata never enters an event payload.

The server answers with a protocol acknowledgement and nothing else:

```json
{"kind":"command_ack","requestId":"...","command":"request_order","accepted":true}
```

`accepted` is not the business result — it says the command was understood. The
result is the persisted event stream, arriving on the same socket. Refusals come
back as `command_error` (`malformed_frame`, `unsupported_frame_kind`,
`unknown_command`, `invalid_command`) or as an unaccepted `command_ack`
(`unknown_order`, `order_already_running`, `duplicate_request`).

Frames are validated in `app/schemas/commands.py` before anything reaches the
runtime, so an arbitrary command name cannot get through.

### The KAYAN runtime

`app/runtime/` is the authoritative business process. It decides which agent
works next, forms intents, calls TrustGate, creates messages and handoffs, moves
task status, and emits events — all through the service layer, never by writing
to PostgreSQL directly.

```python
runtime = KayanRuntime()
run = runtime.request_order(session, order_id="1042", request_id="abc")
```

No browser, no React, no Zustand: a test drives a complete order through this
class alone, which is the proof that the backend owns the process.

- `runtime.py` — `KayanRuntime`, step execution, task transitions, run
  bookkeeping, and `RuntimeGuard` (idempotency + one active run per order)
- `workflow.py` — the ported order workflow as a list of *interactions*; it
  never states actor state
- `collaboration.py` — message/handoff/intent creation, projected onto events
- `commands.py` — protocol dispatch, background execution, shutdown drain

The port reproduces the verified frontend workflow event for event: same
participants, same sequence, same security scenario. The parity is asserted by
`tests/test_runtime.py`.

**Pacing.** The workflow has no reason to sleep, so it runs at full speed by
default; `RUNTIME_PACE_MS` scales the authored delays when you want to watch it.

**Idempotency.** `command_requests.request_id` is a primary key, so a
redelivered command is detected by the database, not by memory. A rejected
request stays on record and cannot be retried into success.

**Concurrency.** One active workflow per order. A second `request_order` for an
order that is already running is refused with `order_already_running`, and no
second run is started against the same task ids.

**Failures.** A step that raises is logged, the run is marked `failed` with the
error text, the task is left blocked, and no completion event is fabricated.

### TrustGate

`app/security/trustgate.py` is the single authoritative backend evaluator, ported
from the verified frontend mock: same capability contracts, same rule order, same
policy names and reasons. In backend mode it is the only thing that decides; the
frontend copy stays for mock mode only.

Rule order: explicit prohibition, then capability scope, then untrusted private
data, then approval token. `customer/8841` from Operations therefore denies under
*Customer Data Scope*, matching the frontend exactly.

### Experiments: baseline vs enforced

The second command initiates one coordinated comparison:

```json
{"kind":"command","command":"run_comparison","requestId":"...","orderId":"1042",
 "seed":"KAYAN-DEMO-1042","runsPerCondition":10}
```

The acknowledgement carries the `experimentId` to poll and explicitly does **not**
mean the experiment has finished:

```json
{"kind":"command_ack","requestId":"...","command":"run_comparison",
 "accepted":true,"experimentId":"exp_..."}
```

**One workflow, one variable.** Both conditions run the same
`KayanRuntime` and the same step list. The only difference is the treatment of the
simulated unauthorized intent:

| | enforced (and every `request_order`) | baseline |
| --- | --- | --- |
| gate | `authorize_intent()` | `simulated_allow()` |
| events | `policy_denied`, `blocked`, recovery | `policy_violation`, workflow continues |
| actual data access | none | **none** |

Baseline records that an unauthorized action *would have been* permitted. It does
not read any customer record, does not disable authorization anywhere else, and
is unreachable from an ordinary order run.

`app/runtime/experiments.py` owns the comparison: it creates the `experiments`
record, drives every trial, and derives the aggregate on read. A trial that raises
is recorded as failed, the comparison continues, and the result is reported as
`partially_failed` — never silently discarded or reported as success.

**Timing.** `events.timestamp` is always **real UTC** — the activity feed shows when
something actually happened, so configuration changes and workflow runs share one
honest clock. Reproducibility comes from `events.clock_offset_ms`, which carries the
authored step-delay position of each workflow event. `derive_run_metrics()` measures
durations and intervals on those offsets, so repeated trials of a condition report
identical logical durations regardless of machine speed. Real elapsed machine time is
recorded separately as `wall_clock_ms`. No step sleeps to manufacture a duration, and
these are deterministic measurements, not a model-performance benchmark.

**Gating.** Experiments are a research capability: `ENABLE_EXPERIMENTS=true` and
`APP_ENV != production`. Otherwise the command is refused with
`experiments_disabled`.

**Isolation and replay.** Every trial owns a distinct task, message, handoff and
event identity, and `events.run_id` names its execution. A trial's evidence is read
back per run, so it can never be mixed with another trial:

- `GET /api/experiments/{id}` — status, derived summary, every trial, progress
- `GET /api/experiments/runs/{runId}` — one run's metrics
- `GET /api/experiments/runs/{runId}/events` — one run's recorded events, in
  sequence order (the evidence used for replay; it is a read of history, never a
  rerun)
- `GET /api/experiments/{id}/export.json` and `/export.csv` — persisted records

### Runs

There is one run record for the whole system: `workflow_runs`. A commanded order
and an experimental trial are both executions; a trial simply also carries
`experiment_id`, `condition`, `seed` and `run_index`. `events.run_id` is a real
foreign key to it, which is what makes per-run history auditable.

- `GET /api/runs?order_id=1042&condition=enforced&experiment_id=exp_...`
- `GET /api/runs/{run_id}`

### Workflow runs

See "Runs" above: `workflow_runs` is the single run record, and
`GET /api/runs?order_id=...` / `GET /api/runs/{run_id}` read it.

### P0 company configuration (schema only)

Eight tables exist so a company can be configured before anything runs. They are
deliberately inert: there are no HTTP routes, no wizard, and no runtime mapping, so
the running system behaves exactly as before.

| Table | Purpose |
| --- | --- |
| `companies` | The configured business: measurable target, one ISO-4217 currency, lifecycle (`draft`/`active`/`paused`). |
| `role_templates` | Versioned role catalogue, seeded at startup. `(key, config_version)` is the primary key. |
| `company_employees` | Configured seats. **Configuration only** — never an `agents` row, never a demo id. |
| `contracts` | The employee's authority: responsibilities, data/tool scope, restrictions, budgets. |
| `budget_accounts` | Ceiling for one accounting period. |
| `budget_reservations` | Funds held for unsettled work. |
| `budget_ledger_entries` | Append-only financial history. |

Rules the database enforces rather than trusting the service layer:

- **One active company.** Partial unique index `uq_one_active_company`. Drafts are
  unlimited, and a paused company does not consume the slot, so pause/resume is
  reversible.
- **Activated contracts are immutable.** A PostgreSQL trigger rejects any change to
  a material column (including budgets, reporting line and `content_hash`) once
  `activated_at` is set, while still allowing the transition to `superseded`. A
  second trigger refuses to delete an activated contract. Partial unique index
  `uq_contract_active_per_employee` keeps one active contract per employee.
- **Money is exact.** `Numeric(18, 6)` mapped to `Decimal` everywhere; one currency
  per company, no FX, and a mismatched currency is rejected rather than converted.
  Reservation `idempotency_key` is unique, so a redelivered reserve is a no-op.

Migration `90c90b1427fa` is verified against a database created empty: upgrade from
`base`, downgrade back, and `alembic check` reporting no model drift are all covered
by `tests/test_p0_migration.py`.

### Governance events

Configuration events are facts like any other: they travel the same `main` stream,
carry `companyId` and the entity ids in the payload, use real UTC timestamps with no
workflow offset, and leave `run_id` null.

A configuration change and its event commit in one transaction.
`EventService.stage()` adds an event to the caller's transaction and
`commit_and_publish()` commits both and publishes afterwards, so a subscriber can
never observe a company the backend failed to record. `record()` is expressed in
terms of the same two calls and is unchanged for existing callers.

### Company configuration (P0.2)

Draft companies and their employees can be configured over HTTP. Everything else
about the running system is unchanged: the canonical five agents, the runtime,
TrustGate, the experiment harness and the WebSocket protocol are untouched, and
configuration still travels on the same `main` event stream rather than a new one.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/setup/templates` | Company templates, their role and task offerings |
| `GET` | `/api/setup/roles?template_key=` | Current versioned role definitions |
| `POST` | `/api/companies` | Create a draft company (201) |
| `GET` | `/api/companies/{id}` | Read the configuration |
| `PATCH` | `/api/companies/{id}` | Partial draft edit |
| `GET` | `/api/companies/{id}/employees` | The company's seats |
| `PUT` | `/api/companies/{id}/workforce` | Replace the whole draft workforce |

**Creation** writes the `Company` and its initial monthly `BudgetAccount` in one
transaction and emits `company_created`. The company is always created in `draft`;
multiple drafts coexist, and the at-most-one-active rule stays a database
constraint. `PATCH` keeps the company and its budget account consistent, refuses a
currency change outright (no FX), and returns 200 without an event when the request
would change nothing.

**Editing** is draft-only: a paused or active company is 409, and `status` is not a
writable field. Activation is a later stage, not a draft edit.

**Workforce replacement** is a replacement, not a merge. Seats omitted from the
request are removed; supplied ids must already belong to the company; new seats get
backend-generated `emp_` ids. Every employee is created in `draft` and none is ever
inserted into the canonical `agents` table. The whole request is validated before
any write, and the rows plus `workforce_configured` commit together — a rejected
request leaves the previous workforce byte-for-byte intact.

**Reporting lines** are validated by `app/company/reporting.py` as a graph over the
proposed workforce, so seats may reference each other regardless of request order.
Self-reference, missing targets, cross-company targets and cycles of any length are
refused. An employee may have no manager, and a diamond is not a cycle.

**Money** is `Decimal` end to end. JSON numbers are converted through their decimal
string form, `NaN` and infinity are refused, and more precision than `Numeric(18, 6)`
holds is rejected rather than rounded.

Errors follow one shape: `404` for a missing company, `409` for an illegal
lifecycle operation, `422` for invalid configuration or an invalid relationship,
with the offending field named in the body.

### Workforce recommendations (P0.3)

The backend can propose a workforce for a draft company. It cannot apply one.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/setup/recommendations` | Generate a proposal (201) |
| `GET` | `/api/setup/recommendations/{id}` | Retrieve a stored proposal |

**A recommendation changes nothing.** Generating one writes a `recommendations` row
and nothing else — no `CompanyEmployee`, no `Contract`, no budget movement, not even
a company `revision` bump. Adopting a proposal is a P0.2 workforce submission.

Only the company id identifies the request. Budget, currency, template and target are
read from the saved company, and restating them is refused: a proposal built on a
stale copy of the ceiling would be a proposal against money that does not exist.

**Providers.** `RecommendationProvider` is a protocol with a registry, a selection
policy and an explicit fallback rule. `TemplateProvider` is deterministic and needs
no credentials. No model provider is configured — the backend declares no inference
dependency and holds no inference credentials — so `RECOMMENDATION_PROVIDER=model`
resolves to the template fallback and says so in the response's warnings. A fallback
is never labelled `model`, and no call is ever fabricated.

**Provider output is untrusted.** Every proposal is re-derived against the catalogue
before storage: role keys and versions must exist, the role must be offered by the
company's template, the seat kind must match the role, scopes must parse as
structured `{resource, operations}` / `{tool, actions}` grants, responsibilities must
be stated, and the reporting graph goes through the same validator P0.2 uses. A
provider cannot grant a permission by asserting it.

**Money.** Allocations are weighted by role and *truncated* — never rounded — before
the remainder is distributed one unit at a time, so `sum(monthly) <= ceiling` holds
exactly in `Decimal`. A seat's per-task ceiling is at most half its monthly
allocation, and the unallocated remainder is reported rather than assumed away.

**Determinism.** The same company, preferences and catalogue version produce a
byte-identical proposal. A request for 20 seats returns the roles the template can
justify and explains that further seats would repeat existing work.

Snapshots are self-contained: each seat records the `config_version` its defaults came
from, its scopes and its rationale, so a later catalogue revision cannot change what
was recommended. Money is stored as decimal strings. The record commits with
`recommendation_generated` in one transaction and is published afterwards — a
provider that fails or returns something invalid leaves no record and no event.

### Contracts and company lifecycle (P0.4)

A configured company can be given contracts, reviewed, activated, paused and resumed.
Activated terms are immutable; a change requires a successor version, a review, and
an explicit activation.

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

**Budgets are requested.** `CompanyEmployee` retains no draft allocation, so
generation takes one per employee and refuses the request unless the set exactly
covers the workforce — no unknown ids, no duplicates, no cross-company references,
per-task within per-month, total within the company ceiling. Nothing is invented.

**Terms are least-privilege by default.** Scopes come from the role's catalogue
defaults, a restriction that forbids finalising without approval becomes an
executable approval rule, and communication defaults to "may talk to my manager".
The supported vocabulary of resources, tools, operations and restrictions is read out
of the seeded catalogue (`app/company/permissions.py`), so an unfamiliar tool is
refused rather than widened.

**The integrity hash covers everything.** Canonical JSON, sorted keys, `Decimal` as a
plain decimal string, SHA-256 over every material term — including budgets and the
reporting line. `5000` and `5000.00` hash identically; a lifecycle change does not
alter the digest. Activation recomputes it and refuses a contract whose terms no
longer match what was recorded.

**Validation is over the whole contract**, not the fields a PATCH happened to send,
and a PATCH that changes nothing returns 200 without an event.

**Activation is one transaction or nothing.** It re-verifies role versions, scopes,
the reporting graph, communication targets, approval rules, budgets and hashes before
writing anything, then activates the contracts, repoints the employees and flips the
company together with their events. A failure anywhere rolls all of it back,
including the staged event rows, and nothing is published.

**Resume is where supersession happens.** Creating a successor supersedes nothing —
the predecessor stays active. Only a resume, with the company paused, activates a
reviewed successor and supersedes its predecessor in the same transaction.

### Budget enforcement (P0.5)

The company ceiling is a hard maximum, enforced by the backend. No billable work
begins without a successful reservation of its **maximum** cost.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/companies/{id}/budget` | Ceiling, spend, reservations, available, per-employee allocations |
| `GET` | `/api/companies/{id}/budget/ledger` | Paginated ledger, filterable by category, employee and task |
| `POST` | `/api/companies/{id}/budget/adjustments` | Explicit, audited ceiling change |

Reserve, settle and release are **not** endpoints. They are trusted backend
operations; exposing them would let any client that can reach the API move a
company's money.

**Three ceilings, tightest wins.** For the company period, for an employee's month
and for one employee on one task, `available = limit - spend - outstanding`. A
request must fit all three. The employee's limits come from their active contract,
read fresh each time and never copied into a field that could drift; the contract's
integrity hash is re-verified before it may authorise anything.

**A denial is a result, not an exception.** It is recorded in the ledger and
committed as `budget_reservation_denied`, creates no active reservation, and returns
an explicit refusal. Rolling back the evidence with an exception would leave a
refusal with no record.

**Counting rules.** Actual spend comes from ledger categories that count as spend;
outstanding commitments come from the reservation table. Counting a reservation as
spend as well would deduct the same money twice.

**Concurrency is a database guarantee.** Reservations lock the period's
`BudgetAccount` `FOR UPDATE`, so two requests that each fit alone cannot both be
approved. A racing duplicate idempotency key replays the winner rather than erroring.

**Settlement reconciles rather than assuming.** The actual charge is recorded and
the remainder released. An actual cost above the reservation is an explicit
reconciliation failure that leaves the reservation committed, so the discrepancy
cannot be spent past.

**The ledger is append-only**, protected by a PostgreSQL trigger against UPDATE and
DELETE. Corrections are new `refund_or_adjustment` entries. Money crosses the API as
decimal strings.

**Adjustment form is absolute** - "the ceiling is now X" - because a delta needs a
sign convention callers get wrong. A reduction below committed money or below active
contract allocations is refused.

**Metering is mocked and labelled.** No inference provider is configured, so
`MockCostMeter` is the only meter and everything it produces is marked `mock`. A
communication and the model call behind it are recorded but charged once.

**`budget_limit_reached` event (P0.5.1).** When a ceiling's available amount reaches
exactly zero, a `budget_limit_reached` event is published with `level`
(`company` | `employee` | `task`), the `limitAmount`, `currency`, and the affected
`employeeId`/`taskId` where applicable. A mere denial with funds still available does
**not** emit it.

**Exhaustion is deduplicated by state (P0.5.1).** A marker ledger entry
(`BudgetLedgerCategory.BUDGET_LIMIT_REACHED`, amount zero) records the transition.
A later release, refund, or ceiling increase restores capacity; the next zero
transition is a new event. This uses the append-only ledger as the state machine --
no new table.

**Injectable UTC accounting clock (P0.5.1).** `BudgetService(session, clock=...)` and
`current_account(now=...)` accept an explicit instant for deterministic month-boundary
tests. Production defaults to the real UTC clock; naive datetimes are rejected.

**Known limitation: the adjustment endpoint is unauthenticated.** KAYAN has no auth
in this phase, so it inherits the local/development posture of the other write
endpoints. Authenticated owner identity and production exposure are a separate
phase.

### WebSocket event bridge

```
GET /ws/events?stream=main[&afterSequence=13]
```

Read-only in both directions. On connect a client receives the stream's persisted
events in ascending `sequence` order, then continues to receive events as they
are published. Inbound frames are drained and discarded; there is no command path
yet.

The handover from "replay history" to "tail live" uses the safe ordering, not the
naive query-then-subscribe (`app/events/connection.py`):

1. subscribe to the bus, buffering everything it publishes
2. read the historical cutoff (highest committed sequence)
3. send persisted events up to the cutoff
4. flush buffered events after the cutoff
5. keep draining, live

Two invariants follow: a committed event is never missed (it is either in the
replay or in the buffer), and nothing is observed twice or out of order, because
sending only advances to `last_sent + 1`. If a sequence is genuinely missing the
connection waits rather than reordering, with a bounded timeout as a backstop.

Frames are the existing client event contract, with epoch-millisecond
`timestamp` (the client does arithmetic on it) plus two additive ordering fields,
`sequence` and `streamId`. Protocol metadata never enters `payload`. REST keeps
ISO-8601 timestamps; only the WebSocket frame uses the client shape
(`EventService.to_client_event`).

Each client owns its connection and its own buffer, so one disconnecting never
interrupts another.

### Development event publisher

`POST /api/dev/events` and `GET /api/dev/streams` exist to prove the bridge works
locally. They are mounted only when `ENABLE_DEV_ENDPOINTS=true` **and**
`APP_ENV != production`, and they go through the normal `EventService`, so a
development event is persisted before it is published like any other.

---

## Connecting a client

```text
ws://127.0.0.1:8000/ws/events?stream=main
ws://127.0.0.1:8000/ws/events?stream=main&afterSequence=19   # resume
```

### Policy decisions are events

A TrustGate decision is stored as structured event payload
(`policyDecision` + `intent`), not as a separate table: the decision and the
event announcing it are the same fact, and two tables would mean two answers to
"what was decided". There is **no** second TrustGate here — the frontend mock
evaluator remains the only enforcement point until a later task moves it.

### Run metrics are derived, never authored

`app/services/run_metrics.py` counts every metric from the persisted event
stream, using the same rules as the frontend harness
(`kayan-3d/src/experiments/experimentMetrics.ts`), so a run measured by either
side agrees. `ExperimentRun` is a materialised read model; the stream is the
authority. Ordering differs in one deliberate way: the backend orders by
`sequence`, the frontend by `timestamp`.

### API contract

API fields are camelCase (`actorId`, `taskId`, `eventType`) so a future
WebSocket frame and a REST response describe the same shape the frontend already
consumes. Database columns stay snake_case. ORM models are never returned
directly.

### Agents

The five seats are seeded from `app/agents/profiles.py`, which mirrors
`kayan-3d/src/agents/agentProfiles.ts`. `tests/test_agent_profile_parity.py`
parses the frontend file and asserts the ids, names, roles, kinds, capabilities
and restrictions still match, so the two cannot drift into a second definition.

External senders such as `ext:supplier` are **not** agents: a message carries
either `from_agent_id` or `external_sender`, never both (enforced by a check
constraint), so no fake employee record can appear.

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./kayan_dev.db` | SQLAlchemy URL. Use `postgresql+psycopg://…` in practice. |
| `APP_ENV` | `development` | Reported at startup. `production` unmounts `/api/dev/*`. |
| `LOG_LEVEL` | `INFO` | Root log level. |
| `ENABLE_DEV_ENDPOINTS` | `false` | Mounts `/api/dev/*` (ignored in production). |
| `RUNTIME_PACE_MS` | `0` | Scales each workflow step's authored delay. 0 = full speed. |
| `ENABLE_EXPERIMENTS` | `false` | Enables the `run_comparison` command (ignored in production). |
| `API_DEFAULT_LIMIT` | `100` | Default page size for list endpoints. |
| `API_MAX_LIMIT` | `500` | Maximum page size. |

---

## Deliberately not built yet

- **The onboarding UI.** P0.2's APIs exist so the wizard can be written against
  something real; no frontend screen consumes them yet.
- **Company activation, pause and resume.** The single-active-company index and the
  lifecycle events exist; the endpoints that would use them do not.
- **Contract-aware workforce changes.** A non-draft company's roster is not
  editable through the workforce endpoint, because contracts become authoritative at
  activation. Changing an employee's authority is a successor version plus a resume,
  never an in-place edit.
- **Enforcement against real work.** The budget service is complete and authoritative,
  but CompanyEmployee is still not mapped to an executing agent, so nothing calls
  it yet. P0.7 runs company work through the pre-execution seam.
- **A model recommendation provider.** The seam, selection policy, labelling and
  fallback all work; no inference client is implemented or configured.
- **Recommendation acceptance.** A proposal is stored as `proposed`. Adopting it is a
  workforce submission, not inferred from generation.
- **Company deletion.** Once a company has activated contracts, deleting it fails at
  the database, because the immutability trigger refuses to destroy contract history.
  That is intended; no delete endpoint is exposed.
- **FX.** One currency per company; a mismatched currency is refused, never
  converted.
- **Real AI calls.** No LLM providers, no autonomous reasoning. The runtime is
  deterministic and scripted, and the experiment is a reproducible logic
  demonstration, not a model-performance benchmark.
- **No authentication, no cloud infrastructure, no containerised app stack.**
- **No Redis/Kafka/Celery, no horizontal scaling.** One explicit stream (`main`),
  and the per-order run guard is in-process.