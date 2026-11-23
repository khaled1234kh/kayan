# KAYAN session correlation and synthetic custody verification

20 November 2026 · Offline engineering report

Both session-candidate fixes passed. The separately versioned custody gate rejected all six classes of prohibited synthetic submissions. The original Windows and Slate demo retained its observed decisions. Real-telemetry feasibility remains **NO-GO** because this pass used an in-process synthetic authority. [Prior remediation and inherited limits](ATTACK_PROVENANCE_V1_P0_REMEDIATION_2026-11-20.md)

## Session-candidate fixes

The resolver previously used unconditional SID equality to discard records, including logons whose SID could not be resolved. It now excludes known incompatible identities or scope, checks time and generation, then treats an incomplete but still plausible logon as unresolved. It leaves every distinct input in contention. A duplicated reference or equal normalized fields supplies no verified original-source identity for deduplication. The result remains a candidate for review. [Resolver](../eval/attack_windows_event_normalizer_v1.py) · [Regression suite](../tests/test_attack_windows_event_normalizer_v1.py)

The previous SID regex checked token shape and digit count. The parser now requires revision 1, one to 15 unsigned 32-bit subauthorities, and the Windows string form for a 48-bit authority. Decimal authority is used below 2³². Larger authority values use 12 hex digits, with hex case normalized for comparison. Leading decimal zeros and the null SID cannot supply identity keys in this profile. Invalid values retain their source lexemes and diagnostics. [Microsoft SID string syntax](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/c92a27b1-c772-4fa7-a432-15df5f1b66a1) · [Microsoft SID structure](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/5cb97814-a1c2-4215-b7dc-76d1f4bfad01)

| Candidate or decoder control | Before | After |
| --- | --- | --- |
| One complete logon and same-scope in-window logon with unresolved SID | `candidate` for the complete logon, in either input order | `unresolved`, `plausible_logon_identity_unresolved`, in either order |
| Subauthority 4,294,967,296 in both XML inputs | Accepted as an identity key and could join | Key is null, raw value retained, `unresolved_sid`, no unique candidate |
| Known incompatible SID or logon token | Valid logon eligible as candidate | Valid logon eligible as candidate |
| Incomplete competitor outside known case, tenant, asset, generation or time boundaries | Valid logon eligible as candidate | Valid logon eligible as candidate |
| Repeated reference, overlapping times, future logon, outside permitted window, or no eligible logons | Unresolved where no unique eligible record remains | Same, including fail-closed behavior when duplicate inputs have equal reference and content |
| Valid SID boundaries | Decimal cases accepted. Hex authorities were excluded. | Decimal and hex limits and 15 subauthorities accepted. Zero or 16 subauthorities, incorrect revision, invalid authority range, noncanonical decimal and null SID withheld as identity keys. |

The first three regression cases ran before the code change. All three failed as expected. The final normalizer suite also checks the existing malformed XML, uncertain generation and time, identity isolation and exact field behavior.

## Synthetic custody gate

The separate offline entry point accepts proposal, manifest and payload bytes plus an authority object obtained independently by the caller. The fixture custodian issues that authority from known synthetic records. It binds assigned case, current snapshot digest, previous accepted snapshot digest, consecutive sequence, active assertion roster, exact assertion and receipt histories, authorized receipt digests and verification time. Rosters select the latest revision of each assertion. Retained histories include superseding assertions, withdrawals and revoked receipts. The gate checks exact current bindings and requires both previous histories to be contained in the current histories. It then calls the existing offline registry and adapter with the custodian's pin, approval set and time. [Custody gate](../eval/attack_evidence_custody_v1.py) · [Synthetic authority and regressions](../tests/test_attack_evidence_custody_v1.py)

| Synthetic submission or control | Unwrapped registry behavior or prior limitation | Custody outcome |
| --- | --- | --- |
| Authorized initial snapshot, complete proof | `all_eligible` | `all_eligible` |
| Authorized successor adds uncited applicable adverse assertion | `none_eligible` | `none_eligible`, `conflicting_or_superseded_evidence` |
| Remove that assertion and use a replacement pin with the original receipt allowlist | `all_eligible` | Invalid, `custody_assertion_roster_mismatch`, including when only the current pin is replaced |
| Missing, wrong, skipped or cross-case predecessor | Accepted the otherwise valid replacement under its supplied pin. Withholding from the adverse assertion alone still applied. | Invalid, `custody_missing_predecessor` or `custody_invalid_continuity` |
| Re-encode the same roster and revisions | Exact-pin checking depends on which pin was supplied | Invalid, `custody_snapshot_mismatch` |
| Replay previously accepted pre-adverse snapshot | `all_eligible` under its own pin | Invalid, `custody_rollback` |
| Omit revoked receipt revision | `all_eligible` after omission. With the revocation present, the registry invalidates the receipt. | Omission invalid, `custody_revision_history_mismatch` |
| Omit a withdrawal or superseding authorized assertion | `all_eligible` after omission. Each complete successor withholds the finding. | Omission invalid, `custody_assertion_roster_mismatch` |
| Repin and reissue a successor after erasing previously accepted history | Per-snapshot validation lacks continuity | Invalid, `custody_history_rewrite` |
| Give an older assessment time to honor expired receipts | `all_eligible` at the older caller time | Invalid at the fixture custodian's time with `untrusted, expired or stale review receipt`. The submission interface exposes no time override. |
| Submit a valid snapshot and receipts from another case | `all_eligible` under its own pin and assigned case | Invalid, `custody_case_mismatch`, under the original assigned case |
| Malformed manifest | Invalid | Invalid before review, `custody_invalid_snapshot` |

For every invalid result the gate emits zero review items. The combined regressions also cover the existing disputed identity, dependent collector ancestry, uncited contradiction and mixed-batch controls.

## Verification and reproduction

All final test invocations completed with zero failures and zero skips. The counts overlap.

| Command group | Passed |
| --- | ---: |
| Focused normalizer and synthetic custody | 65 |
| Provenance registry, normalizer and adapter | 120 |
| V3 and V4 historical guards | 48 |
| Combined offline and integrity suites | 228 |

Run from the repository root.

```powershell
python -B -m pytest tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_evidence_custody_v1.py -q -p no:cacheprovider
python -B -m pytest tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_fact_guard_adapter_v1.py -q -p no:cacheprovider
python -B -m pytest tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_guard_v4.py -q -p no:cacheprovider
python -B -m pytest tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_fact_guard_adapter_v1.py tests/test_attack_evidence_custody_v1.py tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_guard_v4.py tests/test_attack_experiment_d_v3.py tests/test_attack_experiment_d_integrity_v3.py tests/test_attack_evidence_v2.py -q -p no:cacheprovider
python -B -m eval.attack_experiment_d_integrity_v3 audit --prior-authorized-sha256 c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba
python -B -m eval.fixtures.ai.attack_fact_registry_v1.demo
@'
import re,hashlib
from pathlib import Path
p=Path('docs/ATTACK_TRUSTED_FACT_PROVENANCE_V1_RESULTS_2026-11-20.md')
rows=re.findall(r'\| `([^`]+)` \| `([0-9a-f]{64})` \| `([0-9a-f]{64})` \|',p.read_text(encoding='utf-8'))
bad=[f for f,a,b in rows if a!=b or hashlib.sha256(Path(f).read_bytes()).hexdigest()!=a]
assert len(rows)==71 and not bad, bad
print('71 of 71 historical SHA-256 digests matched')
'@ | python -B -
```

The pinned demo returned candidate `logon.xml`, Windows `all_eligible`, incomplete Windows `none_eligible`, and Slate `mixed`. The D revision 2 audit verified all 12 scheduled entries, the approved manifest digest and the saved revision 1 discrepancy. All 71 current historical SHA-256 values matched both recorded columns. [Historical inventory](ATTACK_TRUSTED_FACT_PROVENANCE_V1_RESULTS_2026-11-20.md#historical-integrity)

## Remaining operational and research gates

The custody API assumes a caller can independently obtain the latest externally maintained case assignment, current head, accepted predecessor, receipt approvals and reliable time. Its predecessor checks protect the supplied transition. It has no persistent head store or independently authenticated time service. Replacing or replaying the entire trusted authority object is outside the submission boundary and remains a custody-system responsibility. Complete fixture histories prove that this check detects omissions against the supplied reference. They supply no assurance that a real custodian captured every adverse assertion or that a real reviewer is independent.

**Real-telemetry feasibility remains NO-GO.** A later intake decision needs lawful data access, source custody, lineage and time attestations, independently enrolled and blinded reviewers, and authenticated persistent custody of case assignments, accepted heads and complete decision histories. The exposed synthetic data remains development material. [Research and independent review gates](ATTACK_PROVENANCE_V1_INDEPENDENT_REVIEW_2026-11-20.md#human-reviewed-feasibility-study-gates)
