# Experiment D manifest integrity investigation

**20 November 2026.** The saved revision 1 manifest contains one extra ASCII `a` at zero-based byte offset **286**, inside its materialization-source digest. This made the stored digest 65 hexadecimal characters long. Deleting that one byte **in memory** recovered the exact previously authorized manifest SHA-256. The origin of the write was not established. The original file and its failed audit remain preserved. Experiment D has zero model generations. [Saved manifest](../eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.json) · [Failed preflight evidence](../eval/reports/attack_diagnostics_d_v3_20261120/manifest-r1-failed-preflight-evidence.json)

## Source calculation and root cause

Both original commands call `build_manifest()`. Its source stamp comes from `sha(Path(__file__))`, whose implementation is `sha256(path.read_bytes()).hexdigest()`. The hash directly binds only the complete raw bytes of `eval/attack_experiment_d_v3.py`. That file was 9,494 bytes, UTF-8, with LF line endings and a terminal newline. The hash includes comments, whitespace and all definitions. Imported files do not contribute directly to it. The builder independently checks the frozen v2 registration, source and data pins, and the archived A and B/C inputs. [Frozen D builder](../eval/attack_experiment_d_v3.py) · [SHA helper and JSON writer](../eval/attack_experiment_v2.py)

The original preparation path writes UTF-8 JSON with two-space indentation, ASCII escaping and one terminating LF. The original audit rebuilds the same bytes and compares the complete file byte for byte. The stored and actual source digests are:

| Evidence | Value |
| --- | --- |
| Saved malformed stamp | `39e59cfa52f7461e70612cc3344c775405ae9d455bade4a04f32b1973b5cef1e4` |
| Actual SHA-256 of the source file and recovered authorized stamp | `39e59cfa52f7461e70612cc3344c775405ae9d455bade404f32b1973b5cef1e4` |

The raw manifest had 53,934 bytes. Removing byte `0x61` at offset 286 produced 53,933 bytes identical to a fresh canonical rebuild. The fresh bytes matched the prior stakeholder's authorized SHA-256. This is a saved-byte integrity defect. Reproduction gives no evidence of source changes, serializer nondeterminism, dependency drift or a hash-calculation bug. The original audit correctly rejected the defective file.

## Corrected artifact and independent comparison

| Manifest | SHA-256 |
| --- | --- |
| Original authorization and exactly recovered bytes | `c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba` |
| Original file as preserved on disk | `cc7ec23535c18f7e4cc66faa5c3ca8b757d52e8abd2e5cea3eaf658e6ed690cc` |
| Corrected manifest revision 2 | `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1` |

The corrected source stamp uses the **same raw-file SHA-256 calculation**. The offline revision builder validates digest shape and requires exact canonical recovery of the caller-supplied original authorization hash by a unique one-byte deletion inside the malformed stamp. The new artifact separately records revision and integrity lineage. Its audit compares exact bytes. The original audit and materializer remain intact. [Corrected manifest](../eval/reports/attack_diagnostics_d_v3_20261120/incident-facts-first-manifest.r2.json) · [Revision audit implementation](../eval/attack_experiment_d_integrity_v3.py)

An independent verification deleted the documented byte in memory and checked that byte stream against the original authorization. It then compared the recovered JSON with revision 2 after removing just the two integrity metadata fields. All inherited fields and **12/12 ordered entries** matched, including D1/D2 prompt strings, D3 templates, substitutions, reference objects, schemas, model identity, order and settings. The materialization source matched the recovered digest. The four recovered and revised D3 templates also agreed in **16/16** fixture comparisons across a valid empty extraction, execution failure, malformed extraction and unknown address. The frozen tests separately exercise valid fact transfer and overflow fallback. The scorer and protocol stay at their original versions. This is an artifact integrity revision, with identical experimental semantics.

## Audit results and authorization

The new revision audit passed with v2, A and B/C checks intact. The original failed preflight reproduced and is archived under SHA-256 `da372cdc4e560b59d47359cfb3e1ab5bd9b5cc218c0c933569d1795a85ff0feb`. **65 relevant tests passed in 9.12 seconds.** Read-only local status matched the pinned Ollama 0.40.13 and Qwen2.5 7B digest, with SovereignEG disabled. The original human-gated confirmation and D run directories remained absent.

```powershell
python -B -m eval.attack_experiment_d_integrity_v3 audit --prior-authorized-sha256 c77835b4f0c42afa461f90d053c40cd3c27452aeebccba2c59478e0fb72757ba
python -B -m pytest tests/test_attack_experiment_d_integrity_v3.py tests/test_attack_experiment_d_v3.py tests/test_attack_evidence_guard_v3.py tests/test_attack_evidence_v2.py -q -p no:cacheprovider
```

> I authorize Experiment D only under `attack-diagnostics-v3.0` using manifest revision 2 with SHA-256 `eee6d99987a304d55fb565b24bab3a10b64efbe6aa7f4ac9c68ef9c4d200d0b1`. Execute exactly 12 local Qwen2.5 7B generation attempts, once in manifest order, after the revision audit, exact file hash check, historical integrity and local runtime checks pass. Use the frozen D3 materialization and explicit failure fallback. Retain raw requests, responses, hashes, errors and scores. Scope ends with the exploratory report. No retries, replacements, external inference or other experiments are authorized.
