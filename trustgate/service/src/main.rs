use axum::{
    routing::{get, post},
    Router,
    Json,
    http::{HeaderMap, StatusCode, header},
    extract::{ConnectInfo, State, Query},
};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;
use tower_http::cors::CorsLayer;

mod models;
mod policy;
mod taint;
mod audit;
mod authorize;
mod roe;
mod roe_http;
#[cfg(test)]
mod tests;

use models::*;
use policy::PolicyEngine;
use audit::AuditLog;
use crate::audit::AuditLog as AL;

#[derive(Clone)]
pub struct AppState {
    pub policy_engine: Arc<RwLock<PolicyEngine>>,
    pub audit_log: Arc<RwLock<AuditLog>>,
}

#[derive(Deserialize)]
struct AuditQuery {
    limit: Option<usize>,
    offset: Option<usize>,
}

#[tokio::main]
async fn main() {
    let state = AppState {
        policy_engine: Arc::new(RwLock::new(PolicyEngine::new())),
        audit_log: Arc::new(RwLock::new(AuditLog::new("audit_log.jsonl"))),
    };

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8000")
        .await
        .unwrap();

    println!("TrustGate (Cedar) listening on http://0.0.0.0:8000");
    axum::serve(listener, app(state).into_make_service_with_connect_info::<SocketAddr>())
        .await
        .unwrap();
}

fn app(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/authorize", post(authorize::authorize))
        .route("/roe/load", post(roe_http::load_roe))
        .route("/audit", get(get_audit))
        .route("/audit/verify", get(verify_audit))
        .route("/audit/reconcile", post(reconcile_audit))
        .layer(CorsLayer::permissive())
        .with_state(state)
}

async fn health(
    State(state): State<AppState>,
) -> Json<HealthResponse> {
    let pe = state.policy_engine.read().await;
    let al = state.audit_log.read().await;
    Json(HealthResponse {
        engine: "cedar-policy 4.14.0".to_string(),
        roe_authentication: "HMAC-SHA256".to_string(),
        status: "ok".to_string(),
        version: "0.2.0".to_string(),
        policy_loaded: pe.has_policy(),
        audit_entries: al.entry_count(),
    })
}

async fn get_audit(
    State(state): State<AppState>,
    Query(params): Query<AuditQuery>,
) -> Json<serde_json::Value> {
    let al = state.audit_log.read().await;
    let limit = params.limit.unwrap_or(100);
    let offset = params.offset.unwrap_or(0);
    let entries = al.get_entries(limit, offset);
    let total = al.entry_count();
    Json(serde_json::json!({
        "entries": entries,
        "total": total,
    }))
}

async fn verify_audit(
    State(state): State<AppState>,
) -> Json<serde_json::Value> {
    let al = state.audit_log.read().await;
    let (valid, broken_at, message) = al.verify_chain();
    Json(serde_json::json!({
        "valid": valid,
        "broken_at": broken_at,
        "message": message,
    }))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct AuditReferences {
    engagement_id: String,
    entry_ids: Vec<String>,
}

#[derive(Serialize)]
struct AuditReconciliation {
    valid: bool,
    entries: Vec<audit::DecisionReference>,
}

fn canonical_uuid(value: &str) -> bool {
    uuid::Uuid::parse_str(value).is_ok_and(|id| id.to_string() == value)
}

async fn reconcile_audit(
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<AuditReferences>,
) -> Result<Json<AuditReconciliation>, StatusCode> {
    if !peer.ip().is_loopback() || headers.contains_key(header::ORIGIN) {
        return Err(StatusCode::FORBIDDEN);
    }
    let ids: HashSet<&str> = request.entry_ids.iter().map(String::as_str).collect();
    if ids.is_empty() || ids.len() > 128 || ids.len() != request.entry_ids.len()
        || !canonical_uuid(&request.engagement_id) || ids.iter().any(|id| !canonical_uuid(id))
    {
        return Err(StatusCode::BAD_REQUEST);
    }
    // Use one ledger read lock for verification and selection so a writer
    // cannot change the set of entries between the two operations.
    let ledger = state.audit_log.read().await;
    let (valid, _, _) = ledger.verify_chain();
    let entries = if valid {
        ledger.decision_references(&request.engagement_id, &ids)
    } else {
        Vec::new()
    };
    Ok(Json(AuditReconciliation { valid, entries }))
}

#[cfg(test)]
mod audit_reconciliation_tests {
    use super::*;
    use serde_json::json;
    use uuid::Uuid;

    fn fixture() -> (String, AuditLog, String, String) {
        let path = std::env::temp_dir().join(format!("kayan-audit-reconcile-{}.jsonl", Uuid::new_v4()));
        let path = path.to_string_lossy().into_owned();
        let mut log = AuditLog::new(&path);
        let case = Uuid::new_v4().to_string();
        let entry = log.append(json!({
            "engagement_id": case, "agent_id": "test-observer", "agent_role": "recon_agent",
            "tool_name": "fixture_read", "target": "127.0.0.1", "decision": "DENY",
            "tool_args": {"note": "private fixture argument"}
        }));
        (path, log, case, entry.entry_id)
    }

    fn state(log: AuditLog) -> State<AppState> {
        State(AppState {
            policy_engine: Arc::new(RwLock::new(PolicyEngine::new())),
            audit_log: Arc::new(RwLock::new(log)),
        })
    }

    #[tokio::test]
    async fn reconcile_returns_only_scoped_decisions_and_no_raw_arguments() {
        let (path, log, case, id) = fixture();
        let state = state(log);
        let peer = "127.0.0.1:1234".parse().unwrap();
        let match_result = reconcile_audit(ConnectInfo(peer), state.clone(), HeaderMap::new(),
            Json(AuditReferences { engagement_id: case, entry_ids: vec![id.clone()] }))
            .await.unwrap().0;
        let public = serde_json::to_value(match_result).unwrap();
        assert_eq!(public["valid"], true);
        assert_eq!(public["entries"][0]["entry_id"], id);
        assert_eq!(public["entries"][0]["decision"], "DENY");
        assert_eq!(public["entries"][0].as_object().unwrap().len(), 7);
        let wrong_case = reconcile_audit(ConnectInfo(peer), state, HeaderMap::new(),
            Json(AuditReferences { engagement_id: Uuid::new_v4().to_string(), entry_ids: vec![id] }))
            .await.unwrap().0;
        assert!(wrong_case.valid && wrong_case.entries.is_empty());
        std::fs::remove_file(path).unwrap();
    }

    #[tokio::test]
    async fn reconcile_works_through_the_production_router_over_loopback_http() {
        let (path, log, case, id) = fixture();
        let state = state(log);
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let server_state = state.0.clone();
        let server = tokio::spawn(async move {
            axum::serve(listener, app(server_state).into_make_service_with_connect_info::<SocketAddr>())
                .await.unwrap();
        });
        let client = reqwest::Client::builder()
            .no_proxy()
            .timeout(std::time::Duration::from_secs(5))
            .build().unwrap();
        let response: serde_json::Value = client.post(format!("http://{address}/audit/reconcile"))
            .json(&json!({"engagement_id": case, "entry_ids": [id]}))
            .send().await.unwrap().error_for_status().unwrap().json().await.unwrap();
        assert_eq!(response["valid"], true);
        assert_eq!(response["entries"][0]["entry_id"], id);
        assert_eq!(state.0.audit_log.read().await.entry_count(), 1);
        server.abort();
        std::fs::remove_file(path).unwrap();
    }

    #[tokio::test]
    async fn reconcile_refuses_remote_browser_and_duplicate_requests() {
        let (path, log, case, id) = fixture();
        let state = state(log);
        let request = || Json(AuditReferences { engagement_id: case.clone(), entry_ids: vec![id.clone()] });
        let local = "127.0.0.1:1234".parse().unwrap();
        let remote = "192.0.2.1:1234".parse().unwrap();
        let remote_result = reconcile_audit(ConnectInfo(remote), state.clone(), HeaderMap::new(), request()).await;
        assert_eq!(remote_result.err(), Some(StatusCode::FORBIDDEN));
        let mut headers = HeaderMap::new();
        headers.insert(header::ORIGIN, "https://example.invalid".parse().unwrap());
        let browser = reconcile_audit(ConnectInfo(local), state.clone(), headers, request()).await;
        assert_eq!(browser.err(), Some(StatusCode::FORBIDDEN));
        let duplicates = reconcile_audit(ConnectInfo(local), state, HeaderMap::new(), Json(AuditReferences {
            engagement_id: case, entry_ids: vec![id.clone(), id],
        })).await;
        assert_eq!(duplicates.err(), Some(StatusCode::BAD_REQUEST));
        std::fs::remove_file(path).unwrap();
    }

    #[tokio::test]
    async fn reconcile_releases_no_entries_from_a_corrupt_chain() {
        let (path, log, case, id) = fixture();
        drop(log);
        let mut line: serde_json::Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        line["agent_id"] = json!("changed-test-observer");
        std::fs::write(&path, serde_json::to_vec(&line).unwrap()).unwrap();
        let result = reconcile_audit(ConnectInfo("127.0.0.1:1234".parse().unwrap()),
            state(AuditLog::new(&path)), HeaderMap::new(),
            Json(AuditReferences { engagement_id: case, entry_ids: vec![id] }))
            .await.unwrap().0;
        assert!(!result.valid && result.entries.is_empty());
        std::fs::remove_file(path).unwrap();
    }
}
