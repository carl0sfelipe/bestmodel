//! S41 (`contribute`): turns the best cell of a lab session into an
//! existing contract-0.9.0 signed report — CLI-only, no backend change.
//!
//! Honesty rules that shape this file:
//! - SIM/stub cells are NEVER uploaded (the stub objective is not a
//!   measurement); `--no-upload` writes the local bundle, clearly labelled.
//! - The report reuses the same sign path as every run (canonical JSON,
//!   SHA-256 digest, Ed25519) — never a fabricated field beyond 0.9.0.
//! - Consent is A3: opt-out transparent — visible, pre-checked, one step.

use crate::report_lab::{self, LabReport};
use crate::sign_submission_payload::{
    generate_run_id, sha256_hex, ArtifactEntry, BenchmarkReportPayload, MetricFields,
    ScenarioFields, ScenarioPayload, SCHEMA_VERSION,
};

/// The best cell of a lab, flattened for report building.
pub struct ContributeCell {
    pub config: String,
    pub decode_tok_s: f64,
    pub context_tokens: i64,
}

/// Select the best cell from a lab directory (default: latest finished).
pub fn select_best(label: Option<&str>) -> Result<(LabReport, ContributeCell), String> {
    let root = std::path::Path::new(report_lab::DEFAULT_LAB_ROOT);
    let report = report_lab::load_report(root, label)?;
    let ctx = report
        .best
        .config
        .split_whitespace()
        .find(|token| token.starts_with("ctx="))
        .and_then(|token| token.strip_prefix("ctx="))
        .and_then(|value| value.parse::<i64>().ok())
        .unwrap_or(8192);
    let cell = ContributeCell {
        config: report.best.config.clone(),
        decode_tok_s: report.best.measured,
        context_tokens: ctx,
    };
    Ok((report, cell))
}

/// Contract-0.9.0 report for the cell. The runtime string names the world
/// the number came from (`lab-stub-sim`); the evidence artifact carries the
/// SIM label verbatim — the bundle can never be mistaken for a measurement.
pub fn build_cell_report(
    cell: &ContributeCell,
    lab_label: &str,
    simulation: bool,
    fingerprint: &str,
) -> (BenchmarkReportPayload, String) {
    let runtime = if simulation { "lab-stub-sim" } else { "llama_cpp_lab" };
    let evidence = format!(
        "SIM — stub lab {lab_label} — best config {} — {:.1} tok/s from the deterministic simulator; not a benchmark claim",
        cell.config, cell.decode_tok_s
    );
    let report = BenchmarkReportPayload {
        schema_version: SCHEMA_VERSION.to_string(),
        run_id: generate_run_id(),
        runtime: runtime.to_string(),
        runtime_version: format!("tpe-lab-{lab_label}"),
        hardware_fingerprint: fingerprint.to_string(),
        scenario: ScenarioPayload::Llm(ScenarioFields {
            prompt_tokens: 4096,
            generated_tokens: 512,
            batch_size: 1,
            context_tokens: cell.context_tokens as u32,
        }),
        // Non-decode metrics do not exist in a stub lab; 0.0 is the schema's
        // neutral value and the SIM evidence + runtime string say why.
        metrics: MetricFields {
            ttft_ms: 0.0,
            prefill_tok_s: 0.0,
            decode_tok_s: cell.decode_tok_s,
            peak_vram_mib: 0.0,
            power_watt_avg: 0.0,
            seconds_per_clip: None,
            it_per_s: None,
            frames_per_s: None,
        },
        artifacts: vec![ArtifactEntry {
            artifact_kind: "runtime_stdout".to_string(),
            sha256: sha256_hex(evidence.as_bytes()),
        }],
        recipe_id: None,
    };
    (report, evidence)
}
