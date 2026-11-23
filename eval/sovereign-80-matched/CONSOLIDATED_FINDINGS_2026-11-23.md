# KAYAN TrustGate — Consolidated Findings Report

**23 November 2026 (Africa/Cairo) · Khaled Mohamed (20231160)**
**Scope:** all completed KAYAN TrustGate research, engineering and cloud-evaluation findings to date, integrated into one supervisor-ready document.
**Evidence status:** every number below is either `MEASURED` (a real recorded run with saved artifacts) or explicitly labelled as a design, plan or unmeasured item. No mock result is reported as a model measurement.

> **Important framing.** Several benchmarks in this project measure *different things* on *different datasets*. They are reported below in separate sections and are **not** merged into a single ranking. In particular the recovered 80-case role benchmark, the 30-case operational Planner test, the 32-case ATT&CK mapping tests, the 18/19-case extraction diagnostics and `eval/ai_benchmark.py` are distinct instruments.

---

## 1. Executive summary

KAYAN TrustGate is a defensive evidence-review prototype in which five specialist roles (Planner, Recon, Web-App, Network, Reporting) coordinate under an **independent** Rust/Cedar authorization gate (TrustGate). Signed rules of engagement, admission-v2 evidence custody and audit are authoritative and stay independent of model output. The operational baseline remains local Qwen2.5 7B; no model has ever been given tool, scope or approval authority.

**Findings, in one paragraph.** The engineering checkpoint `06e5f12` passed Ubuntu Go CI (180 tools tests, 10 TrustGate tests, one pre-existing live-Cedar skip), and the acceptance matrix now has 21 automated-verified, 3 operationally-verified and 1 independently-validated criterion, with 9 still in progress. On the original frozen 80-case role holdout, the five local checkpoints scored 5–28 exact passes out of 80 (6.25%–35.0%); Qwen3 8B led exact passes (28/80), Granite 4.2 8B led evidence F1 (0.762), and no local winner was confirmatory. Cloud evaluation initially failed twice for reasons unrelated to model quality — the first real run spent all 512 output tokens on reasoning (12/12 truncated, 0 usable answers), and the corrected reasoning probe then failed exact citation grounding. A **matched** re-run of the genuine frozen 80-case benchmark on 23 November, with `reasoning_effort="none"` to honour the original `think: false` control, produced the first defensible cloud accuracy figure: **SovereignEG/Qwen3.8-27B-FP8 scored 72/80 = 90.00% exact**, evidence F1 0.945, zero unsupported affirmative claims, zero malformed outputs, at 1.32167372 EGP catalogue-equivalent. This beat every local arm in every role with paired 95% intervals that exclude zero. It supports continuing the cloud pivot **as a scoped research candidate only** — replication on a fresh independently labelled cohort is required before any production decision, and all TrustGate/Cedar/ROE controls remain unchanged.

### Headline answer to the supervisor's questions

| Question | Measured answer |
| --- | --- |
| Did the 27B cloud model beat Qwen2.5 7B exact accuracy? | **Yes** — 72/80 vs 18/80, +67.5 pp, paired 95% CI [+56.25, +77.50]. |
| Did it beat Qwen3 8B exact accuracy? | **Yes** — 72/80 vs 28/80, +55.0 pp, CI [+45.00, +65.00]. |
| Did evidence quality improve / unsupported claims fall? | **Yes** — evidence F1 0.945 vs 0.693 (Qwen3) and 0.454 (Qwen2.5 7B); unsupported affirmative decisions **0** vs 41 and 78. |
| Any role regressions? | **None** — Planner 11/16, Recon 16/16, Web-App 16/16, Network 15/16, Reporting 14/16; all ≥ every local arm. Planner remains hardest. |
| Cost / runtime tradeoff? | 1.32167372 EGP catalogue-equivalent, ~5 min wall time incl. one rate-limit pause; endpoint p50 1.16 s / p95 1.69 s (not host-comparable to local). |
| Is the comparison valid? | Yes, to the *recovered original* frozen 80-case benchmark only (identical manifest, order, prompt, schemas, scorer, temperature 0, 384-token budget, documented parameter remaps). It is a **retrospective matched synthetic benchmark**, not a fresh blinded human-adjudicated holdout. |
| Continue the cloud pivot? | **Yes, as a scoped research candidate** with replication on a fresh independently labelled cohort. Not a production authorization. |

---

## 2. What was built — architecture and security invariants

- Five roles have distinct capabilities with auditable assignment, outcome and recovery states (`pentagi/live_engagement.py`, `console/backend/session_store.py`).
- The proposed cloud-ready review design keeps egress under a deterministic scheduler and model gateway, while TrustGate/Cedar alone owns the policy decision on any effect. Operator approval and signed scope are inputs to the gate, not to the model.
- Admission v2, provenance/custody (71 historical inventory digests and 5 source hashes), signed ROE and execution controls are unchanged by the evaluation work. All historical negative results are preserved.
- Secrets are kept outside the checkout; the adapter is mock-only by default (`SovereignEGProvider.__init__` raises `PermissionError` without `MockTransport`) and was **not** bypassed. The live evaluation used dedicated evaluation-only HTTP code with an external credential that was never logged.

**Action required:** the SovereignEG key previously pasted in chat must be rotated before any shared or public use.

---

## 3. Local model evidence — the original frozen 80-case role benchmark

**Instrument:** archived `KAYAN-TrustGate-Offline-Benchmarks` package, recovered byte-for-byte from `KAYAN_Offline_Benchmark_Evidence_2026-11-13.zip`. Manifest `roles_frozen.json` SHA-256 `09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0`; 120 cases total (80 held-out, 16 per role, 40 calibration in distinct families); 9 scorer integrity tests pass.

**Protocol:** Ollama 0.40.13, quantized Q4_K_M, temperature 0, seed 42, 4,096-token context, 384-token output budget, thinking disabled, one serving slot, RTX 5060 Laptop (8,151 MiB) with Vulkan. Exact pass = all expected labels and citations plus acceptable Planner dependency order; evidence F1 = item + label + source-reference triple. Deterministic held-out order via `Random(20261112)`.

### 3.1 Measured results — all six arms on the same 80 cases

| Model | Status | Exact passes | Exact accuracy | Affirmative F1 | Evidence F1 | Abstention F1 | Unsupported affirmatives | p50 / p95 (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **SovereignEG/Qwen3.8-27B-FP8 (cloud, 23 Nov)** | MEASURED | **72/80** | **90.00%** | **0.935** | **0.945** | **0.984** | **0** | 1.16 / 1.69 |
| Qwen3 8B (local) | MEASURED | 28/80 | 35.00% | 0.745 | 0.693 | 0.857 | 41 | 2.37 / 3.84 |
| Granite 4.2 8B (local) | MEASURED | 27/80 | 33.75% | 0.762 | 0.762 | 0.879 | 39 | 3.57 / 5.04 |
| Llama 3.1 8B (local) | MEASURED | 23/80 | 28.75% | 0.714 | 0.688 | 0.847 | 36 | 2.53 / 3.92 |
| Qwen2.5 7B (local; operational baseline) | MEASURED | 18/80 | 22.50% | 0.544 | 0.454 | 0.571 | 78 | 2.17 / 3.78 |
| Qwen2.5 1.5B (local; compact) | MEASURED | 5/80 | 6.25% | 0.634 | 0.454 | 0.316 | 84 | 1.12 / 1.56 |

The five local values re-score exactly to the historical saved artifacts; the independent offline validation reproduced 18/28/27/23/5 of 80 and evidence F1 .454/.693/.762/.688/.454. Cloud latency is recorded but **excluded from ranking** (different host/endpoint).

### 3.2 Exact passes by role (out of 16 each)

| Role | Cloud 27B | Qwen3 8B | Granite 8B | Llama 8B | Qwen2.5 7B | Qwen2.5 1.5B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Planner | **11** | 3 | 7 | 0 | 3 | 1 |
| Recon | **16** | 7 | 4 | 5 | 5 | 1 |
| Web-App | **16** | 7 | 7 | 5 | 6 | 1 |
| Network | **15** | 8 | 4 | 7 | 1 | 0 |
| Reporting | **14** | 3 | 5 | 6 | 3 | 2 |

The rule-based Planner oracle solved 16/16 of the Planner fixtures versus 3/16 for Qwen2.5 7B — i.e. the authored rules themselves were sufficient; model planning was the weak link. The cloud arm's eight failures were five Planner, two Reporting and one Network case; none emitted an unsupported affirmative decision.

### 3.3 Paired uncertainty

Cloud-minus-local, 5,000 role-stratified family-cluster bootstrap replicates:

| Reference arm | Exact-pass difference (pp) | 95% interval (pp) | Evidence-F1 difference | 95% interval |
| --- | ---: | ---: | ---: | ---: |
| Qwen2.5 7B | +67.50 | [+56.25, +77.50] | +0.492 | [+0.387, +0.605] |
| Qwen3 8B | +55.00 | [+45.00, +65.00] | +0.253 | [+0.201, +0.305] |
| Granite 4.2 8B | +56.25 | [+46.25, +66.25] | +0.184 | [+0.133, +0.242] |
| Llama 3.1 8B | +61.25 | [+48.75, +73.75] | +0.258 | [+0.180, +0.340] |
| Qwen2.5 1.5B | +83.75 | [+76.25, +90.00] | +0.491 | [+0.449, +0.531] |

All intervals exclude zero. Historically, local arms did **not** separate cleanly: Qwen3 led Granite by +1.25 pp exact (CI −7.50 to +10.00) while Granite led evidence F1 by .069 [.032, .107]. These are exploratory intervals over small authored synthetic families, unadjusted for multiple comparisons, not population estimates.

### 3.4 Local-only follow-ups (same benchmark family, separate analyses)

- **Specialization replay:** calibration-selected role mix scored 26/80 vs 23/80 for shared Llama (+3.75 pp, CI [0, +7.50]) but evidence F1 fell .688→.624. Adding Granite gave 28/80 vs 27/80 shared Granite (+1.25 pp, CI [−2.50, +5.00]). Eight calibration cases per role made selection unstable.
- **Switching cost:** a fixed mixed route needed 30.79 s median vs 13.49 s shared Llama and 11.69 s shared Qwen on four groups; eight switches cost 70.73 s of reported load. A Granite/Llama mix took 40.38 s vs 18.25 s shared Granite. Second reason to retain one shared model.
- **Incomplete:** Qwen3.5, Granite 4.2 3B and RedSage unmeasured; a resumed Qwen3 8B transfer failed SHA-256 and was replaced by a registry-verified pull.

---

## 4. Operational Planner benchmark — 4 November 2026

**Instrument:** 30 authored Planner-only coordination cases, real local `qwen2.5:7b`, real TrustGate authorization, frozen dataset SHA-256 `46692264b5eb9ef301c67c3c38f5c52e9e35fa6b27695df746070a7bc6d646e9`, nine evaluator checks passed.

- **24/30 (80.0%) first attempt; 26/30 (86.7%) after the existing validation/correction path.** Four final failures: one token-repeat abort, one unsupported curl task mis-assigned to Reporting and accepted by the validator, and two rationales omitting recorded failure/verification gaps.
- Some passing plans invented unsupported CLI options/ports — recorded but unscored. Audit 1,247→1,280 entries, 32 Planner inference requests plus ROE load, all allowed. No specialist tools ran; no real findings.

This is a controlled contract pass rate, **not** general Planner or vulnerability-detection accuracy, and is not comparable with the 80-case role benchmark.

---

## 5. Scheduling, serving and policy evidence

- **Mock workflow:** all 128 timed runs and 256 coverage runs matched an independent topological-order/terminal-state oracle. Dependency scheduling reduced median paired time 30.5% on independent-evidence fixtures, 17.75% on an inventory prerequisite, 0.79% on a serial control — but these are synthetic waits, not end-to-end speed.
- **Real-inference scheduling:** with Qwen2.5 7B the median paired reduction was **0.13%**; Llama −0.09%, Granite +0.06%, Qwen3 +0.27%. 8/8 expected terminals, 20/20 identical response bodies for Qwen2.5. No demonstrated end-to-end gain.
- **Inference slots:** actual serving, 10 request pairs — one vs two slots gave 0.346 vs 0.340 requests/s and median pair 4.88 s vs 5.24 s (median within-pair reduction 26.10%, CI −51.75 to +32.84%). A scheduler-based slot test showed 12.89% reduction with one arm order but only 1.84% after reversal. **Keep one slot as default.**
- **Security:** broker suite 19/19 scenarios — 14 expected denials rejected, 4 benign deliveries accepted with audit links, 3 invalid graphs rejected, zero false refusals, no unauthorized mock effect committed. Authenticated identity and policy decisions were fixture inputs. An independent Rust/Cedar unit build was blocked on Windows by Application Control error 4551; the last verified operational Cedar results remain historical, and the canonical Go CI branch `06e5f12` passed 180 tools + 10 TrustGate tests with the live-Cedar skip.

---

## 6. ATT&CK evidence-mapping studies

**Distinct instruments; reported separately from the role benchmark.**

- **Deterministic retrieval pilot (32 cases):** exact-ID micro F1 .115 (baseline / checked-in mixed TF-IDF), .154 Enterprise TF-IDF, .346 Enterprise BM25, .409 with structural checks. Official Enterprise v20.1 snapshot matched MITRE's SHA-256; BM25 moved .346→.385 across versions (+.038, CI [0, .097]) with byte-identical paired model responses.
- **Actual Qwen2.5 7B mapping (32 held-out cases, 20 gold mappings, 13 with no supported mapping):** no retrieval .063 micro F1, Enterprise TF-IDF .444, BM25 .522, **BM25 + ID/evidence checks .686 micro F1 / .800 evidence precision**, cutting false positives 14→3 while retaining 12 true positives. Structural checks added +.164 F1 [.088, .246].
- **Blinded AI label review** agreed on mapping in 32/32 and exact sets in 30/32; re-scoring against alternative labels changed values but preserved ordering. Independent **human** adjudication remains outstanding.
- **November 20 ablation** on 32 already-inspected cases: 22/32 exact for field BM25 @ 5, 26/32 for hybrid E5-192 @ 5; matched interval includes zero. A one-shot confirmation is preregistered for 24 frozen cases with a jointly-sufficient/independently-sufficient evidence rubric; no new mapping scores were produced and no real returns or adjudication have occurred.
- **Track A offline checkpoint (20 Nov):** 72 archived Qwen2.5 7B replies reproduced **0/72 complete proof groups** and **0/40 expected technique occurrences with complete evidence**. A paired proof-assembly intervention raised eligible fully-supported items from 0/4 to 4/4 with supplied human-authored evidence groups — the gain belongs to evidence assembly/checking, not model grounding. 54 mock requests, 18/18 schema-valid, no provider latency/cost evidence, no external request.

---

## 7. Reporting, custody and evidence-admission engineering

Measured improvements on frozen synthetic archives (headline results):

- **Projection benchmark (9 archives):** baseline Reporting showed 1/4 supported occurrences; occurrence-aware Reporting 4/4 with exact source addresses; both admitted 0/6 withheld occurrences and rejected the invalid archive; verifier agreed with all 11 authored dispositions.
- **Action holdout (8 synthetic families):** appending verified action excerpts raised observed-action coverage 1/8→8/8 and preferred-excerpt recovery 9/16→16/16; the full 9-occurrence case still surfaced no actions (all 8 slots occupied). Authorized-only archive made no request.
- **Signed finding/occurrence attribution:** 7/7 frozen three-role cases, up from 2/7; combined run passed 293 tests including real Rust restart coverage. Specialist attribution 7/9→9/9 exact; historical owned-lab archive kept 10/10 transcript-only.
- **Recovery and integrity:** saved real Slate response re-passes verification; corrupted/reserved fallback reports return HTTP 409 without rewriting; export is bound to the SHA-256 of the exact saved JSON shown in the panel; late or wrong-agent contradictions and stale imports are rejected; current review and enrollment are rechecked at receipt insertion.
- **Frozen full-summary comparison:** reference swap improved aggregate observed-action coverage 9/50→16/50 at the cost of two preferred excerpts; full reviewed proof retained 215/215 exact role-to-source links vs 212/215 previously.

These are synthetic/custody verification results, not general accuracy claims.

---

## 8. Cloud pivot — full timeline, including failures

| Date / stage | What was authorized and run | Measured outcome |
| --- | --- | --- |
| 20 Nov · Track A | Mock POSTs (B/C/D) with configured 27B model, same evidence and archived replies; `track-a.invalid`, `MockTransport` only. | 54 mock requests serialized/scored, 18/18 schema-valid, 0/10 complete groups. **No provider schema, entitlement, quality, billing or latency evidence.** |
| 21 Nov · first real run | 12 diagnostic requests + 1 separate probe, `max_tokens=512`, provider **default reasoning**, 10.50624224 EGP reserved, allowance-only. | All 12 HTTP 200, exact model, but **12/12 `finish_reason=length`**, 512 reasoning tokens each, no visible answer; **0/3 complete findings in every arm**. A protocol failure, not an accuracy result. Probe alone: valid empty-facts schema, `stop`, 33/78 tokens. |
| 21 Nov · reasoning-budget v2 Stage A | One probe with `reasoning_effort="none"`, `max_tokens=1024`. | HTTP 200, visible schema-valid answer, `stop`, **0 reasoning tokens**, no clamp/param headers — but it returned a natural-language string where `E1.1` was required, so the **exact citation check failed**. Stage B not authorized. |
| 21 Nov · Reporting selection | One real cloud selection for Archived Reporting. | HTTP 200, exact model, 260 input / 62 output / 0 reasoning tokens, 0.906 s, 0.00192 EGP. This was extractive Reporting only, not overall accuracy. |
| **23 Nov · matched 80-case run (this takeover)** | Recovered genuine frozen harness; dedicated evaluation-only runner; 80 held-out cases, `reasoning_effort="none"`, max_tokens 384, strict JSON schema, temperature 0, sequential, 160-request / 10-EGP caps, explicit owner authorization. | **72/80 = 90.00% exact, evidence F1 0.945, 0 unsupported, 0 invalid, 0 errors** — see §3. |

**Why earlier cloud results were not accuracy measurements:** the first run exhausted the output budget on reasoning (a setting mismatch with the frozen `think: false`), and the Stage A probe tested answer availability and exact citation, not the role benchmark. `reasoning_effort="none"` was used to *match* the original control, never to improve the cloud arm.

**Parameter mapping in the matched run** (frozen → cloud): `format`→strict `response_format`; `num_predict 384`→`max_tokens 384`; `think:false`→`reasoning_effort:"none"`; temperature 0 unchanged; `seed`, `num_ctx`, `keep_alive` not sent (no documented provider equivalent). Provider context/chat templating/tokenization remain non-identical.

---

## 9. Cost, latency and execution integrity of the matched cloud run

- **Cost:** 1.32167372 EGP catalogue-equivalent for 80 scored requests plus one HTTP 429 request that was discarded and re-sent (81 total, cap 160, ceiling 10 EGP). At rates 8.41 EGP/M input and 67.29 EGP/M output; under the owner-confirmed allowance-only setting the expected balance charge is 0 EGP. The API returned token counts but no itemized charge, so this is a catalogue-rate inference, not an invoice.
- **Tokens:** 35,897 input / 15,155 output (≈449 in / 189 out per case).
- **Latency:** p50 1.164 s, p95 1.693 s per case; ~5.03 min wall time including the 429 stop at case 21 and a resume paced at 4 s (15 starts/min, below the published 20/min limit). Not host-comparable to local GPU timings.
- **Integrity:** all 80 scored responses HTTP 200, exact authorized model ID, `finish_reason=stop`, zero reasoning tokens/reasoning content, no `X-Dropped-Params`/`X-Mapped-Params`/`X-Output-Clamped` headers, zero retries from schema errors, identical system prompt and strict schema on all 80, no scoring keys or expected answers in request bodies, no credential material in artifacts. The 429 was excluded and re-sent under the same authorization with no prompt/rubric/score change. If fewer than 80 cases had completed, the run would have been reported as incomplete with no extrapolation.

---

## 10. Engineering acceptance status

`docs/ENGINEERING_ACCEPTANCE.json` (verified 2026-11-22), 34 criteria total:

| Status | Count |
| --- | ---: |
| `independently_validated` | 1 |
| `verified_operational` | 3 |
| `verified_automated` | 21 |
| `in_progress` | 9 |

Standing mission criteria (§ENGINEERING_MISSION.md): keep authorization/rules/ROE/evidence admission independent of model output; measure accuracy, safety, abstention, latency, tokens, resources and cost separately; keep development and held-out families separate and preserve negative results; zero standing live cloud requests (historical one-shot permissions have their own scope); verify security, operational, cloud, evaluation, reliability, academic and production criteria individually; real telemetry remains unauthorized.

---

## 11. Limitations to state explicitly

1. **Retrospective matched synthetic benchmark** — 80 authored cases in held-out families separate from 40 calibration cases, but ground truth and contracts were authored for this pilot. Not a fresh independent blinded human-adjudicated holdout; no general security-accuracy estimate.
2. **Deployment differences** — cloud tokenization, chat template and context handling cannot be matched exactly to local Ollama; the comparison includes these, not only model capability.
3. **Not interchangeable with other instruments** — do not merge the 90% figure with the 24/30 Planner pass rate, the .686 ATT&CK mapping F1, the 18-case extraction diagnostic, or `eval/ai_benchmark.py` (a different 19-case evidence-mapping benchmark). One 27B Reporting success (HTTP 200, 260/62 tokens) is not an accuracy result.
4. **Small, unadjusted intervals** — exploratory bootstrap over few synthetic families, no multiple-comparison control.
5. **Reasoning disabled by design** — to honour frozen `think: false`; no claim is made about the model's reasoning-enabled performance.
6. **Hardware/Cuda** — local fine-tuning was never started; torch is `2.6.0+cpu` with `cuda_available=False`. 4-bit QLoRA of 7–8B is the realistic 8 GB ceiling; do not claim the 27B was trained or that a local model beat it on a controlled training comparison.
7. **Historical negatives preserved** — the 12/12 truncation, the Stage A citation failure, the 0/72 proof-group result, the failed Cedar build on Windows and the live-grounding regression all remain valid records.

---

## 12. Recommendations and next gates

1. **Adopt the 90.00% figure as the matched-benchmark cloud result** for the progress report, with the exact caveats above. It is the first measurement showing a clear advantage on KAYAN's own frozen role benchmark.
2. **Continue the cloud pivot as a scoped research candidate only.** No production authorization follows from this run. Next: replicate on a fresh, independently labelled synthetic cohort with blinded human adjudication, matched budgets and a same-setting local arm.
3. **Keep TrustGate/Cedar, signed ROE, admission v2, provenance/custody, tool permissions and tool scope unchanged.** No production authorization-rule change to pass a benchmark; no cloud-only prompt improvements.
4. **Rotate the exposed SovereignEG key** before sharing these artifacts publicly; keep credentials outside the checkout.
5. **Before any further live traffic:** re-verify Student allowance, automatic balance use off, paid overage off and current rates; obtain a fresh explicit bounded authorization with request cap and spend ceiling.
6. **Keep real-telemetry intake unauthorized** and keep the operational baseline local until independent validation and a deployment-specific security review are complete.

---

## Appendix A — Artifact index

Canonical development checkout: `<REPO_ROOT>` (main checkout untouched by the evaluation work; its pre-existing uncommitted work was left intact).
Isolated evaluation worktree: `<EVAL_WORKTREE>`, branch `eval/sovereign-80-case-accuracy` from `1f63244`. The sanitized, publishable subset is included in this repository under `eval/sovereign-80-matched/`.

| Artifact | Location |
| --- | --- |
| This consolidated report | `kayan-eval-sovereign-80\KAYAN_CONSOLIDATED_FINDINGS_2026-11-23.md` |
| Matched-run supervisor report | `eval\cloud_matched\SUPERVISOR_REPORT_2026-11-23.md` |
| Frozen protocol, mapping, cost model | `eval\cloud_matched\frozen_protocol.py`, `README.md`, `REQUEST_PLAN.md` |
| Matched runner / scorer / verifier | `eval\cloud_matched\run_matched.py`, `resume_matched.py`, `score_matched.py`, `make_mock_fixture.py` |
| Recovered verbatim frozen harness + 5 raw local arms | `eval\reference\role-benchmark\` |
| Full redacted live ledger and scored cases | Kept private (raw model responses/request metadata); not published |
| Final re-scored comparison | Kept private; offline re-score reproduced `summary.json` and `summary.csv` byte-for-byte |
| Published frozen harness, scorer and metrics | `eval/sovereign-80-matched/` (this repository) |
| Historical cloud failure records | `kayan-trustgate\docs\CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md`, `CLOUD_PIVOT_REASONING_BUDGET_V2.md`, `CLOUD_PIVOT_ACCURACY_CHECKPOINT.md` |
| Research baseline | `kayan-trustgate\docs\RESEARCH_UPDATE.md`, role-benchmark `RESULTS.md` / `PROTOCOL.md` |
| Engineering state | `kayan-trustgate\MASTER_HANDOFF.md`, `docs\ENGINEERING_MISSION.md`, `docs\ENGINEERING_ACCEPTANCE.json` |

## Appendix B — Key digests

| Item | SHA-256 / value |
| --- | --- |
| Frozen role manifest | `09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0` |
| Live CI checkpoint | `06e5f12` |
| First real cloud run ledger | `ee395377b6cdb2982682643c11db60602dedd8d376d522ecea7fd4d509adb923` |
| Reasoning-budget Stage A record | `271544c978063f25ade957e988dd2657f6a3c4e47054d71ddf5e86ebc93f6b86` |
| Matched cloud run | 80/80 cases, 81 requests, `MEASURED`, exclusive-create `.build/cloud-matched-2026-11-23-resumed` |
