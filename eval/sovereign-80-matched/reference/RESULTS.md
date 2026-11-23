# KAYAN TrustGate offline pilot results

**Experiments executed 12–13 November 2026, Cairo time.** Literature cutoff remains 12 November. The project repository was read for context and source references. The experiments used a separate workspace, synthetic defensive records, loopback model inference and inert mock effects.

## Decision

Keep the operational system at its existing model and serving settings. Advance the hybrid Planner and deterministic scheduler **as a defensive evidence-review prototype**. Keep one inference slot as the initial default while the workflow-specific benefit of two slots is replicated. Study versioned ATT&CK retrieval with evidence checks before considering training. The measured benefits are specific to these fixtures, and the model comparison does not justify replacing the operational checkpoint or assigning five different models.

| Decision | What this pilot established | Next evidence needed |
|---|---|---|
| Scheduler | Dependency scheduling reduced time in the mock fixtures with independent work. The matched Qwen2.5, Llama, Granite and Qwen3 checks with real one-slot inference showed no clear gain. Both preserved all expected terminal states. | Repeat with independently collected defensive workflows and measured task service times. |
| Inference slots | The two-slot engine overlapped requests. Throughput rose on four scheduled groups and fell slightly in the separate serving comparison. | Repeat the counterbalanced comparison with more groups and measure serving queue delay separately. |
| Shared checkpoint | Qwen3 8B led exact passes by one case over Granite 4.2 8B. Granite led evidence F1 and Planner exact passes, with higher latency and peak GPU use. | Expand the independent holdout and replicate per-role trade-offs. |
| Compact specialist | Qwen2.5 1.5B was faster and used less GPU memory, with substantially fewer exact passes. | Evaluate compact models on narrower roles using predeclared quality margins. |
| ATT&CK | The BM25 plus structural checks arm was strongest on the scored 32-case Qwen pilot. Both independent labels and independent evidence validation are still needed. | Test independently adjudicated reports, better abstention handling and version changes separately. |
| TrustGate | The mock broker denied every expected rejected case and allowed the benign controls. Fresh Cedar compilation was blocked by host Application Control. | Run the existing Rust unit suite on a permitted host and independently assess real identity, audit and replay controls before relying on them. |

## 1. Model quality and latency

Five checkpoints each saw the same 80 held-out cases, 16 per role. Each also completed the same 40 calibration cases. All are authored record interpretation or inert dependency decisions. An exact pass requires all expected labels and citations, plus an acceptable dependency order for Planner. Evidence F1 scores the item, label and source-reference triple. Affirmative F1 treats each role's affirmative class as the positive label. The frozen manifest has 120 total cases, with 40 calibration cases in distinct families. Its SHA-256 is `09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0`.

| Checkpoint | First / final exact | Affirmative P / R / F1 | Evidence F1 | p50 / p95 | Peak GPU used |
|---|---:|---:|---:|---:|---:|
| Qwen2.5 7B | 18 / 18 of 80 | .481 / .626 / .544 | .454 | 2.17 / 3.78 s | 5,531 MiB |
| Llama 3.1 8B | 23 / 23 of 80 | .676 / .758 / .714 | .688 | 2.53 / 3.92 s | 6,738 MiB |
| Qwen2.5 1.5B | 5 / 5 of 80 | .506 / .848 / .634 | .454 | 1.12 / 1.56 s | 2,160 MiB |
| Granite 4.2 8B | 27 / 27 of 80 | .685 / .859 / .762 | .762 | 3.57 / 5.04 s | 7,142 MiB |
| Qwen3 8B | 28 / 28 of 80 | .699 / .798 / .745 | .693 | 2.37 / 3.84 s | 6,570 MiB |

| Role | Qwen2.5 7B | Llama 3.1 8B | Qwen2.5 1.5B | Granite 4.2 8B | Qwen3 8B |
|---|---:|---:|---:|---:|---:|
| Planner | 3/16 | 0/16 | 1/16 | 7/16 | 3/16 |
| Recon | 5/16 | 5/16 | 1/16 | 4/16 | 7/16 |
| Web-App | 6/16 | 5/16 | 1/16 | 7/16 | 7/16 |
| Network | 1/16 | 7/16 | 0/16 | 4/16 | 8/16 |
| Reporting | 3/16 | 6/16 | 2/16 | 5/16 | 3/16 |

On the 16 Planner cases, Qwen2.5 7B produced 8 invalid orders and 3 dependency violations. Llama produced 12 invalid orders and 4 dependency violations, while scoring higher on Planner evidence F1 (.641 versus .414). The compact checkpoint produced 15 invalid orders and 17 dependency violations, with .443 evidence F1. Granite produced 8 invalid orders and zero explicit prerequisite violations, with .844 Planner evidence F1. Qwen3 produced 9 invalid orders and one explicit dependency violation, with .614 Planner evidence F1. Invalid order also includes missing or extraneous task IDs. One case can contain multiple dependency violations.

The existing rule-based test oracle solved 16/16 of those same Planner fixtures, versus 3/16 for Qwen2.5 7B. This control checks whether the stated readiness and dependency rules are sufficient for the authored cases. Open-ended planning and the effect of removing the Planner from a coordinated workflow remain unmeasured. [Planner rule control](results/planner-rule-control-v1/summary.json)

All 400 held-out cases completed without inference errors. Qwen3 triggered two structural repairs on Planner cases. Both final responses were schema-valid and neither changed an exact failure into a pass. The other four checkpoints triggered no repairs. The original three checkpoints produced 78, 36 and 84 unsupported affirmative decisions and abstention F1 of .571, .847 and .316. Granite and Qwen3 produced 39 and 41 unsupported affirmatives, with abstention F1 of .879 and .857 respectively. JSON validity therefore provides a weak standalone quality measure. Exact scores require matching the full case, including its evidence. The earlier live Planner-only 24/30 first-pass and 26/30 after correction used different tasks, scoring and integration. Preserve those historical figures separately.

Llama 3.1 improved exact-pass rate by **6.25 percentage points** relative to Qwen2.5 7B, with a paired family-bootstrap 95% interval of **−6.25 to +18.75 points**. Its evidence F1 difference was +.234 [.154, .319]. The compact model's exact-pass difference against 7B was −16.25 points [−23.75, −8.75]. The bootstrap resamples small, authored case families within each role. These are exploratory uncertainty intervals. The role counts are too small to declare winners, and scoring the rule-defined fixtures does not replace independent human labels.

Granite improved exact-pass rate by **11.25 percentage points** against Qwen2.5 7B, paired 95% interval **+2.50 to +20.00**. Its difference against Llama was +5.00 points [−3.75, +13.75]. Evidence F1 exceeded Llama by +.074 [.025, .126]. Against Qwen2.5 7B, the Planner difference was +25 points [6.25, 43.75] on four authored families. These role intervals are exploratory and unadjusted for multiple comparisons. Across all five checkpoints, Granite led Planner, Qwen3 led Recon and Network, Granite and Qwen3 tied on Web-App, and Llama led Reporting. Granite’s peak machine GPU use was 7,142 MiB out of 8,151 MiB, which leaves the interactive console’s concurrent memory cost unmeasured.

Qwen3 improved exact pass rate by **12.50 points** against Qwen2.5 7B [1.25, 23.75]. Its +1.25-point difference against Granite has a paired interval of **−7.50 to +10.00**. Granite led Qwen3 in evidence F1 by .069 [.032, .107]. Qwen3 used 572 MiB less peak machine GPU memory and returned a lower aggregate p95, and its Planner p95 including repairs was 15.34 s. Granite and Qwen3 are the strongest candidates for further offline comparison, with different strengths.

Ollama 0.40.13 served quantized Q4_K_M checkpoints with temperature 0, seed 42, a 4,096-token context, 384-token output budget, no tools, thinking disabled and a single serving slot. Measurements use the RTX 5060 Laptop GPU with the Vulkan backend. GPU peaks are machine-wide samples, and latency includes local HTTP and first-case loading. The primary CUDA smoke timed out after 90.02 seconds. A CPU smoke succeeded in 7.03 seconds, and the Vulkan smoke succeeded in 15.41 seconds including load. Different smoke paths are diagnostic, not timed competitors. The interrupted first Llama attempt was retained and excluded.

[Full role summary](results/role-comparison-final-v1/summary.json) · [Role-level paired intervals](results/final-role-intervals.json) · [CSV](results/role-comparison-final-v1/summary.csv) · [Exact-pass chart](results/role-comparison-final-v1/exact-passes.svg) · [Latency chart](results/role-comparison-final-v1/inference-p95.svg) · [Frozen cases](data/roles_frozen.json)

### Shared versus specialized checkpoints

Qwen2.5 7B and Llama 3.1 8B each completed the 40 calibration cases. The calibration-only rule chose by exact pass count, then evidence F1, then checkpoint name. The calibration-selected shared policy chose Llama. The per-role policy selected Qwen2.5 7B for Planner and Llama for the other four roles. On held-out replay the mix passed **26/80** versus **23/80** for shared Llama, a +3.75-point difference [0, +7.50]. Evidence F1 fell from **.688 to .624**, a difference of −.064 [−.110, −.019]. Selection used calibration outputs only. This exploratory replay was assembled after the held-out runs. It reuses the previously measured held-out responses, so this comparison cannot measure live switching, escalation, or a deployed specialist configuration. [Selection record](results/specialization-replay-v1/selection.json) · [Paired replay](results/specialization-replay-v1/summary.json)

A separate run executed that fixed role assignment on four calibration workflow groups with one resident checkpoint and one inference slot. The mixed route passed 10/20 exact contracts and all four expected terminal states with zero request or format errors. Median group wall time was **30.79 s**, compared with **13.49 s** for shared Llama and **11.69 s** for shared Qwen in the same dependency-ready groups. Eight model changes accounted for 70.73 s in Ollama-reported load duration. Median load was 8.81 s at a switch and 9.46 ms otherwise. Run order was fixed and these groups overlap model selection, so the 10/20 score is descriptive. This demonstrates a switching cost on this host and gives a second reason to retain one shared model. No model chose its own checkpoint or gained execution authority. [Switch timing](results/integrated-fixed-routing-v1/switches.json) · [Fixed route summary](results/integrated-fixed-routing-v1/summary.json) · [Workflow time chart](results/integrated-fixed-routing-v1/model-switching.svg)

After the compact model completed calibration, including it in the replay switched the selected Planner to Qwen2.5 1.5B. Shared Llama remained the calibration choice. The mixed policy scored 24/80 versus 23/80 exact on holdout, with evidence F1 of .634 versus .688. The change in selection from adding a candidate shows how sensitive eight calibration cases per role are. [Three-checkpoint replay](results/specialization-three-models-v1/summary.json)

With Granite included, calibration selected shared Granite and a mixed policy using Llama for Recon and Granite for the other four roles. Adding Qwen3 left both choices unchanged. On holdout, the mixture scored 28/80 versus 27/80 exact for shared Granite, a difference of +1.25 points [−2.50, +5.00]. Evidence F1 was .746 versus .762, a difference of −.016 [−.039, +.008]. The fixed Granite/Llama mixture was also executed on the same four calibration groups. It passed 12/20 exact with all four expected terminals and zero API or format errors. Median wall time was **40.38 s** versus **18.25 s** for shared Granite. Eight switches accounted for 90.27 s of reported load time. The result repeats the single-resident switching trade-off on a different mixture. [Five-checkpoint replay](results/specialization-final-v1/summary.json) · [Granite routing run](results/integrated-granite-routing-v1/summary.json)

## 2. Scheduling, serving and policy evidence

The mock workflow compared a fixed serial order with dependency-ready execution, using four fixed graphs, 16 paired repeats per graph and one mock inference slot. **All 128 timed runs matched the reference terminal states.** A separate seeded coverage check generated 128 distinct graphs. Both modes matched an independent topological-order and terminal-state oracle in all 256 runs. Dependency mode showed worker overlap in 96 of those graphs. The same-seed coverage replay reproduced both files byte-for-byte. [Coverage summary](results/workflow-coverage-v1/summary.json) · [Raw graph outcomes](results/workflow-coverage-v1/graphs.jsonl)

| Fixture | Median paired reduction | 95% paired interval |
|---|---:|---:|
| Independent evidence reviews | 30.50% | 27.67 to 33.53% |
| Inventory prerequisite | 17.75% | 16.42 to 19.61% |
| Serial dependency control | 0.79% | −4.68 to 6.13% |
| Failed branch with partial report | 31.58% | 29.14 to 33.81% |

These are measured wall times over synthetic waits. They do not predict end-to-end speed for the operational assessment system. In the independent case, the median sum of wait at the single mock inference slot rose to 94.35 ms even as makespan fell.

A matched offline scheduling check then used real Qwen2.5 7B inference with one client slot and the same frozen prompts in both modes. Four paired workflow fixtures produced 8/8 expected terminal states, 20/20 identical response bodies between modes and 6/20 exact role contracts per mode, with zero inference or format errors. Median paired wall-time reduction was **0.13%** (four changes from −5.23% to +5.95%). Dependency mode added up to 6.49 s of summed client queue wait within a group. Each task consumed its fixed defensive record. The model responses had no scheduling authority and were not passed to other model calls. This small check found no demonstrated end-to-end speed gain with real inference. [Paired Qwen timings](results/integrated-qwen-v1/summary.json) · [Raw Qwen outputs](results/integrated-qwen-v1/raw.jsonl)

On the same four groups, shared Llama 3.1 8B produced 8/8 expected terminal states and no inference or format errors. Its median paired wall-time reduction was −0.09% (−7.38% to +4.85%). The serial and dependency arms passed 9/20 and 8/20 exact contracts, respectively, and 18/20 matched response bodies were identical. Matched prompts and temperature zero did not guarantee byte-identical responses. The run used calibration fixtures. [Paired Llama timings](results/integrated-llama-v1/summary.json) · [Raw Llama outputs](results/integrated-llama-v1/raw.jsonl)

Shared Granite 4.2 8B reached all eight expected terminal vectors in the same setup. It passed 11/20 exact contracts in each mode, with 20/20 identical paired responses and zero inference or format errors. Median paired wall-time reduction was +0.06%, and median dependency group wall time was 18.25 s. These are calibration cases. The checkpoint comparison used separate sessions in a fixed order. [Granite workflow summary](results/integrated-granite-v1/summary.json)

Shared Qwen3 8B matched all eight fixture terminals and passed 11/20 exact contracts in each mode, with 20/20 identical paired responses. It made no inference API errors. The same Planner case returned non-strict JSON in both modes, so two contract errors were retained. The workflow pilot makes one request per fixture step and does not repair responses. Median paired wall-time reduction was +0.27%, with a 12.77 s median dependency-group time. Fixture terminals score scheduling and transport completion separately from model response quality. [Qwen3 workflow summary](results/integrated-qwen3-v1/summary.json) · [Raw outputs](results/integrated-qwen3-v1/raw.jsonl)

The separate **actual serving** experiment submitted two concurrent requests in each of ten calibration pairs. One-slot and two-slot arms used the same model and cases. The two-slot log records two available sequences and simultaneous slot activity. Both arms passed 7/20 exact contracts with no request errors.

| Measurement | One slot | Two slots |
|---|---:|---:|
| Requests per second over measured pairs | .346 | .340 |
| Median pair wall time | 4.88 s | 5.24 s |
| p95 individual request time | 7.24 s | 11.66 s |
| Peak machine GPU used | 5,665 MiB | 6,083 MiB |

Median within-pair reduction was 26.10%, with a paired interval of −51.75 to +32.84%. Median paired changes, separate arm medians and aggregate throughput are distinct measures. The wide interval and the aggregate results do not support increasing slots by default. This fixed-order serving run bypassed no security controls. It used the research-only HTTP client, which has no application actions and does not take KAYAN's process-local lock.

A second slot comparison used the dependency-ready scheduler with the four fixed Qwen calibration groups. Two slots reduced median paired group wall time by **12.89%** and raised throughput from .396 to .458 requests/s. All eight workflow terminal vectors matched, all 40 requests completed without inference or format errors, and 19/20 paired response bodies matched. The one- and two-slot arms passed 6/20 and 7/20 exact contracts, respectively. The differing result came from the serial control. The engine recorded four simultaneous request pairs and the client showed overlap in three of the four groups. Reversing arm order on the same four groups reduced the median gain to **1.84%**, with throughput .416 versus .423 requests/s. Its eight terminals and 40 requests passed the same runtime checks. It again recorded four simultaneous engine request pairs. The independent group changed from +25.55% to −9.22% reduction. The failure group showed about 12% reduction in both orders. The order sensitivity and mixed throughput results support keeping one slot as the default. [One-slot-first](results/integrated-slots-v1/summary.json) · [Two-slot-first](results/integrated-slots-reversed-v1/summary.json) · [Engine overlap](results/integrated-slots-v1/two/engine.json)

The broker suite passed **19/19** scenarios. It rejected 14 expected denied messages, accepted four benign deliveries with audit links and zero false refusals, and rejected three invalid graphs. No unauthorized mock effect was committed. Authenticated identity and policy decisions were fixture inputs. The unit-build attempt on a source copy was blocked when Windows refused to execute dependency build scripts with error 4551. The last verified operational Cedar results remain historical. No live Gate was started or verified during this pilot.

[Mock workflow methods and results](WORKFLOW.md) · [Workflow timing chart](results/workflow-pilot-v1/workflow-chart.svg) · [Mock security traces](results/workflow-pilot-v1/workflow-security.json) · [Serving comparison](results/serving-comparison.json) · [Cedar build log](results/cedar-unit.log)

## 3. ATT&CK evidence mapping

The deterministic retrieval pilot measured **.115** exact-ID micro F1 for the calibration-majority/no-retrieval baseline, **.115** for the checked-in mixed TF-IDF corpus, **.154** for Enterprise-only TF-IDF, **.346** for Enterprise BM25, and **.409** after structural checks on BM25. The same-corpus ranker comparison separates the change in ranking from removing OWASP and other non-Enterprise candidates.

The official ATT&CK Enterprise v20.1 snapshot matched MITRE's published SHA-256. The unchanged deterministic BM25 scorer moved from **.346 to .385 micro F1** across the two versions, with one additional correct assignment (9 to 10 of 20). The paired difference was +.038 [0, .097]. Both versions contain 706 active Enterprise IDs and have .600 top-three candidate recall on these cases. The main Qwen ablation below used the original pinned index. A separate counterbalanced 64-call Qwen run compared the two versions under the same BM25 and validation settings. Eight of 32 cases received different reference blocks, but all 32 paired model responses were byte-identical. Both versions scored .522 raw and .686 validated micro F1, with six malformed responses per version and zero inference errors. [Qwen version-pair results](results/grounding-snapshot-model-v1/summary.json) [Snapshot comparison](results/grounding_snapshot_v20_1/grounding_holdout_summary.json) · [Verification record](results/attack_snapshot_verified.json) · [Official checksums](https://github.com/mitre-attack/attack-stix-data/releases/expanded_assets/v20.1)

A separate **actual Qwen2.5 7B** experiment used the same 32 held-out defensive cases, 20 gold mappings, four held-out families and 13 cases with no supported mapping. The checkpoint, prompt, context budget, output schema and evidence inputs were held fixed. A top-three reference block was the only input difference among model arms. The validation variant reused the unchanged BM25 responses. It did not make a second call.

| Arm | TP / FP / FN | Micro F1 | Macro F1 | Evidence precision | Invalid abstention outputs |
|---|---:|---:|---:|---:|---:|
| No retrieval | 1 / 11 / 19 | .063 | .071 | .083 | 20/32 |
| Enterprise TF-IDF | 10 / 15 / 10 | .444 | .557 | .400 | 7/32 |
| Enterprise BM25 | 12 / 14 / 8 | .522 | .686 | .462 | 6/32 |
| BM25 plus ID and evidence checks | 12 / 3 / 8 | .686 | .719 | .800 | 6/32 |

All 96 requests returned. The invalid outputs included a source ID while returning a null technique, contrary to the two-field abstention contract. The table scores them as no predicted mapping and separately records the errors. No generation arm returned a contract-valid abstention. The CSV field named abstentions counts rows with no scored prediction, including invalid outputs and, in the validated arm, rejected predictions. The archived exact-case rate measures only equality of technique sets and can count a malformed negative response as exact. All 13 negative cases in the no-retrieval arm returned invalid abstentions. Structural checks reduced false positives by 11 while retaining 12 true positives. One of 13 negative cases still received a positive mapping. Across four synthetic families, the BM25 versus TF-IDF micro-F1 difference was +.077 [−.043, +.212], and the structural check added +.164 [.088, .246] over the same outputs. Each case can return at most one label. Citation validation uses ID membership, observation provenance and lexical overlap. The fixtures do not establish semantic sufficiency on external evidence.

A blinded case-level review by one AI reviewer agreed on whether to map in 32/32 cases and on exact technique-and-evidence sets in 30/32. The reviewer disagreed on two technique labels for the same cited observations and found a third example ambiguous. Re-scoring the same outputs against those alternative labels gave micro F1 of .063, .444, .565 and .743 in table order. The ordering stayed the same. The frozen scores are unchanged, and the cases still need independent human adjudication. [Blinded label comparison](results/grounding-label-review-v1/comparison.json) · [Score sensitivity](results/grounding-label-review-v1/score-sensitivity.json)

Keep the original negative live grounding evidence. Its toggle changed multiple context sources, and this isolated pilot measures a different task with different outputs. No model was trained. Begin with reproducible retrieval and abstention checks, then use independently reviewed multi-label cases before deciding whether a licensed adapter experiment would solve a remaining problem.

[Deterministic pilot](GROUNDING_PILOT.md) · [Model mapping manifest](results/grounding-model-qwen-v1/manifest.json) · [Model mapping CSV](results/grounding-model-qwen-v1/summary.csv) · [Raw model outputs](results/grounding-model-qwen-v1/raw.jsonl) · [Mapping chart](results/grounding-model-qwen-v1/mapping-f1.svg)

## Evidence and reproduction

The [protocol](PROTOCOL.md) records scope, primary sources and how to run each study. JSONL rows contain raw outputs or timed mock observations. The analyzers re-score the saved role responses and check the matched case IDs and model manifests before computing comparisons. The source and input manifests identify the checked-in KAYAN references. The benchmark does not need credentials, production sessions or the lab to reproduce its measurements.

### Architecture coverage

| Roadmap arm | Evidence collected |
|---|---|
| A · fixed serial, shared Qwen | Mock serial timing, separate Qwen role runs and the Qwen fixed-order offline scheduling check. |
| B · dependency-aware, one slot | Paired mock timing and matched offline Qwen check with real one-slot inference. |
| C · increased inference slots | Actual one-/two-slot serving on ten request pairs plus four matched scheduled groups. |
| D · alternative shared checkpoint | Matched frozen role cases and a separate offline scheduling check. |
| E · role-selected checkpoints | Held-out replay of calibration-selected models and real switching costs on four calibration groups. Adaptive escalation remains unmeasured. |

The arms isolate individual effects. They do not supply a ranking of five integrated systems. The production runtime, independent enforcement, and live results are outside the experiment.

### Incomplete comparisons

- Qwen3.5, Granite 4.2 3B and RedSage remain unmeasured. The resumed Qwen3 8B transfer failed SHA-256 validation. The fresh pull matched the registry digest and was used for the completed Qwen3 arm. [Exact first-transfer error](results/qwen3-digest-mismatch.txt) · [Verified blob](results/qwen3-download-verified.json)
- The independent Cedar unit build was attempted against a byte-copied source snapshot with disposable fixture keys. Windows blocked the build scripts for icu_properties_data v2.4.0 and rustversion v1.0.23 with “An Application Control policy has blocked this file. (os error 4551)”. No Rust tests ran. The mock suite and historical Cedar reports remain distinct from that attempted build.

