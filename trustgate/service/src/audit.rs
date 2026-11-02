use crate::models::AuditEntry;
use chrono::Utc;
use hex;
use hmac::{Hmac, KeyInit, Mac};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use uuid::Uuid;

type HmacSha256 = Hmac<Sha256>;

pub struct AuditLog {
    log_path: String,
    entries: Vec<AuditEntry>,
    // Original payload order is needed to verify pre-canonicalization records.
    persisted_payloads: Vec<serde_json::Value>,
    load_error: Option<(usize, String)>,
}

#[cfg(test)]
mod canonical_tests {
    use super::*;
    use serde_json::{Value, json};

    fn path() -> String {
        std::env::temp_dir()
            .join(format!("kayan-canonical-audit-{}.jsonl", Uuid::new_v4()))
            .to_string_lossy()
            .into_owned()
    }
    fn sample() -> Value {
        json!({"engagement_id":"canonical-test","agent_id":"planner","agent_role":"planner_agent",
            "tool_name":"llm_inference","tool_args":{"z":3,"nested":{"z":"Résumé","a":true},"a":[2,1]},
            "target":"127.0.0.1","technique":"planning","decision":"ALLOW","reason":"Test only",
            "provenance":{"z":"trusted","a":"trusted"}})
    }
    fn legacy(path: &str) -> Value {
        let mut log = AuditLog::new(path);
        let entry = log.append(sample());
        let mut raw = serde_json::to_value(entry).unwrap();
        let map = raw.as_object_mut().unwrap();
        map.remove("entry_hash");
        map.remove("signature");
        let hash = hex::encode(Sha256::digest(
            serde_json::to_string(&raw).unwrap().as_bytes(),
        ));
        raw["entry_hash"] = json!(hash);
        raw["signature"] = json!(AuditLog::sign_entry(&hash));
        std::fs::write(path, format!("{}\n", raw)).unwrap();
        raw
    }

    #[test]
    fn hash_ignores_recursive_object_key_order() {
        let a: Value = serde_json::from_str(r#"{"z":{"b":2,"a":1},"a":[{"z":3,"a":4}]}"#).unwrap();
        let b: Value = serde_json::from_str(r#"{"a":[{"a":4,"z":3}],"z":{"a":1,"b":2}}"#).unwrap();
        assert_eq!(AuditLog::compute_hash(&a), AuditLog::compute_hash(&b));
        assert_ne!(
            AuditLog::compute_hash(&json!([1, 2])),
            AuditLog::compute_hash(&json!([2, 1]))
        );
    }
    #[test]
    fn current_nested_unicode_journal_survives_reload() {
        let path = path();
        let mut log = AuditLog::new(&path);
        for _ in 0..4 {
            log.append(sample());
        }
        assert!(log.verify_chain().0);
        assert!(AuditLog::new(&path).verify_chain().0);
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn legacy_insertion_order_stays_byte_identical() {
        let path = path();
        legacy(&path);
        let before = std::fs::read(&path).unwrap();
        let mut reloaded = AuditLog::new(&path);
        assert!(reloaded.verify_chain().0);
        assert_eq!(std::fs::read(&path).unwrap(), before);
        reloaded.append(sample());
        assert!(AuditLog::new(&path).verify_chain().0);
        assert!(std::fs::read(&path).unwrap().starts_with(&before));
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn legacy_payload_tampering_is_rejected() {
        let path = path();
        let mut raw = legacy(&path);
        raw["reason"] = json!("changed");
        std::fs::write(&path, raw.to_string()).unwrap();
        assert!(!AuditLog::new(&path).verify_chain().0);
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn legacy_signature_is_still_required() {
        let path = path();
        let mut raw = legacy(&path);
        raw["signature"] = json!("0".repeat(64));
        std::fs::write(&path, raw.to_string()).unwrap();
        assert!(!AuditLog::new(&path).verify_chain().0);
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn malformed_journal_is_not_treated_as_empty_valid_history() {
        let path = path();
        std::fs::write(&path, "{invalid JSON\n").unwrap();
        let result = AuditLog::new(&path).verify_chain();
        assert!(!result.0);
        assert_eq!(result.1, Some(0));
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn current_unknown_field_tampering_is_rejected() {
        let path = path();
        let mut log = AuditLog::new(&path);
        let entry = log.append(sample());
        let mut raw = serde_json::to_value(entry).unwrap();
        raw["unrecognized"] = json!("added after signing");
        std::fs::write(&path, raw.to_string()).unwrap();
        assert!(!AuditLog::new(&path).verify_chain().0);
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn legacy_unknown_payload_fields_cannot_be_dropped_during_verification() {
        let path = path();
        let mut raw = legacy(&path);
        raw.as_object_mut().unwrap().remove("entry_hash");
        raw.as_object_mut().unwrap().remove("signature");
        raw["unrecognized"] = json!("must not disappear");
        let hash = hex::encode(Sha256::digest(raw.to_string().as_bytes()));
        raw["entry_hash"] = json!(hash);
        raw["signature"] = json!(AuditLog::sign_entry(&hash));
        std::fs::write(&path, raw.to_string()).unwrap();
        assert!(!AuditLog::new(&path).verify_chain().0);
        std::fs::remove_file(path).unwrap();
    }
}

impl AuditLog {
    pub fn new(log_path: &str) -> Self {
        let mut al = Self {
            log_path: log_path.to_string(),
            entries: Vec::new(),
            persisted_payloads: Vec::new(),
            load_error: None,
        };
        al.load_existing();
        al
    }

    fn load_existing(&mut self) {
        let path = Path::new(&self.log_path);
        if path.exists() {
            if let Ok(file) = std::fs::File::open(path) {
                let reader = BufReader::new(file);
                for (index, line) in reader.lines().enumerate() {
                    if let Ok(line) = line {
                        let line = line.trim().to_string();
                        if !line.is_empty() {
                            match serde_json::from_str::<serde_json::Value>(&line).and_then(|raw| {
                                serde_json::from_value::<AuditEntry>(raw.clone())
                                    .map(|entry| (entry, raw))
                            }) {
                                Ok((entry, mut raw)) => {
                                    if let Some(map) = raw.as_object_mut() {
                                        map.remove("entry_hash");
                                        map.remove("signature");
                                    }
                                    self.entries.push(entry);
                                    self.persisted_payloads.push(raw);
                                }
                                Err(_) => {
                                    self.load_error
                                        .get_or_insert((index, "Unreadable audit record".into()));
                                }
                            }
                        }
                    } else {
                        self.load_error
                            .get_or_insert((index, "Audit read error".into()));
                    }
                }
            } else {
                self.load_error = Some((0, "Audit file cannot be read".into()));
            }
        }
    }

    fn compute_hash(entry_data: &serde_json::Value) -> String {
        fn sorted(value: &serde_json::Value) -> serde_json::Value {
            match value {
                serde_json::Value::Object(map) => {
                    let mut keys: Vec<_> = map.keys().collect();
                    keys.sort();
                    let mut result = serde_json::Map::new();
                    for key in keys {
                        result.insert(key.clone(), sorted(&map[key]));
                    }
                    serde_json::Value::Object(result)
                }
                serde_json::Value::Array(values) => {
                    serde_json::Value::Array(values.iter().map(sorted).collect())
                }
                _ => value.clone(),
            }
        }
        let canonical = serde_json::to_string(&sorted(entry_data)).expect("JSON value serializes");
        let mut hasher = Sha256::new();
        hasher.update(canonical.as_bytes());
        hex::encode(hasher.finalize())
    }

    fn sign_entry(entry_hash: &str) -> String {
        let key = std::env::var("TRUSTGATE_HMAC_KEY")
            .unwrap_or_else(|_| "kayan-trustgate-default-key-change-in-prod".to_string());
        let mut mac = HmacSha256::new_from_slice(key.as_bytes()).unwrap();
        mac.update(entry_hash.as_bytes());
        hex::encode(mac.finalize().into_bytes())
    }

    fn verify_signature(entry_hash: &str, signature: &str) -> bool {
        let key = std::env::var("TRUSTGATE_HMAC_KEY")
            .unwrap_or_else(|_| "kayan-trustgate-default-key-change-in-prod".to_string());
        let mut mac = HmacSha256::new_from_slice(key.as_bytes()).unwrap();
        mac.update(entry_hash.as_bytes());
        let expected = hex::encode(mac.finalize().into_bytes());
        expected == signature
    }

    fn get_previous_hash(&self) -> String {
        if self.entries.is_empty() {
            let mut hasher = Sha256::new();
            hasher.update(b"GENESIS");
            hex::encode(hasher.finalize())
        } else {
            self.entries.last().unwrap().entry_hash.clone()
        }
    }

    pub fn append(&mut self, entry_data: serde_json::Value) -> AuditEntry {
        let entry_id = entry_data
            .get("entry_id")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| Uuid::new_v4().to_string());

        let timestamp = entry_data
            .get("timestamp")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| Utc::now().to_rfc3339());

        let previous_hash = self.get_previous_hash();

        let mut entry = AuditEntry {
            entry_id,
            previous_hash,
            timestamp,
            engagement_id: entry_data
                .get("engagement_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            agent_id: entry_data
                .get("agent_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            agent_role: entry_data
                .get("agent_role")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            tool_name: entry_data
                .get("tool_name")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            tool_args: entry_data
                .get("tool_args")
                .and_then(|v| serde_json::from_value(v.clone()).ok())
                .unwrap_or_default(),
            target: entry_data
                .get("target")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            technique: entry_data
                .get("technique")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            decision: entry_data
                .get("decision")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            reason: entry_data
                .get("reason")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            provenance: entry_data
                .get("provenance")
                .and_then(|v| serde_json::from_value(v.clone()).ok())
                .unwrap_or_default(),
            entry_hash: String::new(),
            signature: String::new(),
        };

        // Compute entry hash
        let hash_input = serde_json::to_value(&entry).unwrap();
        // Remove entry_hash and signature from hash input
        let mut hash_obj = hash_input.clone();
        if let serde_json::Value::Object(ref mut map) = hash_obj {
            map.remove("entry_hash");
            map.remove("signature");
        }
        entry.entry_hash = Self::compute_hash(&hash_obj);
        entry.signature = Self::sign_entry(&entry.entry_hash);

        // Append to in-memory list
        self.entries.push(entry.clone());
        self.persisted_payloads.push(hash_obj);

        // Append to disk
        if let Ok(json_str) = serde_json::to_string(&entry) {
            let mut file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.log_path)
                .unwrap();
            writeln!(file, "{}", json_str).unwrap();
        }

        entry
    }

    pub fn get_entries(&self, limit: usize, offset: usize) -> Vec<AuditEntry> {
        let mut entries: Vec<AuditEntry> = self.entries.iter().rev().cloned().collect();
        entries.drain(..offset.min(entries.len()));
        entries.truncate(limit);
        entries
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>, String) {
        if let Some((index, reason)) = &self.load_error {
            return (false, Some(*index), reason.clone());
        }
        if self.entries.is_empty() {
            return (true, None, "Empty log — valid".to_string());
        }

        let mut prev_hash = {
            let mut hasher = Sha256::new();
            hasher.update(b"GENESIS");
            hex::encode(hasher.finalize())
        };

        for (i, entry) in self.entries.iter().enumerate() {
            if entry.previous_hash != prev_hash {
                return (
                    false,
                    Some(i),
                    format!("Chain broken at entry {}: previous_hash mismatch", i),
                );
            }

            if !Self::verify_signature(&entry.entry_hash, &entry.signature) {
                return (false, Some(i), format!("Signature invalid at entry {}", i));
            }

            // Recompute hash
            let mut hash_obj = serde_json::to_value(entry).unwrap();
            if let serde_json::Value::Object(ref mut map) = hash_obj {
                map.remove("entry_hash");
                map.remove("signature");
            }
            let recomputed = Self::compute_hash(&hash_obj);
            if self
                .persisted_payloads
                .get(i)
                .map(Self::compute_hash)
                .as_deref()
                != Some(recomputed.as_str())
            {
                return (
                    false,
                    Some(i),
                    format!("Hash mismatch at entry {}: stored payload differs", i),
                );
            }
            if recomputed != entry.entry_hash {
                // Read-only compatibility for the exact stored JSON ordering.
                // HMAC is already verified above. Require identical typed payload
                // semantics as well; never repair a hash or accept changed data.
                let legacy_valid = self
                    .persisted_payloads
                    .get(i)
                    .map(|raw| {
                        let encoded = serde_json::to_string(raw).expect("JSON value serializes");
                        let digest = hex::encode(Sha256::digest(encoded.as_bytes()));
                        digest == entry.entry_hash && Self::compute_hash(raw) == recomputed
                    })
                    .unwrap_or(false);
                if !legacy_valid {
                    return (
                        false,
                        Some(i),
                        format!("Hash mismatch at entry {}: tampering detected", i),
                    );
                }
            }

            prev_hash = entry.entry_hash.clone();
        }

        (
            true,
            None,
            format!("Chain valid — {} entries verified", self.entries.len()),
        )
    }

    pub fn clear(&mut self) {
        self.entries.clear();
        self.persisted_payloads.clear();
        self.load_error = None;
        let path = Path::new(&self.log_path);
        if path.exists() {
            let _ = std::fs::remove_file(path);
        }
    }
}
