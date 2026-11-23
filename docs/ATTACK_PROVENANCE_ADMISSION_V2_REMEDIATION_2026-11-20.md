# Offline evidence admission v2 sign-off remediation

20 November 2026 · Ready for an independent engineering rerun. Real-telemetry intake remains **NO-GO**. [Independent findings](ATTACK_PROVENANCE_ADMISSION_V2_SIGNOFF_2026-11-20.md)

## Corrections

**External ancestry.** Before the change, the issuer hashed a default-filled source row. An omitted `upstream` and an explicit empty array produced identical commitments. The independent review observed T1490 becoming eligible in this condition. This pass reproduced the digest equality before implementation. Issuance now checks explicit ancestry before creating commitments and evaluates the independent catalogue for conflicting aliases and unresolved parents. Uncertainty propagates to descendants. Malformed rows and inconsistent graphs fail validation. An explicit shared origin can be attested as declared and still contributes dependent evidence. On admission, the submitted row must also declare ancestry explicitly. [Issuer and verifier](../eval/attack_evidence_admission_v2.py) · [Lineage resolver](../eval/attack_fact_registry_v1.py)

The new `kayan.source-attestation/2` commitment binds the validated source row, case ID, exact snapshot digest, head sequence and predecessor digest. The evidence manifest still declares `kayan.offline-evidence/2` and the authority still carries a set of digests. Older source-only digests no longer satisfy the verifier. When bytes or head identity change, approvals must be reissued by the separate authority. The synthetic fixture defaults to a catalogue derived from the fixture. The new paired tests supply a distinct external catalogue. [Fixture issuer](../eval/fixtures/ai/attack_admission_v2.py)

**Process/session denials.** Before the change, a reviewed denial of a different session caused the same event-wide veto as a denial of the session on which the finding relied. This pass reproduced that result. Strict v2 projection now treats a scoped denial as unrelated when it names a distinct session under the same verified principal, authority and occurrence scope. An ambiguous denial remains a veto. A denial of the relied-upon association still withholds the claim. Competing affirmative links continue through the inherited v3/v4 check. [Scope and projection](../eval/attack_fact_guard_adapter_v1.py)

## Before and after

| Synthetic control | Before | After |
| --- | --- | --- |
| External backup ancestry omitted, submitted backup explicitly a root | Digest equality reproduced. Independent review observed both claims eligible. | `mixed`. T1486 eligible. T1490 withheld with `independent_attribution_missing`. |
| External backup root explicit, submitted backup ancestry omitted | Missing submitted ancestry already prevented independent attribution. | Same `mixed` result and reason as above. |
| Both catalogues explicitly declare separate roots | Both eligible. | `all_eligible`, both eligible in either row order. |
| Shared upstream, or external alias with conflicting ancestry | Shared upstream withheld T1490. The old external issuer did not check the alias graph. | `mixed`. T1486 eligible. T1490 withheld with `independent_attribution_missing` in both orders. |
| Source approvals from a different case, snapshot digest, sequence or predecessor | The old digest format covered the source row only. | `none_eligible`. Both claims have `independent_attribution_missing`. |
| Malformed external ancestry | New control. | Issuance raises a validation error. |
| Affirmative P7 → B19 | Both eligible. | Both eligible. |
| Same-session or ambiguous denial | Matching denial withheld T1486 in the independent review. | `mixed`. T1490 eligible. T1486 withheld with `conflicting_or_superseded_evidence`. A cited denial also adds `extraneous_citation`. |
| Denial of a distinct session with matched authority and principal | T1486 withheld with `conflicting_or_superseded_evidence`, T1490 eligible. | Both eligible when uncited. If cited, T1486 is withheld with `extraneous_citation` and `source_or_event_mismatch`. T1490 stays eligible. |
| Two incompatible affirmative links | T1486 withheld and T1490 eligible. | Same `mixed` result with `process_session_unverified` for T1486. Citing the competing link adds `extraneous_citation`. |

The denial matrix tests both assertion orders and cited and uncited forms. The ambiguous controls include missing association scope and a different authority whose session identity cannot safely be compared. The ancestry matrix includes separate catalogues, shared origin, transitive incomplete approvals, conflicting aliases and unaffected siblings. [Regression source](../tests/test_attack_evidence_admission_v2.py)

## Verification

- **31** new regressions passed. The focused selection deselected the original 54.
- **85** admission tests passed, including the original 54. The fixture calls were updated for the new commitment format. Original verdict expectations were retained.
- **313** combined tests passed, comprising 85 admission and 228 historical tests. Zero failures or skips.
- The original demo reproduced candidate `logon.xml`, Windows `all_eligible` with one item, missing-custody Windows `none_eligible` and Slate `mixed` with one item.
- Experiment D revision 2 validated 12 scheduled entries and digest `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1`. The revision 1 discrepancy remains recorded at byte offset 286.
- **71/71** unique historical SHA-256 digests matched both inventory columns. [Pinned demo and inventory commands](ATTACK_PROVENANCE_V1_P1_CUSTODY_2026-11-20.md#verification-and-reproduction)

Run from the repository root.

```powershell
python -B -m pytest -q -p no:cacheprovider tests/test_attack_evidence_admission_v2.py -k 'independent_catalogue or reused_for_another_head or malformed_external or denial_is_scoped'
python -B -m pytest -q -p no:cacheprovider tests/test_attack_evidence_admission_v2.py
python -B -m pytest -q -p no:cacheprovider tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_fact_guard_adapter_v1.py tests/test_attack_evidence_custody_v1.py tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_guard_v4.py tests/test_attack_experiment_d_v3.py tests/test_attack_experiment_d_integrity_v3.py tests/test_attack_evidence_v2.py tests/test_attack_evidence_admission_v2.py
python -B -m eval.fixtures.ai.attack_fact_registry_v1.demo
python -B -m eval.attack_experiment_d_integrity_v3 audit --prior-authorized-sha256 c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba
```

Commitments require an independently authenticated approval channel and a current custody head. The verifier still relies on the caller for authority freshness, reviewer authenticity, trusted time and catalogue completeness. The synthetic exercise verifies the offline checks. Real intake requires separately approved operational custody and human review. [Study prerequisites](ATTACK_PROVENANCE_ADMISSION_V2_SIGNOFF_2026-11-20.md#verification-and-disposition)
