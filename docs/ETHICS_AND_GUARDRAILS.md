# Authorized local-lab boundary — checked 2026-11-01

The live MVP only executes its bounded catalogue against the owned http://127.0.0.1:8888 lab. It requires a successfully authenticated ROE load before starting the model loop. A model cannot register an arbitrary shell command, payload or destination through this catalogue.

The Python live engine authorizes each model/tool operation and delivered operator/agent message through the Rust gate. The upstream Go adapter currently gates flow-start inference permission and each executor dispatch; it does not yet authorize every upstream model call individually. Do not describe these as equivalent coverage. Unknown actions, forbidden actions, expired/missing ROEs and out-of-scope destinations are denied. The local process and signing-key holders remain trusted; these boundaries are not remote multi-user authentication or proof against arbitrary host compromise.

The Go local profile accepts only operator-signed, exact owned-lab command templates. A model proposal selects a template; executable fields are reconstructed from that independently signed authority. The original proposal and target-output source IDs remain untrusted audit data. Unsupported commands and repeated intents are refused; reloaded flows with unknown history cannot execute environment tools. This is a bounded template dispatcher, not general semantic taint tracking. External function registrations are disabled so they cannot replace non-executing workflow handlers.

Explicit ROE workflow permission allows untrusted bodies as non-executing planning/delegation/result text. That exception never grants trust to a target or execution argument. Child tool dispatches still pass the same gate and signed menu. UI badges must not imply that a model's entire context became trusted.

Only candidates reproduced with a fresh second request are published as verified by the live harness. XSS evidence is raw HTML script reflection, not a browser execution test. Path traversal uses an agent-created nonsecret lab fixture. No real credentials or sensitive files are used as proof by the live catalogue. The older baseline has false-positive detectors and remains labeled separately.

Audit records are hash-chained and HMAC-signed in a mutable file. Describe this as tamper-evident evidence, not immutable storage. Preserve raw reports, failed attempts and zero-finding results; do not turn model narrative into verified facts or hide an adverse evaluation result.

The proposal's historical incident narrative was not independently established by this implementation pass and is not asserted here as a verified event.

Open lifecycle backlog: engagement completion does not revoke the loaded ROE. Time expiry is enforced, but some older fixtures use a 2099 end time. The new Go comparison issuer uses a short explicit window (30 minutes in the evaluator); that bounds expiry but is not completion revocation. Do not claim immediate revocation until a tested lifecycle hook exists.
