use std::collections::HashSet;

use benchmark_probe::comfyui_adapter::{parse_comfy_events, sampler_node_ids};

const EVENTS_FIXTURE: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/tests/fixtures/comfy-events.ndjson"
);
const WORKFLOW_FIXTURE: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/recipes/workflows/wan22-flf2v-api.json.tpl"
);

/// Replays the frozen fixture after substituting markers the same way the
/// adapter does, so the fixture workflow yields the real sampler node id.
fn load_fixture_events() -> Vec<(f64, serde_json::Value)> {
    let raw = std::fs::read_to_string(EVENTS_FIXTURE).expect("fixture readable");
    raw.lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| {
            let value: serde_json::Value = serde_json::from_str(line).expect("valid NDJSON line");
            let ts = value.get("ts").and_then(|t| t.as_f64()).expect("ts field");
            (ts, value)
        })
        .collect()
}

#[test]
fn frozen_fixture_yields_exact_expected_numbers() {
    let events = load_fixture_events();
    let mut samplers = HashSet::new();
    samplers.insert("8".to_string());
    let metrics = parse_comfy_events(&events, &samplers, 81).expect("metrics parse");
    assert!((metrics.seconds_per_clip - 4.0).abs() < 1e-9, "clip={}", metrics.seconds_per_clip);
    assert_eq!(metrics.seconds_sampling, Some(2.0));
    assert!(
        (metrics.it_per_s.expect("it/s present") - 10.0).abs() < 1e-9,
        "it_per_s={:?}",
        metrics.it_per_s
    );
    assert!((metrics.frames_per_s - 20.25).abs() < 1e-9);
    assert_eq!(metrics.sampler_steps, Some(20));
}

#[test]
fn vae_decode_progress_is_not_sampler_progress() {
    // Node "10" (VAEDecode) emits progress 40/81 in the fixture; the sampler
    // window must stay 1.5→3.5 (2.0 s) — covered by the exact numbers above.
    // This test pins the discriminator itself: VAEDecode is not a sampler id.
    let workflow: serde_json::Value = {
        let raw = std::fs::read_to_string(WORKFLOW_FIXTURE).expect("tpl readable")
            .replace("__WIDTH__", "1280")
            .replace("__HEIGHT__", "720")
            .replace("__FRAMES__", "81")
            .replace("__STEPS__", "20")
            .replace("__CFG__", "3.5")
            .replace("__SHIFT__", "5.0")
            .replace("__SEED__", "42")
            .replace("__FIRST_IMAGE__", "in/first.png")
            .replace("__LAST_IMAGE__", "in/last.png")
            .replace("__PROMPT__", "")
            .replace("__MODEL__", "wan22-i2v-flf2v");
        serde_json::from_str(&raw).expect("materialized workflow valid")
    };
    let samplers = sampler_node_ids(&workflow);
    assert!(samplers.contains("8"), "WanFirstLastFrameToVideo is a sampler: {samplers:?}");
    assert!(!samplers.contains("10"), "VAEDecode must not be a sampler");
    assert!(!samplers.contains("1"), "UNETLoader must not be a sampler");
}

#[test]
fn stream_without_sampler_progress_still_measures_clip_wall() {
    let events = vec![
        (
            0.0,
            serde_json::json!({"type": "executing", "data": {"node": "1"}}),
        ),
        (
            5.0,
            serde_json::json!({"type": "output", "data": {"node": "11"}}),
        ),
    ];
    let metrics = parse_comfy_events(&events, &HashSet::new(), 81).expect("metrics parse");
    assert_eq!(metrics.seconds_per_clip, 5.0);
    assert_eq!(metrics.seconds_sampling, None);
    assert_eq!(metrics.it_per_s, None);
    assert!((metrics.frames_per_s - 81.0 / 5.0).abs() < 1e-9);
}

#[test]
fn empty_stream_is_an_error() {
    let err = parse_comfy_events(&[], &HashSet::new(), 81).expect_err("must fail");
    assert!(err.contains("no events"), "unexpected error: {err}");
}

#[test]
fn single_event_stream_is_an_error() {
    let events = vec![(0.0, serde_json::json!({"type": "status"}))];
    let err = parse_comfy_events(&events, &HashSet::new(), 25).expect_err("must fail");
    assert!(err.contains("implausible"), "unexpected error: {err}");
}
