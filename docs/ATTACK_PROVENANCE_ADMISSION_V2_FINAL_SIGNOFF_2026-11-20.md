# Final targeted engineering sign-off for evidence admission v2

20 November 2026 · Independent offline rerun

1. **Offline engineering verdict — PASS.** Both original counterexamples now give the required per-claim decisions. The defined positive, adverse and sibling controls passed. The rerun found no material failure within this bounded contract.
2. **Feasibility protocol preparation — GO.** Study design, privacy planning and synthetic rehearsals may proceed.
3. **Real-telemetry intake — NO-GO.** Operational approval requires lawful data-owner authorization, independently authenticated source lineage and current custody heads, complete adverse-decision and revocation records, trusted time, and independent human review and adjudication. Production use requires separate authorization.

## Decisive controls

I inspected the admission entry point, external issuer, lineage resolver, session applicability and custody checks. I reconstructed both original counterexamples in memory using the synthetic Slate fixture and the public v2 entry point, in addition to running the repository tests. [Prior sign-off](ATTACK_PROVENANCE_ADMISSION_V2_SIGNOFF_2026-11-20.md) · [Remediation](ATTACK_PROVENANCE_ADMISSION_V2_REMEDIATION_2026-11-20.md)

| Input change | Observed decision |
| --- | --- |
| All four roots explicitly declared and attested | Four commitments issued. T1486 and T1490 eligible. |
| Omit only the backup collector's ancestry in the external catalogue, keeping identical submitted bytes, pin, receipts and time | Three commitments issued. Only T1486 eligible. T1490 withheld with `independent_attribution_missing`. |
| Issue the complete catalogue's commitments for another case, snapshot digest, sequence or predecessor, changing one field at a time | Each commitment set was disjoint from the correct set. Neither claim qualified. Each had `independent_attribution_missing`. |
| P7 linked to B19, with an uncited denial for a verified distinct session | T1486 and T1490 eligible in both assertion orders. |
| Denial concerns B19, or the denied association has unknown scope | Only T1490 eligible. T1486 withheld with `conflicting_or_superseded_evidence` in both orders. |
| Competing affirmative association for the same P7 occurrence | Only T1490 eligible. T1486 withheld with `process_session_unverified` in both orders. |
| Proposal explicitly cites the distinct-session denial | The cited-denial regression withheld T1486 with `extraneous_citation` and `source_or_event_mismatch`. T1490 remained eligible. |

Issuance checks field presence and collector ancestry before creating a commitment. The verifier recomputes that commitment under the supplied current head. Shared upstreams, conflicting aliases and incomplete transitive approvals failed to establish independence in the regression suite. The session rule compares the scoped, reviewed relationship. Applicable uncited disputes still reach the guard. [Attestation contract](../eval/attack_evidence_admission_v2.py) · [Lineage resolver](../eval/attack_fact_registry_v1.py#L215) · [Session applicability](../eval/attack_fact_guard_adapter_v1.py#L18)

## Verification record

| Rerun | Observed |
| --- | ---: |
| New regressions only | 31 passed, 54 deselected |
| Complementary existing admission selection | 54 passed, 31 deselected |
| Historical offline selection | 228 passed |
| Joint invocation | **313 passed**, zero failures or skips |
| Historical digest inventory | **71/71** unique file paths matched both recorded SHA-256 columns |

The historical and admission runs included disputed identity, unsupported uncertainty fields, adverse and conflicting process/session evidence, collector dependence, current-head continuity, omissions, revocations and mixed-batch isolation. The pinned demo returned candidate `logon.xml`, Windows `all_eligible` with one review item, Windows missing the custody citation `none_eligible` with zero items, and Slate `mixed` with one item. The Experiment D revision 2 offline audit verified 12 scheduled entries, SHA-256 `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1`, and the retained revision 1 discrepancy at byte 286. All reported counts reproduced. [Test and audit commands](ATTACK_PROVENANCE_ADMISSION_V2_REMEDIATION_2026-11-20.md#verification) · [Digest command](ATTACK_PROVENANCE_V1_P1_CUSTODY_2026-11-20.md#verification-and-reproduction)

### Reviewed file identities

| File | SHA-256 of local bytes |
| --- | --- |
| `eval/attack_evidence_admission_v2.py` | `f69c16febd155c59d9caff5512b7500dd5a2c2aa723437340c7c31236584f9e0` |
| `eval/attack_fact_registry_v1.py` | `f326331b224c85b09f4684859e2668d6543eaa8235b7b4c714a57ecd7db932fb` |
| `eval/attack_fact_guard_adapter_v1.py` | `4f0389c2cd132d211883321915b9b211c630fc820cbdeb0c9f7173aa0340eeca` |
| `eval/attack_evidence_custody_v1.py` | `ae54a40132eab5e2c5d21504ea6dd859df21ca89772f0da256ca5abac0ebcb7d` |
| `eval/fixtures/ai/attack_admission_v2.py` | `a3aa3750343b083faa6c8ff8d84de45c818fe71cc24eace224df9be4bb29ac61` |

This sign-off applies to the offline v2 entry point with synthetic evidence and an independently supplied authority assumed current. The fixture exercises the logic under that assumption. Authenticating the authority and establishing the truth of a real source declaration remain operational responsibilities.
