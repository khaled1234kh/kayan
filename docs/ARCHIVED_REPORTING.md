# Archived Reporting

21 November 2026

Open the console and select **Reporting → Archived Reporting**. The built-in Slate assessment uses completed synthetic source records and execution outcomes from the existing reviewed fixture. This review does not start an assessment. Legacy assessment exports lack the admission-v2 custody and review inputs and are not accepted by this route. The existing five-agent workflow and its local Reporting path retain their original settings.

## Run locally

```powershell
.\Start-Kayan.ps1 -Component Gate
.\Start-Kayan.ps1 -Component Review
python -B -m console.backend.authorize_archived_reporting
```

Open [the operations floor](http://127.0.0.1:5173/). With the Reporting agent selected, expand **Archived Reporting**, choose **Local evidence report** and click **Run Reporting**. The local operator command grants only report writing for the fixed synthetic case for 30 minutes. If the window expires, the saved result remains viewable and exportable.

## Evidence and cloud behavior

Reporting pins the archive bytes, resolves review records in the fixed case and calls admission v2. The synthetic T1486 finding is supported by E1.1 and E2.1. Admission withholds T1490 for missing independent attribution. Synthetic receipts exercise the verifier under fixture assumptions.

The SovereignEG option is disabled unless the operator sets `KAYAN_REPORTING_APPROVED_SHA256` to the exact generated scope digest before starting the backend. It also requires a separate Reporting-only ROE permitting inference as well as report writing, the configured key supplied through `SOVEREIGNEG_API_KEY`, and confirmed Student allowance controls. The app never signs or loads that ROE. TrustGate decides both actions before the one-shot request is reserved. The approved scope cannot be reused after the provider attempt is recorded.

SovereignEG can select and prioritize verified quotations and defensive controls. The server renders the selected material with the underlying source identifiers and ATT&CK title. Admitted findings, withheld hypotheses and coverage limits always come from the deterministic path. The feature intentionally uses extractive explanations and reviewed templates because an address allowlist cannot validate arbitrary model-written claims. Empty, malformed, truncated, mismatched and out-of-scope responses produce a clearly marked local fallback.

## Occurrence-aware selection

For repeated techniques, a versioned payload gives each admitted finding and excerpt a request-local alias. Withheld occurrences contribute only an alias and technique ID. The payload binds an opaque digest of the assessment and evidence revision. The server resolves each permitted selection back to its original source address and occurrence. It rejects duplicate JSON fields, duplicate selections, legacy-style IDs in the new format, and unknown or withheld IDs.

The backend reloads the verified archive and rechecks the exact grant after the egress decision and before provider setup. It checks again before publishing the response. In mocked tests, changes detected before provider setup left the grant unspent. An in-flight change still consumed the one attempt and prevented publication of the stale cloud result. These checks do not form an atomic lease across the local custody store and the provider. Two competing app instances sharing one attempt directory made exactly one mock request.

The legacy Slate digest is unchanged. The occurrence-aware payload requires separate approval for its digest, provider and spending boundary. The tests used only synthetic archives and mock transport.

## Verification

- Actual browser interaction on the existing 3D console used the running FastAPI app, the real Rust/Cedar gate and a mocked SovereignEG HTTP response. The panel rendered the model label, E1.1 and E2.1, T1486, the withheld T1490, and the export link. The HTTP view and download matched the saved mock report. No external provider call was sent. TrustGate audit entries were `6e0f6b80-ec6e-40c9-afb5-6ba8eb870940` for report writing and `b03cc325-2ca8-40d3-a89c-e9a0812e0a0f` for inference. Saved report SHA-256 `43d2a2bfe47d5d541515dfa0f55bfffad364c3bb4680e95e2033dc17dcb547c3`. Evidence is under `.build/reporting-ui-verification/`.
- 144 targeted Python tests and 28 Rust tests passed. The frontend production build, session panel check and 14 transport checks passed. Go `pkg/trustgate` passed. Windows Application Control blocked the compiled `pkg/tools` test process, so it has no test result in this pass.
- The normal console was restarted, local Reporting saved one supported and one withheld item, and the cloud execution control was disabled. All 71 historical digests and five admission-verifier source digests matched.

## Real smoke test completed

On 21 November 2026, the owner authorized exactly one Reporting request for `synthetic-slate-reporting`, scope SHA-256 `0173f8049d8c4190487ac75f321d976dce58c9b557005dc5a1c2dbfece7d0fb0`, on SovereignEG Qwen3.8-27B-FP8. The authorization allowed up to 1 EGP through the Student allowance only. Balance fallback and paid overages showed off before and after the run.

One click in the 3D console sent one approved request. TrustGate allowed report writing (`ad746f80-a061-44d1-bdbd-2d76e4382af9`) and inference (`35e25ab4-7cc4-4cd3-bc49-3556e2e17699`). SovereignEG returned HTTP 200, request ID `req_jNZbbEdvOHtAH-0M_ow9U`, a normal stop and a valid selection of E1.1, E2.1 and both defensive controls. It used 260 uncached input tokens, 62 output tokens, zero reasoning tokens and 0.906 seconds measured by the app. Catalogue-rate equivalent was 0.00192 EGP. The response did not itemize a charge.

The rendered report showed T1486 admitted and T1490 withheld for missing independent attribution. Browser export was exercised and the downloaded HTTP response matched the persisted report byte for byte (SHA-256 `47d450040b5bb52f4447700c58491f03b2b2cd5363a65236686225d42105da28`). The screenshot, export and redacted provider exchange are in `.build/reporting-live-smoke-2026-11-21/`. The standard backend and local-only Reporting permission were restored. The one-call approval is consumed.
