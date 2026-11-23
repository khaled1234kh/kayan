# Archived Reporting selection replay

The frozen set contains 14 authored inputs over four synthetic archives. Each run exercises the Reporting API, an exact fixture grant, the real provider transport adapter with an in-memory HTTP response, and the saved export. The fixture pins each archive and request digest. Reproduce with `python -B -m eval.archived_reporting_selection`. [Frozen inputs and oracle](../eval/fixtures/ai/archived_reporting_selection_v1.json)

Seven valid replies were accepted. Six invalid or unavailable replies returned the exact local summary, recommendations and coverage. One archive had no admitted findings and made zero attempts. All 14 cases preserved the exact admitted findings and withheld claims. All 13 saved selection or fallback responses matched their downloads byte for byte.

The seven valid replies include deliberately reversed, partial and weak-relevance selections. Their order and source choices are scored against the same authored preference used for the local composer.

| Selection metric | Local composer | Authored replies |
| --- | ---: | ---: |
| Preferred excerpts among excerpts returned | 11/11 | 10/12 |
| Preferred excerpts recovered | 11/13 | 10/13 |
| Exact ordered excerpt lists | 5/7 | 4/7 |
| Correct order among comparable excerpt pairs | 4/4 | 3/4 |
| Preferred recommendations recovered | 14/14 | 13/14 |
| Exact ordered recommendation lists | 7/7 | 5/7 |

The saved summary and console now report admitted finding occurrences, occurrences cited by the summary and occurrences cited by an observed-action excerpt. These counts come from the final verified references. A partial fixture cites one of two occurrences, while the weak-relevance fixture cites both and includes zero observed-action excerpts. The counts describe presentation coverage. The verifier's complete findings remain in the report.

The corrected replay reproduced the baseline outcomes and selection scores with the new coverage metadata. The Slate request digest is intact. This replay measures adapter behavior and shows how to score relevance and ranking. It provides no estimate of local or live cloud model accuracy. [Baseline results](../eval/reports/archived_reporting_selection_v1_baseline.json) · [Results with coverage](../eval/reports/archived_reporting_selection_v1_after.json)
