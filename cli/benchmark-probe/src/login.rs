//! S42 (`login`): the CLI side of S23 — store an account token in a 0600
//! config file and register the LOCAL Ed25519 PUBLIC key with the account
//! via the existing POST /v1/auth/signing-keys. Existing endpoints only;
//! the private key never leaves the machine; the token is never printed.

use serde::{Deserialize, Serialize};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;

use crate::sign_submission_payload::{load_or_create_signing_key, resolve_key_path};

const CONFIG_RELATIVE_PATH: &str = ".config/benchmark-probe/config";
const TOKEN_ENV_VAR: &str = "BENCHMARK_PROBE_API_TOKEN";
const API_URL_ENV_VAR: &str = "BENCHMARK_PROBE_API_URL";
const DEFAULT_API_URL: &str = "http://localhost:8000";

#[derive(Debug, Default, Serialize, Deserialize)]
pub struct LoginConfig {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub token: Option<String>,
    /// A3 consent (opt-out transparent): None = never asked; Some(true) =
    /// pre-checked default accepted; Some(false) = opted out, always honored.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub consent_share_runs: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signing_key_id: Option<String>,
}

pub fn config_path() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(CONFIG_RELATIVE_PATH)
}

pub fn load_config() -> LoginConfig {
    fs::read_to_string(config_path())
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or_default()
}

pub fn save_config(config: &LoginConfig) -> Result<(), String> {
    let path = config_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("create {}: {e}", parent.display()))?;
    }
    let json = serde_json::to_string_pretty(config).map_err(|e| format!("serialize config: {e}"))?;
    fs::write(&path, json.as_bytes()).map_err(|e| format!("write {}: {e}", path.display()))?;
    // 0600 — the file holds the account token.
    fs::set_permissions(&path, fs::Permissions::from_mode(0o600))
        .map_err(|e| format!("chmod 600 {}: {e}", path.display()))?;
    Ok(())
}

/// Env wins (existing behavior), config file is the fallback (S42 contract 4).
pub fn effective_token() -> Option<String> {
    std::env::var(TOKEN_ENV_VAR).ok().filter(|t| !t.is_empty()).or_else(|| {
        let t = load_config().token?;
        (!t.is_empty()).then_some(t)
    })
}

pub fn api_url() -> String {
    std::env::var(API_URL_ENV_VAR).unwrap_or_else(|_| DEFAULT_API_URL.to_string())
}

/// RFC 8410 SubjectPublicKeyInfo, hand-encoded like the private side
/// (decision D6 in sign_submission_payload — do not "modernize" to a crate
/// default): SEQUENCE { SEQUENCE { OID id-Ed25519 }, BIT STRING pubkey }.
fn encode_spki_pem(public_key: &[u8; 32]) -> String {
    // 12-byte header: 302a 3005 0603 2b6570 0321 00 + 32 bytes
    let mut der = vec![
        0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00,
    ];
    der.extend_from_slice(public_key);
    use base64::Engine as _;
    let encoded = base64::engine::general_purpose::STANDARD.encode(&der);
    let mut pem = String::from("-----BEGIN PUBLIC KEY-----\n");
    pem.push_str(&encoded);
    pem.push('\n');
    pem.push_str("-----END PUBLIC KEY-----\n");
    pem
}

/// The PUBLIC half of the local signing key (creating the pair on first
/// use, exactly like every --sign invocation does).
pub fn public_key_pem() -> Result<String, String> {
    let signing = load_or_create_signing_key(&resolve_key_path())?;
    Ok(encode_spki_pem(&signing.verifying_key().to_bytes()))
}

/// Register the public key with the account (existing endpoint). Returns
/// the server-assigned key id — never fabricated: a non-2xx is an error.
pub fn register_signing_key(label: &str) -> Result<String, String> {
    let Some(token) = effective_token() else {
        return Err("no account token — pass --token or set BENCHMARK_PROBE_API_TOKEN".into());
    };
    let pem = public_key_pem()?;
    let url = format!("{}/v1/auth/signing-keys", api_url());
    let response = reqwest::blocking::Client::new()
        .post(&url)
        .bearer_auth(&token)
        .json(&serde_json::json!({ "label": label, "public_key_pem": pem }))
        .send()
        .map_err(|e| format!("request {url}: {e}"))?;
    let status = response.status();
    let body: serde_json::Value = response.json().unwrap_or(serde_json::Value::Null);
    if !status.is_success() {
        let detail = body.get("detail").and_then(|d| d.as_str()).unwrap_or("");
        return Err(format!("register signing key: HTTP {status} {detail}"));
    }
    body.get("id")
        .and_then(|id| id.as_str())
        .map(|id| id.to_string())
        .ok_or_else(|| "server accepted the key but returned no id".to_string())
}

/// `login --status`: prints state, never the token.
pub fn status_text() -> String {
    let config = load_config();
    let token_line = if config.token.is_some() {
        "logged in (token stored in ~/.config/benchmark-probe/config, 0600)"
    } else if std::env::var(TOKEN_ENV_VAR).map(|t| !t.is_empty()).unwrap_or(false) {
        "logged in via BENCHMARK_PROBE_API_TOKEN (nothing stored)"
    } else {
        "not logged in"
    };
    let key_line = match &config.signing_key_id {
        Some(id) => format!("signing key registered: {id}"),
        None => "signing key: not registered with the account".into(),
    };
    let consent_line = match config.consent_share_runs {
        Some(true) => "consent: sharing enabled (opt-out transparent, A3)",
        Some(false) => "consent: opted out — uploads will be skipped",
        None => "consent: not asked yet (first contribute will show the notice)",
    };
    format!("{token_line}\n{key_line}\n{consent_line}")
}

pub fn is_logged_in() -> bool {
    load_config().token.is_some()
        || std::env::var(TOKEN_ENV_VAR).map(|t| !t.is_empty()).unwrap_or(false)
}
