# KAYAN evidence admission feasibility protocol

20 November 2026 · Draft for approval · Study execution and intake unauthorized

## Questions and hypotheses

| Question | Falsifiable working hypothesis |
| --- | --- |
| Can the supported Windows normalizer preserve the fields needed for review? | In-scope fields match independently verified source values and documented transformations. A wrong identity, event outcome or time value used to approve a claim falsifies the corresponding safety expectation. |
| Can KAYAN distinguish supported from unsupported session associations? | Candidate links never join an independently refuted or unresolved pair, and the proportion of supported reference links recovered meets the approved coverage floor. A candidate is a correlation result. Verified attribution requires separate evidence. |
| Can admission and the guard distinguish sufficient submitted ATT&CK evidence? | Eligible review items all have a complete adjudicated evidence group for the same occurrence, and the proportion of eligible, complete positives meets the approved floor. An unsupported eligible item falsifies the pilot safety criterion. |
| Can independent staff operate the workflow? | Required evidence and authority records can be produced and verified within approved labor and turnaround limits. Missing audit records and excess overhead are measured as feasibility failures. |

## Evaluated workflow

Evaluate `attack_windows_event_normalizer_v1` for Windows Security XML 1102 version 0 and 4624 version 2, including its session-candidate function. Use the public `attack_evidence_admission_v2.evaluate_in_custody` entry point with signed-off custody, registry, scoped projection and v4/v3 guard dependencies. Keep the verified local revision and dependency versions pinned. Restrict the primary finding analysis to T1685.005 evidence for Windows event-log clearing. A 4624 record can contribute session context. The adjudicated evidence group must establish the mechanics, relevant linkage, independent attribution, applicable authorization and outcome. Independently approved contextual material may support those facts within the collection agreement. [Engineering sign-off](ATTACK_PROVENANCE_ADMISSION_V2_FINAL_SIGNOFF_2026-11-20.md) · [Normalizer](../eval/attack_windows_event_normalizer_v1.py) · [Admission](../eval/attack_evidence_admission_v2.py)

The primary study verifies **submitted** candidate claims and evidence. A separate preparer supplies fixed human-authored proposals and prepares inputs from authorized observations. Preparers, reference reviewers and adjudicator have separate roles. Reference reviewers annotate original pseudonymized evidence, without seeing the proposal, normalized fields, admission decisions or historic labels. Freeze the submitted inputs and reference labels independently before scoring. The system receives authorized review receipts for its input evidence through custody, using human input decisions made without access to the reference answers. Record input decision labor separately. This workflow measures conditional verification and operational labor. Finding discovery, autonomous evidence gathering and model grounding accuracy require a different design.

## Cases and cohort

The sampling unit is a bounded incident or maintenance episode. The primary analysis unit is one preselected event–technique claim per episode, with occurrence defined by case, event and event revision. A separate episode-level analysis covers all claims, including mixed batches and extra items. Field and candidate-link evaluations use individual adjudicated fields and clear-event/logon pairs, nested within episode. Group related episodes by shared host, source, operator or organizational campaign for dependence reporting.

| Reference stratum | Eligibility and expected treatment |
| --- | --- |
| Positive | Completed clearing, corroborated with sufficient scope, attribution and authorization evidence to support an eligible claim. |
| Negative | Evidence affirmatively refutes the claim, such as authorized maintenance or a refuted event attribution. Preserve the original disproving evidence. |
| Ambiguous | Competing links, inconsistent accounts or unresolved authorization prevent a decision. Retain each plausible alternative and the uncertainty. |
| Incomplete | Selected supported observations are present but an essential evidence role is unavailable. Document the missing role and keep the episode in the analysis. |

Include only episodes within an approved source, host and time scope, with a supported anchor profile or an authorized logging record relevant to the candidate, governed original-byte provenance, and enough surrounding context to determine why the claim is supported or undecidable. A missing link or stipulated evidence gap can be a valid study case. Exclude unsupported profiles as primary evidence, out-of-scope material, compromised custody, identifiers without approved handling, duplicates, and all exposed development fixtures, prior confirmation packets and their derivatives. Log exclusions and reasons before outcome review. Capture invalid or blocked attempts encountered after enrollment in the flow and feasibility denominators. Exclude unauthorized data before collection.

An independent custodian assembles a new, authorized cohort by prespecified sampling windows and selection rules. Use an enriched, stratified sample so rare negative and ambiguous cases are represented. Sample within strata using prespecified screening indicators, retaining screen logs and differences between provisional strata and adjudicated labels. Preselect the primary claim by a documented rule using occurrence and evidence availability before reference scoring or verifier output. A custodian compares source episode IDs and content hashes against an exposure and duplicate register kept within the approved environment. Cases sharing an episode receive a single group ID. Use wholly separate synthetic rehearsal materials. Freeze opaque IDs, roster, sampling strata and hashes before unblinding. Report actual case mix and selection flow. Stratum enrichment limits prevalence claims.

## Size and interpretation

Provisional target is **48 independent episodes**, aiming for 12 per reference stratum and one primary claim per episode. This is a workload-based feasibility target, yielding 96 initial independent packet reviews plus adjudication. Feasibility depends on staff capacity and eligible cases. Freeze the final target and minimum viable strata before intake. Report a shortfall as such and obtain a prospectively approved amendment for any design change. With 0 false eligible claims among 36 independent nonpositive episodes, the exact one-sided 95% upper bound would still be about 8%. Smaller effective sample sizes or clustering widen uncertainty. This pilot supports estimates of process performance and failure modes. Confirmatory claims require a separately powered, held-out design.

Expected threats include enrichment and single-organization bias, incomplete operational records, shared collectors and event clusters, timestamp resolution and clock skew, pseudonymization effects on joins, imperfect human reference labels, human-prepared proposals, and taxonomy or software version drift. Report the scope of conclusions by profile, technique and cohort. Analyze disagreement and unresolved cases explicitly. [Evaluation plan](ATTACK_ADMISSION_FEASIBILITY_PREREGISTRATION.md)

## Prior evidence

Exploratory v2 completed 0/10 evidence groups in every arm/pass. Experiment A raised expected ID selection from 0/6 to 6/6 after candidate substitution while complete groups stayed at 0/6. Fixed-technique B/C yielded 0/4 complete positive groups and 3/4 correct negative or ambiguous abstentions. Experiment D completed 0/3 groups in both workflows. Its additional correct abstention occurred under an empty extraction fallback. These retained results concern generation on exposed fictional cases. The offline engineering PASS concerns deterministic verification against controlled inputs. [Frozen evaluation and limitations](ATTACK_POST_DIAGNOSTIC_ARCHITECTURE_REVIEW_2026-11-20.md)
