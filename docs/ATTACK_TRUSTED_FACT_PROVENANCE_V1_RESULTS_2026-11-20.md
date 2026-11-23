# KAYAN offline fact provenance v1 implementation

20 November 2026 · Synthetic acceptance results

The offline prototype connects pinned Windows XML and reviewed fixture evidence to the existing v4 guard. It emits the disposition and supporting provenance for each technique. A session candidate from telemetry remains a separate output. The approved design and documented source profiles are the reference for the implementation. [Provenance proposal and source documentation](ATTACK_TRUSTED_FACT_PROVENANCE_V1_PROPOSAL_2026-11-20.md)

## Implementation and trust boundary

| Module | Interface and responsibility |
| --- | --- |
| [Fact registry](../eval/attack_fact_registry_v1.py) | `verify(manifest_bytes, payloads, expected_sha256=…, approved_receipts=…, at=…)` checks exact snapshot and payload bytes, immutable record and review chains, source lineage, record and statement references, active assertions and receipts. The separate `parse_suggestions` interface returns unverified suggestion records for inspection. |
| [Windows normalizer](../eval/attack_windows_event_normalizer_v1.py) | `normalize_observation` validates saved UTF-8 XML for Security 1102 v0 and 4624 v2. It returns decoded source values, namespace-aware locators, integer UTC nanoseconds, timestamp precision and unsupported-profile diagnostics. `session_candidate` compares caller-scoped observations and provides an unresolved result unless a single candidate meets the identity, generation and interval rules. |
| [V4 adapter](../eval/attack_fact_guard_adapter_v1.py) | `evaluate` verifies the pinned case before projection, checks scoped roles, resolves origin families and passes active adverse evidence even when uncited. It validates the emitted claim partition before creating individual review items. |

The threat model covers substitution of record or manifest bytes, locator and revision drift, reviewer impersonation through incoming fields, relays that duplicate upstream evidence, scope collisions, untrusted suggestions and downstream misuse of a mixed result. The trusted offline caller supplies the manifest hash, external reviewer-to-receipt digest allowlist, verification time and exact observation payloads. A receipt digest binds reviewed input version, reviewer, exact assertion, decision, rationale and validity period. Fixture approvals come from a synthetic test issuer and pinned files. In real intake the caller would need a separate authenticated channel for approvals, lineage catalogue, trusted time and active snapshot selection. Accepting these inputs from the same untrusted producer would defeat the boundary.

The case manifest binds record ID and revision to a native locator, source, byte length and hash. A statement binds to one exact record revision and uses a text byte span or namespace-aware XML locator. Assertions carry event revision, role, scope, applicable interval and review receipt. The resolver retains earlier revisions for audit, checks active heads and fails verification when active review refers to stale evidence or a revoked, expired or unenrolled receipt. A reviewed withdrawal projects an event-scoped veto. Source lineage uses canonical collector family and transitive upstream origins. Attribution cannot count as independent when its support overlaps an action's lineage or exact record digest.

The parser rejects unsafe XML, imposes byte and depth bounds, validates required unique fields and retains unsupported profiles with a diagnostic. It preserves lexical source field values after XML decoding along with the original bytes. The session candidate compares 1102 subject fields with 4624 target fields, using explicit case, tenant, asset, authority and session generation. The fixture's reviewed clock bounds are caller inputs. Its XML timestamp precision does not verify clock accuracy or session lifetime. Claimed authorization applies only when the event's full possible time interval and identity/action scope fit a reviewed decision. An absent or disjoint grant supplies no affirmative evidence of unauthorized action.

The adapter projects one primary citation per reviewed assertion because v4 uses a flat proposal. An admitted item attaches every statement in the corresponding reviewed assertion and the exact event record, receipt and evidence revisions. A companion reference remains review provenance. The adapter does not implement a new multi-occurrence or independent alternative-group claim grammar. It checks applicable adverse evidence at event scope before it emits eligibility. Its explicit batch states are `all_eligible`, `mixed`, `none_eligible`, `abstained` and `invalid`. The `review_items` list is the set a consumer can forward for analyst review.

## Reproduced demo and behavior

Run from the repository root.

```powershell
python -B -m eval.fixtures.ai.attack_fact_registry_v1.demo
```

The demo verifies the pinned Windows manifest and original XML bytes before using the normalized fields. The XML retains the 1102 subject SID, the 4624 target SID and the distinct logon ID lexemes `0x55cd1d` and `0x0055CD1D`. They resolve to the same native token in the fixture scope. Both timestamps retain their nine fractional digits. The result identifies `logon.xml` as a candidate. The fixture's independently sourced custody narrative and separate denial-of-permission record supply the reviewed attribution and authorization, with review receipts and exact source references in the JSON trace. Physical operator identity, operational collector independence and real organizational authority remain unknown outside those fixture assumptions. [Fixture and demo](../eval/fixtures/ai/attack_fact_registry_v1/demo.py)

| Input | V4 behavior | Prototype output observed |
| --- | --- | --- |
| Reviewed Windows action, custody and authorization | Eligible given a complete reviewed fact bank | `all_eligible`. T1685.005 eligible for analyst review with E1.1, E2.1 and E3.1, plus the source-bound companion logon statement in its trace. |
| Same pinned Windows bank, custody cite omitted | Claim withheld | `none_eligible`. T1685.005 withheld with `independent_attribution_missing`. |
| Two complete individually reviewed slate events | Both eligible, including the two reviewed uses of E1.1 | `all_eligible` in regression tests. Each eligible item has its own event receipt and the shared exact statement. |
| Slate recovery missing attribution | Batch status eligible because encryption passes. Recovery appears in the rejection map | `mixed`. Review items contain only T1486. T1490 remains withheld with `independent_attribution_missing`. |

The v4 verdict rules are preserved. Changes in prototype outcomes arise from its stricter input admission and the explicit per-claim result contract.

## Acceptance evidence

| Area | Verified outcome |
| --- | --- |
| Byte integrity, schema and references | Tampered bytes, missing records, unsupported schema, duplicate identifiers, bad digests, invalid text spans and wrong XML selectors failed verification. |
| XML and session candidates | DTD, malformed XML, excessive length or depth, duplicate required fields and wrong profile headers were rejected. Unsupported versions retained a diagnostic and could not anchor an eligible claim. Same-name users across tenants, mismatched hosts/SIDs, reused tokens across generations, missing clock/generation and competing matches stayed unresolved. |
| Time, authorization and outcome | Reversed, overlapping and out-of-window candidates stayed unresolved. Unknown, disjoint or partially matching authority failed to establish unauthorized action. Authorized, failed, unresolved and zero-support cases were withheld. |
| Lineage, review and revision | Duplicate collector aliases and relays could not supply independent attribution. Broken lineage, stale/invalid/expired/unenrolled/revoked receipts, superseded observations and injected review fields failed closed. |
| Scoped contradiction and sharing | An uncited applicable veto withheld its event while a separate event stayed eligible. A newer reviewed withdrawal superseded its predecessor. The same source statement legitimately supported two events through separate reviewed associations. |
| Proposal boundary and disposition accounting | Empty valid proposals abstained. Malformed or duplicate envelopes and inconsistent v4 partitions were invalid. A mixed batch emitted exactly one eligible item in the fixture. Unverified suggestions had no trusted projection. |

**Focused suites** 74 passed, 0 failed, 0 skipped. **Combined offline suites** 167 passed, 0 failed, 0 skipped. The combined count includes the focused suites and original v3/v4 guard, v2 scoring, D materialization and D integrity tests. The revision 2 audit passed and reported exactly 12 frozen entries. The saved mismatched revision 1 and its failed preflight evidence remain preserved.

```powershell
python -B -m pytest tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_fact_guard_adapter_v1.py -q -p no:cacheprovider
python -B -m pytest tests/test_attack_fact_registry_v1.py tests/test_attack_windows_event_normalizer_v1.py tests/test_attack_fact_guard_adapter_v1.py tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_guard_v4.py tests/test_attack_experiment_d_v3.py tests/test_attack_experiment_d_integrity_v3.py tests/test_attack_evidence_v2.py -q -p no:cacheprovider
python -B -m eval.attack_experiment_d_integrity_v3 audit --prior-authorized-sha256 c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba
```

## Historical integrity

Compared SHA-256 of 71 pre-existing research files and retained artifacts before and after the change. The inventory covers both historical guards, the scorer, registered experiment sources and fixtures, research reports, manifests, and archived v2/A/B/C/D results and ledgers. All 71 exact digests matched.

<details>
<summary>Before and after SHA-256 inventory</summary>

| Path | SHA-256 before | SHA-256 after |
| --- | --- | --- |
| `.build/attack_diagnostics_v3_a/attempts.jsonl` | `4e7cb6d9fcdbb33f7dc02cef39c4449c50a358034759012666a1f79195bc7202` | `4e7cb6d9fcdbb33f7dc02cef39c4449c50a358034759012666a1f79195bc7202` |
| `.build/attack_diagnostics_v3_a/authorization.json` | `406731d1ff1ce48a8a4932fa25201967d80f88f646c096b2829e6d0315ab92c0` | `406731d1ff1ce48a8a4932fa25201967d80f88f646c096b2829e6d0315ab92c0` |
| `.build/attack_diagnostics_v3_a/comparison.json` | `634bc5b4b350dd00311a8a6e5266b8358c43a0c2a862e442174c79a22de34370` | `634bc5b4b350dd00311a8a6e5266b8358c43a0c2a862e442174c79a22de34370` |
| `.build/attack_diagnostics_v3_a/completion.json` | `397b51d1708d914802a9debde5453f0e9ddb2b2e5683c0b65320f27b292c80e8` | `397b51d1708d914802a9debde5453f0e9ddb2b2e5683c0b65320f27b292c80e8` |
| `.build/attack_diagnostics_v3_bc/attempts.jsonl` | `ee6f93be1ee6eeff03a730f148fdd7b6c1266bec02b514098d866a6cce88861f` | `ee6f93be1ee6eeff03a730f148fdd7b6c1266bec02b514098d866a6cce88861f` |
| `.build/attack_diagnostics_v3_bc/authorization.json` | `f1c0c86409238da59a0a33ff9366b05f5ae5bf7c7dc98df72f637723647d3354` | `f1c0c86409238da59a0a33ff9366b05f5ae5bf7c7dc98df72f637723647d3354` |
| `.build/attack_diagnostics_v3_bc/completion.json` | `0258a37149c8f7af42cc62f2c92626e5bc5febc554d81712c24271de739a3d4a` | `0258a37149c8f7af42cc62f2c92626e5bc5febc554d81712c24271de739a3d4a` |
| `.build/attack_diagnostics_v3_d/attempts.jsonl` | `ac6e45d1df1c5c44dab71575740fb439af6cd9e8ad7883046c8ec3909126dd20` | `ac6e45d1df1c5c44dab71575740fb439af6cd9e8ad7883046c8ec3909126dd20` |
| `.build/attack_diagnostics_v3_d/authorization.json` | `2dfc2e307dc3df75c7bf66f8bc96225fe8d1aae48475a7a2d0e6846f35fbe5ce` | `2dfc2e307dc3df75c7bf66f8bc96225fe8d1aae48475a7a2d0e6846f35fbe5ce` |
| `.build/attack_diagnostics_v3_d/completion.json` | `097210a292bb201e48f4accf54b2dd6942bd28c3a6ca366753e968e88436bbce` | `097210a292bb201e48f4accf54b2dd6942bd28c3a6ca366753e968e88436bbce` |
| `.build/attack_exploratory_v2/resources.jsonl` | `2a7cab6d7701bdd59f8b87dd4eb62a2155442bdb0be2eae6598aa74ad78cca97` | `2a7cab6d7701bdd59f8b87dd4eb62a2155442bdb0be2eae6598aa74ad78cca97` |
| `.build/attack_exploratory_v2/run/attempts.jsonl` | `3fde89e782aa4c753aabb5b9604ed2d0ea56f90ca6fc6587bc95efca537214ca` | `3fde89e782aa4c753aabb5b9604ed2d0ea56f90ca6fc6587bc95efca537214ca` |
| `.build/attack_exploratory_v2/run/results.json` | `d193412c182f84477a595b229b64b1b117474ebb8b887666c96bd948a72d38d5` | `d193412c182f84477a595b229b64b1b117474ebb8b887666c96bd948a72d38d5` |
| `.build/attack_exploratory_v2/run/run-lock.json` | `5b8106a4e86d14f1e7a35fc7f65a14eeef95d2f68a087509d4ee4435622b2923` | `5b8106a4e86d14f1e7a35fc7f65a14eeef95d2f68a087509d4ee4435622b2923` |
| `.build/attack_exploratory_v2/runner.log` | `2b5face21a3bf4bb43939bdbd308aed79a71c893ca61a0b513f1e6f1d9deac58` | `2b5face21a3bf4bb43939bdbd308aed79a71c893ca61a0b513f1e6f1d9deac58` |
| `.build/attack_exploratory_v2/stakeholder-authorization.json` | `1034705f667a887ae34c5f7f8b88dece6ed09899fa516ccdd0829fa481c2381e` | `1034705f667a887ae34c5f7f8b88dece6ed09899fa516ccdd0829fa481c2381e` |
| `docs/ATTACK_BLINDED_REVIEWER_INSTRUCTIONS.md` | `d0ee1ebb2169bbca051a66c34ccbb14f225bbf92e70a3dc0a6efffa2f461aee6` | `d0ee1ebb2169bbca051a66c34ccbb14f225bbf92e70a3dc0a6efffa2f461aee6` |
| `docs/ATTACK_CONFIRMATION_HANDOFF_2026-11-20.md` | `2aad1bbbee477aefb2d71eb3e8b734c82ebb51f0949dffe40eee2645d5023399` | `2aad1bbbee477aefb2d71eb3e8b734c82ebb51f0949dffe40eee2645d5023399` |
| `docs/ATTACK_DIAGNOSTIC_A_RESULTS_V3_2026-11-20.md` | `1b9560bca81cf776e4606f7377d8daab8c322c6ecaad3982828761220c4e9761` | `1b9560bca81cf776e4606f7377d8daab8c322c6ecaad3982828761220c4e9761` |
| `docs/ATTACK_DIAGNOSTIC_BC_PREPARATION_V3_2026-11-20.md` | `341737b044d2ec0abaeffdaf606e4ef0c49ae5fef748f22c3661ddfbbc130288` | `341737b044d2ec0abaeffdaf606e4ef0c49ae5fef748f22c3661ddfbbc130288` |
| `docs/ATTACK_DIAGNOSTIC_BC_RESULTS_V3_2026-11-20.md` | `a51be2778513dfd0f6c382c47299c4b1a14fa78de30530d3bd1bdb9fc29ad35c` | `a51be2778513dfd0f6c382c47299c4b1a14fa78de30530d3bd1bdb9fc29ad35c` |
| `docs/ATTACK_DIAGNOSTIC_D_INTEGRITY_V3_2026-11-20.md` | `9e099fd8ad5980167397dc84cc93371456ff2a704d57b596e4c2108b1b3dffb6` | `9e099fd8ad5980167397dc84cc93371456ff2a704d57b596e4c2108b1b3dffb6` |
| `docs/ATTACK_DIAGNOSTIC_D_PREPARATION_V3_2026-11-20.md` | `e619fb9a5e098c60fbbacfed2a0437706c873ccb70479f1fdacc3339712738b1` | `e619fb9a5e098c60fbbacfed2a0437706c873ccb70479f1fdacc3339712738b1` |
| `docs/ATTACK_DIAGNOSTIC_D_RESULTS_V3_2026-11-20.md` | `0892c3896926a3271ae6b46ad38cc5e971d00cea283a6118b0bbc32d4ddf4350` | `0892c3896926a3271ae6b46ad38cc5e971d00cea283a6118b0bbc32d4ddf4350` |
| `docs/ATTACK_DIAGNOSTIC_PROTOCOL_V3_2026-11-20.md` | `29a41fb4a57e222a16e565ef4bc090a66a7a9761a37ad739e742b14a9ec90d14` | `29a41fb4a57e222a16e565ef4bc090a66a7a9761a37ad739e742b14a9ec90d14` |
| `docs/ATTACK_EVIDENCE_EXPERIMENT_V2_2026-11-20.md` | `0dac2ce448191c7fc9b07c0723298f909db38423709b48919973813a8a7f9802` | `0dac2ce448191c7fc9b07c0723298f909db38423709b48919973813a8a7f9802` |
| `docs/ATTACK_EVIDENCE_GUARD_V4_2026-11-20.md` | `357077807f915e41ff6ebcc4cc90c43ce4a78ce2976d31782cb905344a65398c` | `357077807f915e41ff6ebcc4cc90c43ce4a78ce2976d31782cb905344a65398c` |
| `docs/ATTACK_EXPLORATORY_V2_RESULTS_2026-11-20.md` | `40242fdff0959b3e21c50e8654793a33bf6fa17c9332c87315aadb906a18bfaa` | `40242fdff0959b3e21c50e8654793a33bf6fa17c9332c87315aadb906a18bfaa` |
| `docs/ATTACK_LABEL_REVIEW_AND_CONFIRMATION_2026-11-20.md` | `3d146d12cdff3df559e9659d9bf38231acf215f1b456869ca9c656d71e6f85cc` | `3d146d12cdff3df559e9659d9bf38231acf215f1b456869ca9c656d71e6f85cc` |
| `docs/ATTACK_MAPPING_ABLATION_2026-11-20.md` | `a51e74693ddfcd8a3248dc0615f1017872f95f239999b88e90b403d02523879f` | `a51e74693ddfcd8a3248dc0615f1017872f95f239999b88e90b403d02523879f` |
| `docs/ATTACK_POST_DIAGNOSTIC_ARCHITECTURE_REVIEW_2026-11-20.md` | `184d9580296b13f8f45445a6e81c7a5a68c8784e24b6764c08ea177ff25e55cd` | `184d9580296b13f8f45445a6e81c7a5a68c8784e24b6764c08ea177ff25e55cd` |
| `docs/ATTACK_PROFESSIONAL_RESEARCH_REVIEW_2026-11-20.md` | `b944e6d42dc2fda3b356255584e5c54f186c46cd1d2630283b618a0b1c934fd5` | `b944e6d42dc2fda3b356255584e5c54f186c46cd1d2630283b618a0b1c934fd5` |
| `docs/ATTACK_RESEARCH_CORRECTIVE_ACTIONS_2026-11-20.md` | `fffec2142363f87d2b424447ca7d3f49219a6ee4fdfcd1a06da905a0c3eeb148` | `fffec2142363f87d2b424447ca7d3f49219a6ee4fdfcd1a06da905a0c3eeb148` |
| `docs/ATTACK_RESEARCH_VALIDITY_2026-11-20.md` | `8ae28978c1ddae3259ef9079cccfce3e788b333845246411f6b3571e40945541` | `8ae28978c1ddae3259ef9079cccfce3e788b333845246411f6b3571e40945541` |
| `docs/ATTACK_RETRIEVAL_AND_EVIDENCE_MAPPING_2026-11-20.md` | `9e301bc4e89c3e58a73b262d07a29024d0e607b628dafac2a1a061ee760ae03a` | `9e301bc4e89c3e58a73b262d07a29024d0e607b628dafac2a1a061ee760ae03a` |
| `docs/ATTACK_ROOT_CAUSE_V3_2026-11-20.md` | `9ba175a8f41cf893b048eb5dfc2d20b2c15170e92369ca95e970df02fb4b0adc` | `9ba175a8f41cf893b048eb5dfc2d20b2c15170e92369ca95e970df02fb4b0adc` |
| `docs/ATTACK_TRUSTED_FACT_PROVENANCE_V1_PROPOSAL_2026-11-20.md` | `8518790bbc6bc694a7650d3b18a74c7e882e20ce619eb82e1547902a0376a030` | `8518790bbc6bc694a7650d3b18a74c7e882e20ce619eb82e1547902a0376a030` |
| `eval/attack_diagnostic_metrics_v3.py` | `370e2f466839ad2e51c552c400f7a39ad0967bb5035c74a85f5e2c70fddda8a9` | `370e2f466839ad2e51c552c400f7a39ad0967bb5035c74a85f5e2c70fddda8a9` |
| `eval/attack_evidence_guard_v3.py` | `73e54559ef04b8aecb6e0e375713a591b1d7735081524e42ce65d6722c0c9e6a` | `73e54559ef04b8aecb6e0e375713a591b1d7735081524e42ce65d6722c0c9e6a` |
| `eval/attack_evidence_guard_v4.py` | `61a9553088599f648d87b0ca8bf564a71ea0eca8e738bfa370490a28ad1d50f3` | `61a9553088599f648d87b0ca8bf564a71ea0eca8e738bfa370490a28ad1d50f3` |
| `eval/attack_evidence_v2.py` | `7fcd1a4b1c758f12ad65bef8b1e33f981ec408aaaef3b358e3b4cfa8d1090929` | `7fcd1a4b1c758f12ad65bef8b1e33f981ec408aaaef3b358e3b4cfa8d1090929` |
| `eval/attack_experiment_a_analysis_v3.py` | `4b2557044f2c356ab5749deb9449a1585dfa73ae6538db4e7549b09438452f57` | `4b2557044f2c356ab5749deb9449a1585dfa73ae6538db4e7549b09438452f57` |
| `eval/attack_experiment_a_v3.py` | `89da65362486eb0710caed1cd4114614671772b2a347de55ab66aee2ebe92e8a` | `89da65362486eb0710caed1cd4114614671772b2a347de55ab66aee2ebe92e8a` |
| `eval/attack_experiment_bc_v3.py` | `65943cd1bac7d5d3059d03cfca049d5ddc7ceb85d3d49c24dc13f1df49eb08e8` | `65943cd1bac7d5d3059d03cfca049d5ddc7ceb85d3d49c24dc13f1df49eb08e8` |
| `eval/attack_experiment_d_guard_v3.py` | `a64560a9749ac8120c06b395ddafbf74101491d8b468ca23f6b6ede3f8f7dc22` | `a64560a9749ac8120c06b395ddafbf74101491d8b468ca23f6b6ede3f8f7dc22` |
| `eval/attack_experiment_d_integrity_v3.py` | `3ccde10abc1f4a4c0347029936df7fc09e2201a7ff61d1dc5804402e469f89f6` | `3ccde10abc1f4a4c0347029936df7fc09e2201a7ff61d1dc5804402e469f89f6` |
| `eval/attack_experiment_d_v3.py` | `39e59cfa52f7461e70612cc3344c775405ae9d455bade404f32b1973b5cef1e4` | `39e59cfa52f7461e70612cc3344c775405ae9d455bade404f32b1973b5cef1e4` |
| `eval/attack_experiment_v2.py` | `525da332ac16e7efd1fbc9d592de8be6d75eed350fde8acb810d66007e02c982` | `525da332ac16e7efd1fbc9d592de8be6d75eed350fde8acb810d66007e02c982` |
| `eval/attack_forensics_v3.py` | `47afa61d9e626425a8f69f21f35bc6ed15a9b782d996ce24e7890a9b9ddb7e2e` | `47afa61d9e626425a8f69f21f35bc6ed15a9b782d996ce24e7890a9b9ddb7e2e` |
| `eval/fixtures/ai/attack_mapping_v2/observations.json` | `791fbcb3aedf4d8872de3f9eab0cc5244aabd3877808c519f2f61b9017831e17` | `791fbcb3aedf4d8872de3f9eab0cc5244aabd3877808c519f2f61b9017831e17` |
| `eval/fixtures/ai/attack_mapping_v2/rubric.json` | `1a8dd827e61dc5c3f4c769ec74102bf0676e14c7a84c25e4df01d727b5251c66` | `1a8dd827e61dc5c3f4c769ec74102bf0676e14c7a84c25e4df01d727b5251c66` |
| `eval/reports/attack_diagnostics_bc_v3_20261120/fixed-technique-requests.json` | `fef24e05b445dcaf4c48ba362a36383487d3f8bf039c3b928ab2b4933bfe74fc` | `fef24e05b445dcaf4c48ba362a36383487d3f8bf039c3b928ab2b4933bfe74fc` |
| `eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.json` | `cc7ec23535c18f7e4cc66faa5c3ca8b757d52e8abd2e5cea3eaf658e6ed690cc` | `cc7ec23535c18f7e4cc66faa5c3ca8b757d52e8abd2e5cea3eaf658e6ed690cc` |
| `eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.r2.json` | `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1` | `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1` |
| `eval/reports/attack_diagnostics_d_v3_20261120/manifest-r1-failed-preflight-evidence.json` | `da372cdc4e560b59d47359cfb3e1ab5bd9b5cc218c0c933569d1795a85ff0feb` | `da372cdc4e560b59d47359cfb3e1ab5bd9b5cc218c0c933569d1795a85ff0feb` |
| `eval/reports/attack_diagnostics_d_v3_20261120/offline-guard-diagnostic.json` | `41bb2cb6dbd544a33dbe017ef51255a05da9d8815e35941cbf0760f4680e67b1` | `41bb2cb6dbd544a33dbe017ef51255a05da9d8815e35941cbf0760f4680e67b1` |
| `eval/reports/attack_forensics_v3_20261120/matrix.json` | `dcdd2402cd936ee9e74f21159f357701b590ae380097d1fb43d283595e0b975a` | `dcdd2402cd936ee9e74f21159f357701b590ae380097d1fb43d283595e0b975a` |
| `eval/reports/attack_forensics_v3_20261120/matrix.md` | `e90320fb75988f07853e8d097b44c187cf9ec46ac8f969f62949ced72d017cd7` | `e90320fb75988f07853e8d097b44c187cf9ec46ac8f969f62949ced72d017cd7` |
| `eval/reports/attack_forensics_v3_20261120/offline-secondary.json` | `32bb45603b7b22bfad436f1f3b58e25e6983ec6fdb4cbbc8fc9a4afe6835ff45` | `32bb45603b7b22bfad436f1f3b58e25e6983ec6fdb4cbbc8fc9a4afe6835ff45` |
| `eval/reports/attack_forensics_v3_20261120/oracle-a-requests.json` | `634372410ae089de674f3ea1c3e4b7b4150a6f046ea3087c1124c874eabe3ecc` | `634372410ae089de674f3ea1c3e4b7b4150a6f046ea3087c1124c874eabe3ecc` |
| `eval/reports/attack_forensics_v3_20261120/SHA256SUMS.txt` | `43a07dc8b793481f73b6380a0adf8f05b22c2a566c81e3f80d9529c2dd6c2534` | `43a07dc8b793481f73b6380a0adf8f05b22c2a566c81e3f80d9529c2dd6c2534` |
| `eval/reports/attack_mapping_v2_20261120/engineering-verification.json` | `b75be4c9bc32bc0007f284d394c565cd2ae60f4ae6213328f1abfb72dbf436bb` | `b75be4c9bc32bc0007f284d394c565cd2ae60f4ae6213328f1abfb72dbf436bb` |
| `eval/reports/attack_mapping_v2_20261120/pytest-full.txt` | `2dd621b07dbe3f81657eca68585b79f4ac0d7f0d9d394757694d13ca8362e9c8` | `2dd621b07dbe3f81657eca68585b79f4ac0d7f0d9d394757694d13ca8362e9c8` |
| `eval/reports/attack_mapping_v2_20261120/pytest-targeted.txt` | `ce975a2e0b7a8d6ffa6ea83b8d09888f52b17e0dc76cee6f2908fba612af5425` | `ce975a2e0b7a8d6ffa6ea83b8d09888f52b17e0dc76cee6f2908fba612af5425` |
| `eval/reports/attack_mapping_v2_20261120/registration.json` | `66254d7c5fa4128faac5749bf78ae3a5ba8de324ee232b505098e462d955d8c3` | `66254d7c5fa4128faac5749bf78ae3a5ba8de324ee232b505098e462d955d8c3` |
| `eval/reports/attack_mapping_v2_20261120/SHA256SUMS.txt` | `e710e368d33243e7df0c4946c8c7862cc2fddb5083d8ff9754d734eb1ce8b623` | `e710e368d33243e7df0c4946c8c7862cc2fddb5083d8ff9754d734eb1ce8b623` |
| `tests/test_attack_evidence_guard_v3.py` | `d3aec653cd3f974ec9d4bba50a618677669a1d590bf569ebfb20ba8f8bc00dee` | `d3aec653cd3f974ec9d4bba50a618677669a1d590bf569ebfb20ba8f8bc00dee` |
| `tests/test_attack_evidence_guard_v4.py` | `6a7c38bc712fb5cfc51292d604c2d9c774ef0316a3e3df5ed76bf4343f56ec1b` | `6a7c38bc712fb5cfc51292d604c2d9c774ef0316a3e3df5ed76bf4343f56ec1b` |
| `tests/test_attack_evidence_v2.py` | `5ccca35e19d97536802bb63bc1da48b2f54c2aa482aa8453b172b9fb6feadaf8` | `5ccca35e19d97536802bb63bc1da48b2f54c2aa482aa8453b172b9fb6feadaf8` |
| `tests/test_attack_experiment_d_integrity_v3.py` | `a6f9a28cf1a7851271c5b082e68139aaf179cdd80b4e91a2450feb486383c364` | `a6f9a28cf1a7851271c5b082e68139aaf179cdd80b4e91a2450feb486383c364` |
| `tests/test_attack_experiment_d_v3.py` | `e44280316e532fcdb89706f661ab57fd60def5e5fe6113d7653e2ae11ef46661` | `e44280316e532fcdb89706f661ab57fd60def5e5fe6113d7653e2ae11ef46661` |

</details>

The fixtures establish deterministic guard behavior under pinned, authored provenance and review assumptions. Collection completeness, source truth, actual account control, trustworthy clock calibration, reviewer independence and semantic entailment in real telemetry require external evidence and independent validation. This checkpoint is offline and synthetic. Experiment E remains deferred.
