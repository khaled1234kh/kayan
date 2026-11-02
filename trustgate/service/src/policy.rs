use std::collections::{HashMap, HashSet};
use std::str::FromStr;
use cedar_policy::{Authorizer, Context, Decision, Entities, EntityUid, PolicySet as CedarSet, Request};

#[derive(Debug, Clone, PartialEq)]
pub enum Effect { Permit, Forbid }
#[derive(Debug, Clone)]
pub struct Condition { pub key: String, pub operator: String, pub value: serde_json::Value }
#[derive(Debug, Clone)]
pub struct PolicyRule {
    pub rule_id: String, pub effect: Effect, pub principal: Option<String>,
    pub action: Option<String>, pub resource_pattern: Option<String>,
    pub conditions: Vec<Condition>, pub description: String,
}
#[derive(Debug, Clone)]
pub struct PolicySet {
    pub engagement_id: String, pub rules: Vec<PolicyRule>,
    pub forbidden_actions: HashSet<String>, pub time_window: Option<(String, String)>,
}
impl PolicySet {
    pub fn new(engagement_id: String) -> Self {
        Self { engagement_id, rules: vec![], forbidden_actions: HashSet::new(), time_window: None }
    }
}

/// Exhaustive capability action sets. Unknown technique names grant no actions.
fn actions(technique: &str) -> &'static [&'static str] {
    match technique {
        "recon" => &["port_scan", "service_scan", "http_probe", "web_crawl", "discover_endpoints", "llm_inference"],
        "web-app" => &["sql_injection_test", "xss_test", "command_injection_test", "directory_traversal",
            "verify_xss", "verify_sql_injection", "verify_command_injection", "verify_path_traversal", "llm_inference"],
        "network" => &["port_scan", "service_scan", "llm_inference"],
        "reporting" => &["llm_inference", "write_report"],
        "planning" => &["llm_inference"],
        "workflow" => &["plan_tasks", "delegate_task", "record_result", "complete_task"],
        "operator-status" | "operator-instruction" | "agent-message" => &["message_send"],
        _ => &[],
    }
}

/// Non-executing workflow payloads remain untrusted data. Only their body may
/// be treated as data; destinations/execution arguments never get this exception.
pub fn decision_provenance(tool: &str, technique: &str, provenance: &HashMap<String, String>) -> HashMap<String, String> {
    let mut filtered = provenance.clone();
    if technique == "workflow" && actions("workflow").contains(&tool) {
        filtered.remove("body");
    }
    filtered
}
fn quoted(text: &str) -> String { serde_json::to_string(text).unwrap() }
pub fn compile_cedar(set: &PolicySet) -> Result<CedarSet, String> {
    let mut source = String::new();
    for rule in &set.rules {
        let principal = match &rule.principal {
            Some(p) if p != "*" => format!("principal == Agent::{}", quoted(p)),
            _ => "principal".into(),
        };
        let technique = rule.action.as_deref().unwrap_or("");
        let (action, mut conditions) = if rule.effect == Effect::Permit {
            let allowed = actions(technique);
            if allowed.is_empty() { continue; }
            (format!("action in [{}]", allowed.iter().map(|a| format!("Action::{}", quoted(a))).collect::<Vec<_>>().join(", ")),
             vec![format!("context.technique == {}", quoted(technique))])
        } else {
            (format!("action == Action::{}", quoted(technique)), vec![])
        };
        if let Some(pattern) = &rule.resource_pattern {
            if pattern.contains('/') {
                conditions.push(format!("ip(context.target).isInRange(ip({}))", quoted(pattern)));
            } else if pattern != "*" {
                conditions.push(if pattern.contains('*') {
                    format!("context.target like {}", quoted(pattern))
                } else {
                    format!("context.target == {}", quoted(pattern))
                });
            }
        }
        for condition in &rule.conditions {
            if condition.operator != "eq" { return Err(format!("Unsupported condition {}", condition.operator)); }
            conditions.push(format!("context.{} == {}", condition.key, condition.value));
        }
        let effect = if rule.effect == Effect::Permit { "permit" } else { "forbid" };
        source.push_str(&format!("{}({}, {}, resource) when {{ {} }};\n", effect, principal, action,
            if conditions.is_empty() { "true".into() } else { conditions.join(" && ") }));
    }
    CedarSet::from_str(&source).map_err(|e| format!("Cedar compilation failed: {e}"))
}
fn instant(value: &str) -> Option<chrono::DateTime<chrono::Utc>> {
    chrono::DateTime::parse_from_rfc3339(value).ok().map(|t| t.with_timezone(&chrono::Utc))
        .or_else(|| chrono::NaiveDateTime::parse_from_str(value, "%Y-%m-%dT%H:%M:%S%.f").ok().map(|t| t.and_utc()))
}
pub fn time_valid(window: &Option<(String, String)>) -> bool {
    match window {
        Some((start, end)) => match (instant(start), instant(end)) {
            (Some(a), Some(b)) => { let now = chrono::Utc::now(); a <= now && now <= b }
            _ => false,
        },
        None => true,
    }
}
pub struct PolicyEngine {
    policy_sets: HashMap<String, PolicySet>, cedar_sets: HashMap<String, CedarSet>,
}
impl PolicyEngine {
    pub fn new() -> Self { Self { policy_sets: HashMap::new(), cedar_sets: HashMap::new() } }
    pub fn load_policy_set(&mut self, set: PolicySet) -> Result<(), String> {
        let cedar = compile_cedar(&set)?;
        self.cedar_sets.insert(set.engagement_id.clone(), cedar);
        self.policy_sets.insert(set.engagement_id.clone(), set); Ok(())
    }
    pub fn get_policy_set(&self, id: &str) -> Option<&PolicySet> { self.policy_sets.get(id) }
    pub fn has_policy(&self) -> bool { !self.policy_sets.is_empty() }
    pub fn evaluate(&self, id: &str, role: &str, tool: &str, target: &str, technique: &str,
        provenance: &HashMap<String, String>, context: &HashMap<String, serde_json::Value>)
        -> (String, String, Option<String>) {
        let Some(set) = self.policy_sets.get(id) else { return ("DENY".into(), format!("No policy set for engagement {id}"), None) };
        let checked_provenance = decision_provenance(tool, technique, provenance);
        if checked_provenance.values().any(|p| p == "untrusted") { return ("DENY".into(), "Tainted argument has untrusted provenance".into(), None) }
        if set.forbidden_actions.contains(tool) || set.forbidden_actions.contains(technique) {
            return ("DENY".into(), format!("Action '{tool}/{technique}' is forbidden"), None)
        }
        let result = (|| -> Result<_, String> {
            let principal = EntityUid::from_str(&format!("Agent::{}", quoted(role))).map_err(|e| e.to_string())?;
            let action = EntityUid::from_str(&format!("Action::{}", quoted(tool))).map_err(|e| e.to_string())?;
            let resource = EntityUid::from_str(&format!("Target::{}", quoted(target))).map_err(|e| e.to_string())?;
            let mut values = serde_json::to_value(context).map_err(|e| e.to_string())?;
            values["target"] = serde_json::json!(target); values["technique"] = serde_json::json!(technique);
            values["engagement_active"] = serde_json::json!(true);
            values["time_in_window"] = serde_json::json!(time_valid(&set.time_window));
            let ctx = Context::from_json_value(values, None).map_err(|e| e.to_string())?;
            let request = Request::new(principal, action, resource, ctx, None).map_err(|e| e.to_string())?;
            let response = Authorizer::new().is_authorized(&request, &self.cedar_sets[id], &Entities::empty());
            Ok(response.decision())
        })();
        match result {
            Ok(Decision::Allow) => ("ALLOW".into(), "Cedar permit matched authenticated ROE capability, target and time window".into(), Some(format!("cedar:{id}:{technique}"))),
            Ok(_) => ("DENY".into(), "Cedar default-deny or forbid: capability, scope or time-window mismatch".into(), None),
            Err(error) => ("DENY".into(), format!("Cedar evaluation failed closed: {error}"), None),
        }
    }
}
