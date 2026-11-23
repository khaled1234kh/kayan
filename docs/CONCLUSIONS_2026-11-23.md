# Evidence-backed conclusions — 2026-11-23

## What is established by existing evidence

The Qwen3.8 27B model accessed through SovereignEG outperformed the previously tested local checkpoints on KAYAN's retrospective 80-case synthetic benchmark.

Offline replay with the untouched scorer reproduced the historical summary
exactly: `72/80 = 90.00%` exact role-contract accuracy, with zero unsupported
affirmatives and zero invalid outputs. Local re-scores under the same scorer
ranged from `5/80` to `28/80`. The canonical decision confusion matrix for the
cloud arm shows the errors that exact pass alone hides: 8 missed findings, 8
bad citations, 8 incomplete chains, 6 incorrect withholdings and 2 false
abstentions across the 80 cases.

These are retrospective, authored-synthetic, exact-contract results. They are
not an independently labelled holdout and not a production accuracy estimate.

## What is not established

- **No causal hosting claim.** Model generation, size, quantization, serving
  and placement changed together. Only experiment B can isolate placement and
  it is blocked pending identical checkpoint digests and fresh authorization.
- **No semantic-entailment claim.** The frozen scorer checks item labels and
  exact item+label+record triples, not open-ended reasoning quality.
- **No judge validation.** DeepEval is wired but pinned and offline; no judge
  was run, so judge agreement and bias are unmeasured.
- **No independent ground truth.** The 40 new cases are provisional; no real
  blind reviewers or adjudicator have participated.
- **No red-team result.** The 14-case security suite is defined, not run.

## Framework conclusions

1. A defensible framework can be built entirely offline by separating
   structural validity, decision correctness, evidence correctness and
   operational success, and by keeping exact pass, confusion matrices and
   error categories distinct.
2. The frozen baseline can be preserved byte-for-byte while a versioned rubric
   handles richer cases (multi-record, cross-session, attribution) that the
   historical shape cannot express.
3. Independent annotation must be gated by real identities and bound
   adjudication; the code refuses placeholder reviewers and refuses to freeze
   labels without them.
4. Supplementary LLM judging is safe only when pinned, model-distinct,
   agreement-checked and subordinate to deterministic scoring.
5. Controlled comparisons need identical checkpoints, fixed prompts/schemas/
   scorers/decoding, prespecified runs, clustered uncertainty and a stopping
   rule; without these, the historical contrast is descriptive only.

## Acceptance state

All quantitative gates (`G1`–`G6`) are `not_met` because no confirmatory run or
independent annotation has occurred. `G7` (accurate reporting of the 90%
result) is `met_documentation_only`. No claim of production readiness is made.

## Delivery map (A–H)

| Item | Deliverable | Artifact |
| --- | --- | --- |
| A | Evaluation audit | `docs/EVALUATION_AUDIT_2026-11-23.md` |
| B | Experiment matrix | `eval/decision_eval/reports/EXPERIMENT_MATRIX.json` |
| C | Working framework | `eval/decision_eval/*.py` |
| D | Dataset readiness | `docs/DATASET_READINESS_2026-11-23.md` |
| E | Offline re-analysis | `eval/decision_eval/reports/OFFLINE_REANALYSIS.{json,md}` + charts |
| F | Controlled experiment configs | `experiments.py` A–D and `protocol.py` |
| G | Evidence-backed conclusions | this document |
| H | Completion report | this document and the pull-request description |

## Reproduction

```powershell
python -B -m eval.decision_eval.run_framework
```

No new paid cloud or judge call was made in producing any artifact in this PR.
