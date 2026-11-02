use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ROEScope {
    pub targets: Vec<String>,
    pub allowed_techniques: Vec<String>,
    #[serde(default)]
    pub forbidden_actions: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ROETimeWindow {
    pub start: String,
    pub end: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ROEContract {
    pub engagement_id: String,
    pub authorized_by: String,
    pub scope: ROEScope,
    pub time_window: ROETimeWindow,
    pub signature: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCallRequest {
    pub engagement_id: String,
    pub agent_id: String,
    pub agent_role: String,
    pub tool_name: String,
    #[serde(default)]
    pub tool_args: HashMap<String, serde_json::Value>,
    pub target: String,
    pub technique: String,
    #[serde(default)]
    pub provenance: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizeResponse {
    pub decision: String,
    pub reason: String,
    pub policy_id: Option<String>,
    pub audit_entry_id: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub engine: String,
    pub roe_authentication: String,
    pub status: String,
    pub version: String,
    pub policy_loaded: bool,
    pub audit_entries: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub entry_id: String,
    pub previous_hash: String,
    pub timestamp: String,
    pub engagement_id: String,
    pub agent_id: String,
    pub agent_role: String,
    pub tool_name: String,
    pub tool_args: HashMap<String, serde_json::Value>,
    pub target: String,
    pub technique: String,
    pub decision: String,
    pub reason: String,
    pub provenance: HashMap<String, String>,
    pub entry_hash: String,
    pub signature: String,
}
