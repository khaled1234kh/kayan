# KAYAN cloud/parallel AI layer

**Current checkpoint, 20 November 2026.** The experimental cloud operations are paused. Status is side-effect-free, experimental analysis does not issue ROEs, and ATT&CK retrieval uses a verified local Enterprise 20.1 archive. [Current source and evidence](CLOUD_PIVOT_SECURITY_AND_EVAL.md). The following sections record the initial experiment.

**Status (20 November 2026): implemented and verified end to end. This is an additive experiment, not a replacement for the governed local-runtime assessment.**

This document describes the new `ai/` package: a SovereignEG cloud LLM provider, MITRE ATT&CK retrieval-augmented generation, four parallel LangGraph agents and TrustGate-enforced actions. The legacy sequential runtime in `pentagi/` and the console UI are unchanged.

## 1. Goals and non-goals

| Goal | How it is met |
|---|---|
| Use `SovereignEG/Qwen3.8-27B-FP8` | Configurable OpenAI-compatible provider; local `qwen2.5:7b` retained as fallback/baseline |
| Parallel specialist agents | LangGraph graph with four concurrent agent nodes and a single aggregation node |
| MITRE-grounded evidence | Official ATT&CK Enterprise STIX downloaded, embedded and retrieved; cited technique IDs validated deterministically |
| Stay inside the Student Plan | 2 concurrent requests (semaphore) **and** 20 requests/minute (sliding-window limiter) |
| Keep TrustGate authoritative | Every agent inference and the report write require an independent `/authorize` ALLOW; denials fail closed |
| Measure instead of assume | Per-provider request/token/reasoning usage accounting; baseline models kept for comparison |

Non-goals: no fine-tuning in this phase; no new target tool access; no permission/spending decisions delegated to the model; no claim that 27B is better than the baselines without a controlled benchmark.

## 2. Data flow

```
Founder request + evidence (untrusted text)
              |
              v
   [prepare]  ->  security  --+
              ->  research  --+
              ->  risk      --+-->  [aggregate]  -> ConsolidatedAssessment
              ->  operations --+          |
                    |                     |
        +-----------+---------------------+-----------+
        |                                             |
   MITRE RAG retrieval                        TrustGate /authorize
   (STIX, embeddings, ID validation)          (fail closed; signed ROE)
        |                                             |
        +---------> SovereignEG / Ollama <------------+
                    (semaphore + rate limiter)
```

Concurrency is intentional at the **agent** level. Actual inference requests are still capped at 2 concurrent and 20/minute by the provider, so four concurrent agents cannot exceed the account allowance.

## 3. Components

### 3.1 Configuration and secrets

- `config/ai.json` holds non-secret settings: provider names, models, token budgets, concurrency/rate limits, MITRE URLs/cache paths, TrustGate URL and evaluation baselines.
- The API key is read only from the `SOVEREIGNEG_API_KEY` environment variable, loaded from the repository-local `.env` by `ai/config.py`. `.env` and `.env.*` are git-ignored. Existing process environment variables take precedence.
- `ai/api.py` exposes `api_key_configured: bool` — never the key itself. No provider code logs or returns the key.
- **The key was pasted into chat during setup and should be rotated before any shared/public use.** Rotation only requires updating the local `.env`; running providers re-read the variable on each request.

### 3.2 Provider abstraction (`ai/providers/`)

- `base.py` — `ChatMessage`, `LLMResponse`, `EmbeddingResult`, `UsageStats`, `LLMProvider` and the sliding-window `RateLimiter`.
- `sovereign.py` — OpenAI-compatible `/chat/completions` and `/embeddings`. Handles `reasoning_content` separately from answer content, records `reasoning_tokens`, retries transient HTTP 429/5xx with `retry-after` support, and drops an unsupported `response_format` on request-shape errors.
- `ollama.py` — local `/api/chat` and `/api/embed` baseline/fallback.
- `registry.py` — lazy provider instances, primary call with fallback **only on infrastructure errors**, and a usage snapshot endpoint.

Reasoning models need headroom: with a small `max_tokens` the visible answer can be empty because all tokens are consumed by reasoning. `max_tokens` is therefore 4000 (observed e2e run: 8,412 completion tokens of which 3,719 were reasoning).

### 3.3 MITRE RAG (`ai/mitre/`)

- `stix.py` — downloads the official Enterprise ATT&CK STIX bundle, keeps non-revoked `attack-pattern` objects, joins mitigation names and produces `MitreTechnique` records with source URLs.
- `rag.py` — embeds technique text in batches, caches a validated `.npz` index under the ignored `data/mitre/`, and retrieves top-k evidence by cosine similarity. If cloud embeddings are unavailable it falls back to a local TF-IDF index rather than silently returning nothing.
- Deterministic validation (`validate_technique_ids`, used by `parse_agent_result`) removes any technique ID that is not in the downloaded catalogue and records it as an assumption/limitation.

Current corpus from the configured URL: 706 Enterprise techniques. Retrieval sanity check: a PowerShell/encoded-command query returns `T1059.001 PowerShell` first.

### 3.4 Parallel agents (`ai/orchestrator/`)

- `state.py` — typed shared state; `agent_results`, `trustgate_decisions` and `errors` use `operator.add` reducers so concurrent nodes cannot overwrite each other.
- `schemas.py` — strict Pydantic output contracts with defensive JSON extraction (fenced or bare JSON); malformed model output becomes a bounded plain-text summary instead of crashing a node.
- `agents.py` — four roles (security, research, risk, operations). Each first calls TrustGate, then retrieves evidence, then calls the model. The prompt separates evidenced claims from assumptions and marks retrieved MITRE records as untrusted background reference, never instructions.
- `graph.py` — `prepare -> [4 parallel agents] -> aggregate`. Aggregation deduplicates findings, records unverified IDs and denials as limitations, and requires a separate `write_report` authorization.
- `run_assessment()` loads a narrow analysis-only ROE for the engagement before running the graph.

### 3.5 TrustGate enforcement (`ai/trustgate/`)

`AITrustGate` reuses the existing `integration.trustgate_client.TrustGateClient`, so the policy payload and fail-closed semantics are identical to the legacy runtime.

- `ensure_roe()` signs and loads an ROE scoped to loopback with only `planning`, `reporting` and `workflow` techniques, and no tool/permission/escalation grants.
- Agent inference uses the Gate's canonical Cedar principal `planner_agent` with technique `planning` and action `llm_inference`; aggregation uses `reporting_agent` / `reporting` / `write_report`.
- `tool_args` contain only KAYAN-controlled metadata. Untrusted evidence is labelled inside the prompt, not passed as tainted authorization arguments (tainted arguments are correctly denied by the Gate).
- A denied or unreachable Gate blocks inference — the agent records an error and produces no findings. No code path executes an action on a DENY or transport error.

## 4. HTTP API

Installed by `install_ai_api()` in `console/backend/main.py`, on port 8001 alongside the existing APIs:

| Method | Path | Purpose |
|---|---|---|
| GET | `/ai/status` | Provider/model, key-configured flag, limits, agent names, MITRE index state, usage |
| GET | `/ai/usage` | Per-provider request/token/reasoning counters |
| POST | `/ai/mitre/reindex` | Force STIX re-download and re-embedding |
| POST | `/ai/assess` | Start an assessment job (202) with `{founder_request, evidence, engagement_id?}` |
| GET | `/ai/assess/{job_id}` | Poll job status/result |

## 5. Setup

```powershell
# one-time, from the repository root
python -m pip install -r requirements.txt   # adds langgraph, numpy, scikit-learn
# create local .env (git-ignored) containing:
#   SOVEREIGNEG_API_KEY=<your key>
```

The Gate, backend, lab and office are started as in the main README. On the first `/ai/*` call the runtime downloads the STIX bundle (~seconds) and builds the embedding cache; subsequent starts load the cache.

Tests are fully offline (mocked provider HTTP and a fake TrustGate):

```powershell
python -B -m pytest tests -q -p no:cacheprovider
```

## 6. Verification evidence (20 November 2026)

- Imports/compile clean; full suite **173 passed, 4 skipped** (8 new tests in `tests/test_ai_layer.py`).
- MITRE corpus: 706 techniques; PowerShell query retrieves `T1059.001` first.
- TrustGate: untainted loopback ROE requests return `ALLOW — Cedar permit matched authenticated ROE capability, target and time window`; tainted and unscoped requests are denied.
- Full HTTP `/ai/assess` e2e: 4 agents completed, 5 authorizations (4 inference + 1 report write) allowed, 15 findings with validated technique IDs (`T1059.001`, `T1114.002`, `T1546.013`, …), 4 chat requests / 8,412 completion tokens / 3,719 reasoning tokens / 132 embedding tokens.
- Secret scan: the API key is absent from all candidate source files; `.env` is confirmed git-ignored.

## 7. Benchmark plan — no claimed winner

Keep the existing models as explicit baselines (see `evaluation.baselines` in `config/ai.json`): `qwen2.5:7b`, `qwen3:8b`, `granite-4.2-8b`, plus `SovereignEG/Qwen3.8-27B-FP8`.

Prior external figures measure **different things** and must not be collapsed into one ranking: Qwen2.5 7B `22.5%` exact contract passes, Qwen3 8B `35%` exact contract passes, Granite 4.2 8B `0.762` evidence-mapping F1. A fair comparison needs the same dataset and scorer for all candidates, tracking accuracy, latency and token cost together. Fine-tuning/QLoRA is deferred until such experiments show a need.

## 8. Honest limitations

- This is a defensive review/analysis path; it performs no live target testing and adds no tool authority.
- No grounding improvement is claimed for the legacy lab runtime. Retrieval quality here was checked with one sanity query, not a grounding benchmark.
- The reasoning model is expensive in tokens; the 20/min and 2-concurrency limits bound throughput, and a full four-agent assessment takes noticeably longer than a single call.
- The sliding-window limiter is per-process. Multiple backend replicas would need a shared limiter to respect the account-wide allowance.
- Cloud inference sends the request text to SovereignEG. Treat it as an external processor; do not submit regulated data without the appropriate review.
- Schema validation and ID checking reduce but do not eliminate unsupported claims. Agent findings still require human review, and destructive/high-impact actions remain subject to separate human approval outside this layer.

## 9. File map

```
ai/config.py                 config + .env loading (secrets never serialised)
ai/providers/                chat/embed interface, SovereignEG, Ollama, registry, limiter
ai/mitre/                    STIX parsing, embeddings, TF-IDF fallback, retrieval, ID validation
ai/orchestrator/             state, schemas, 4 agents, LangGraph graph
ai/trustgate/client.py       signed ROE + fail-closed authorization
ai/api.py                    FastAPI routes
config/ai.json               non-secret configuration
tests/test_ai_layer.py       offline tests for providers, RAG, rate limit and graph
console/backend/main.py      install_ai_api() wiring
```
