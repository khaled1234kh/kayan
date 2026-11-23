# Draft preregistered evaluation plan

20 November 2026 · Registration, thresholds and execution approval pending

## Freeze before intake

Record protocol version and hash ___, verifier revision and file hashes ___, Windows profile and taxonomy version/hash ___, eligibility and sampling windows ___, minimum viable strata and maximum enrollment ___, actor/time matching tolerance ___, rubric version ___, independent staff roles ___, allowed amendment procedure ___ and analysis environment/version ___. Sign and retain a dated pre-intake registration. Before first scoring, bind the frozen cohort and proposal manifests, input receipt ledger and independently locked reference labels to that registration. Separate additional analyses as exploratory and log their reasons and timing.

Primary evaluation uses one preselected claim per independent episode. For the operational run emit full per-claim dispositions and only route `review_items` to adjudication of emitted items. Record invalid, withheld, abstained and eligible statuses separately. A withheld unrelated sibling cannot inherit another claim's eligibility. Only exact occurrence matches and a complete, applicable adjudicated evidence group support a positive score. Supplementary analyses can include all claims and outcome reasons. Unexpected duplicates or out-of-roster emitted items count toward unsupported outputs and trigger review. Seal the evaluation outputs before joining reference labels.

| Metric | Numerator and denominator |
| --- | --- |
| Normalization correctness | Exact raw-to-normalized agreement under the pinned field-specific mapping / adjudicated expected field instances, by profile and field. Report critical errors, missing outputs and extra fields separately. Legitimately absent or unsupported fields have their own tally. |
| False session links | Candidate clear–logon pairs adjudicated refuted or unsupported / emitted candidate pairs. Show unresolved reference pairs separately within that total and provide a refuted-only sensitivity result. |
| Missed session links | Supported reference clear–logon pairs absent from candidate output / adjudicated supported pairs. Distinguish candidate recovery from final reviewed attribution. |
| False eligible findings | Adjudicated negative, ambiguous or incomplete primary claims marked eligible / all adjudicated nonpositive primary claims. Report each stratum and invalid cases separately. |
| Unsupported emitted items | Emitted items with incorrect occurrence/technique, incomplete support, or applicable adverse facts / all emitted review items. Audit extra items and duplicate emissions. |
| Complete eligible positives | Eligible primary claims with a complete adjudicated support group / all adjudicated positives. Include missing and invalid outputs as misses. |
| Appropriate withholding and abstention | Reference-withhold claims correctly withheld / claims assigned that disposition, and empty proposals appropriately abstained / reference cases requiring no submission in the separate case-level abstention check. Report invalid outputs and inappropriate abstentions separately. |
| Reviewer agreement | Before adjudication, identical categorical labels / double-reviewed units and Cohen’s kappa for primary dispositions. Report label prevalence, contingency matrix, exact claim-ID and evidence-group agreement, and undefined kappa where marginals are degenerate. |
| Provenance completeness | Applicable bindings verifiably present / required bindings, and complete emitted items / all emitted items. Audit record digest and locator, source lineage, case/head, assertion and receipt revision, trusted time and adverse history. |
| Time and overhead | Median, IQR, p90 and observed range with sample size for normalization, admission and end-to-end wall time per episode. Record staff minutes per episode by role, adjudication fraction, retries and blocked cases. Keep wait time separate from active time. |

Report raw counts and denominators alongside proportions, by stratum where relevant. An empty denominator is undefined. Provide 95% intervals for primary rates, using Wilson intervals for independent episode-level proportions and a one-sided exact upper bound for zero safety events in the independent primary cohort. For nested metrics resample independent episode groups as clusters where enough exist. With too few groups, report descriptive counts, an explicit limitation and sensitivity by group. Report missingness, excluded episodes, adjudication changes and any protocol departures by stage. Cross-tabulate stratum against eligibility, withholding, abstention and invalidity.

## Draft criteria for stakeholder ratification

| Gate | Proposed decision rule |
| --- | --- |
| Safety | Zero unsupported eligible review items and zero false eligible primary claims during the pilot. Any such event pauses the study and counts against the gate, including if later corrected. |
| Evidence trace | Verify every required custody binding for every emitted review item. One unverifiable required binding triggers a pause. |
| Positive usefulness | Proposed complete-eligible positive coverage floor of 75%, with at least 12 independently adjudicated positives. Proposed session-link recovery floor of 75% with a separately approved minimum supported pair count. Report intervals even if point estimates clear the floors. Zero eligible output fails usefulness. |
| Workload and analyzability | Stakeholder to set median and p90 staff time limits ___, minimum stratum coverage ___ and maximum incomplete or invalid operational fraction ___ before intake. |

Pause at the first unsupported eligible claim, cross-case/tenant join, missing adverse or revocation record, unverifiable head or time, loss of independent review or privacy incident. Block affected processing and release, preserve the audit trail under the approved retention rules, notify the responsible owners, reconcile prior items and record remediation. Resume only with written research, custody and data-owner approval plus privacy authorization where required. Keep the first-pass results and any approved rerun as separate evidence.

These draft thresholds support a feasibility decision. They provide no population guarantee or production authorization. Final thresholds, unit definitions, stopping rules and any amendments require dated stakeholder approval. Registration ID ___ · Study lead ___ · Statistician ___ · Stakeholder ___ · Date ___ · **Status pending**.
