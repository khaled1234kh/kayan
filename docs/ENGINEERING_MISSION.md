# KAYAN TrustGate engineering mission

KAYAN aims for dependable coordination across Planner, Recon, Web-App, Network and Reporting, with independent enforcement and auditable evidence. The [acceptance matrix](ENGINEERING_ACCEPTANCE.json) records what each subsystem must demonstrate and the scope of its current evidence. The [proposal](TA_PROPOSAL_REPORT.md), [research update](RESEARCH_UPDATE.md) and [master handoff](../MASTER_HANDOFF.md) record the requirements and research history.

## Standing criteria

- Keep signed rules of engagement, Rust/Cedar authorization, review, evidence admission and execution independent of model output. Preserve action-specific decisions, restricted scope and auditable outcomes.
- Measure task selection, dependency correctness, recovery, loops and unnecessary operations for Planner. Measure grounded observations, attribution, coverage and false claims for specialists. Measure admitted findings, evidence-group completeness, withheld claims and recommendation fidelity for Reporting.
- Compare shared local, role-specific and hybrid configurations under a matched protocol. Measure task accuracy, safety, abstention, latency, token use, resource use and cost separately. Keep development families separate from held-out cases, preserve negative results and report uncertainty. Base decisions about training on observed failure modes.
- Prefer source verification, occurrence and attribution checks, applicable adverse evidence and explicit abstention. Admission v2 retains its signed-off authority. Preserve the distinction between verifying submitted proof and generating proof.
- Keep a local working baseline. Require bounded requests, explicit egress approval, effective spend controls and accurate provider attribution. The standing mission authorizes zero live cloud requests. Historical one-shot permissions have their own scope.
- Verify security, correctness, operational, cloud, evaluation, reliability, academic and production criteria individually. Record which evidence is synthetic, owned-lab, historical, operational or independently validated. Real telemetry still requires separate approvals and custody.

## Checkpoint

The authorized repository's Go CI branch head is `06e5f12`. [Ubuntu CI](https://github.com/khaled1234kh/kayan/actions/runs/44919189760) executed 180 tools tests and 10 TrustGate tests with zero failures and the existing live Cedar skip. The local checkout also contains unpublished Reporting, evidence, research and UI work. Keep that work intact and stage reviewed source and fixtures explicitly.

The verified local report is now saved atomically with the one-shot Archived Reporting reservation. An interrupted mocked request previously left the result and export unavailable after an application restart. Reopening the same evidence revision now recovers the local report and preserves the consumed approval. The test uses the FastAPI route with a synthetic gate and in-memory HTTP transport.

New cloud selections persist validated finish reason, input/output/reasoning tokens and measured provider latency. Malformed or out-of-budget token usage yields the existing local fallback. The full console ASGI check recovered and exported the fallback after an injected interruption, with the original Slate request digest and a single mocked attempt. Historical reports retain their original metadata.

The next coding task is to add an end-to-end request deadline to Archived Reporting and test recovery when individual transport operations progress but total runtime exceeds the deadline.
