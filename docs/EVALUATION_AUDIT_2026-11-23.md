# Evaluation audit — 2026-11-23

## Scope

This audit covers the historical evidence that exists in the KAYAN repository
before the decision-evaluation framework in `eval/decision_eval/`. It is a
design and provenance audit, not a new experiment. No provider or judge call
was made to produce it.

## What the 90% number actually is

The Qwen3.8 27B model accessed through SovereignEG outperformed the previously tested local checkpoints on KAYAN's retrospective 80-case synthetic benchmark.

The frozen scorer was replayed byte-for-byte against saved outputs and
reproduced `72/80 = 90.00%` exact role-contract accuracy, Affirmative F1
`0.935`, Evidence F1 `0.945`, Abstention F1 `0.984`, zero unsupported
affirmatives, zero invalid outputs and zero errors. Local arms re-scored with
the same untouched scorer: Qwen2.5 7B `18/80`, Qwen3 8B `28/80`, Granite 4.2
8B `27/80`, Llama 3.1 8B `23/80`, Qwen2.5 1.5B `5/80`.

The 90% figure is therefore:

- **exact role-contract accuracy** on **80 authored synthetic heldout cases**;
- a **retrospective matched benchmark**, not a fresh blinded holdout;
- **not** a human-adjudicated or independently labelled study;
- **not** real-world vulnerability-detection accuracy and **not** a production
  readiness claim.

The exact wording above is retained deliberately. It does **not** claim that
cloud hosting caused the improvement.

## Confounders in the historical contrast

The +55-point contrast between the best cloud arm and the best local arm is
not identified. At least the following changed together:

| Factor | Cloud arm | Local arms | Identified? |
| --- | --- | --- | --- |
| Model generation | Qwen3.8 | Qwen2.5 / Qwen3 / Granite 4.2 / Llama 3.1 | No |
| Parameter count | 27B | 1.5B–8B | No |
| Hosting / placement | SovereignEG managed | local Ollama | No |
| Quantization | FP8 | assorted local quantizations | No |
| Serving and schemas | OpenAI-compatible strict JSON schema | Ollama `format` | No |
| Decoding | temperature 0, `max_tokens` 384, reasoning off | temperature 0, `num_predict` 384 | Partly |
| Network / hardware | provider-managed | local machine | No |
| Comparison timing | retrospective replay | historical saved runs | No |

Section B of `reports/EXPERIMENT_MATRIX.json` is the only experiment designed
to isolate placement, and it is **blocked** until a byte-identical checkpoint
digest is confirmed on both placements. Until then, no hosting-causation claim
is permitted.

## Frozen 80-case design limitations

- 80 heldout cases, 16 per role, from 20 families × 4 variants.
- Controls: 40 benign and 40 quoted-instruction cases; these are author
  controls, not independently sampled conditions.
- Decision labels: `contradicted` 48, `insufficient` 45, `confirmed` 34,
  `blocked` 33, `ready` 31, `supported` 17, `include` 17, `omit` 16,
  `abstain` 15. Planner has **no abstain class**; multiclass matrices must
  not treat its absence as a miss.
- The scorer credits item labels and source references as item+label+record
  triples. A correct reference attached to a wrong claim or label receives no
  credit. This is a strict authored contract, not a semantic-entailment test.
- Repeated runs would measure repeatability; they are not new independent
  cases.
- The 19-case `eval/ai_benchmark.py` evidence-mapping benchmark, the 30-case
  Planner test, the 32-case ATT&CK mapping studies and the 18/19-case
  extraction diagnostics remain separate and are not merged into this cohort.

## Audit of the 18-case ATT&CK extraction cohort

Provenance was recovered from `eval/reports/attack_mapping_v2_20261120/registration.json`
and `docs/ATTACK_ROOT_CAUSE_V3_2026-11-20.md`:

- `label_source = "AI-authored synthetic key"` — there is no independent
  human label source.
- 18 cases, 9 positive and 9 negative/ambiguous, six scenario families.
- Two complete passes reuse the same cases.
- Ten target technique occurrences across six technique IDs; one
  multi-technique case and one sufficiency alternative.
- No independent adjudication, no source-independence attestations and no
  operational prevalence estimates.

Verdict: **development material only** — pilot, calibration and failure-mode
discovery. It must not be described as fresh, unseen or independently
labelled, and it is excluded from confirmatory accuracy claims. A machine
readable copy of the audited registration is in
`eval/decision_eval/datasets/attack_v2_registration_reference.json`, and the
audit logic is reproducible via
`eval.decision_eval.dataset.audit_legacy_cohort()`.

## Structural vs decision vs evidence vs operational validity

The framework reports these separately and never collapses them into one
score:

1. **Structural validity** — does the output satisfy the JSON contract,
   include every item once and use valid labels?
2. **Decision correctness** — does each item label match ground truth in the
   canonical Supported / Contradicted / Abstain classes?
3. **Evidence correctness** — are citations item-owned, complete and free of
   fabrication or wrong attribution?
4. **Operational success** — authorization, scope, tool-catalogue compliance
   and red-team behaviour.

Exact case-level pass rate, multiclass confusion matrices and the disjoint
error taxonomy are exported as distinct fields. Unsupported affirmatives,
false abstentions, missed findings, incorrect admissions/withholdings, bad
citations, wrong attribution and incomplete chains remain separate error
categories.

## Negative findings preserved

- `0/3` complete evidence groups and `12/12` truncated cloud run remain
  recorded as failures, not filtered out.
- The exact-citation probe failed and is not represented as a success.
- Windows Application Control blocks local Rust build scripts, one Go
  subpackage and LangGraph transitive `ormsgpack`; Ubuntu CI covered Go,
  Rust still needs a permitted environment for full local verification.
- Cloud remains optional and mock-only in production; no new live
  SovereignEG request was made for this framework.

## References

- `eval/sovereign-80-matched/README.md` and `SHA256SUMS.txt`
- `docs/CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md`
- `docs/ATTACK_ROOT_CAUSE_V3_2026-11-20.md`
- `eval/decision_eval/reports/OFFLINE_REANALYSIS.md`
