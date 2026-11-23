# ATT&CK research validity assessment

| Claim | Assessment | Basis |
| --- | --- | --- |
| Hybrid E5-192 led field-weighted BM25 in the matched diagnostic run. | Supported for those 32 author-scored fictional cases. | 26/32 versus 22/32 exact. Pair F1 was .733 versus .533. The two omitted-label sensitivity comparison still favored hybrid, 25/30 versus 21/30, and stays post hoc. |
| Hybrid has a repeatable material benefit or is equivalent to BM25. | Unestablished. | The matched 95% interval includes zero, the cases were reused, and a prior identical-context hybrid run scored 24/32. No equivalence margin or adjudicated confirmation was applied. |
| The 192-token cap discards catalogue content. | Measured. | 567/706 passages exceeded it and at least 549 detection-strategy suffixes lay beyond it. Increasing the cap improved standalone E5 retrieval and reduced hybrid top-five recall in this cohort. No universal cap preference follows. |
| Current failures have both retrieval and evidence-interpretation components. | Supported on named cases. | `fresh-13` is a hybrid candidate miss. `fresh-09`, `fresh-15` and `fresh-22` establish errors even with relevant context or a real quote. Mechanisms behind response variation remain unresolved. |
| The deterministic scorer establishes semantic evidence support. | Unestablished at quote level. | It binds IDs and text to records and evaluates adjudicated groups. A semantically irrelevant span from the correct record can pass. The 56 cases give limited tests of evidence drawn from separate records. |
| The study has verified author labels or independent confirmation. | Unestablished. | AI review disputes two author positives and records uncertainty. The 24 confirmations now have provisional AI judgments. Human agreement and independent confirmation remain unavailable. |
| The results establish TrustGate security or production readiness. | Outside the tested scope. | Evaluation used fictional retrospective observations. Stored model scores do not measure an authorization decision, live assessment performance, or tenant isolation. |

Report this work as a matched offline diagnostic experiment and a reproducible error analysis. Use BM25 as the low-complexity comparator and hybrid E5-192 as the research challenger. A stronger claim requires a newly reserved cohort unknown to the AI reviewer and independent adjudication under a protocol recorded before inference. [Full review and sources](ATTACK_PROFESSIONAL_RESEARCH_REVIEW_2026-11-20.md)
