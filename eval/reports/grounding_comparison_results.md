# Grounding off/on comparison

This deterministic harness receives retrieval context but does not use an LLM to alter tool selection or payloads. Equal outcomes demonstrate wiring, not a grounding effectiveness improvement.

| Condition | Findings | Allowed | Denied | MITRE lab coverage | Evidence precision |
|---|---:|---:|---:|---:|---:|
| grounding_off | 9 | 9 | 0 | 100.0% | 25.0% (1/4) |
| grounding_on | 9 | 9 | 0 | 100.0% | 25.0% (1/4) |

Existing tracker includes declared techniques and has five lab categories; finding-only coverage uses the six existing reporting labels. Neither is coverage of all ATT&CK.

Evidence precision validates the captured raw response against explicit lab criteria. General classification accuracy is unmeasured; informational findings are excluded.