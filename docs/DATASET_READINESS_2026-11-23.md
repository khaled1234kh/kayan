# Dataset readiness — 2026-11-23

## Status: provisional, not frozen

`eval/decision_eval/datasets/decision_cases_v0_1.jsonl` contains 40 genuinely
new provisional decision cases: 8 per agent across Planner, Recon, Web-App,
Network and Reporting. None reuses records, families, prompts or labels from
the historical 80-case role benchmark or the 18-case ATT&CK extraction
cohort.

Every case is marked:

```json
"annotation_status": "provisional",
"provenance": { "independent": false, "author": "...", "reviewers": [], "adjudicator": null }
```

These labels are **authored for framework development**. They are not
independent, not blind-reviewed and not adjudicated. `dataset.load_dataset(...,
require_frozen=True)` refuses to load them as frozen, and the acceptance gate
`G1-annotation` is `not_met`.

## Coverage

Twelve challenge categories are represented across the five agents:

`positive`, `negative`, `contradictory`, `ambiguous`, `incomplete`, `benign`,
`similar_but_unrelated`, `multi_record`, `cross_session`, `attack_ambiguous`,
`missing_link`, `adversarial_instruction`.

Each case carries: `case_id`, `dataset_revision`, `scenario_family`, `agent`,
`challenge_category`, `evidence`, `ground_truth`, `citations`, `abstention`,
`actions`, `scope` (authorized, synthetic), `limitations`, `rubric_version`,
`provenance` and `annotation_status`. Planner cases additionally carry
`dependencies` and `execution_order`.

## Integrity

- Dataset SHA-256 manifest: `eval/decision_eval/datasets/SHA256SUMS.txt`.
- Verified with `eval.decision_eval.dataset.verify_manifest(...)`.
- Regeneration is deterministic:
  `python -B -m eval.decision_eval.build_provisional_dataset`.
- A perfect output passes all 40 cases under the versioned scorer and an empty
  output passes none, confirming the cases are answerable and the scorer is
  not trivially satisfiable.

## Independent annotation protocol

`eval/decision_eval/annotation.py` implements the path from provisional to
frozen. It never invents a reviewer.

1. `issue_blind_forms()` removes ground truth, model output, provenance author
   and annotation status, and issues two forms (A and B) with a bound
   `packet_sha256`.
2. Two **real, named** reviewers return separate sheets with a label,
   item-owned evidence IDs and a written justification per case. `validate_annotation()`
   checks a real identity (placeholder names are rejected), a qualification,
   an independence attestation, a completion date and a hash bound to the
   issued form.
3. `compare_annotations()` computes raw label agreement, Cohen's kappa, raw
   evidence-set agreement and a mean evidence Jaccard, and emits an explicit
   disagreement record per conflicting case.
4. A **real, named** adjudicator resolves every disagreement in a sheet bound
   to the packet and the agreement report, dated after both reviews.
   `validate_adjudication()` enforces this ordering.
5. Only then may `freeze_labels()` set `annotation_status = "frozen"` and bind
   `label_version`, `adjudicator` and `adjudication_sha256`.

Gate `G1-annotation` requires raw agreement >= 0.80, Cohen's kappa >= 0.60 and
all disagreements adjudicated. Until genuine returns exist, the dataset stays
provisional and no confirmatory claim may use it.

## Scoring

Versioned cases are scored by `eval/decision_eval/versioned_scorer.py`, which
applies the `diagnostics-v1` rubric consistently to all arms and supports
multi-record evidence that the frozen 80-case shape cannot express. The
frozen role-contract scorer in `eval/sovereign-80-matched/reference/` is left
untouched and is used only for the historical 80-case baseline.

## Red-team suite

`eval/decision_eval/redteam.py` defines 14 separate security cases covering
prompt injection, fake authority, scope escalation, forged/missing
authorization, cross-engagement leakage, attribution errors, fabricated
citations, tool-catalogue violations, malicious retrieval, unauthorized
publication, stale approvals, contradictory records and timeout/recovery.
Active tests are restricted to authorized synthetic or owned-loopback
environments. The suite currently exports case definitions and deterministic
checkers; it has not been executed against a model.
