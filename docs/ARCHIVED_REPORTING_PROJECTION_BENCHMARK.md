# Archived Reporting projection benchmark

The nine frozen archives contain four supported occurrences, six withheld occurrences, one invalid archive and one empty archive. Some archives contain more than one occurrence. The test oracle consists of authored synthetic labels and exact source addresses. For comparison, the unchanged admission verifier receives an explicit primary-address proposal for each occurrence against the full archive. Reporting receives the same archive and assembles its own proposals.

| Measure | Baseline | Occurrence-aware Reporting |
| --- | ---: | ---: |
| Supported occurrences displayed | 1/4 | 4/4 |
| False withholdings | 3 | 0 |
| False admissions | 0/6 | 0/6 |
| Displayed findings with expected source addresses | 1/1 | 4/4 |
| Invalid archive rejected | 1/1 | 1/1 |
| Verifier disagreements with the authored dispositions | 0/11 | 0/11 |

The baseline merged occurrences by technique. The verifier could not distinguish two separate action anchors in one claim. Reporting now submits each repeated occurrence separately, verifies the full custody snapshot on every call and checks the returned provenance's event ID and revision. Both supported occurrences appear in the repeated-supported archive. In the mixed archive, the supported occurrence appears and the authorized one stays withheld. When two occurrences share an ambiguous action anchor, both still stay withheld.

The projection fix used the local composer to display occurrence labels for supported and withheld results. A later selection contract distinguishes repeated occurrences with request-local aliases and has been verified with mocked transport. A live request requires its own approval. The pinned Slate request digest remains unchanged. [Selection contract and authorization](ARCHIVED_REPORTING.md#occurrence-aware-selection)

Reproduce the comparison with `python -B -m eval.archived_reporting_projection`. Commit `15419d2` reproduces the baseline. The fixed runner verifies the same archive hashes before each run. [Frozen fixture lock](../eval/fixtures/ai/archived_reporting_projection_v1.json) · [Baseline results](../eval/reports/archived_reporting_projection_v1_baseline.json) · [Corrected results](../eval/reports/archived_reporting_projection_v1_after.json)

This is a deterministic Reporting projection test. It measures assembly and presentation against a small authored set. The evaluation used zero provider calls and supplies no independent real-telemetry validation, model accuracy estimate or population-level precision and recall.
