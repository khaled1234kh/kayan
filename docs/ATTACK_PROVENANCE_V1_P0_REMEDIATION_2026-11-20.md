# Offline provenance v1 P0 remediation

20 November 2026 · Synthetic verification

The three confirmed finding-level defects now withhold the affected claims. A complete, consistent finding still qualifies for analyst review. Real-telemetry feasibility remains **NO-GO** pending the two session-candidate fixes and independently controlled study intake. [Independent review and initial reproductions](ATTACK_PROVENANCE_V1_INDEPENDENT_REVIEW_2026-11-20.md)

## Root causes and verdicts

| Fixture variation | Before | After |
| --- | --- | --- |
| Windows P7 with only the reviewed binding to the event session | `all_eligible` | `all_eligible` |
| Same Windows claim with a second reviewed P7 binding to session `0x99` | `all_eligible` | `none_eligible`. V4 and the adapter return `process_session_unverified`. |
| Slate conflict on the encryption process with a separate eligible recovery claim | `all_eligible` when the conflict cite was omitted. With a separate conflict cite the old adapter returned `mixed` but only reported missing or extraneous citation evidence for encryption. | `mixed` in either order, with or without the conflict citation. T1486 is withheld with `process_session_unverified`. A separately cited conflicting link also gives `extraneous_citation`. T1490 remains eligible. |
| Windows custody source shares the audit origin | `none_eligible` | `none_eligible`, including through a transitive relay. |
| Move the custody record to an alias of the same custody collector that omits its parent | `all_eligible` | `none_eligible`, with `independent_attribution_missing`, `source_or_event_mismatch` and `extraneous_citation`. An unrelated, independently sourced sibling stays eligible in the Slate regression. |
| Windows event with a populated but explicitly disputed principal, authority, session or generation | `all_eligible` | `none_eligible`, with `ambiguous_or_missing_action` and `mechanic_or_objective_unverified`. |
| Windows event with a populated but explicitly disputed time | `all_eligible` | `none_eligible`, with `authorization_unverified`, `extraneous_citation` and `source_or_event_mismatch`. |
| Complete Windows disclosure with separate custody and authority evidence | `all_eligible` | `all_eligible`. |

The adapter had matched the whole assertion scope before projection, dropping the competing session and then substituting the event session on projected facts. Process-link review now uses the same reviewed case, event, tenant, asset, generation and process. The adapter preserves reviewed session values for the unchanged v4 conflict check. Bindings for another event, host, tenant, generation or process leave the positive control eligible. An explicitly disputed field is treated as unknown in scope or time applicability, while its candidate value remains in the approved snapshot for investigation. [Adapter](../eval/attack_fact_guard_adapter_v1.py)

The registry previously resolved upstream ancestry per source alias. It now canonicalizes upstream IDs to collector identities and checks agreement among the aliases of each collector. Disagreeing or incomplete alias ancestry disqualifies the source and its descendants from proving independence. All declared edges still participate in missing-parent and cycle checks. The proof can be withheld at claim level while evidence and its lineage remain inspectable. Explicit roots declared in the trusted catalogue still require independent custody verification outside the prototype. [Registry](../eval/attack_fact_registry_v1.py)

The synthetic issuer separately pins and receipts each variation. The new suite constructs the reported Windows and transitive alias cases, tests reversed assertion or source ordering, and observes both guard and adapter verdicts for the separate Slate sibling. [Deterministic regressions](../tests/test_attack_fact_guard_adapter_v1.py)

## Verification

Before implementation, the first 19 new cases reproduced 17 failures and passed two consistent-ancestry controls. After correction the final focused selection, including the exact Windows P7 case, passed **20 tests**. Each final suite below reported zero failures and zero skips. The 187 total includes the smaller suites.

| Suite | Passed |
| --- | ---: |
| New P0 selection | 20 |
| Registry, normalizer and adapter | 94 |
| Historical v3 and v4 guards | 48 |
| Combined offline evaluation and integrity | 187 |

Running the adapter tests first exposed a pre-existing test-isolation issue. A negative test mutated the fixture issuer's shared scope dictionary. The test now mutates a deep copy. The original pinned demo runs successfully, and the suite passes in that order.

```powershell
python -B -m pytest tests/test_attack_fact_guard_adapter_v1.py -k 'conflicting_reviewed or alias_ancestry or disputed_lineage or explicit_dispute or windows_p7' -q -p no:cacheprovider
python -B -m pytest tests/test_attack_fact_guard_adapter_v1.py tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py -q -p no:cacheprovider
python -B -m pytest tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_guard_v4.py -q -p no:cacheprovider
python -B -m pytest tests/test_attack_fact_guard_adapter_v1.py tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_guard_v4.py tests/test_attack_experiment_d_v3.py tests/test_attack_experiment_d_integrity_v3.py tests/test_attack_evidence_v2.py -q -p no:cacheprovider
python -B -m eval.attack_experiment_d_integrity_v3 audit --prior-authorized-sha256 c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba
python -B -m eval.fixtures.ai.attack_fact_registry_v1.demo
```

The original demo returned session candidate `logon.xml`, Windows `all_eligible`, missing-custody Windows `none_eligible` and Slate `mixed`. The revision 2 audit passed, including the 12 scheduled entries and the saved revision 1 discrepancy at byte offset 286. All **71 of 71 historical file digests** matched both columns of the retained inventory. [Full historical SHA-256 inventory](ATTACK_TRUSTED_FACT_PROVENANCE_V1_RESULTS_2026-11-20.md#historical-integrity)

## P1 regressions proposed for separate approval

- An in-window logon with the same supplied scope and native token but an unresolved SID can be dropped, making another logon appear unique. Use the fixture's valid logon plus an incomplete competitor. Expect unresolved. Use a competitor with a known incompatible SID as the negative control and expect the otherwise valid candidate. Compare compatibility before treating a missing identity as exclusion. Deduplicate only against verified source identity.
- A SID with an out-of-range subauthority remains usable. Put the same out-of-range SID in both XML fixtures. Expect an unresolved normalized SID with the raw value retained and no candidate. Test the supported SID component boundaries and a valid fixture control. Parse and check revision, authority, subauthority count and numeric ranges. Both fixes concern candidate correlation.

## Remaining custody gate and next decision

An intact full snapshot pin rejects adverse-row removal. A replacement pin can admit a snapshot missing an adverse assertion while the original receipt allowlist is still sufficient for its surviving assertions. The current receipt checks verify membership and binding for active rows present in the selected snapshot. Evidence completeness across snapshots requires an independently controlled active-assertion roster, previous snapshot head digest, complete withdrawal and revocation history, a trusted verification time and a binding from the assigned case to its expected snapshot. The independent custodian must reject rollback, wrong-case inputs and dropped adverse heads before analyst review. [Confirmed omission comparison and study gates](ATTACK_PROVENANCE_V1_INDEPENDENT_REVIEW_2026-11-20.md#root-of-trust-and-revision-review)

The next separately authorized step should be a bounded offline P1 pass covering the two candidate defects and a synthetic custody dry run for the controls above. Require successful negative and positive controls and repeat the historical audit. Real intake requires a separate decision after the independent source-custody and review gates pass.
