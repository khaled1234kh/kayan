# ATT&CK v3 Experiment D results · Incident facts first

**20 November 2026.** The staged workflow completed **0/3 evidence groups**, the same as the one-pass baseline. It produced one additional correct abstention, on a case that received an empty extraction fallback. Three of four D2 outputs exceeded the frozen conservative D3 context bound. The only case that received extracted facts, `silver`, acquired an additional unsupported mapping. This run demonstrated no improvement in evidence grounding. [Preparation and frozen rules](ATTACK_DIAGNOSTIC_D_PREPARATION_V3_2026-11-20.md)

## Integrity and execution

Revision 2 of `attack-diagnostics-v3.0` was authorized for exactly 12 local attempts against SHA-256 `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1`. The revision-aware audit passed and the exact revision 2 file supplied the eight static payloads and four D3 templates. The preflight verified the source digest, all ordered entries, frozen v2/A/B/C inputs, Ollama 0.40.13 and the pinned Qwen2.5 7B digest. The earlier malformed revision 1 and its failed preflight remained byte-identical. The human-gated run remained sealed. SovereignEG reported disabled before and after.

All 12 requests returned HTTP 200 with finish reason `stop`, without a retry or substitution. The loaded model reported a 4,096-token context. Offline replay matched all serialized requests to the manifest or deterministic D3 materialization, checked each SHA-256 and raw response, reproduced all fallback decisions and recomputed every D1/D3 score with the unchanged frozen scorer. [Revision 2 manifest](../eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.r2.json) · [Revision 1 integrity evidence](ATTACK_DIAGNOSTIC_D_INTEGRITY_V3_2026-11-20.md) · [Raw ledger](../.build/attack_diagnostics_v3_d/attempts.jsonl)

## Frozen-score comparison

| Metric | D1 | D3 |
| --- | ---: | ---: |
| Complete expected technique groups | 0/3 | 0/3 |
| Positive cases with all groups complete | 0/2 | 0/2 |
| Expected technique IDs selected with incomplete evidence | 3/3 | 3/3 |
| Correct abstentions on negative cases | 0/2 | 1/2 |
| Negative cases with one or more false mappings | 2/2 | 1/2 |
| Distinct unsupported technique claims on negative cases | 8 | 5 |
| Unsupported technique claims overall | 13 | 10 |
| Relevant citations | 3/13 | 3/10 |
| Unsupported citations | 10 | 7 |
| Invalid mapping outputs | 0/4 | 0/4 |

Each positive ID selection cited one keyed statement. The complete evidence chains required multiple statements across records. A higher citation fraction in D3 reflects fewer unsupported citations overall, while the number of relevant citations stayed at three. No additional required evidence was cited.

| Case | D1 → D3 | Missing evidence or mapping error |
| --- | --- | --- |
| cedar | Same IDs and citations. T1685.005 with E2.1, plus unsupported T1685.006 with E1.1 in both arms. | E2.1 establishes the completed Windows clear. Neither response cited E3.1 for the session-to-actor link and unauthorized status. E1.1 is a possible clear. |
| slate | Same three IDs. Both cite E2.1 for T1486 and E3.1 for T1490. Both also claim unsupported T1578.001, citing E3.2 in D1 and E3.1 in D3. | Both keyed IDs omit B19 attribution and authorization at E1.1. Recovery inhibition also omits E4.1, the completed purge and actor-to-batch link. The extra claim changes from snapshots retained on a spare node to snapshots lost. Neither supports snapshot creation. |
| silver | Four → five unsupported findings. D3 adds T1087.004 on E2.2 and changes the citation for T1548.005 from E1.1 to E1.2. Both report T1098.003 using E1.1. | The grant was authorized by the same-tenant schedule at E2.1. The other tenant’s compromised same-name principal in E2.2 cannot establish hostile identity for this grant. |
| flint | Four false mappings → valid abstention. | The source journal is unavailable and the allegation was retracted. The D3 answer gives no rationale and received no D2 facts. |

## D2 extraction and what reached D3

All four D2 responses passed execution, schema and observation-address checks, producing 31 proposed facts. Three used `context_bound_exceeded` when rendered with the full original observations and references. They entered D3 as empty arrays with explicit error codes. The frozen byte-based bounds include the reserved 370 output tokens. An over-limit bound is evidence of the conservative preflight rule firing. It is not a measurement of how many Qwen tokens the discarded prompt would actually use.

| Case | D2 facts | Full D3 bound including output reserve | D3 received |
| --- | ---: | ---: | --- |
| cedar | 8 | 4,184 | Empty fallback |
| slate | 8 | 4,160 | Empty fallback |
| silver | 7 | 3,983 | Seven unverified facts |
| flint | 8 | 4,130 | Empty fallback |

**Cedar.** E2.1 and E2.2 yielded the clear and audit restart, and E3.1 yielded the intruder and session link. The separate maintenance activity was included from E3.2 without its distinct 6N session qualifier. The E1.1 item dropped “possible,” the E1.2 item named Desk J rather than identifying JUN-4 as the affected host, and the authorization item described token isolation rather than the intruder’s unauthorized status. E3.1 carries that status, and the actor value did contain “unauthorized intruder.” The output captured parts of the chain while leaving the host, completion and session qualification underspecified. None of these extractions reached D3.

**Slate.** E2.1 supported the encryption action and the project-archive and drawings items. The response omitted the effect that drawings became unavailable. It cited E3.1 and E3.2 together for “snapshots” without distinguishing the lost recoverable copies on SE-2 from those retained on SE-3. It extracted B19 and B91, but it omitted B19’s unauthorized status and the purge in E4.1. Its B91 actor item includes E3.2, which never names B91. E4.2 does connect B91’s ticket to SE-3, and the SE-2 link has support in E1.1/E2.1. The extracted links did not establish the two separately completed events, and none reached D3.

**Silver.** The grant, role, removal and finance-review actor are supported. The schedule and `change 418` are cited, but the extracted value does not state that the schedule authorized the grant for the applicable interval. The “compromised account reported” item is a real reported fact about a different tenant and a same-name principal. Rendering it as an outcome without that qualifier makes it misleading in the current grant’s chain. D3 had the full original qualifying observations. It still cited only the grant as support for T1098.003 and put an additional unsupported technique on E2.2. This shows that D3 failed to resolve the evidence correctly. The run cannot establish whether a specific extraction item caused the extra claim.

**Flint.** The eight entries preserved the allegation, host, lack of corroboration, journal and relay, outage timing, retraction and incident record. The journal item omitted its unavailable status, though the accompanying no-corroboration item cited that source. The allegation and retraction values retained their qualifiers. The extraction did not invent a confirmed clear or actor. Its fallback delivered no facts. D3’s improved abstention therefore cannot be attributed to those extracted values.

## Model-generation costs and interpretation

| Stage | Calls | Summed request wall time | Ollama prompt tokens | Generated tokens | Ollama generation time |
| --- | ---: | ---: | ---: | ---: | ---: |
| D1 | 4 | 11.31 s | 2,335 | 422 | 6.45 s |
| D2 | 4 | 14.73 s | 1,071 | 906 | 14.21 s |
| D3 | 4 | 6.18 s | 2,841 | 330 | 5.14 s |
| D2 + D3 | 8 | 20.91 s | 3,912 | 1,236 | 19.35 s |

The staged path added **9.60 seconds** of summed request wall time, **1,577** server-reported prompt tokens and **814** generated tokens. The D1 total included a cold load of about 3.85 seconds, so phase ordering and server reuse affect the timing comparison. Energy and incremental hardware use were unmeasured. The costs above are local server compute and wall time. No external provider was called.

D3 added instructions, an extra generation and additional budget. Its primary comparison is therefore a test of that workflow as executed, including fallbacks. Three failures to carry the extraction into mapping leave limited exposure to the proposed intervention. The results establish no grounding benefit on these four fictional cases. They leave open whether a separately tested representation could transfer a fuller, correctly qualified extraction and whether mapping would use it. The one correct abstention on a fallback and the worsening on the only fact-fed case should both be retained in the interpretation.

## Slate guard limitation and separately scoped correction

The existing offline guard accepts the encryption and recovery proposals when independently reviewed facts are scoped to their respective events. A combined flat fact bank gives E1.1 a reviewed attribution entry under each event. Address-only expansion fetches both event keys for each claim and makes both fail the single-event requirement. This is an offline fixture result. The guard was neither used to score D1/D3 nor modified during D.

A separately reviewed correction should resolve the trusted event context per proposed claim, then retrieve reviewed facts by event key and citation address. A reviewed shared source may support several events, each through its own reviewed association. Event resolution should fail closed when ambiguous. Regression coverage should require both slate claims to pass together when correctly scoped, and still reject cross-event mixing, mismatched actor/time/asset, absent attribution, incompatible authorization or outcome, and ambiguous event resolution. The model’s unverified extraction cannot supply a trusted event key. [Frozen guard diagnostic](../eval/reports/attack_diagnostics_d_v3_20261120/offline-guard-diagnostic.json)

## Retained artifacts

| Artifact | SHA-256 |
| --- | --- |
| Revision 2 manifest | `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1` |
| Original malformed revision 1 | `cc7ec23535c18f7e4cc66faa5c3ca8b757d52e8abd2e5cea3eaf658e6ed690cc` |
| Revision 1 failed preflight evidence | `da372cdc4e560b59d47359cfb3e1ab5bd9b5cc218c0c933569d1795a85ff0feb` |
| Attempt ledger | `ac6e45d1df1c5c44dab71575740fb439af6cd9e8ad7883046c8ec3909126dd20` |
| Authorization record | `2dfc2e307dc3df75c7bf66f8bc96225fe8d1aae48475a7a2d0e6846f35fbe5ce` |
| Completion | `097210a292bb201e48f4accf54b2dd6942bd28c3a6ca366753e968e88436bbce` |
| Cedar D3 wire request | `f4b37508a2b30cf15ae3efd89653516174e9ed256c1ba1790283d078892d6148` |
| Slate D3 wire request | `a52edb95858260b8777a7316fec92ca4f20c04cdf192afaeaaa42641516fe7b0` |
| Silver D3 wire request | `757bb8b8fa3ea86f5e372101b201e10820c036c3356286d725e474925786e3b0` |
| Flint D3 wire request | `b6fa65ffe96809a87f8ced2e0cc8e53bf70921c43a0e755b31d2e6963776523c` |

[Authorization](../.build/attack_diagnostics_v3_d/authorization.json) · [Completion](../.build/attack_diagnostics_v3_d/completion.json)
