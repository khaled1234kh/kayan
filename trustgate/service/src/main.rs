use axum::{
    routing::{get, post},
    Router,
    Json,
    http::StatusCode,
    extract::{State, Query},
};
use serde::{Deserialize, Serialize};
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

    let app = Router::new()
        .route("/health", get(health))
        .route("/authorize", post(authorize::authorize))
        .route("/roe/load", post(roe_http::load_roe))
        .route("/audit", get(get_audit))
        .route("/audit/verify", get(verify_audit))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8000")
        .await
        .unwrap();

    println!("TrustGate (Cedar) listening on http://0.0.0.0:8000");
    axum::serve(listener, app).await.unwrap();
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
