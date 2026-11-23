# KAYAN offline decision-evaluation framework — 2026-11-23

This directory adds a defensible, offline-first evaluation framework for the
five KAYAN agents without making any new paid cloud or judge call.

## Design rules (enforced in code)

1. The frozen 80-case role-contract scorer is the historical baseline and is
   never edited. New rubrics are versioned (`diagnostics-v1`) and applied
   consistently to all arms.
2. Deterministic scoring is primary. DeepEval / LLM-judge output is
   supplementary and can never become ground truth.
3. No network call, judge call or cloud inference happens by default.
4. Human labels remain `provisional` until real independent reviewers and an
   adjudicator attest and bind them.
5. Exact case-level accuracy, canonical multiclass confusion matrices and a
   disjoint error taxonomy are reported separately.

## Modules

| Module | Purpose |
| --- | --- |
| `protocol.py` | Canonical inference protocol: exact model/revision, prompt bytes + SHA-256, schema hash, temperature 0, seed, tokens, reasoning, retrieval, scorer, remappings/clamps/ignored settings, and bounded pre-flight cost envelope. |
| `scoring.py` | Loads the untouched frozen scorer and helpers; canonical label mapping; historical exact pass and error taxonomy for saved outputs. |
| `versioned_scorer.py` | `diagnostics-v1` scorer for the new dataset; supports multi-record evidence; never calls the frozen scorer. |
| `confusion.py` | Full and row-normalized confusion matrices, TP/FP/FN/TN, precision/recall/F1, macro/micro/weighted F1, balanced accuracy, abstention metrics, per-agent and pooled aggregation. |
| `statistics.py` | Wilson intervals, paired bootstrap (optionally clustered by scenario family), exact McNemar, Cohen's kappa and judge bias. |
| `dataset.py` | Versioned case schema, loader, SHA-256 manifests, and reproducible audit of the 18-case historical cohort. |
| `annotation.py` | Blind forms, two real reviewers, disagreement records, bound adjudication, kappa/raw agreement, and freeze gate. |
| `deepeval_adapter.py` | Pinned DeepEval `4.3.4`; `GEval`, `Faithfulness`, `ContextualRelevancy`, `AnswerRelevancy`, `TaskCompletion`; deterministic ATT&CK/evidence/citation/authorization metrics; offline mock and judge-agreement checks. |
| `experiments.py` | Controlled experiment configurations A–D, one-factor/factorial designs, prespecified 3 runs, stopping rule and quantitative acceptance gates. |
| `redteam.py` | Separate 14-case security suite with restricted environment and deterministic checkers. |
| `cost.py` | Append-only ledger for latency (p50/p90/p95), tokens, reasoning tokens, requests/case, timeouts, HTTP errors, retries, rate limits, EGP cost, local RAM/VRAM, energy, cost per correct case and cost per accepted assessment. |
| `charts.py` | Dependency-free SVG confusion-matrix charts. |
| `reanalysis.py` | Offline re-scoring of saved outputs with stored-score verification. |
| `build_provisional_dataset.py` | Deterministic generator for 40 new provisional cases. |
| `run_framework.py` | Regenerates dataset, re-analysis, matrices, charts, suite and manifests with zero network calls. |

## Reproduce

```powershell
# Regenerate all offline artifacts (no provider or judge call)
python -B -m eval.decision_eval.run_framework

# Skip re-analysis if the local-only saved outputs are not present
python -B -m eval.decision_eval.run_framework --skip-reanalysis

# Verify frozen manifest and re-scoring imports
python -B -c "import sys; sys.path.insert(0, 'eval/sovereign-80-matched'); import frozen_protocol as fp; print(len(fp.heldout_entries(fp.load_manifest())))"
```

Saved cloud responses and local request ledgers stay under the local-only
`.build` and `eval/reference/role-benchmark/results` directories; they are
never copied into the repository. Set `KAYAN_SAVED_ROOT` to that local
directory before running re-analysis; otherwise use `--skip-reanalysis`.

## Canonical decision mapping

| Agent | Supported | Contradicted | Abstain |
| --- | --- | --- | --- |
| Planner | `ready` | `blocked` | *(no class)* |
| Recon | `confirmed` | `contradicted` | `insufficient` |
| Web-App | `supported` | `contradicted` | `insufficient` |
| Network | `confirmed` | `contradicted` | `insufficient` |
| Reporting | `include` | `omit` | `abstain` |

Planner's missing abstain row is reported as zero support with null
per-class metrics. It is never counted as a false abstention.

## DeepEval integration

DeepEval is pinned to `4.3.4` (`https://pypi.org/project/deepeval/4.3.4/`;
docs at `https://deepeval.com/docs`). `build_judge_metrics()` returns an
offline specification by default and imports nothing. A live run requires
`allow_judge_calls=True`, `offline=False`, a pinned installation, a frozen
judge model ID distinct from the evaluated model, and fresh bounded
authorization. Judge disagreement is measured against the deterministic
scorer with kappa, raw agreement and prevalence bias; all disagreements are
recorded. Judge tokens, latency and cost are accounted separately.

## Experiments and authorization

Experiments A–D are declarations only. Before any real run:

1. Confirm exact model IDs and checkpoint revisions/digests.
2. Freeze dataset revision and acceptance matrix.
3. Compute requests/token worst case with `protocol.preflight_budget`.
4. Estimate EGP cost at catalogue rates, verify allowance and overage policy.
5. Present a bounded authorization request and wait for explicit approval.

No real SovereignEG or other paid cloud-model call is authorized by this PR.
The previous 80-case cloud approval is consumed. The exposed SovereignEG key
must be rotated before any shared or public use.

## Claim-to-evidence matrix

`reports/EXPERIMENT_MATRIX.json` maps every claim to dataset, metric, baseline,
arm, scorer, result placeholder, CI, limitations, artifact and verification
status. Gate thresholds are fixed before confirmatory testing and are listed
in `docs/EVALUATION_AUDIT_2026-11-23.md` and the framework report.
