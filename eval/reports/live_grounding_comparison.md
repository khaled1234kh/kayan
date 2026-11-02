# Real local-Qwen grounding off/on comparison

One bounded assessment per condition with the same Qwen2.5:7b model, temperature 0, role contracts, lab and tool catalogue. No model/tool mocks. Both include the same live status question, queued instruction and deliberately target-tainted input probe.

| Condition | Findings | Allowed | Denied | Existing MITRE tracker coverage | Fresh-nonce reproduction |
|---|---:|---:|---:|---:|---:|
| Off | 1 | 23 | 1 | 20% | 1/1 (100%) |
| On | 0 | 23 | 2 | 0% | N/A (0 findings) |

Off engagement: e5122eda-87d3-44ce-ae9e-3ec719715855. On engagement: 58e65511-41de-4a3b-9904-cc384a6caeab.

Allowed/denied counts come from the Rust audit endpoint after assessment and status response; ROE-load entries are excluded. Counts include model inference, tools, verification, governed messages and report authorization. They are not comparable to the deterministic baseline's tool-only authorization counts.

Primary coverage reuses EngagementOrchestrator._compute_mitre_coverage against the saved actual findings. Live agents declare no preset MITRE lists, so off covers T1190 (1/5 lab categories, 20%) and on covers none (0%). The existing assess_finding_evidence rubric also returns off 1/1 (100%) and on N/A; classification accuracy remains null. These functions were replayed against persisted evidence without repeating the engagement. Secondary tool-result coverage is 60% for both (3/5 distinct catalogue labels): off T1046/T1190/T1592; on T1046/T1590/T1592. Neither metric measures all ATT&CK.

Off reproduced a reflected-XSS HTML script marker twice. Browser execution was not checked. On produced zero findings: the Web-App model proposed a retrieved skill packet ID (`testing-for-xss-vulnerabilities-with-burpsuite`) as a tool. Cedar denied the unregistered action, the bounded specialist loop stopped, and no vulnerability test executed for that role. The second on-condition denial is this proposal; the other denial in both runs is the deliberately tainted operator-input probe.

This result does not show a grounding benefit; it exposes an action-selection/continuation weakness. Do not replace it with the earlier deterministic 9-finding comparison or claim a higher accuracy. Blinded classification accuracy remains unmeasured.

Live WebSocket snapshots observed: off 158, on 152; both contained multiple nonempty incremental output states. All five per-agent session endpoints returned populated transcripts, the instruction received a safe-boundary delivery receipt, and the status question received an actual model reply.

Model calls with retrieved ATT&CK/OWASP context: off 0, on 9. Full per-run artifacts: live_grounding_off.json and live_grounding_on.json. Visual acceptance remains unverified.
