# Archived Reporting at the eight-excerpt limit

The frozen suite uses six synthetic archives and authored selections at the eight-excerpt limit. It covers duplicate context, underrepresented occurrences, an authorized withheld occurrence, outcome-only summaries, summaries already showing actions, and a case in which attribution and authorization excerpts have known preference. Preferences are test oracles. The fixtures do not represent independent review or a model ranking experiment. [Frozen cases](../eval/fixtures/ai/archived_reporting_full_summary_v1.json)

| Metric | Append-only baseline | Two-swap candidate |
| --- | ---: | ---: |
| Occurrences with observed actions in the summary | 9/50 | 16/50 |
| Occurrences shown in the summary | 45/50 | 48/50 |
| Preferred excerpts among 48 slots | 43/48 | 46/48 |
| Cases losing preferred excerpts | 0/6 | 1/6 |

The candidate preserved selected outcome and action excerpts, kept a minimum of six original references in order, and retained every already cited occurrence. It failed the frozen per-case preference gate. In the trade-off case, replacing two contextual excerpts added two observed actions and lost two preferred excerpts. Both control cases stayed unchanged. The candidate is confined to the offline evaluator. [Per-case decision and scores](../eval/reports/archived_reporting_full_summary_v1.json)

The application keeps the accepted summary intact. The **Other verified actions** disclosure lists one already admitted action source per occurrence still missing one after the usual append-only pass. The export stores only technique, occurrence and source ID references to existing findings. The console resolves all three fields and requires the mechanic role before displaying the original excerpt. The headline coverage still counts only the eight summary slots.

The rendered desktop preview used a synthetic Gate and in-memory provider response. The summary cited seven of eight admitted occurrences and included one observed action. The disclosure showed the other seven admitted actions. The authorized ninth occurrence stayed withheld and its excerpt was absent. The browser export matched the 15,488 saved bytes. SHA-256 is `a793dd35ee76c7f262a29388d94e9c873c3126a5ccd4bcc637012de8dd119419`. [Rendered fixture](images/archived-reporting-full-summary-mock-preview.jpg)

Reproduce the comparison using `python -B -m eval.archived_reporting_full_summary`. The frozen fixture SHA-256 is `889f6e19f0a12bebe875b0b0f3454f4277e652da8768b8d9dc10878742d8f062`. Three focused tests cover the decision, occurrence isolation and saved output. The isolated checkout passed 73 Python tests, the canonical checkout passed 201, and the frontend panel check and production build passed. The pinned Slate request, three historical Reporting replays, 71 historical artifact hashes and five signed verifier hashes matched. The comparison used authored inputs and made zero model requests.

## Saved result verification

The read and download endpoint now verifies the saved archive identity, admitted and withheld claims, source excerpts, controls and presentation metadata against the current archive. Cloud-mode results must match the approved request digest. Existing reports can omit metadata introduced later. Successful checks return the original bytes, and invalid projections return HTTP 409 without rewriting the file or reopening an attempt. The console clears any previously displayed result when the read fails.

Before this change, all six altered finalized fixtures and the altered interrupted fallback in the initial batch were returned as HTTP 200. The updated tests cover those cases plus false custody status and a boolean substituted for a numeric count. A legacy selection remains byte-identical, and the original real Slate cloud result passed the same verification locally. This check establishes consistency with the current verified archive. Original model ranking, usage, historical audit identity and storage integrity still depend on the runtime record and its custody.

The isolated Python suite passed 83 tests and the canonical checkout passed 211, including admission, custody and guard regressions. The nine-variant corruption test set, legacy selected control and one-shot behavior are exercised by `python -B -m pytest -q -p no:cacheprovider tests/test_archived_reporting.py -k "modified_saved_report or legacy_selected_report_bytes or modified_recovery_report"`. Four saved Reporting evaluations, the Slate request digest, 71 historical artifact hashes and five signed-off verifier digests matched.
