use std::process::{Command, Output};

use canirunit::{suggest, RunEntry};

const RUNS_FIXTURE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/runs-3090.json");
const RUNS_EMPTY: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/runs-empty.json");

fn load_runs() -> Vec<RunEntry> {
    let raw = std::fs::read_to_string(RUNS_FIXTURE).expect("fixture readable");
    serde_json::from_str(&raw).expect("valid fixture")
}

#[test]
fn three_runs_yield_exact_weighted_mean() {
    // Weights 0.5, 1.0, 0.5 over 88.0, 92.0, 96.0:
    // (0.5*88 + 1.0*92 + 0.5*96) / 2.0 = 92.0 exactly.
    let runs = load_runs();
    let outcome = suggest("gpu-rtx-3090", "decode_tok_s", &runs).expect("suggest ok");
    assert_eq!(outcome.match_class, "exact_gpu");
    assert_eq!(outcome.suggestions.len(), 1);
    let suggestion = &outcome.suggestions[0];
    assert_eq!(suggestion.model_release_id, "model-qwen3-8b");
    assert_eq!(suggestion.n_runs, 3);
    assert!((suggestion.expected - 92.0).abs() < 1e-9, "got {}", suggestion.expected);
    // Weighted variance: 0.5*(88-92)^2 + 1.0*(92-92)^2 + 0.5*(96-92)^2) / 2.0 = 8.0
    assert!((suggestion.variance - 8.0).abs() < 1e-9, "got {}", suggestion.variance);
    assert_eq!(suggestion.source_class, "measured_signed");
    assert!(suggestion.explanation.contains("3 run(s)"));
    assert!(suggestion.explanation.contains("model-qwen3-8b"));
    assert!(suggestion.explanation.contains("variance"));
    // The 4090 run must never leak into a 3090 suggestion.
    assert!(!suggestion.explanation.contains("130"));
}

#[test]
fn video_metric_ranks_lower_is_better() {
    let runs = load_runs();
    let outcome = suggest("gpu-rtx-3090", "seconds_per_clip", &runs).expect("suggest ok");
    assert_eq!(outcome.better, "lower");
    let suggestion = &outcome.suggestions[0];
    assert_eq!(suggestion.model_release_id, "model-wan22-i2v-flf2v-14b");
    assert_eq!(suggestion.recipe_id.as_deref(), Some("wan22-flf2v-720p-81f-v1"));
    assert!((suggestion.expected - 123.4).abs() < 1e-9);
}

#[test]
fn zero_runs_is_honest_unknown() {
    let runs: Vec<RunEntry> = Vec::new();
    let outcome = suggest("gpu-rtx-5090", "decode_tok_s", &runs).expect("suggest ok");
    assert_eq!(outcome.match_class, "unknown");
    assert!(outcome.suggestions.is_empty());
    let explanation = outcome.explanation.expect("explanation present");
    assert!(explanation.contains("no measured runs"), "got: {explanation}");
    assert!(explanation.contains("gpu-rtx-5090"));
}

#[test]
fn unsupported_metric_is_an_error() {
    let runs = load_runs();
    let err = suggest("gpu-rtx-3090", "vibes", &runs).expect_err("must fail");
    assert!(err.contains("unsupported task metric"));
}

fn run_binary(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_canirunit"))
        .args(args)
        .output()
        .expect("failed to spawn canirunit binary")
}

#[test]
fn cli_end_to_end_from_fixture() {
    let output = run_binary(&[
        "suggest",
        "--gpu",
        "gpu-rtx-3090",
        "--task",
        "decode_tok_s",
        "--runs",
        RUNS_FIXTURE,
    ]);
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let text = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = serde_json::from_str(&text).expect("stdout is JSON");
    assert_eq!(parsed["match_class"], "exact_gpu");
    assert_eq!(parsed["suggestions"][0]["n_runs"], 3);
    assert_eq!(parsed["suggestions"][0]["expected"], 92.0);
}

#[test]
fn cli_no_runs_exits_three_with_unknown_class() {
    let output = run_binary(&[
        "suggest",
        "--gpu",
        "gpu-rtx-5090",
        "--task",
        "decode_tok_s",
        "--runs",
        RUNS_EMPTY,
    ]);
    assert_eq!(output.status.code(), Some(3));
    let parsed: serde_json::Value =
        serde_json::from_str(&String::from_utf8_lossy(&output.stdout)).expect("JSON");
    assert_eq!(parsed["match_class"], "unknown");
}
