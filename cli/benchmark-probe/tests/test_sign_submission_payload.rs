use std::path::PathBuf;

use benchmark_probe::sign_submission_payload::{
    canonicalize_report, load_or_create_signing_key, payload_digest, sha256_hex,
    sign_payload_digest, ArtifactEntry, BenchmarkReportPayload, MetricFields, ScenarioFields,
    SCHEMA_VERSION,
};
use ed25519_dalek::{Signature, Verifier};

fn sample_report() -> BenchmarkReportPayload {
    BenchmarkReportPayload {
        schema_version: SCHEMA_VERSION.to_string(),
        run_id: "01test-run".to_string(),
        runtime: "llama_cpp".to_string(),
        runtime_version: "b4568".to_string(),
        hardware_fingerprint: "sha256:fingerprint".to_string(),
        scenario: ScenarioFields {
            prompt_tokens: 4096,
            generated_tokens: 512,
            batch_size: 1,
            context_tokens: 8192,
        },
        metrics: MetricFields {
            ttft_ms: 812.0,
            prefill_tok_s: 5041.0,
            decode_tok_s: 18.7,
            peak_vram_mib: 21811.0,
            power_watt_avg: 412.0,
        },
        artifacts: vec![ArtifactEntry {
            artifact_kind: "runtime_stdout".to_string(),
            sha256: sha256_hex(b"stdout log"),
        }],
    }
}

fn temp_key_path(label: &str) -> PathBuf {
    std::env::temp_dir()
        .join(format!("benchmark-probe-test-{}", std::process::id()))
        .join(format!("{label}.pem"))
}

#[test]
fn signature_roundtrip_verifies_with_public_key() {
    let key_path = temp_key_path("roundtrip");
    let signing_key = load_or_create_signing_key(&key_path).expect("create key");
    let canonical = canonicalize_report(&sample_report()).expect("canonicalize");
    let digest = payload_digest(&canonical);
    let signature_hex = sign_payload_digest(&signing_key, &digest);

    let signature_bytes = hex::decode(&signature_hex).expect("signature hex");
    let signature = Signature::from_slice(&signature_bytes).expect("signature");
    signing_key
        .verifying_key()
        .verify(digest.as_bytes(), &signature)
        .expect("signature verifies");
}

#[test]
fn existing_key_is_reused_not_regenerated() {
    let key_path = temp_key_path("reuse");
    let first = load_or_create_signing_key(&key_path).expect("create key");
    let second = load_or_create_signing_key(&key_path).expect("reload key");
    assert_eq!(first.to_bytes(), second.to_bytes());
}

#[test]
fn canonicalization_is_idempotent_for_identical_payloads() {
    let report = sample_report();
    let canonical_first = canonicalize_report(&report).expect("canonicalize");
    let canonical_second = canonicalize_report(&report).expect("canonicalize");
    assert_eq!(canonical_first, canonical_second);
    assert_eq!(
        payload_digest(&canonical_first),
        payload_digest(&canonical_second)
    );
}

#[test]
fn report_contains_all_required_fields() {
    let canonical = canonicalize_report(&sample_report()).expect("canonicalize");
    let value: serde_json::Value = serde_json::from_str(&canonical).expect("valid JSON");
    assert_eq!(value["schema_version"], SCHEMA_VERSION);
    for field in [
        "run_id",
        "runtime",
        "runtime_version",
        "hardware_fingerprint",
        "scenario",
        "metrics",
        "artifacts",
    ] {
        assert!(value.get(field).is_some(), "missing field {field}");
    }
    for scenario_field in [
        "prompt_tokens",
        "generated_tokens",
        "batch_size",
        "context_tokens",
    ] {
        assert!(
            value["scenario"].get(scenario_field).is_some(),
            "missing scenario field {scenario_field}"
        );
    }
    for metric_field in [
        "ttft_ms",
        "prefill_tok_s",
        "decode_tok_s",
        "peak_vram_mib",
        "power_watt_avg",
    ] {
        assert!(
            value["metrics"].get(metric_field).is_some(),
            "missing metric field {metric_field}"
        );
    }
    let artifact = &value["artifacts"][0];
    assert!(artifact.get("artifact_kind").is_some());
    assert!(artifact.get("sha256").is_some());
}

#[test]
fn artifact_digest_is_deterministic_for_identical_bytes() {
    let first = format!("sha256:{}", sha256_hex(b"artifact payload"));
    let second = format!("sha256:{}", sha256_hex(b"artifact payload"));
    let different = format!("sha256:{}", sha256_hex(b"other payload"));
    assert_eq!(first, second);
    assert_ne!(first, different);
    assert!(first.starts_with("sha256:"));
}
