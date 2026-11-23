# ATT&CK independent label review and fresh confirmation

**Historical preparation, 2026-11-20, Africa/Cairo.** Two blinded forms per cohort were generated. The 24 frozen observations have since been reviewed by an AI, with provisional judgments outside the human gate. The original workflow remains sealed and no confirmation inference was executed. [Current AI research review](ATTACK_PROFESSIONAL_RESEARCH_REVIEW_2026-11-20.md)

Use the new handoff for all confirmation work. It provides the versioned joint-evidence rubric, private review and adjudication workflow, stakeholder decision template and registered runner. The prior preparatory notes below are retained for context. [Current handoff](ATTACK_CONFIRMATION_HANDOFF_2026-11-20.md)

## Review packets

| Cohort | Cases | Use |
| --- | ---: | --- |
| [Original diagnostic packet](../eval/reports/ai_retrieval_mapping_20261120/blinded_review_packet.json) | 32 | Audit the original author rubric using independent reviewers. Publish any changed labels as a new version. |
| [Frozen confirmation observations](../eval/fixtures/ai/evidence_mapping_confirmation_v1_unlabelled.json) | 24 across 12 families | Obtain independent labels before one held-out confirmation. Reviewer copies hide family membership and shuffle the case order deterministically. |

Use the appropriate Reviewer A and B files under [the review folder](../eval/reports/ai_mapping_ablation_20261120/review/). The files contain only fictional source records and blank review fields. Give each reviewer only their own forms and the pinned taxonomy reference. Preserve originals and returned forms separately. Keep author labels, model output, metrics and other reviewers' answers out of the review.

The fresh observation file is locked by SHA-256 `9451fde497ce8fa228f0eb0a7de2e836f514e6e5a8c165771637691d1f35d50c`. The fresh set introduces additional behavioral categories and evidence patterns, including corrections, authorized changes, unexecuted events, unrelated simulations and genuine ambiguity. Its synthetic authorship remains a limitation.

## Independent review and adjudication

1. Recruit two qualified reviewers familiar with defensive telemetry and ATT&CK. Record their identity or qualified pseudonym, the packet hash, review date and taxonomy version. Each uses Enterprise ATT&CK 20.1 and completes every row independently.
2. Record what happened, target and source when established, the reliability of the cited records, and how contradictions were resolved. Distinguish a confirmed adversary action, authorized action, prevention, unconfirmed story, insufficient observations, unresolved contradiction and a simulation. Use an empty mapping when the evidence does not support an active technique. Mark ambiguous cases even when choosing to abstain.
3. Cite the record IDs that jointly carry the distinguishing facts. Note when evidence only supports the mapping jointly, for example when separate sources prove the action and absence of authorization. Adjudication must record how such multi-record mappings are scored before any model run.
4. Calculate raw agreement and Cohen’s kappa for the disposition, any mapping, exact ID sets and exact technique–record pairs. The supplied comparator rejects altered inputs, invalid IDs, incomplete rows and reused reviewer IDs. A missing kappa means no variance for that agreement calculation. The JSON contains disagreements and ambiguous rows for adjudication.
5. An adjudicator reviews the disagreement log and the evidence. Record separate decisions for parent versus sub-technique, domain versus cloud account, local versus remote mailbox, clearing events versus disabling capture, and host shutdown versus service interruption wherever those distinctions occur. Annotate any rubric gaps and record the final evidence and rationale. Keep both originals and write adjudicated cases to a new label file, with the packet hash and version. Keep the existing labels, outputs and reported scores intact.

From the project root after both genuine forms have been returned:

```powershell
python -B -m eval.ai_mapping_review compare $packetPath $newAgreementPath $reviewerAPath $reviewerBPath
```

Set those paths to the original input packet, a new output JSON filename, and the two completed forms respectively.

## Fresh experiment lock

Use field BM25 @ 5 and hybrid E5-192 @ 5 with the same pinned Qwen model, base prompt and schema. Freeze the adjudicated label hash, code hashes, candidate parameters and family pairs before inference. The existing diagnostic runner enforces the previously frozen fixture and cannot silently switch to the fresh cohort. A separate final runner must verify the new input and label digests before allowing inference. [Experiment lock](../eval/reports/ai_mapping_ablation_20261120/review/confirmation-lock.json) · [Diagnostic decision](ATTACK_MAPPING_ABLATION_2026-11-20.md)

Before any final model output is generated, record the stakeholder-approved tolerance or cost rule for unsupported mappings versus missed confirmed events. The practical decision is to keep field-weighted BM25 unless the candidate delivers a repeatable end-to-end gain that justifies its overhead and satisfies that rule. Report uncertainty instead of treating overlap with zero as equivalence. No numerical acceptance margin has been approved.

Run both locked arms once and publish exact case counts, pair precision/recall/F1, false positives, missed events, positive-case recall, negative specificity, abstentions, schema and provenance-block counts, and the family-paired 95% intervals. Report latency, prompt/completion tokens and resource use. If the result is inconclusive, publish it as such. Any additional tuning requires another independently reviewed cohort. Preserve the original research evidence and keep deployment and authorization decisions separate.
