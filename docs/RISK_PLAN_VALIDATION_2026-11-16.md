# Risk Plan and Option A validation

**November 16, 2026.** The evaluation calls `POST /planning/risk-plan` and `POST /planning/direct-mitigation` through the actual planning routes in an in-process test app. It evaluates applicability to fictional descriptions and consistency of the generated output. Phase 1 and Option A perform no model inference, authorization, target access or tool execution.

## Results

| Check | Baseline | Revised |
| --- | ---: | ---: |
| Exact scenario set, 32 targeted profiles | 19/32 | 32/32 |
| Full case pass, including expected gap labels and output integrity | 5/32 | 32/32 |
| Correct abstention on 17 negative profiles | 5/17 | 17/17 |
| Scenario predictions, TP / FP / FN | 16 / 12 / 1 | 17 / 0 / 0 |
| Scenario micro-F1 | 0.711 | 1.000 |
| Cases with output integrity defects | 27/32 | 0/32 |
| Supplemental wording check, 12 additional profiles | 10/12 on first check | 12/12 after two targeted fixes |

The primary fixture was labelled before running the baseline at `eb6d1f34aac11a5983995b76100ddd2684d6d681`. Cases were selected to expose likely failure modes and informed the changes. For the supplemental check, labels were written after the initial changes and before testing those profiles. Its 10/12 result (micro-F1 0.889) measures the first check on that wording. The 12/12 recheck is a regression result on known cases. The fixtures lack independent annotation and cannot estimate general accuracy.

- Some retired, prohibited, proposed or unrelated controls looked applicable on keyword overlap. Current checks suppress matching in many such descriptions and require co-occurrence within a clause for most scenario rules. A separate clause can still supply complementary recovery cues. This favors abstention and may miss facts split across clauses or expressed in unfamiliar language.
- A vendor-access match previously suppressed every shared-identity match, including independent internal accounts. Suppression is now local to the overlapping evidence. A gap can influence the ordering only when linked to the scenario evidence. The rank measures review relevance.
- Option A added a null legacy `priority` field to hypotheses. It now preserves the current Phase 1 representation. The test checks exact text offsets, pinned framework entries, consistent rankings, zero findings, and one evidence-linked recommendation per displayed hypothesis.
- The supplemental check preserved two failures before correction. A future cloud-storage question triggered a match, and the phrasing “backed up daily” with an unchecked restore went unrecognized. The recheck covers both and preserves the first outputs.

## Reproduce

From the project root, choose fresh output paths.

```powershell
python -B -m eval.planning_validity_eval --output tmp/planning-validity.json
python -B -m eval.planning_validity_eval --fixture eval/fixtures/planning_context_transfer.json --output tmp/planning-transfer.json
python -B -m pytest -q tests/test_contextual_planning.py tests/test_ta_alignment.py tests/test_planner_accuracy_eval.py
```

The focused Python run passed **32 tests**. The frontend TA-alignment rendering checks passed via `npm run check:ta-alignment` in `console/office`. Those checks do not establish browser acceptance.

[Primary fixture](../eval/fixtures/planning_context_validity.json) · [Baseline](../eval/reports/planning_validity_20261116/before.json) · [Recheck](../eval/reports/planning_validity_20261116/after.json) · [Supplemental fixture](../eval/fixtures/planning_context_transfer.json) · [First supplemental run](../eval/reports/planning_validity_20261116/transfer.json) · [Supplemental recheck](../eval/reports/planning_validity_20261116/transfer-recheck.json)

## What the plan establishes

Each supported hypothesis points to a statement in the profile and a pinned reference. The application records severity, impact, likelihood and mitigation urgency as unassessed. For a real organization, the asset or control owner must confirm the cited conditions and provide supporting records before any hypothesis becomes an assessed risk. For example, a recovery hypothesis should be checked against a dated restore record, the restored data’s integrity and the recovery objectives. A reference or an empty plan provides no assurance that a control works or that risk is absent.

The Qwen-driven Planner is a separate system. The historical 24/30 first-attempt and 26/30 post-correction scores remain the last recorded operational Planner results. Its grader tests passed, and no new model run was performed. A defensible model comparison can use a frozen, independently labelled offline review cohort and separately report exact decisions, unsupported claims, evidence links and abstentions. [Research and Planner results](RESEARCH_UPDATE.md)
