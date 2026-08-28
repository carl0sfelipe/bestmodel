//! Builds the 0.9.0 benchmark report, canonicalizes it, and signs the payload
//! digest with a local Ed25519 key (plan sections 9.3 and 12.1).

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use ed25519_dalek::pkcs8::DecodePrivateKey;
use ed25519_dalek::{Signer, SigningKey};
use rand::rngs::OsRng;
use serde::Serialize;
use sha2::{Digest, Sha256};

pub const SCHEMA_VERSION: &str = "0.9.0";
pub const DIGEST_PREFIX: &str = "sha256:";
const KEY_ENV_VAR: &str = "BENCHMARK_PROBE_KEY_PATH";
const DEFAULT_KEY_RELATIVE_PATH: &str = ".config/benchmark-probe/ed25519.pem";

#[derive(Clone, Serialize)]
pub struct ScenarioFields {
    pub prompt_tokens: u32,
    pub generated_tokens: u32,
    pub batch_size: u32,
    pub context_tokens: u32,
}

/// Video scenario (Épico 1). Own fields, never the token fields above (AD-1).
#[derive(Clone, Serialize)]
pub struct VideoScenarioFields {
    pub scenario_kind: &'static str,
    pub width: u32,
    pub height: u32,
    pub frames: u32,
    pub steps: u32,
    pub cfg: f64,
    pub shift: f64,
    pub seed: u64,
}

#[derive(Clone, Serialize)]
#[serde(untagged)]
pub enum ScenarioPayload {
    Llm(ScenarioFields),
    Video(VideoScenarioFields),
}

#[derive(Clone, Serialize)]
pub struct MetricFields {
    pub ttft_ms: f64,
    pub prefill_tok_s: f64,
    pub decode_tok_s: f64,
    pub peak_vram_mib: f64,
    pub power_watt_avg: f64,
    // Video/diffusion metrics (Épico 1). Optional so LLM reports stay
    // byte-identical to schema 0.9.0 (digest stability).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seconds_per_clip: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub it_per_s: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub frames_per_s: Option<f64>,
}

#[derive(Clone, Serialize)]
pub struct ArtifactEntry {
    pub artifact_kind: String,
    pub sha256: String,
}

#[derive(Clone, Serialize)]
pub struct BenchmarkReportPayload {
    pub schema_version: String,
    pub run_id: String,
    pub runtime: String,
    pub runtime_version: String,
    pub hardware_fingerprint: String,
    pub scenario: ScenarioPayload,
    pub metrics: MetricFields,
    pub artifacts: Vec<ArtifactEntry>,
    // Video runs reference the standardized workload they measured (Épico 1).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recipe_id: Option<String>,
}

pub fn canonicalize_report(report: &BenchmarkReportPayload) -> Result<String, String> {
    let value = serde_json::to_value(report).map_err(|err| err.to_string())?;
    serde_json::to_string(&sort_object_keys(&value)).map_err(|err| err.to_string())
}

fn sort_object_keys(value: &serde_json::Value) -> serde_json::Value {
    match value {
        serde_json::Value::Object(map) => {
            let sorted: BTreeMap<String, serde_json::Value> = map
                .iter()
                .map(|(key, inner)| (key.clone(), sort_object_keys(inner)))
                .collect();
            serde_json::Value::Object(sorted.into_iter().collect())
        }
        serde_json::Value::Array(items) => {
            serde_json::Value::Array(items.iter().map(sort_object_keys).collect())
        }
        leaf => leaf.clone(),
    }
}

pub fn payload_digest(canonical_payload: &str) -> String {
    let digest = Sha256::digest(canonical_payload.as_bytes());
    format!("{DIGEST_PREFIX}{}", hex::encode(digest))
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn resolve_key_path() -> PathBuf {
    match std::env::var(KEY_ENV_VAR) {
        Ok(path) => PathBuf::from(path),
        Err(_) => home_dir().join(DEFAULT_KEY_RELATIVE_PATH),
    }
}

fn home_dir() -> PathBuf {
    PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".to_string()))
}

pub fn load_or_create_signing_key(key_path: &Path) -> Result<SigningKey, String> {
    if key_path.exists() {
        return read_signing_key(key_path);
    }
    create_signing_key(key_path)
}

fn read_signing_key(key_path: &Path) -> Result<SigningKey, String> {
    let pem = fs::read_to_string(key_path)
        .map_err(|err| format!("unable to read key at {}: {err}", key_path.display()))?;
    SigningKey::from_pkcs8_pem(&pem)
        .map_err(|err| format!("invalid Ed25519 key at {}: {err}", key_path.display()))
}

fn create_signing_key(key_path: &Path) -> Result<SigningKey, String> {
    let signing_key = SigningKey::generate(&mut OsRng);
    let pem = encode_pkcs8_v1_pem(&signing_key.to_bytes());
    if let Some(parent) = key_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("unable to create key directory: {err}"))?;
    }
    fs::write(key_path, pem.as_bytes())
        .map_err(|err| format!("unable to write key at {}: {err}", key_path.display()))?;
    Ok(signing_key)
}

// RFC 8410 PKCS#8 v1: SEQUENCE { INTEGER 0, AlgorithmIdentifier(id-Ed25519),
// OCTET STRING { OCTET STRING seed } }. The fixed 16-byte DER prefix keeps the
// encoding portable across PEM parsers.
fn encode_pkcs8_v1_pem(seed: &[u8; 32]) -> String {
    const PKCS8_ED25519_PREFIX: [u8; 16] = [
        0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04,
        0x20,
    ];
    let mut der = Vec::with_capacity(PKCS8_ED25519_PREFIX.len() + seed.len());
    der.extend_from_slice(&PKCS8_ED25519_PREFIX);
    der.extend_from_slice(seed);
    let encoded = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &der);
    let mut pem = String::from("-----BEGIN PRIVATE KEY-----\n");
    pem.push_str(&encoded);
    pem.push('\n');
    pem.push_str("-----END PRIVATE KEY-----\n");
    pem
}

pub fn sign_payload_digest(signing_key: &SigningKey, digest: &str) -> String {
    hex::encode(signing_key.sign(digest.as_bytes()).to_bytes())
}

pub fn generate_run_id() -> String {
    let mut random_bytes = [0u8; 16];
    rand::RngCore::fill_bytes(&mut OsRng, &mut random_bytes);
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0);
    format!("{timestamp:012x}{}", hex::encode(random_bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_report() -> BenchmarkReportPayload {
        BenchmarkReportPayload {
            schema_version: SCHEMA_VERSION.to_string(),
            run_id: "run-1".to_string(),
            runtime: "llama_cpp".to_string(),
            runtime_version: "b4568".to_string(),
            hardware_fingerprint: "sha256:abc".to_string(),
            scenario: ScenarioPayload::Llm(ScenarioFields {
                prompt_tokens: 4096,
                generated_tokens: 512,
                batch_size: 1,
                context_tokens: 8192,
            }),
            metrics: MetricFields {
                ttft_ms: 812.0,
                prefill_tok_s: 5041.0,
                decode_tok_s: 18.7,
                peak_vram_mib: 21811.0,
                power_watt_avg: 412.0,
                seconds_per_clip: None,
                it_per_s: None,
                frames_per_s: None,
            },
            artifacts: vec![ArtifactEntry {
                artifact_kind: "runtime_stdout".to_string(),
                sha256: "deadbeef".to_string(),
            }],
            recipe_id: None,
        }
    }

    #[test]
    fn canonicalization_is_deterministic() {
        let report = sample_report();
        let first = canonicalize_report(&report).expect("canonicalize");
        let second = canonicalize_report(&report).expect("canonicalize");
        assert_eq!(first, second);
        assert_eq!(payload_digest(&first), payload_digest(&second));
    }

    #[test]
    fn canonical_keys_are_sorted() {
        let canonical = canonicalize_report(&sample_report()).expect("canonicalize");
        let artifacts_pos = canonical.find("\"artifacts\"").expect("artifacts key");
        let run_id_pos = canonical.find("\"run_id\"").expect("run_id key");
        assert!(artifacts_pos < run_id_pos);
    }
}
