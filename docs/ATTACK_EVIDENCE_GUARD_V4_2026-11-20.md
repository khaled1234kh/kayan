# Offline ATT&CK evidence guard v4

20 November 2026 · Deterministic research engineering

The v4 guard admitted both independently supported `slate` findings together. Removing the reviewed E1.1 association for either event withheld that finding alone. These results use the existing AI analyst-normalized fictional facts.

## Defect and correction

V3 first expands every cited address into all its reviewed facts. It then rejects a claim when that expansion contains multiple events. E1.1 legitimately identifies the same unauthorized session for two different occurrences. Each occurrence has its own mechanic and outcome. Address-only expansion makes both claims appear to mix events.

V4 groups flat proposals by technique and resolves exactly one cited mechanic that matches the technique inside a caller-selected case. It forwards every proposed address and the complete reviewed fact set for the selected event to the historical guard. That guard checks proof roles, independent attribution, completion, authorization and process/session linkage, including applicable adverse evidence that the proposal omitted. V4 separately checks that every citation exists within the selected event. V3's address expansion reads from a default dictionary and can create an empty entry for a missing cite before its membership check. V3 still withheld those claims as extraneous. The explicit v4 check restores the missing-address reason.

The new interface is `review(raw, *, case_id, reviewed_cases)` in [attack_evidence_guard_v4.py](../eval/attack_evidence_guard_v4.py). The caller supplies a mapping from trusted case IDs to tuples of the existing reviewed `Fact` type. The JSON proposal carries technique/citation pairs. Accepted entries add `case_id` and `event` to the technique and citations. Per-technique rejections retain reasons, including when another claim is eligible. Duplicate pairs and malformed envelopes fail proposal validation. Unknown cases or untyped reviewed input fail review-input validation. Multiple plausible anchors for a technique withhold that claim because the flat proposal cannot disambiguate repeated occurrences.

## Before and after

Both techniques were submitted together in each row. Their event tenant and asset are `fixture` and `SE-2`.

| Reviewed input | Claim | V3 disposition and reasons | V4 disposition and reasons |
| --- | --- | --- | --- |
| Complete banks | T1486 | Withheld. `source_or_event_mismatch`. | Eligible for analyst review. Event `archive-encryption`, E1.1 and E2.1. |
| Complete banks | T1490 | Withheld. `source_or_event_mismatch`. | Eligible for analyst review. Event `snapshot-purge-Z`, E1.1, E3.1 and E4.1. |
| E1.1 association removed for T1486's event | T1486 | Withheld. `source_or_event_mismatch`. | Withheld. `authorization_unverified`, `extraneous_citation`, `independent_attribution_missing`, `source_or_event_mismatch`. |
| Same removal | T1490 | Eligible for analyst review. E1.1, E3.1 and E4.1. | Eligible for analyst review. Event `snapshot-purge-Z`, E1.1, E3.1 and E4.1. |
| E1.1 association removed for T1490's event | T1486 | Eligible for analyst review. E1.1 and E2.1. | Eligible for analyst review. Event `archive-encryption`, E1.1 and E2.1. |
| Same removal | T1490 | Withheld. `source_or_event_mismatch`. | Withheld. `authorization_unverified`, `extraneous_citation`, `independent_attribution_missing`, `source_or_event_mismatch`. |

## Offline verification

The primary regression was run against v3 before the new module existed. It failed with `source_or_event_mismatch` for both findings. The final focused run had **28 passed, 0 failed, 0 skipped**. The combined offline guard, materialization, integrity and scoring suites had **93 passed, 0 failed, 0 skipped**. No safety regressions were observed in these tests. They cover wrong-only and unknown cites, cross-event action/outcome mixing, competing anchors, missing or incompatible attribution, case isolation, hostile-status and authorization checks, conflicting process/session links, failed or unresolved outcomes, contradictions and retractions. The tests also reject attempts to add model-proposed facts or event identifiers through the proposal. [Regression suite](../tests/test_attack_evidence_guard_v4.py)

```powershell
python -B -m pytest tests/test_attack_evidence_guard_v4.py -q -p no:cacheprovider
python -B -m pytest tests/test_attack_evidence_guard_v4.py tests/test_attack_evidence_guard_v3.py tests/test_attack_experiment_d_v3.py tests/test_attack_experiment_d_integrity_v3.py tests/test_attack_evidence_v2.py -q -p no:cacheprovider
python -B -m eval.attack_experiment_d_integrity_v3 audit --prior-authorized-sha256 c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba
```

The revision-aware audit passed and reproduced the original revision 1 integrity discrepancy at byte offset 286. I compared the raw-byte SHA-256 digests of 39 historical files before and after implementation. Every digest matched. The table records the baseline and verified final digest for each file.

<details>
<summary>Historical SHA-256 inventory</summary>

| Repository path | Identical before/after SHA-256 |
| --- | --- |
| `.build/attack_diagnostics_v3_a/attempts.jsonl` | `4e7cb6d9fcdbb33f7dc02cef39c4449c50a358034759012666a1f79195bc7202` |
| `.build/attack_diagnostics_v3_a/authorization.json` | `406731d1ff1ce48a8a4932fa25201967d80f88f646c096b2829e6d0315ab92c0` |
| `.build/attack_diagnostics_v3_a/comparison.json` | `634bc5b4b350dd00311a8a6e5266b8358c43a0c2a862e442174c79a22de34370` |
| `.build/attack_diagnostics_v3_a/completion.json` | `397b51d1708d914802a9debde5453f0e9ddb2b2e5683c0b65320f27b292c80e8` |
| `.build/attack_diagnostics_v3_bc/attempts.jsonl` | `ee6f93be1ee6eeff03a730f148fdd7b6c1266bec02b514098d866a6cce88861f` |
| `.build/attack_diagnostics_v3_bc/authorization.json` | `f1c0c86409238da59a0a33ff9366b05f5ae5bf7c7dc98df72f637723647d3354` |
| `.build/attack_diagnostics_v3_bc/completion.json` | `0258a37149c8f7af42cc62f2c92626e5bc5febc554d81712c24271de739a3d4a` |
| `.build/attack_diagnostics_v3_d/attempts.jsonl` | `ac6e45d1df1c5c44dab71575740fb439af6cd9e8ad7883046c8ec3909126dd20` |
| `.build/attack_diagnostics_v3_d/authorization.json` | `2dfc2e307dc3df75c7bf66f8bc96225fe8d1aae48475a7a2d0e6846f35fbe5ce` |
| `.build/attack_diagnostics_v3_d/completion.json` | `097210a292bb201e48f4accf54b2dd6942bd28c3a6ca366753e968e88436bbce` |
| `.build/attack_exploratory_v2/resources.jsonl` | `2a7cab6d7701bdd59f8b87dd4eb62a2155442bdb0be2eae6598aa74ad78cca97` |
| `.build/attack_exploratory_v2/run/attempts.jsonl` | `3fde89e782aa4c753aabb5b9604ed2d0ea56f90ca6fc6587bc95efca537214ca` |
| `.build/attack_exploratory_v2/run/results.json` | `d193412c182f84477a595b229b64b1b117474ebb8b887666c96bd948a72d38d5` |
| `.build/attack_exploratory_v2/run/run-lock.json` | `5b8106a4e86d14f1e7a35fc7f65a14eeef95d2f68a087509d4ee4435622b2923` |
| `.build/attack_exploratory_v2/runner.log` | `2b5face21a3bf4bb43939bdbd308aed79a71c893ca61a0b513f1e6f1d9deac58` |
| `.build/attack_exploratory_v2/stakeholder-authorization.json` | `1034705f667a887ae34c5f7f8b88dece6ed09899fa516ccdd0829fa481c2381e` |
| `docs/ATTACK_DIAGNOSTIC_PROTOCOL_V3_2026-11-20.md` | `29a41fb4a57e222a16e565ef4bc090a66a7a9761a37ad739e742b14a9ec90d14` |
| `eval/attack_evidence_guard_v3.py` | `73e54559ef04b8aecb6e0e375713a591b1d7735081524e42ce65d6722c0c9e6a` |
| `eval/attack_evidence_v2.py` | `7fcd1a4b1c758f12ad65bef8b1e33f981ec408aaaef3b358e3b4cfa8d1090929` |
| `eval/attack_experiment_d_guard_v3.py` | `a64560a9749ac8120c06b395ddafbf74101491d8b468ca23f6b6ede3f8f7dc22` |
| `eval/fixtures/ai/attack_mapping_v2/observations.json` | `791fbcb3aedf4d8872de3f9eab0cc5244aabd3877808c519f2f61b9017831e17` |
| `eval/fixtures/ai/attack_mapping_v2/rubric.json` | `1a8dd827e61dc5c3f4c769ec74102bf0676e14c7a84c25e4df01d727b5251c66` |
| `eval/reports/attack_diagnostics_bc_v3_20261120/fixed-technique-requests.json` | `fef24e05b445dcaf4c48ba362a36383487d3f8bf039c3b928ab2b4933bfe74fc` |
| `eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.json` | `cc7ec23535c18f7e4cc66faa5c3ca8b757d52e8abd2e5cea3eaf658e6ed690cc` |
| `eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.r2.json` | `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1` |
| `eval/reports/attack_diagnostics_d_v3_20261120/manifest-r1-failed-preflight-evidence.json` | `da372cdc4e560b59d47359cfb3e1ab5bd9b5cc218c0c933569d1795a85ff0feb` |
| `eval/reports/attack_diagnostics_d_v3_20261120/offline-guard-diagnostic.json` | `41bb2cb6dbd544a33dbe017ef51255a05da9d8815e35941cbf0760f4680e67b1` |
| `eval/reports/attack_forensics_v3_20261120/matrix.json` | `dcdd2402cd936ee9e74f21159f357701b590ae380097d1fb43d283595e0b975a` |
| `eval/reports/attack_forensics_v3_20261120/matrix.md` | `e90320fb75988f07853e8d097b44c187cf9ec46ac8f969f62949ced72d017cd7` |
| `eval/reports/attack_forensics_v3_20261120/offline-secondary.json` | `32bb45603b7b22bfad436f1f3b58e25e6983ec6fdb4cbbc8fc9a4afe6835ff45` |
| `eval/reports/attack_forensics_v3_20261120/oracle-a-requests.json` | `634372410ae089de674f3ea1c3e4b7b4150a6f046ea3087c1124c874eabe3ecc` |
| `eval/reports/attack_forensics_v3_20261120/SHA256SUMS.txt` | `43a07dc8b793481f73b6380a0adf8f05b22c2a566c81e3f80d9529c2dd6c2534` |
| `eval/reports/attack_mapping_v2_20261120/engineering-verification.json` | `b75be4c9bc32bc0007f284d394c565cd2ae60f4ae6213328f1abfb72dbf436bb` |
| `eval/reports/attack_mapping_v2_20261120/pytest-full.txt` | `2dd621b07dbe3f81657eca68585b79f4ac0d7f0d9d394757694d13ca8362e9c8` |
| `eval/reports/attack_mapping_v2_20261120/pytest-targeted.txt` | `ce975a2e0b7a8d6ffa6ea83b8d09888f52b17e0dc76cee6f2908fba612af5425` |
| `eval/reports/attack_mapping_v2_20261120/registration.json` | `66254d7c5fa4128faac5749bf78ae3a5ba8de324ee232b505098e462d955d8c3` |
| `eval/reports/attack_mapping_v2_20261120/SHA256SUMS.txt` | `e710e368d33243e7df0c4946c8c7862cc2fddb5083d8ff9754d734eb1ce8b623` |
| `tests/test_attack_evidence_guard_v3.py` | `d3aec653cd3f974ec9d4bba50a618677669a1d590bf569ebfb20ba8f8bc00dee` |
| `tests/test_attack_experiment_d_v3.py` | `e44280316e532fcdb89706f661ab57fd60def5e5fe6113d7653e2ae11ef46661` |

</details>

## What the guard can establish

The guard verifies consistency and completeness relative to reviewed assignments. A `Fact` instance does not attest to its own provenance. The caller must control the review input and establish real source lineage. Independence uses the existing reviewed source IDs. The event identity includes a pre-correlated occurrence, and the actor value represents a reviewed classification. Raw principal resolution, timestamp and authorization-interval checks, collector independence and semantic interpretation of raw telemetry still require trustworthy normalization and independent review. Fresh blinded validation is needed to estimate behavior beyond these fixtures.

This change has no production integration. Experiment E remains deferred.
