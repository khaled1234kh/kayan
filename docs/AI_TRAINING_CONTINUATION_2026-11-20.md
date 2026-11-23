# Continuation plan — training a model on MITRE ATT&CK STIX

**Current decision, 20 November 2026.** Fine-tuning and cloud inference remain deferred. Start with the [matched retrieval ablation and independent-review checkpoint](ATTACK_MAPPING_ABLATION_2026-11-20.md) and the [security record](CLOUD_PIVOT_SECURITY_AND_EVAL.md). The plan below is preserved as a conditional historical proposal.

**Status: planned, not started. Written 2026-11-20.** This is the handoff for the agent continuing after the cloud/parallel AI layer was implemented. Read [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) first for what already exists.

## 0. Decision to make first: is training actually needed?

Fine-tuning is **not** a default next step; it is a hypothesis to test. Before spending GPU time:

1. Freeze an evaluation set (section 3) and measure the current RAG + SovereignEG 27B and the local baselines.
2. Identify a concrete failure that RAG does not fix (e.g. systematic technique-ID confusion, evidence-mapping errors, schema violations).
3. Train only against that failure, then re-run the **same** harness. If there is no measurable gain, keep RAG-first and record the negative result.

Training does not replace retrieval. ATT&CK is updated quarterly; a fine-tuned model has a knowledge cutoff, so RAG remains the source of current technique facts.

## 1. Source data — the local STIX zip

`<LOCAL_USER>\Downloads\attack-stix-data-master.zip` (252 MB) contains official MITRE `attack-stix-data` bundles:

| Domain | Files | Latest in zip |
|---|---|---|
| Enterprise | `enterprise-attack/enterprise-attack-<version>.json`, 1.0 → 20.1 plus `enterprise-attack.json` | 20.1 — `enterprise-attack-20.1.json`, 53,982 KB |
| Mobile | `mobile-attack/mobile-attack-<version>.json`, 1.0 → 20.1 | 20.1 — 6,000 KB |
| ICS | `ics-attack/ics-attack-<version>.json`, 8.0 → 20.1 | 20.1 — 5,167 KB |

The live RAG currently downloads `enterprise-attack.json` from GitHub, which matches the 20.1 size above. For training, **pin a version** (20.1) from the local zip instead of the moving `master` file, and record the SHA-256 of every file used.

Steps:
1. Extract with Python `zipfile` to an ignored directory (e.g. `data/stix/attack-stix-data/`; add to `.gitignore`). Do not commit the 252 MB zip or extracted bundles.
2. Verify `index.json`/`CHANGELOG.md` in the archive to confirm the version mapping; do not assume the highest number is newest without checking.
3. Add a `local_stix_path` option to `config/ai.json` and `ai/config.py` so `ai/mitre/stix.py::load_techniques()` prefers the local pinned file and falls back to the URL. Keep the version and hash in the RAG status/response for provenance.
4. Extend `ai/mitre/stix.py` if Mobile/ICS are needed. The current parser uses `x_mitre_detection`, `kill_chain_phases` and `course-of-action` `mitigates` relationships; those exist in all three domains. Filter by `x_mitre_domains`/domain matrix rather than merging everything blindly.

## 2. Build an instruction dataset (not raw text dumping)

Create `ai/training/build_dataset.py` and `ai/training/__init__.py`. Output JSONL under an ignored `data/training/` directory.

For each current (non-revoked, non-deprecated) `attack-pattern` object, emit several instruction pairs using only fields present in the STIX object:

- **ID → detail:** "What is ATT&CK technique T1059.001 and how is it detected?" → name + description + detection + mitigations + tactics + source URL.
- **Behaviour → mapping:** take a behaviour phrase from `description`/`detection` and ask for the technique ID/tactic; answer only with IDs verified present in the dataset.
- **Detection/mitigation → technique:** reverse direction from `x_mitre_detection` and mitigation names.
- **Uncertainty/negative cases:** prompts with insufficient evidence must answer "insufficient evidence; no technique ID can be confirmed" — never force a guess.

Rules:
- Keep `external_references` (`mitre-attack` `external_id`, `url`) as provenance metadata in every record: STIX id, ATT&CK ID, version, source URL, file hash.
- Hold out a **technique-disjoint** test split (by ATT&CK ID, not random lines) so the model cannot memorise IDs it saw in training. Log the split counts and IDs.
- Include previously measured hard cases (e.g. T1059.001 PowerShell vs T1546.013 PowerShell Profile) as a small stress slice, clearly labelled.
- Do not put the API key, engagement text, lab target details or any secret into the dataset.

## 3. Freeze the evaluation harness BEFORE training

Create `eval/ai_benchmark.py`. The same cases and scorer must run for every candidate:

- `qwen2.5:7b` (Ollama), `qwen3:8b`, `granite-4.2-8b` (local baselines where available), `SovereignEG/Qwen3.8-27B-FP8` (cloud), RAG-only, and any fine-tuned candidate.
- Metrics recorded **separately**: exact contract pass %, technique-ID exact match / micro-F1, evidence-mapping F1, unsupported-ID rate, latency (p50/p95), and token cost (including `reasoning_tokens`).
- Never collapse the prior external figures into one ranking: Qwen2.5 7B `22.5%` exact contract passes, Qwen3 8B `35%` exact contract passes, Granite 4.2 8B `0.762` evidence-mapping F1 measure different things.
- Save raw outputs, prompts, model/version/config hashes and the split manifest under `eval/reports/ai_benchmark_<date>/`.

## 4. Environment / hardware reality (checked 2026-11-20)

- GPU: **NVIDIA GeForce RTX 5060, 8,151 MiB** (`nvidia-smi` works).
- Installed torch: `2.6.0+cpu`, `torch.cuda.is_available() == False`. A CUDA build is required before training.
- Install (in a virtualenv or the project env): CUDA-enabled `torch`, plus `peft`, `trl`, `bitsandbytes`, `datasets`, `accelerate`. Re-check `torch.cuda.is_available()` and `nvidia-smi` memory before starting.
- Realistic target: **4-bit QLoRA on a 7–8B open model** (e.g. Qwen2.5-7B-Instruct obtained with the appropriate licence), small per-device batch (1–2), gradient accumulation, LoRA on attention projections. Full fine-tuning of 27B or training the SovereignEG cloud model is out of scope and impossible with this setup.
- Store adapters under an ignored local directory (e.g. `data/models/`). Add to `.gitignore`. Do not publish model weights or the dataset if licensing/attribution is unclear.

## 5. Train, compare, decide

1. Train QLoRA adapters with a fixed seed and logged hyperparameters; validate on the held-out val split; stop on the pre-registered metric, not by eyeballing samples.
2. Run `eval/ai_benchmark.py` unchanged for the fine-tuned candidate and the frozen baselines.
3. Adopt the adapter only if it improves the targeted metric **and** does not increase unsupported technique IDs or break the agent JSON schema. Otherwise keep RAG-first and record the negative result in the same report.
4. Re-run `python -B -m pytest tests -q -p no:cacheprovider` and the full `/ai/assess` HTTP flow after any source change.

## 6. Non-negotiable boundaries

- TrustGate remains authoritative: fine-tuning never grants permissions; every sensitive action still needs an independent Gate ALLOW. No model gets tool/scope/approval authority.
- Human approval still required for destructive/high-impact actions. This AI layer performs analysis only; no live target testing.
- No secrets in datasets, prompts, logs, reports or git. `.env`, `data/mitre/`, `data/stix/`, `data/training/`, `data/models/` must be git-ignored. Check `git status` before staging.
- Preserve every historical result and negative finding in `MASTER_HANDOFF.md`, especially "no grounding improvement was demonstrated". A new RAG sanity check is not a grounding benchmark.
- Do not claim the cloud 27B was trained, that a local model beat it, or that training improved accuracy without the frozen harness output. No result number without a fresh run or an explicit historical label.

## 7. Definition of done for Phase B

- [ ] Decision recorded (train or not) with the failure it addresses.
- [ ] Local pinned STIX source wired into RAG with version + hash provenance.
- [ ] Dataset builder + split manifest + sample JSONL reviewed.
- [ ] Evaluation harness frozen, raw outputs saved for all candidates.
- [ ] CUDA environment verified; QLoRA adapter trained if the decision was to train.
- [ ] Comparison report with honest conclusion (gain, no gain, or blocked).
- [ ] `MASTER_HANDOFF.md`, `TODO.md`, `docs/AI_ARCHITECTURE.md` and evidence updated; tests green.
