use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum Provenance {
    Trusted,
    Untrusted,
}

pub struct TaintTracker {
    taint_map: HashMap<String, Provenance>,
}

impl TaintTracker {
    pub fn new() -> Self {
        Self {
            taint_map: HashMap::new(),
        }
    }

    pub fn mark_trusted(&mut self, key: &str) {
        self.taint_map.insert(key.to_string(), Provenance::Trusted);
    }

    pub fn mark_untrusted(&mut self, key: &str) {
        self.taint_map.insert(key.to_string(), Provenance::Untrusted);
    }

    pub fn get_provenance(&self, key: &str) -> Provenance {
        self.taint_map.get(key).cloned().unwrap_or(Provenance::Untrusted)
    }

    pub fn is_tainted(&self, key: &str) -> bool {
        self.get_provenance(key) == Provenance::Untrusted
    }

    pub fn check_tool_call(&self, provenance: &HashMap<String, String>) -> (bool, String, Vec<String>) {
        let mut tainted_args = Vec::new();
        for (arg_name, prov) in provenance {
            if prov == "untrusted" {
                tainted_args.push(arg_name.clone());
            }
        }
        if !tainted_args.is_empty() {
            return (false, format!("Tainted arguments detected: {:?}", tainted_args), tainted_args);
        }
        (true, "All arguments have trusted provenance".to_string(), Vec::new())
    }
}
