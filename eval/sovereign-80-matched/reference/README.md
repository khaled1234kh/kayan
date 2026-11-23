# KAYAN TrustGate offline benchmark workspace

Start with the [doctor's briefing](DOCTOR_BRIEF.md), [the measured results](RESULTS.md) or [the frozen protocol](PROTOCOL.md). The original KAYAN repository, audit files and session remain in their own location. This workspace is the isolated pilot.

| Evidence | What to open |
|---|---|
| Model cases, output schemas and ground truth | [Frozen manifest](data/roles_frozen.json), [scorers](role_cases.py), [scorer tests](test_roles.py) |
| Five held-out checkpoint results | [CSV](results/role-comparison-final-v1/summary.csv), [paired statistics](results/role-comparison-final-v1/summary.json), [exact-pass chart](results/role-comparison-final-v1/exact-passes.svg), [latency chart](results/role-comparison-final-v1/inference-p95.svg) |
| Raw first/final outputs and telemetry | [Qwen2.5 7B](results/qwen2_5-7b/heldout/cases.jsonl), [Llama 3.1 8B](results/llama3_1-8b/heldout/cases.jsonl), [Qwen2.5 1.5B](results/qwen2_5-1_5b/heldout/cases.jsonl), [Granite 4.2 8B](results/granite4_2-8b/heldout/cases.jsonl), [Qwen3 8B](results/qwen3-8b/heldout/cases.jsonl) |
| Shared versus calibration-selected role models | [Final selection](results/specialization-final-v1/selection.json), [paired replay](results/specialization-final-v1/summary.json) |
| Dependency scheduler and mock security | [Methods](WORKFLOW.md), [timed rows](results/workflow-pilot-v1/workflow-raw.jsonl), [security decisions](results/workflow-pilot-v1/workflow-security.json), [graph coverage](results/workflow-coverage-v1/summary.json) |
| Real one-slot scheduling and model switching | [Methods](INTEGRATED_SCHEDULING.md), [shared Qwen](results/integrated-qwen-v1/summary.json), [shared Llama](results/integrated-llama-v1/summary.json), [shared Granite](results/integrated-granite-v1/summary.json), [shared Qwen3](results/integrated-qwen3-v1/summary.json), [fixed Qwen/Llama mix](results/integrated-fixed-routing-v1/summary.json), [fixed Granite/Llama mix](results/integrated-granite-routing-v1/summary.json) |
| Real one-/two-slot serving comparison | [Statistics](results/serving-comparison.json), [scheduled comparison](results/integrated-slots-v1/summary.json), [reversed order](results/integrated-slots-reversed-v1/summary.json), [one-slot raw](results/serving-one-slot/pairs.jsonl), [two-slot raw](results/serving-two-slots/pairs.jsonl) |
| Deterministic and real-model ATT&CK pilots | [Deterministic pilot](GROUNDING_PILOT.md), [real-model mapping](results/grounding-model-qwen-v1/summary.csv), [snapshot comparison](results/grounding_snapshot_v20_1/grounding_holdout_summary.json), [label review](results/grounding-label-review-v1/comparison.json), [chart](results/grounding-model-qwen-v1/mapping-f1.svg) |
| Test and build evidence | [Python checks](results/python-validation-final.log), [Cedar build failure](results/cedar-unit.log) |

Python 3.12 and Ollama 0.40.13 were used. The core benchmarks and plot generation use the standard library, with optional psutil for RAM telemetry. Start the separate research server when reproducing. Its Windows launcher uses PowerShell 7.4 or later. On the recorded host, Vulkan succeeded after the initial CUDA smoke timed out.

```powershell
python -B -m unittest -q test_roles test_analysis test_workflow test_grounding test_grounding_model test_integrated_defensive test_integrated_switching test_integrated_slots
python -B stage_models.py
.\Start-ResearchOllama.ps1 -Slots 1
```

The package excludes model weights, partial downloads, build caches, active download logs and a server log that recorded signed download URLs. Raw local logs remain in the research workspace. Existing Ollama models or separately downloaded official packages are needed to generate new model outputs. The archived outputs can be inspected and re-scored without starting Ollama. In a fresh extraction I reran 37 tests, re-scored all five held-out model arms and reproduced the paired intervals, replayed the deterministic ATT&CK snapshot comparison and reran the Planner rule control. [Extraction check](results/extracted-final-validation.log) The original project documents are local provenance references. Their hashes are archived in `results/source-doc-hashes.json`. The source snapshot under `reference-grounding` includes the upstream attribution and license files. The `reference-gate` snapshot contains source only, with no private keys or audit records.

