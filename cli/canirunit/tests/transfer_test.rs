//! Story 3.2: cross-hardware transfer in `canirunit suggest`.

use std::collections::BTreeMap;
use std::process::{Command, Output};

use canirunit::transfer::{effective_tflops, time_factor, GpuTransferSpec};
use canirunit::{suggest, suggest_with_transfer, RunEntry};

const SPECS_PATH: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/gpu_transfer_specs.json");
const RUNS_4090: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/runs-derived-4090.json");
const RUNS_3090: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/runs-3090.json");

// Provenance of the anchor numbers: the Story 3.1 simulator exported
// gpu-rtx-4090 = 2957.815 s/clip (fp8 path) and gpu-rtx-3090 = 13729.981 s/clip
// (fp16-compute path) from the Python estimator over catalog specs.
const ANCHOR_4090_CLIP_S: f64 = 2957.815;
const DIRECT_3090_ESTIMATE_S: f64 = 13729.981;

fn load_specs() -> BTreeMap<String, GpuTransferSpec> {
    let raw = std::fs::read_to_string(SPECS_PATH).expect("specs readable");
    let list: Vec<GpuTransferSpec> = serde_json::from_str(&raw).expect("valid specs");
    list.into_iter().map(|spec| (spec.id.clone(), spec)).collect()
}

fn load_runs(path: &str) -> Vec<RunEntry> {
    let raw = std::fs::read_to_string(path).expect("runs readable");
    serde_json::from_str(&raw).expect("valid runs")
}

#[test]
fn transfer_reproduces_direct_estimator_within_0_1_percent() {
    // The Rust roofline ratio (catalog: 4090 fp16 82.58 with fp8 doubling vs
    // 3090 35.58) must land within 0.1% of the Python estimator's direct
    // 3090 number — the calibration knob cancels, so this is exact algebra.
    let specs = load_specs();
    let runs = load_runs(RUNS_4090);
    let outcome = suggest_with_transfer("gpu-rtx-3090", "seconds_per_clip", &runs, Some(&specs))
        .expect("suggest ok");
    assert_eq!(outcome.match_class, "roofline_transfer");
    let transferred = outcome.suggestions[0].expected;
    let relative_error = (transferred - DIRECT_3090_ESTIMATE_S).abs() / DIRECT_3090_ESTIMATE_S;
    assert!(
        relative_error < 0.001,
        "transfer {transferred} vs direct {DIRECT_3090_ESTIMATE_S} (err {relative_error:.5})"
    );
    assert_eq!(outcome.suggestions[0].source_class, "derived");
}

#[test]
fn explanation_names_anchor_factor_and_disclaimer() {
    let specs = load_specs();
    let runs = load_runs(RUNS_4090);
    let outcome = suggest_with_transfer("gpu-rtx-3090", "seconds_per_clip", &runs, Some(&specs))
        .expect("suggest ok");
    let explanation = &outcome.suggestions[0].explanation;
    assert!(explanation.contains("gpu-rtx-4090"), "anchor named: {explanation}");
    assert!(explanation.contains("factor 4.64"), "numeric factor: {explanation}");
    assert!(explanation.contains("NOT measured"), "disclaimer: {explanation}");
    assert!(explanation.contains("different architecture"), "cross-family: {explanation}");
}

#[test]
fn same_architecture_family_transfer_gets_higher_tier() {
    // 4070 Ti Super and 4090 are both Ada: same_arch_family, and the factor
    // follows eff(4090)/eff(4070ti) = 165.16/88.2.
    let specs = load_specs();
    let runs = load_runs(RUNS_4090);
    let outcome =
        suggest_with_transfer("gpu-rtx-4070-ti-super", "seconds_per_clip", &runs, Some(&specs))
            .expect("suggest ok");
    assert_eq!(outcome.match_class, "same_arch_family");
    let anchor = &specs["gpu-rtx-4090"];
    let target = &specs["gpu-rtx-4070-ti-super"];
    let expected = ANCHOR_4090_CLIP_S * time_factor(anchor, target);
    let got = outcome.suggestions[0].expected;
    assert!((got - expected).abs() < 0.05, "got {got}, expected {expected}");
}

#[test]
fn rate_metric_transfers_in_the_opposite_direction() {
    // decode_tok_s (higher is better): a slower target gets a SMALLER value.
    let specs = load_specs();
    let runs: Vec<RunEntry> = serde_json::from_str(
        r#"[{
            "run_id": "llm-4090", "gpu_model_id": "gpu-rtx-4090",
            "model_release_id": "model-qwen3-8b", "recipe_id": null,
            "source_class": "measured_signed", "trust_score": 1.0,
            "age_days": 0.0, "decode_tok_s": 130.0
        }]"#,
    )
    .expect("valid");
    let outcome = suggest_with_transfer("gpu-rtx-3090", "decode_tok_s", &runs, Some(&specs))
        .expect("suggest ok");
    let anchor = &specs["gpu-rtx-4090"];
    let target = &specs["gpu-rtx-3090"];
    let expected = 130.0 / time_factor(anchor, target);
    assert_eq!(outcome.match_class, "roofline_transfer");
    assert!(
        (outcome.suggestions[0].expected - expected).abs() < 0.05,
        "got {}, expected {expected}",
        outcome.suggestions[0].expected
    );
    assert!(outcome.suggestions[0].expected < 130.0);
}

#[test]
fn exact_runs_are_never_shadowed_by_transfer() {
    let specs = load_specs();
    let runs = load_runs(RUNS_3090); // has a measured 3090 LLM run
    let outcome = suggest_with_transfer("gpu-rtx-3090", "decode_tok_s", &runs, Some(&specs))
        .expect("suggest ok");
    assert_eq!(outcome.match_class, "exact_gpu");
    assert_eq!(outcome.suggestions[0].source_class, "measured_signed");
}

#[test]
fn without_specs_transfer_does_not_happen() {
    let runs = load_runs(RUNS_4090);
    let outcome = suggest_with_transfer("gpu-rtx-3090", "seconds_per_clip", &runs, None)
        .expect("suggest ok");
    assert_eq!(outcome.match_class, "unknown");
    // And the classic 3-arg API stays intact.
    assert_eq!(suggest("gpu-rtx-3090", "seconds_per_clip", &runs).unwrap().match_class, "unknown");
}

#[test]
fn effective_tflops_follow_fp8_silicon_support() {
    let specs = load_specs();
    assert_eq!(effective_tflops(&specs["gpu-rtx-4090"]), 82.58 * 2.0);
    assert_eq!(effective_tflops(&specs["gpu-rtx-3090"]), 35.58); // sm86: no fp8 doubling
}

fn run_binary(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_canirunit"))
        .args(args)
        .output()
        .expect("failed to spawn canirunit")
}

#[test]
fn cli_transfers_with_gpus_flag_and_stays_unknown_without_it() {
    let with = run_binary(&[
        "suggest", "--gpu", "gpu-rtx-3090", "--task", "seconds_per_clip",
        "--runs", RUNS_4090, "--gpus", SPECS_PATH,
    ]);
    assert!(with.status.success(), "stderr: {}", String::from_utf8_lossy(&with.stderr));
    let text = String::from_utf8_lossy(&with.stdout);
    let parsed: serde_json::Value = serde_json::from_str(&text).expect("JSON out");
    assert_eq!(parsed["match_class"], "roofline_transfer");
    assert_eq!(parsed["suggestions"][0]["source_class"], "derived");

    let without = run_binary(&[
        "suggest", "--gpu", "gpu-rtx-3090", "--task", "seconds_per_clip",
        "--runs", RUNS_4090,
    ]);
    assert_eq!(without.status.code(), Some(3));
    let parsed: serde_json::Value =
        serde_json::from_str(&String::from_utf8_lossy(&without.stdout)).expect("JSON out");
    assert_eq!(parsed["match_class"], "unknown");
}
