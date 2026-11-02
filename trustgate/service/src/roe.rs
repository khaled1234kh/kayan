use serde::{Deserialize, Serialize};
use sha2::Sha256;
use hmac::{Hmac, Mac, KeyInit};
use std::io::Write;
use hex;
use std::collections::HashSet;
use crate::models::ROEContract;
use crate::policy::{PolicySet, PolicyRule, Condition, Effect};

const DEFAULT_FORBIDDEN: &[&str] = &[
    "exfiltrate_data",
    "destructive_payload",
    "social_engineering",
    "modify_target",
    "delete_data",
];

fn technique_to_role(technique: &str) -> &str {
    match technique {
        "recon" => "recon_agent",
        "web-app" => "webapp_agent",
        "network" => "network_agent",
        "reporting" => "reporting_agent",
        "planning" => "planner_agent",
        "operator-status" | "operator-instruction" => "operator",
        _ => "*",
    }
}

pub fn signing_key() -> String {
    if let Ok(key) = std::env::var("TRUSTGATE_ROE_KEY") {
        assert!(key.len() >= 32, "TRUSTGATE_ROE_KEY must contain at least 32 characters");
        return key.trim().to_string();
    }
    let directory = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../data");
    std::fs::create_dir_all(&directory).expect("create private runtime directory");
    let path = directory.join("roe_signing_key");
    match std::fs::OpenOptions::new().write(true).create_new(true).open(&path) {
        Ok(mut file) => {
            let key = format!("{}{}", uuid::Uuid::new_v4().simple(), uuid::Uuid::new_v4().simple());
            file.write_all(key.as_bytes()).expect("write ROE key");
        }
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {},
        Err(error) => panic!("open ROE signing key: {error}"),
    }
    std::fs::read_to_string(path).expect("read ROE signing key").trim().to_string()
}
pub fn sign_canonical(canonical: &str) -> String {
    let key = signing_key();
    let mut mac = Hmac::<Sha256>::new_from_slice(key.as_bytes()).unwrap();
    mac.update(canonical.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

pub fn verify_signature(roe: &ROEContract) -> bool {
    if roe.signature.is_empty() {
        return false;
    }
    let canonical = format!(
        "{}:{}:{}:{}",
        roe.engagement_id,
        roe.authorized_by,
        serde_json::to_string(&roe.scope).unwrap_or_default(),
        serde_json::to_string(&roe.time_window).unwrap_or_default()
    );
    let key = signing_key();
    let mut mac = Hmac::<Sha256>::new_from_slice(key.as_bytes()).unwrap();
    mac.update(canonical.as_bytes());
    mac.verify_slice(&hex::decode(&roe.signature).unwrap_or_default()).is_ok()
}

pub fn compile_roe(roe: &ROEContract) -> PolicySet {
    let mut policy_set = PolicySet::new(roe.engagement_id.clone());
    policy_set.time_window = Some((roe.time_window.start.clone(), roe.time_window.end.clone()));

    // Forbidden actions from ROE + defaults
    for action in &roe.scope.forbidden_actions {
        policy_set.forbidden_actions.insert(action.clone());
    }
    for action in DEFAULT_FORBIDDEN {
        policy_set.forbidden_actions.insert(action.to_string());
    }

    // Permit rules: one per (technique, target) pair
    for technique in &roe.scope.allowed_techniques {
        for target in &roe.scope.targets {
            let rule = PolicyRule {
                rule_id: format!("permit_{}_{}", technique, target.replace('/', "_").replace('.', "_")),
                effect: Effect::Permit,
                principal: Some(technique_to_role(technique).to_string()),
                action: Some(technique.clone()),
                resource_pattern: Some(target.clone()),
                conditions: vec![
                    Condition {
                        key: "engagement_active".to_string(),
                        operator: "eq".to_string(),
                        value: serde_json::Value::Bool(true),
                    },
                    Condition {
                        key: "time_in_window".to_string(),
                        operator: "eq".to_string(),
                        value: serde_json::Value::Bool(true),
                    },
                ],
                description: format!("Allow {} on {}", technique, target),
            };
            policy_set.rules.push(rule);
        }
    }

    // Forbid rules for forbidden actions
    for action in &policy_set.forbidden_actions {
        let rule = PolicyRule {
            rule_id: format!("forbid_{}", action),
            effect: Effect::Forbid,
            principal: Some("*".to_string()),
            action: Some(action.clone()),
            resource_pattern: Some("*".to_string()),
            conditions: vec![],
            description: format!("Forbidden action: {}", action),
        };
        policy_set.rules.push(rule);
    }

    policy_set
}

pub fn create_signed_roe(
    authorized_by: &str,
    targets: Vec<String>,
    allowed_techniques: Vec<String>,
    forbidden_actions: Vec<String>,
) -> ROEContract {
    use uuid::Uuid;
    let engagement_id = Uuid::new_v4().to_string();

    let roe = ROEContract {
        engagement_id: engagement_id.clone(),
        authorized_by: authorized_by.to_string(),
        scope: crate::models::ROEScope {
            targets,
            allowed_techniques,
            forbidden_actions,
        },
        time_window: crate::models::ROETimeWindow {
            start: chrono::Utc::now().to_rfc3339(),
            end: "2099-12-31T23:59:59".to_string(),
        },
        signature: String::new(),
    };

    // Compute signature
    let canonical = format!(
        "{}:{}:{}:{}",
        roe.engagement_id,
        roe.authorized_by,
        serde_json::to_string(&roe.scope).unwrap_or_default(),
        serde_json::to_string(&roe.time_window).unwrap_or_default()
    );
    let signature = sign_canonical(&canonical);

    ROEContract {
        signature,
        ..roe
    }
}
