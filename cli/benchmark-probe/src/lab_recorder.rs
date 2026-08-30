//! lab_recorder.rs — L01 slice: the frozen, resumable lab directory.
//!
//! experiments/<label>/ holds:
//!   meta.json   — the frozen experiment header (written once, at create)
//!   index.jsonl — one JSON line per trial, append-only
//!   best.json   — written at finish with the winner + server command
//!
//! Format is AI-friendly and flat by design (L01: "flat, AI-friendly, one
//! line per cell").

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use argos_opt::{Dim, Value};
use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
pub struct LabMeta {
    pub method: String,
    pub seed: u64,
    pub max_evals: usize,
    pub objective: String,
    pub space: Vec<Dim>,
    pub simulation: bool,
}

#[derive(Debug, Serialize)]
pub struct LabBest {
    pub params: Vec<Value>,
    pub value: f64,
    pub server_command: String,
}

pub struct LabRecorder {
    dir: PathBuf,
    index_path: PathBuf,
}

impl LabRecorder {
    /// Creates experiments/<label>/ fresh. An existing directory with the
    /// same label is an error (labs are immutable once recorded; resume
    /// comes from argos-opt's TrialLog, not from editing a lab).
    pub fn create(root: &Path, label: &str, meta: &LabMeta) -> Result<LabRecorder, String> {
        let dir = root.join(label);
        if dir.exists() {
            return Err(format!("lab dir already exists: {}", dir.display()));
        }
        fs::create_dir_all(&dir).map_err(|e| format!("create {}: {e}", dir.display()))?;
        let meta_json = serde_json::to_string_pretty(meta)
            .map_err(|e| format!("meta serialize: {e}"))?;
        fs::write(dir.join("meta.json"), format!("{meta_json}\n"))
            .map_err(|e| format!("write meta.json: {e}"))?;
        let index_path = dir.join("index.jsonl");
        fs::write(&index_path, b"").map_err(|e| format!("create index.jsonl: {e}"))?;
        Ok(LabRecorder { dir, index_path })
    }

    /// One line per trial; `value: None` is a failed trial (null in JSON).
    pub fn append(&self, trial: usize, params: &[Value], value: Option<f64>) -> Result<(), String> {
        let line = serde_json::json!({ "trial": trial, "params": params, "value": value });
        let mut f = OpenOptions::new()
            .append(true)
            .open(&self.index_path)
            .map_err(|e| format!("open {}: {e}", self.index_path.display()))?;
        writeln!(f, "{line}").map_err(|e| format!("append index.jsonl: {e}"))
    }

    pub fn finish(&self, best: &LabBest) -> Result<(), String> {
        let json = serde_json::to_string_pretty(best)
            .map_err(|e| format!("best serialize: {e}"))?;
        fs::write(self.dir.join("best.json"), format!("{json}\n"))
            .map_err(|e| format!("write best.json: {e}"))
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn meta() -> LabMeta {
        LabMeta {
            method: "tpe".into(),
            seed: 42,
            max_evals: 10,
            objective: "stub".into(),
            space: vec![Dim::Integer { low: 0, high: 1 }],
            simulation: true,
        }
    }

    #[test]
    fn recorder_roundtrip_and_refusal() {
        let root = std::env::temp_dir().join(format!("bm-lab-rec-{}", std::process::id()));
        fs::remove_dir_all(&root).ok();
        let rec = LabRecorder::create(&root, "lab-a", &meta()).unwrap();
        for i in 0..10 {
            rec.append(i, &[Value::Int(i as i64)], if i % 3 == 0 { None } else { Some(i as f64) })
                .unwrap();
        }
        rec.finish(&LabBest {
            params: vec![Value::Int(7)],
            value: 1.0,
            server_command: "llama-server -m MODEL.gguf".into(),
        })
        .unwrap();

        // interrupted run = 10 valid JSONL lines, nulls preserved
        let text = fs::read_to_string(root.join("lab-a/index.jsonl")).unwrap();
        let lines: Vec<serde_json::Value> =
            text.lines().map(|l| serde_json::from_str(l).unwrap()).collect();
        assert_eq!(lines.len(), 10);
        assert_eq!(lines[0]["value"], serde_json::Value::Null);
        assert_eq!(lines[1]["value"], 1.0);

        // same label is refused: labs are immutable once recorded
        assert!(LabRecorder::create(&root, "lab-a", &meta()).is_err());
        fs::remove_dir_all(&root).ok();
    }
}
