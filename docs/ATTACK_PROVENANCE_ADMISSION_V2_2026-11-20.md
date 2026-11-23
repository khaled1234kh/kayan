# KAYAN offline evidence admission v2

The description below records the initial implementation. The current commitment format and session-denial semantics are documented in the [sign-off remediation report](ATTACK_PROVENANCE_ADMISSION_V2_REMEDIATION_2026-11-20.md).

20 November 2026 · Synthetic verification

**The three admission corrections pass offline verification. Real-telemetry intake remains NO-GO.** Feasibility protocol preparation can proceed. Independent engineering sign-off and operational custody sign-off are separate prerequisites for a real-data decision. [Independent review](ATTACK_PROVENANCE_V1_POST_REMEDIATION_REVIEW_2026-11-20.md)

## Contract

The new entry point is `eval.attack_evidence_admission_v2.evaluate_in_custody(proposal, manifest_bytes, payloads, authority=...)`. The manifest declares `kayan.offline-evidence/2`. It retains the original record, assertion, receipt and citation formats. The schema marker participates in the full manifest pin and evidence digest. The caller supplies an `AdmissionAuthority` with assigned case, current head, predecessor, receipt allowlist, verification time and a frozen set of attested source-row digests. The source attestation digest uses the registry's canonical JSON SHA-256 of the complete validated `Source` row, including the attestation reference, collector, family and upstream IDs. Source approval comes from the separate authority channel. [Entry point](../eval/attack_evidence_admission_v2.py) · [Custody fields](../eval/attack_evidence_custody_v1.py)

- **Process/session.** `linked` is affirmative. It can supply proof only after the matching review receipt, statement references and scope pass verification. An applicable `unlinked` or `unresolved` active review becomes a veto in the scoped fact bank, including when the proposal omits its citation. Competing affirmative sessions still go through the existing v4/v3 linkage check. Unknown values invalidate the snapshot with the assertion ID and rejected value.
- **Uncertainty.** The supported keys are `tenant`, `asset`, `authority`, `principal`, `session`, `session_generation` and `time`. Unrecognized keys invalidate the snapshot with the event ID and unsupported keys. The exact submitted bytes retain the original keys, reasons and populated values for investigation. The diagnostic reports the keys without interpreting them. A canonical dispute withholds the affected claim.
- **Ancestry.** An explicit empty array declares a root. An explicit populated array declares upstream dependencies. An omitted declaration, a row outside the external attestation set, or a collector with conflicting alias declarations cannot establish independence. That status propagates to descendants. Overlapping families and shared upstreams still count as dependent even when every row is attested. Unknown referenced parents invalidate the snapshot. The existing guard withholds an affected claim with missing independent attribution and preserves an unaffected event.
- **Custody.** V2 compares the supplied bytes against the current pin before JSON parsing. An exact predecessor replay returns `custody_rollback`. Other mismatches return `custody_snapshot_mismatch`. A matching pin still requires assigned case, continuity, active roster and assertion and receipt histories, including retention of predecessor history. The change reduces parsing of mismatched bytes. No resource-exhaustion test was performed.

The v1 entry points retain the historical implicit-root convention and custody reason ordering. The v4 and v3 guard files and pinned v1 fixture files retain their original contents. V2 uses a separate synthetic Slate fixture issuer and the existing guard. The result still exposes per-claim dispositions and explicit batch state. [V2 fixtures](../eval/fixtures/ai/attack_admission_v2.py) · [Regression suite](../tests/test_attack_evidence_admission_v2.py)

## Reproduction and verdict matrix

Before editing implementation, I ran the boundaries identified in the independent review. The v1 assertion schema accepted `linked`, `unlinked` and `unresolved` for the same process/session role. The inherited linkage predicate used the role, process and session and ignored the value. On the Windows fixture, the v1 applicability check returned `unknown` for `session_generation` and `principal`, and `match` for `generation` and `identity`. The v1 lineage resolver returned resolved for both omitted and explicit empty upstream lists. These before measurements were admission and applicability checks. The after column gives executed end-to-end results under synthetic custody.

| Control or adverse condition | V2 outcome and exact reasons |
| --- | --- |
| Reviewed `linked` assertion with correct process and session | `all_eligible`, T1486 and T1490. |
| Matching positive link plus `unlinked` or `unresolved` review on that process | `mixed`, T1490 eligible. T1486 has `conflicting_or_superseded_evidence`. Add `extraneous_citation` when the adverse citation is supplied. Tested in both orderings. |
| Sole `unlinked` or `unresolved` association | `mixed`, T1490 eligible. T1486 has `conflicting_or_superseded_evidence` and `process_session_unverified`. |
| Two reviewed affirmative links naming different sessions | `mixed`, T1490 eligible. T1486 has `process_session_unverified`, plus `extraneous_citation` if the contradictory cite is supplied. Tested in both orderings. |
| Negative association concerns another process | Both claims eligible when the irrelevant citation is omitted. If cited, T1486 is withheld with `extraneous_citation` and `source_or_event_mismatch`. T1490 stays eligible. Tested in both orderings. |
| Unknown process/session value `unspecified` | `invalid`, zero review items. Diagnostic names `link` and its unsupported value. |
| Canonical `session_generation` or `principal` dispute | `mixed`, T1490 eligible. T1486 has `ambiguous_or_missing_action` and `mechanic_or_objective_unverified` in both orderings. |
| Unsupported `generation` or `identity` key | `invalid`, zero review items, with event and key diagnostic in both orderings. This is a snapshot-level schema rejection. |
| Explicit attested separate roots or attested separate upstream | `all_eligible`, both claims eligible. |
| Omitted ancestry, missing approval of explicit root or parent, changed attestation reference, shared family, shared upstream, conflicting alias or incomplete alias | `mixed`, T1486 eligible. T1490 has `independent_attribution_missing`. Each variation was tested in both source orderings. |
| Unknown upstream ID | `invalid`, `invalid upstream lineage`, zero review items. |
| Empty external source attestation set | `none_eligible`, both claims have `independent_attribution_missing`. |
| Exact pin for v1 schema or a trusted snapshot carrying suggestion rows | `invalid`, `custody_invalid_snapshot`, zero review items. |
| Attested source with no external receipt approvals | `invalid`, `untrusted, expired or stale review receipt`, zero review items. |
| Trailing-space mutation against current pin | `invalid`, `custody_snapshot_mismatch`. Parser sentinel verified parsing was skipped. |
| Same bytes as predecessor, with either the old pin or a claimed new head | `invalid`, `custody_rollback`. |
| Independently repinned equivalent successor with complete history | `all_eligible`, both claims eligible. |
| Independently repinned successor omits a prior assertion and receipt | `invalid`, `custody_history_rewrite`, zero review items. |

## Verification

The final focused suite passed **54** and the historical suite passed **228**. The joint suite passed **282**, with zero failures or skips. The first focused run returned 48 passes and one incorrect test expectation for the empty-attestation control. The fixture's cited statement still supported authorization, so the exact withheld reason was only `independent_attribution_missing`. The test expectation was corrected. Additional positive and negative controls were then added.

Run from the repository root.

```powershell
python -B -m pytest -q -p no:cacheprovider tests/test_attack_evidence_admission_v2.py
python -B -m pytest -q -p no:cacheprovider tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_fact_guard_adapter_v1.py tests/test_attack_evidence_custody_v1.py tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_guard_v4.py tests/test_attack_experiment_d_v3.py tests/test_attack_experiment_d_integrity_v3.py tests/test_attack_evidence_v2.py
python -B -m eval.fixtures.ai.attack_fact_registry_v1.demo
python -B -m eval.attack_experiment_d_integrity_v3 audit --prior-authorized-sha256 c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba
```

Append `tests/test_attack_evidence_admission_v2.py` to the historical suite command for the joint run. The pinned demo returned candidate `logon.xml`, Windows `all_eligible` (1 item), Windows with the custody citation omitted `none_eligible` (0) and Slate `mixed` (1). The D audit verified 12 scheduled requests, revision 2 SHA-256 `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1` and the preserved revision 1 discrepancy at byte offset 286. All **71 unique historical paths** matched both inventory digest columns using the [existing reproduction script](ATTACK_PROVENANCE_V1_P1_CUSTODY_2026-11-20.md#verification-and-reproduction).

## Operational dependencies

An approved digest establishes integrity relative to an external trust decision. The fixture issuer establishes no independent collection origin, human reviewer identity, semantic validity or time authority. A study still needs lawful data-owner permission and privacy controls, authenticated independent acquisition and lineage, a persistent current-head and assignment service, a completeness ledger for adverse evidence and revocation, externally controlled time and reviewer receipt issuance, and blinded independent review with adjudication. Apply the existing feasibility and stop criteria. [Study gates](ATTACK_PROVENANCE_V1_POST_REMEDIATION_REVIEW_2026-11-20.md#gates-for-a-feasibility-study)

Historical ATT&CK grounding results retain their exploratory status. Experiment A recovered six technique IDs and zero complete evidence groups. B/C produced zero of four complete positive groups. Experiment D remained at zero of three in both conditions. This engineering pass provides no new grounding accuracy measurement. [Post-diagnostic review](ATTACK_POST_DIAGNOSTIC_ARCHITECTURE_REVIEW_2026-11-20.md)
