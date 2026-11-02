// Unit tests for TrustGate core logic.
// These mirror the 11 Python test cases from trustgate/_python_prototype/tests/test_authorize.py

#[cfg(test)]
mod tests {
    use super::*;
    use crate::policy::{PolicyEngine, PolicySet, PolicyRule, Condition, Effect};
    use crate::taint::TaintTracker;
    use crate::audit::AuditLog;
    use crate::roe;
    use crate::models::{ROEContract, ROEScope, ROETimeWindow};
    use std::collections::HashMap;

    fn make_roe(engagement_id: &str, targets: Vec<&str>, techniques: Vec<&str>, forbidden: Vec<&str>) -> ROEContract {
        use sha2::{Sha256, Digest};
        let scope = ROEScope {
            targets: targets.iter().map(|s| s.to_string()).collect(),
            allowed_techniques: techniques.iter().map(|s| s.to_string()).collect(),
            forbidden_actions: forbidden.iter().map(|s| s.to_string()).collect(),
        };
        let time_window = ROETimeWindow {
            start: "2020-01-01T00:00:00".to_string(),
            end: "2099-12-31T23:59:59".to_string(),
        };
        let canonical = format!(
            "{}:test-operator:{}:{}",
            engagement_id,
            serde_json::to_string(&scope).unwrap(),
            serde_json::to_string(&time_window).unwrap()
        );
        let signature = roe::sign_canonical(&canonical);

        ROEContract {
            engagement_id: engagement_id.to_string(),
            authorized_by: "test-operator".to_string(),
            scope,
            time_window,
            signature,
        }
    }

    // ─── Test 1: In-scope recon → ALLOW ────────────────────────────────

    #[test]
    fn test_in_scope_recon_allowed() {
        let roe = make_roe("test-recon", vec!["10.0.0.0/24"], vec!["recon"], vec![]);
        assert!(roe::verify_signature(&roe));
        let ps = roe::compile_roe(&roe);

        let mut engine = PolicyEngine::new();
        engine.load_policy_set(ps).unwrap();

        let (decision, _, _) = engine.evaluate(
            "test-recon", "recon_agent", "port_scan", "10.0.0.5", "recon",
            &HashMap::new(),
            &HashMap::from([
                ("engagement_active".to_string(), serde_json::Value::Bool(true)),
                ("time_in_window".to_string(), serde_json::Value::Bool(true)),
            ]),
        );
        assert_eq!(decision, "ALLOW");
    }

    // ─── Test 2: In-scope webapp → ALLOW ───────────────────────────────

    #[test]
    fn test_in_scope_webapp_allowed() {
        let roe = make_roe("test-webapp", vec!["10.0.0.0/24"], vec!["web-app"], vec![]);
        let ps = roe::compile_roe(&roe);

        let mut engine = PolicyEngine::new();
        engine.load_policy_set(ps).unwrap();

        let (decision, _, _) = engine.evaluate(
            "test-webapp", "webapp_agent", "sql_injection_test", "10.0.0.5", "web-app",
            &HashMap::new(),
            &HashMap::from([
                ("engagement_active".to_string(), serde_json::Value::Bool(true)),
                ("time_in_window".to_string(), serde_json::Value::Bool(true)),
            ]),
        );
        assert_eq!(decision, "ALLOW");
    }

    // ─── Test 3: Out-of-scope → DENY ───────────────────────────────────

    #[test]
    fn test_out_of_scope_denied() {
        let roe = make_roe("test-oos", vec!["10.0.0.0/24"], vec!["recon"], vec![]);
        let ps = roe::compile_roe(&roe);

        let mut engine = PolicyEngine::new();
        engine.load_policy_set(ps).unwrap();

        let (decision, _, _) = engine.evaluate(
            "test-oos", "recon_agent", "port_scan", "192.168.1.1", "recon",
            &HashMap::new(),
            &HashMap::from([
                ("engagement_active".to_string(), serde_json::Value::Bool(true)),
                ("time_in_window".to_string(), serde_json::Value::Bool(true)),
            ]),
        );
        assert_eq!(decision, "DENY");
    }

    // ─── Test 4: Forbidden action → DENY ───────────────────────────────

    #[test]
    fn test_forbidden_action_denied() {
        let roe = make_roe("test-forbidden", vec!["10.0.0.0/24"], vec!["recon"], vec!["exfiltrate_data"]);
        let ps = roe::compile_roe(&roe);

        let mut engine = PolicyEngine::new();
        engine.load_policy_set(ps).unwrap();

        let (decision, _, _) = engine.evaluate(
            "test-forbidden", "recon_agent", "exfiltrate_data", "10.0.0.5", "recon",
            &HashMap::new(),
            &HashMap::from([
                ("engagement_active".to_string(), serde_json::Value::Bool(true)),
                ("time_in_window".to_string(), serde_json::Value::Bool(true)),
            ]),
        );
        assert_eq!(decision, "DENY");
    }

    // ─── Test 5: No policy → DENY (default-deny) ──────────────────────

    #[test]
    fn test_default_deny_no_policy() {
        let engine = PolicyEngine::new();

        let (decision, _, _) = engine.evaluate(
            "nonexistent", "recon_agent", "port_scan", "10.0.0.5", "recon",
            &HashMap::new(),
            &HashMap::new(),
        );
        assert_eq!(decision, "DENY");
    }

    // ─── Test 6: Tainted argument → DENY ──────────────────────────────

    #[test]
    fn test_tainted_argument_denied() {
        let tracker = TaintTracker::new();
        let prov = HashMap::from([
            ("target".to_string(), "untrusted".to_string()),
            ("ports".to_string(), "trusted".to_string()),
        ]);
        let (safe, reason, _) = tracker.check_tool_call(&prov);
        assert!(!safe);
        assert!(reason.contains("Tainted") || reason.to_lowercase().contains("untrusted"));
    }

    // ─── Test 7: Tainted pivot → DENY ─────────────────────────────────

    #[test]
    fn test_tainted_pivot_denied() {
        let tracker = TaintTracker::new();
        let prov = HashMap::from([
            ("target".to_string(), "untrusted".to_string()),
            ("ports".to_string(), "trusted".to_string()),
        ]);
        let (safe, _, _) = tracker.check_tool_call(&prov);
        assert!(!safe);
    }

    // ─── Test 8: Audit log records decision ────────────────────────────

    #[test]
    fn test_audit_log_records_decision() {
        let path = std::env::temp_dir().join(format!("trustgate-audit-record-{}.jsonl", uuid::Uuid::new_v4()));
        let mut log = AuditLog::new(&path.to_string_lossy());
        log.clear();

        let entry = log.append(serde_json::json!({
            "engagement_id": "test-audit",
            "agent_id": "recon-001",
            "agent_role": "recon_agent",
            "tool_name": "port_scan",
            "tool_args": {"target": "10.0.0.5"},
            "target": "10.0.0.5",
            "technique": "recon",
            "decision": "ALLOW",
            "reason": "test",
            "provenance": {"target": "trusted"},
        }));

        assert!(!entry.entry_id.is_empty());
        assert_eq!(log.entry_count(), 1);

        log.clear();
    }

    // ─── Test 9: Audit chain valid ─────────────────────────────────────

    #[test]
    fn test_audit_chain_valid() {
        let path = std::env::temp_dir().join(format!("trustgate-audit-chain-{}.jsonl", uuid::Uuid::new_v4()));
        let mut log = AuditLog::new(&path.to_string_lossy());
        log.clear();

        for i in 0..5 {
            log.append(serde_json::json!({
                "engagement_id": "test-chain",
                "agent_id": format!("agent-{}", i),
                "agent_role": "recon_agent",
                "tool_name": "port_scan",
                "tool_args": {"target": "10.0.0.5"},
                "target": "10.0.0.5",
                "technique": "recon",
                "decision": "ALLOW",
                "reason": "test",
                "provenance": {"target": "trusted"},
            }));
        }

        let (valid, _, _) = log.verify_chain();
        assert!(valid);

        log.clear();
    }

    // ─── Test 10: Health check (structural) ────────────────────────────

    #[test]
    fn test_health_structural() {
        // Verify PolicyEngine and AuditLog can be created
        let engine = PolicyEngine::new();
        assert!(!engine.has_policy());

        let log = AuditLog::new("C:/Users/khale/AppData/Local/Temp/opencode/test_audit_10.jsonl");
        assert_eq!(log.entry_count(), 0);
    }

    // ─── Test 11: ROE load + signature verification ────────────────────

    #[test]
    fn test_roe_load_and_signature() {
        let roe = make_roe("test-roe", vec!["10.0.0.0/24", "lab.local"], vec!["recon", "web-app"], vec![]);
        assert!(roe::verify_signature(&roe));

        let ps = roe::compile_roe(&roe);
        assert!(ps.rules.len() > 0);
        assert!(ps.forbidden_actions.contains("exfiltrate_data"));
        assert!(ps.forbidden_actions.contains("destructive_payload"));
    }
}

#[cfg(test)]
mod enforcement_regression {
    use crate::{roe, policy::PolicyEngine};
    use std::collections::HashMap;
    fn decision(roe: &crate::models::ROEContract, role: &str, tool: &str, target: &str, technique: &str) -> String {
        let mut engine = PolicyEngine::new();
        engine.load_policy_set(roe::compile_roe(roe)).unwrap();
        engine.evaluate(&roe.engagement_id, role, tool, target, technique, &HashMap::new(), &HashMap::new()).0
    }
    #[test]
    fn cedar_unknown_tool_is_not_granted_by_allowed_technique() {
        let contract = roe::create_signed_roe("operator", vec!["127.0.0.1".into()], vec!["recon".into()], vec![]);
        assert_eq!(decision(&contract, "recon_agent", "execute_shell", "127.0.0.1", "recon"), "DENY");
    }
    #[test]
    fn cedar_enforces_non_octet_cidr() {
        let contract = roe::create_signed_roe("operator", vec!["10.0.0.128/25".into()], vec!["recon".into()], vec![]);
        assert_eq!(decision(&contract, "recon_agent", "port_scan", "10.0.0.129", "recon"), "ALLOW");
        assert_eq!(decision(&contract, "recon_agent", "port_scan", "10.0.0.1", "recon"), "DENY");
    }
    #[test]
    fn expired_roe_is_denied_even_if_caller_supplies_true_flags() {
        let mut contract = roe::create_signed_roe("operator", vec!["127.0.0.1".into()], vec!["recon".into()], vec![]);
        contract.time_window.end = "2020-01-01T00:00:00".into();
        assert_eq!(decision(&contract, "recon_agent", "port_scan", "127.0.0.1", "recon"), "DENY");
    }
    #[test]
    fn unsigned_or_tampered_roe_is_not_accepted() {
        let mut contract = roe::create_signed_roe("operator", vec!["127.0.0.1".into()], vec!["recon".into()], vec![]);
        assert!(roe::verify_signature(&contract));
        contract.authorized_by = "impersonated".into();
        assert!(!roe::verify_signature(&contract));
        contract.signature.clear();
        assert!(!roe::verify_signature(&contract));
    }
    #[test]
    fn unknown_technique_does_not_create_wildcard_capability() {
        let contract = roe::create_signed_roe("operator", vec!["127.0.0.1".into()], vec!["anything".into()], vec![]);
        assert_eq!(decision(&contract, "recon_agent", "port_scan", "127.0.0.1", "anything"), "DENY");
    }
    #[test]
    fn operator_message_capability_does_not_allow_agent_impersonation() {
        let contract = roe::create_signed_roe("operator", vec!["127.0.0.1".into()], vec!["operator-status".into()], vec![]);
        assert_eq!(decision(&contract, "operator", "message_send", "127.0.0.1", "operator-status"), "ALLOW");
        assert_eq!(decision(&contract, "recon_agent", "message_send", "127.0.0.1", "operator-status"), "DENY");
    }
}

#[cfg(test)]
mod workflow_data_tests {
    use crate::{roe, policy::PolicyEngine};
    use std::collections::HashMap;
    #[test]
    fn signed_workflow_permit_accepts_untrusted_body_as_data_only() {
        let roe=roe::create_signed_roe("operator",vec!["127.0.0.1".into()],vec!["workflow".into()],vec![]);
        let mut gate=PolicyEngine::new(); gate.load_policy_set(roe::compile_roe(&roe)).unwrap();
        let mut provenance=HashMap::from([("target".into(),"trusted".into()),("body".into(),"untrusted".into())]);
        assert_eq!(gate.evaluate(&roe.engagement_id,"recon_agent","record_result","127.0.0.1","workflow",&provenance,&HashMap::new()).0,"ALLOW");
        provenance.insert("target".into(),"untrusted".into());
        assert_eq!(gate.evaluate(&roe.engagement_id,"recon_agent","record_result","127.0.0.1","workflow",&provenance,&HashMap::new()).0,"DENY");
    }
    #[test]
    fn metadata_rule_cannot_authorize_shell_or_relabel_an_execution_argument() {
        let roe=roe::create_signed_roe("operator",vec!["127.0.0.1".into()],vec!["workflow".into(),"recon".into()],vec![]);
        let mut gate=PolicyEngine::new();gate.load_policy_set(roe::compile_roe(&roe)).unwrap();
        let provenance=HashMap::from([("body".into(),"untrusted".into())]);
        assert_eq!(gate.evaluate(&roe.engagement_id,"recon_agent","port_scan","127.0.0.1","recon",&provenance,&HashMap::new()).0,"DENY");
        assert_eq!(gate.evaluate(&roe.engagement_id,"recon_agent","terminal","127.0.0.1","workflow",&provenance,&HashMap::new()).0,"DENY");
        assert_eq!(gate.evaluate(&roe.engagement_id,"recon_agent","record_result","192.0.2.2","workflow",&provenance,&HashMap::new()).0,"DENY");
    }
    #[test]
    fn workflow_body_exception_grants_nothing_without_explicit_roe_capability() {
        let roe=roe::create_signed_roe("operator",vec!["127.0.0.1".into()],vec!["recon".into()],vec![]);
        let mut gate=PolicyEngine::new();gate.load_policy_set(roe::compile_roe(&roe)).unwrap();
        assert_eq!(gate.evaluate(&roe.engagement_id,"recon_agent","record_result","127.0.0.1","workflow",&HashMap::from([("body".into(),"untrusted".into())]),&HashMap::new()).0,"DENY");
    }
}
