use axum::{
    extract::State,
    Json,
    http::StatusCode,
};
use crate::models::{ROEContract};
use crate::policy::PolicyEngine;
use crate::roe;
use crate::AppState;
use crate::audit::AuditLog;

pub async fn load_roe(
    State(state): State<AppState>,
    Json(roe): Json<ROEContract>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // Verify signature
    if !roe::verify_signature(&roe) {
        return Err(StatusCode::BAD_REQUEST);
    }

    // Compile to policy set
    let policy_set = roe::compile_roe(&roe);

    let rules_compiled = policy_set.rules.len();
    let forbidden: Vec<String> = policy_set.forbidden_actions.iter().cloned().collect();

    // Load into policy engine
    {
        let mut pe = state.policy_engine.write().await;
        pe.load_policy_set(policy_set).map_err(|_| StatusCode::BAD_REQUEST)?;
    }

    // Audit the ROE load
    {
        let mut audit_log = state.audit_log.write().await;
        audit_log.append(serde_json::json!({
            "engagement_id": roe.engagement_id,
            "agent_id": "system",
            "agent_role": "system",
            "tool_name": "roe_load",
            "tool_args": {"authorized_by": roe.authorized_by},
            "target": "engagement",
            "technique": "roe_load",
            "decision": "ALLOW",
            "reason": format!("ROE loaded and compiled: {} rules", rules_compiled),
            "provenance": {},
        }));
    }

    Ok(Json(serde_json::json!({
        "status": "loaded",
        "engagement_id": roe.engagement_id,
        "rules_compiled": rules_compiled,
        "forbidden_actions": forbidden,
    })))
}
