# Offline re-analysis of saved outputs

No new inference or paid call was made. Stored raw responses were re-scored with the untouched frozen scorer and stored scores were verified.

Rubric: `role-contract-frozen+diagnostics-v1`. Manifest: `09b3639b388019655fbde0805a9abfbfa9c2136d58e96c94e789220ff93f8eb0`.

## Exact case-level accuracy (historical baseline)

| Arm | Passes | Rate | Wilson 95% CI | Invalid |
| --- | ---: | ---: | --- | ---: |
| SovereignEG/Qwen3.8-27B-FP8 | 72/80 | 90.00% | [81.49, 94.85]% | 0 |
| qwen2.5:7b | 18/80 | 22.50% | [14.73, 32.79]% | 0 |
| qwen3:8b | 28/80 | 35.00% | [25.45, 45.92]% | 0 |
| granite4.2:8b | 27/80 | 33.75% | [24.35, 44.64]% | 0 |
| llama3.1:8b | 23/80 | 28.75% | [19.99, 39.46]% | 0 |
| qwen2.5:1.5b | 5/80 | 6.25% | [2.70, 13.81]% | 0 |

## Canonical decision confusion (rows=truth, columns=prediction)

### SovereignEG/Qwen3.8-27B-FP8

label | supported | contradicted | abstain
--- | ---: | ---: | ---:
supported | 87 | 12 | 0
contradicted | 0 | 95 | 2
abstain | 0 | 0 | 60

macro F1 `0.950155`, weighted F1 `0.945205`, balanced accuracy `0.952723`.

### qwen2.5:7b

label | supported | contradicted | abstain
--- | ---: | ---: | ---:
supported | 62 | 16 | 0
contradicted | 25 | 48 | 6
abstain | 6 | 4 | 32

macro F1 `0.726069`, weighted F1 `0.712328`, balanced accuracy `0.721457`.

### qwen3:8b

label | supported | contradicted | abstain
--- | ---: | ---: | ---:
supported | 79 | 20 | 0
contradicted | 29 | 64 | 4
abstain | 5 | 7 | 48

macro F1 `0.761092`, weighted F1 `0.747086`, balanced accuracy `0.752591`.

### granite4.2:8b

label | supported | contradicted | abstain
--- | ---: | ---: | ---:
supported | 85 | 13 | 1
contradicted | 34 | 59 | 4
abstain | 5 | 4 | 51

macro F1 `0.774574`, weighted F1 `0.759341`, balanced accuracy `0.772278`.

### llama3.1:8b

label | supported | contradicted | abstain
--- | ---: | ---: | ---:
supported | 75 | 24 | 0
contradicted | 33 | 55 | 8
abstain | 3 | 7 | 50

macro F1 `0.722047`, weighted F1 `0.70425`, balanced accuracy `0.721275`.

### qwen2.5:1.5b

label | supported | contradicted | abstain
--- | ---: | ---: | ---:
supported | 84 | 6 | 9
contradicted | 66 | 20 | 11
abstain | 16 | 29 | 15

macro F1 `0.404303`, weighted F1 `0.41889`, balanced accuracy `0.43489`.

## Paired uncertainty and error categories

- **SovereignEG/Qwen3.8-27B-FP8 − qwen2.5:7b**: 67.50 pp (case 95% CI 56.25 to 77.50; family-cluster 95% CI 55.00 to 78.75); McNemar p=0.0.
- **SovereignEG/Qwen3.8-27B-FP8 − qwen3:8b**: 55.00 pp (case 95% CI 43.75 to 66.25; family-cluster 95% CI 43.75 to 66.25); McNemar p=0.0.
- **SovereignEG/Qwen3.8-27B-FP8 − granite4.2:8b**: 56.25 pp (case 95% CI 45.00 to 67.50; family-cluster 95% CI 43.75 to 68.75); McNemar p=0.0.
- **SovereignEG/Qwen3.8-27B-FP8 − llama3.1:8b**: 61.25 pp (case 95% CI 51.25 to 71.25; family-cluster 95% CI 47.50 to 75.00); McNemar p=0.0.
- **SovereignEG/Qwen3.8-27B-FP8 − qwen2.5:1.5b**: 83.75 pp (case 95% CI 76.25 to 91.25; family-cluster 95% CI 73.75 to 92.50); McNemar p=0.0.

Distinct error-bearing cases in SovereignEG/Qwen3.8-27B-FP8:

- `invalid_output`: 0
- `unsupported_affirmative`: 0
- `false_abstention`: 2
- `missed_abstention`: 0
- `missed_finding`: 8
- `incorrect_admission`: 0
- `incorrect_withholding`: 6
- `bad_citation`: 8
- `wrong_attribution`: 0
- `incomplete_chain`: 8
- `missing_items`: 0
- `duplicate_items`: 0
- `unknown_items`: 0

Repeats and agents are not independent cases. These numbers describe the saved retrospective cohort only; they are not a fresh blinded holdout or a production estimate.
