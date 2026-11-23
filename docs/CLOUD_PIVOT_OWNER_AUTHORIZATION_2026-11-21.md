# Project-owner authorization for the SovereignEG diagnostic

21 November 2026 · Source is the project-owner authorization supplied directly in this Codex task.

The project owner attested that the exposed SovereignEG key was revoked, a replacement is available, automatic balance use is disabled, account spending caps are configured and the replacement file was moved outside the Git repository. These are dated owner attestations. The account settings, current file location and provider capabilities have independent preflight checks.

| Approved item | Scope |
| --- | --- |
| Provider and destination | SovereignEG, `https://backend.sovereigneg.com/v1` |
| Exact model | `SovereignEG/Qwen3.8-27B-FP8` |
| Comparison manifest SHA-256 | `c3713861ca304a9ed7c84c3629684865eba517f650860087d2c0d700d7b7c840` |
| Frozen bundle SHA-256 | `7701b717960ec8806ce7eaaea1d4417825fb748d009cd6cd2d042da8b7338e53` |
| Requests | 12 diagnostic inference requests, plus at most one separately identified capability probe. Authenticated metadata used as a capability check counts toward that allowance. |
| Spend | Total ceiling of 20 EGP, including the probe and all charges associated with the experiment. |
| Permitted data | Exact frozen synthetic observations, hypotheses and ATT&CK references. Any probe must use synthetic, nonsensitive content. |
| Prohibited data and operations | Real telemetry, private assessment records, credentials in model inputs or artifacts, custody approvals, private ledgers, scoring keys, other unapproved material, and unrestricted cloud use. Production deployment, public route activation, live penetration testing, fine-tuning, additional experiments, paid upgrades and increased TrustGate authority are prohibited. |

Execution is conditional on confirming the replacement file is outside the checkout and credentials remain unstaged and undisclosed. Verify account-side spend enforcement and actual pricing, record the secondary local budget and request-count controls, and confirm approved routing, model identity and schema support. The exact bundle and synthetic-only scope must match. Stop on an authorization, cost, routing or privacy violation. Preserve errors without retry or substitution. The current authorization covers the exact scope above. Material changes require new approval. [Preflight outcome](CLOUD_PIVOT_REAL_EXECUTION_RESULTS_2026-11-21.md)
