# ROE Contract Schema

## Overview

The Rules of Engagement (ROE) contract defines the authorized scope for a
pentesting engagement. It is signed by the operator and compiled into a
Cedar 4.14.0 policy set by TrustGate.

## Schema

```json
{
  "engagement_id": "uuid",
  "authorized_by": "operator name/signature",
  "scope": {
    "targets": ["10.20.0.0/24", "lab.kayan.local"],
    "allowed_techniques": ["recon", "web-app"],
    "forbidden_actions": ["exfiltrate_data", "destructive_payload"]
  },
  "time_window": {
    "start": "ISO8601",
    "end": "ISO8601"
  },
  "signature": "HMAC-SHA256 of canonical contract fields"
}
```

## Field Descriptions

| Field | Type | Required | Description |
|---|---|---|---|
| engagement_id | UUID | Yes | Unique engagement identifier |
| authorized_by | string | Yes | Name/signature of the authorizing operator |
| scope.targets | string[] | Yes | Authorized IP ranges (CIDR) or domains |
| scope.allowed_techniques | string[] | Yes | Permitted technique categories (recon, web-app, network, reporting) |
| scope.forbidden_actions | string[] | No | Explicitly forbidden actions (always denied) |
| time_window.start | ISO8601 | Yes | Engagement start time |
| time_window.end | ISO8601 | Yes | Engagement end time |
| signature | string | Yes | HMAC-SHA256 of canonical enforcement fields; public-key operator identity is not implemented |

## Optional descriptive engagement context

The intake contract accepts an optional `engagement_context` section with six string fields:
`company_size` (120 characters), `departments` (500), `infrastructure_summary`,
`network_architecture`, `data_storage`, and `customer_touchpoints` (1000 each).
All fields may be absent; unknown fields and non-string values are rejected.

**Descriptive only, zero policy weight.** This is a separate intake section, not
an addition to the Rust signed-ROE object above. `/engagement/start` accepts it
alongside the existing operator/owned-lab authorization fields. Python holds it
outside `self.roe`, supplies it only to Reporting's narrative framing, and labels
it as untrusted descriptive data. It is not included in signing, `load_roe`,
`/authorize`, `policy.rs`, `roe.rs` or any Cedar evaluation input. It does not
authenticate company facts or widen the fixed local-lab scope.

```json
{
  "operator_id": "Local operator",
  "authorization": "I_AUTHORIZE_OWNED_LAB",
  "engagement_context": {
    "company_size": "25 employees",
    "departments": "Operations and support",
    "infrastructure_summary": "Customer web application",
    "network_architecture": "Office network and hosted application",
    "data_storage": "Relational database",
    "customer_touchpoints": "Web portal"
  }
}
```

Phase 1 may separately read this same descriptive input to produce hypothetical
retrieval matches. That offline planning use performs no target access or policy
evaluation and supplies no execution authority.

## Compilation Rules

The ROE compiler turns the contract into a policy set:

1. **Permit rules:** One permit rule per (technique, target) pair. Each rule allows the corresponding agent role to execute the technique on the target, conditioned on engagement being active and time being in window.

2. **Forbid rules:** One forbid rule per forbidden action (from both the ROE and the default forbidden list). These always override permit rules.

3. **Default forbidden actions** (always included regardless of ROE):
   - exfiltrate_data
   - destructive_payload
   - social_engineering
   - modify_target
   - delete_data

4. **Default-deny:** Any tool call not matching a permit rule is denied.

## Technique → Agent Role Mapping

| Technique | Agent Role |
|---|---|
| recon | recon_agent |
| web-app | webapp_agent |
| network | network_agent |
| reporting | reporting_agent |
| planning | planner_agent |
| operator-status / operator-instruction | operator |
| agent-message | enrolled sender (checked by console bridge) |

## Signature Verification

The current local implementation authenticates the canonical contract with a shared HMAC key:
```
HMAC_SHA256(TRUSTGATE_ROE_KEY, engagement_id:authorized_by:scope_json:time_window_json)
```

integration/roe_signing.py and Rust roe.rs must use identical field order and compact UTF-8 JSON. The key comes from TRUSTGATE_ROE_KEY or ignored data/roe_signing_key. Never commit or print it. This authenticates a local shared-key holder, not the human identity in authorized_by; public-key operator identity is not implemented.
