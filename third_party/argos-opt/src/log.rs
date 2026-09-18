//! Trial log: the resumable, on-disk record of what the optimizer did.

use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::space::Value;

/// The outcome of one evaluation. The engine MINIMIZES: `Value(loss)` with
/// a lower loss is better; `Failed` marks a crashed/OOMed trial — it is
/// recorded, never proposed again, and can never win `best()`.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum TrialResult {
    Value(f64),
    Failed,
}

/// One logged trial: what was asked, and what came back.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TrialEntry {
    pub params: Vec<Value>,
    pub result: TrialResult,
}

/// Append-friendly, JSON-serializable log of trials. `Optimizer::resume`
/// replays it to rebuild optimizer state exactly.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct TrialLog {
    pub trials: Vec<TrialEntry>,
}

impl TrialLog {
    pub fn new() -> TrialLog {
        TrialLog { trials: Vec::new() }
    }

    pub fn record(&mut self, params: Vec<Value>, result: TrialResult) {
        self.trials.push(TrialEntry { params, result });
    }

    pub fn len(&self) -> usize {
        self.trials.len()
    }

    pub fn is_empty(&self) -> bool {
        self.trials.is_empty()
    }

    /// Best (lowest-loss) successful trial, if any. First one wins ties.
    pub fn best(&self) -> Option<(&[Value], f64)> {
        let mut best: Option<(usize, f64)> = None;
        for (i, e) in self.trials.iter().enumerate() {
            if let TrialResult::Value(loss) = e.result {
                if best.map(|(_, l)| loss < l).unwrap_or(true) {
                    best = Some((i, loss));
                }
            }
        }
        best.map(|(i, l)| (self.trials[i].params.as_slice(), l))
    }

    pub fn save<P: AsRef<Path>>(&self, path: P) -> Result<(), String> {
        let text = serde_json::to_string(self)
            .map_err(|e| format!("serialize log: {e}"))?;
        fs::write(path.as_ref(), format!("{text}\n"))
            .map_err(|e| format!("write {}: {e}", path.as_ref().display()))
    }

    pub fn load<P: AsRef<Path>>(path: P) -> Result<TrialLog, String> {
        let text = fs::read_to_string(path.as_ref())
            .map_err(|e| format!("read {}: {e}", path.as_ref().display()))?;
        serde_json::from_str(&text).map_err(|e| format!("parse {}: {e}", path.as_ref().display()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_and_best() {
        let mut log = TrialLog::new();
        log.record(vec![Value::Int(1)], TrialResult::Value(3.0));
        log.record(vec![Value::Int(2)], TrialResult::Failed);
        log.record(vec![Value::Int(3)], TrialResult::Value(1.0));
        log.record(vec![Value::Int(4)], TrialResult::Value(1.0)); // ties, first wins

        let dir = std::env::temp_dir().join(format!("argos-log-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("log.json");
        log.save(&path).unwrap();
        let back = TrialLog::load(&path).unwrap();
        assert_eq!(back, log);

        let (p, l) = log.best().unwrap();
        assert_eq!(p, &[Value::Int(3)][..]);
        assert_eq!(l, 1.0);
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn all_failed_has_no_best() {
        let mut log = TrialLog::new();
        log.record(vec![Value::Cat(0)], TrialResult::Failed);
        assert!(log.best().is_none());
    }
}
