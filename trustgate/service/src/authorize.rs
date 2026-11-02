use axum::{
    extract::State,
    Json,
};
use crate::models::{ToolCallRequest, AuthorizeResponse};
use crate::policy::PolicyEngine;
use crate::taint::TaintTracker;
use crate::audit::AuditLog;
use crate::AppState;
use std::sync::Arc;
use tokio::sync::RwLock;

pub async fn authorize(
    State(state): State<AppState>,
    Json(request): Json<ToolCallRequest>,
) -> Json<AuthorizeResponse> {
    let mut audit_log = state.audit_log.write().await;
    let policy_engine = state.policy_engine.read().await;

    // Convert provenance to string map
    let prov_str = request.provenance.clone();

    // Taint check
    let taint_tracker = TaintTracker::new();
    let decision_prov = crate::policy::decision_provenance(&request.tool_name, &request.technique, &prov_str);
    let (taint_safe, taint_reason, _) = taint_tracker.check_tool_call(&decision_prov);

    if !taint_safe {
        let entry = audit_log.append(serde_json::json!({
            "engagement_id": request.engagement_id,
            "agent_id": request.agent_id,
            "agent_role": request.agent_role,
            "tool_name": request.tool_name,
            "tool_args": request.tool_args,
            "target": request.target,
            "technique": request.technique,
            "decision": "DENY",
            "reason": taint_reason,
            "provenance": prov_str,
        }));

        return Json(AuthorizeResponse {
            decision: "DENY".to_string(),
            reason: taint_reason,
            policy_id: None,
            audit_entry_id: entry.entry_id,
            timestamp: chrono::Utc::now().to_rfc3339(),
        });
    }

    // Policy evaluation
    let context = std::collections::HashMap::from([
        ("engagement_active".to_string(), serde_json::Value::Bool(true)),
        ("time_in_window".to_string(), serde_json::Value::Bool(true)),
    ]);

    let (decision, reason, policy_id) = policy_engine.evaluate(
        &request.engagement_id,
        &request.agent_role,
        &request.tool_name,
        &request.target,
        &request.technique,
        &prov_str,
        &context,
    );

    let entry = audit_log.append(serde_json::json!({
        "engagement_id": request.engagement_id,
        "agent_id": request.agent_id,
        "agent_role": request.agent_role,
        "tool_name": request.tool_name,
        "tool_args": request.tool_args,
        "target": request.target,
        "technique": request.technique,
        "decision": decision,
        "reason": reason,
        "provenance": prov_str,
    }));

    Json(AuthorizeResponse {
        decision,
        reason,
        policy_id,
        audit_entry_id: entry.entry_id,
        timestamp: chrono::Utc::now().to_rfc3339(),
    })
}
