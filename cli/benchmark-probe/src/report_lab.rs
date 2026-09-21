//! S40 (`report`): the reader that turns a lab directory into a
//! config/measured/predicted/delta table plus the copy-paste best command.
//! Needs no engine run and no A5 — it displays the delta, it does not gate.
//!
//! Both sides come from recorded artifacts and deterministic code — never
//! invented: `measured` is the trial value from index.jsonl; `predicted` is
//! the deterministic simulator re-evaluated for the same params (for a SIM
//! lab that is the stub objective; a real lab will join the roofline kernel
//! against the known model instead). A delta != 0 therefore means a
//! corrupted record, not a discovery — and SIM cells stay labelled SIM,
//! never presented as a real benchmark.

use argos_opt::Value;
use serde::Deserialize;
use std::path::{Path, PathBuf};

use crate::tuning_search::{stub_objective, FA_CHOICES, KV_CHOICES};

pub const DEFAULT_LAB_ROOT: &str = "experiments";

#[derive(Debug, Deserialize)]
struct IndexLine {
    params: Vec<Value>,
    #[serde(default)]
    value: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct BestFile {
    #[serde(default)]
    params: Vec<Value>,
    #[serde(default)]
    value: f64,
    #[serde(default)]
    server_command: String,
}

#[derive(Debug, Deserialize)]
struct MetaFile {
    #[serde(default)]
    simulation: bool,
    #[serde(default)]
    method: String,
    #[serde(default)]
    seed: u64,
}

#[derive(Debug, serde::Serialize)]
pub struct ReportRow {
    pub config: String,
    pub measured: f64,
    pub predicted: f64,
    pub delta: f64,
}

#[derive(Debug, serde::Serialize)]
pub struct ReportBest {
    pub config: String,
    pub measured: f64,
    pub predicted: f64,
    pub delta: f64,
    pub server_command: String,
}

#[derive(Debug, serde::Serialize)]
pub struct LabReport {
    pub label: String,
    pub simulation: bool,
    pub method: String,
    pub seed: u64,
    pub rows: Vec<ReportRow>,
    pub best: ReportBest,
}

/// Human-readable config from the frozen dim order (ngl, ctx, threads, kv,
/// flash_attn — AGENTS.md / spec L03A).
fn config_of(params: &[Value]) -> String {
    let int = |i: usize| -> i64 {
        match params.get(i) {
            Some(Value::Int(x)) => *x,
            _ => 0,
        }
    };
    let cat = |i: usize, choices: &[&str]| -> String {
        match params.get(i) {
            Some(Value::Cat(k)) => choices.get(*k).unwrap_or(&"?").to_string(),
            _ => "?".to_string(),
        }
    };
    format!(
        "ngl={} ctx={} t={} kv={} fa={}",
        int(0),
        int(1),
        int(2),
        cat(3, &KV_CHOICES),
        cat(4, &FA_CHOICES)
    )
}

/// The deterministic predicted side for one params vector.
fn predicted_of(meta: &MetaFile, params: &[Value]) -> f64 {
    // SIM lab: the stub objective IS the simulator (deterministic); a real
    // lab joins the roofline kernel — the meta flag decides which world the
    // numbers belong to, and the label never lies about it.
    if meta.simulation {
        stub_objective(params).unwrap_or(f64::NAN)
    } else {
        // Real labs are not produced by any shipped path yet (A2
        // owner-blocked); refusing to fabricate a prediction is the honest
        // answer, rendered as NaN and explained in the text output.
        f64::NAN
    }
}

/// Load `experiments/<label>/` (or the latest when label is None).
pub fn load_report(root: &Path, label: Option<&str>) -> Result<LabReport, String> {
    let dir: PathBuf = match label {
        Some(name) => root.join(name),
        None => {
            let mut candidates: Vec<PathBuf> = Vec::new();
            if let Ok(entries) = std::fs::read_dir(root) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.join("best.json").is_file() {
                        candidates.push(path);
                    }
                }
            }
            // Labels are millis timestamps — lexicographic order is age.
            candidates.sort();
            candidates
                .pop()
                .ok_or_else(|| format!("no finished lab under {} — run `benchmark-probe lab --stub` first", root.display()))?
        }
    };
    if !dir.join("best.json").is_file() {
        return Err(format!(
            "no finished lab at {} (missing best.json) — labs are immutable; pick an existing --label",
            dir.display()
        ));
    }

    let meta: MetaFile = read_json(&dir.join("meta.json"))?;
    let best: BestFile = read_json(&dir.join("best.json"))?;
    let index_raw = std::fs::read_to_string(dir.join("index.jsonl"))
        .map_err(|e| format!("read {}: {e}", dir.join("index.jsonl").display()))?;
    let mut lines: Vec<IndexLine> = Vec::new();
    for line in index_raw.lines().filter(|l| !l.trim().is_empty()) {
        lines.push(
            serde_json::from_str(line)
                .map_err(|e| format!("corrupt index line in {}: {e}", dir.display()))?,
        );
    }

    let row_of = |params: &[Value], measured: f64| ReportRow {
        config: config_of(params),
        measured,
        predicted: predicted_of(&meta, params),
        delta: measured - predicted_of(&meta, params),
    };

    // Rows: successful trials (null trials never won anything — shown as skipped).
    let rows: Vec<ReportRow> = lines
        .iter()
        .filter(|l| l.value.is_some())
        .map(|l| row_of(&l.params, l.value.unwrap()))
        .collect();
    if rows.is_empty() {
        return Err(format!("lab {} has no successful trial", dir.display()));
    }

    let best_row = ReportBest {
        config: config_of(&best.params),
        measured: best.value,
        predicted: predicted_of(&meta, &best.params),
        delta: best.value - predicted_of(&meta, &best.params),
        server_command: best.server_command.clone(),
    };

    Ok(LabReport {
        label: dir
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_default(),
        simulation: meta.simulation,
        method: meta.method,
        seed: meta.seed,
        rows,
        best: best_row,
    })
}

fn read_json<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<T, String> {
    let raw = std::fs::read_to_string(path)
        .map_err(|e| format!("unable to read {}: {e}", path.display()))?;
    serde_json::from_str(&raw).map_err(|e| format!("{} is not valid: {e}", path.display()))
}

pub fn render_text(report: &LabReport) -> String {
    let sim = if report.simulation { " — SIM (stub measurements, not a benchmark claim)" } else { "" };
    let mut out = format!(
        "lab {} ({} seed {}){}\n",
        report.label, report.method, report.seed, sim
    );
    out.push_str(&format!(
        "  {:<44} {:>10} {:>10} {:>8}\n",
        "config", "measured", "predicted", "delta"
    ));
    for row in &report.rows {
        out.push_str(&format!(
            "  {:<44} {:>10.1} {:>10.1} {:>8.1}\n",
            row.config, row.measured, row.predicted, row.delta
        ));
    }
    out.push_str(&format!(
        "\nbest: {} — {:.1} (SIM)\ncommand: {}\n",
        report.best.config, report.best.measured, report.best.server_command
    ));
    out.push_str("predicted = deterministic simulator re-evaluated; delta != 0 means a corrupted record.\n");
    out
}

pub fn render_markdown(report: &LabReport) -> String {
    let sim = if report.simulation { " *(SIM — stub, not a benchmark claim)*" } else { "" };
    let mut out = format!(
        "# Lab report — `{}`{}\n\nmethod `{}` · seed {} · {} trials\n\n",
        report.label, sim, report.method, report.seed, report.rows.len()
    );
    out.push_str("| config | measured | predicted | delta |\n|---|---|---|---|\n");
    for row in &report.rows {
        out.push_str(&format!(
            "| `{}` | {:.1} | {:.1} | {:.1} |\n",
            row.config, row.measured, row.predicted, row.delta
        ));
    }
    out.push_str(&format!(
        "\n**Best:** `{}` — {:.1} (SIM)\n\n```bash\n{}\n```\n",
        report.best.config, report.best.measured, report.best.server_command
    ));
    out
}
