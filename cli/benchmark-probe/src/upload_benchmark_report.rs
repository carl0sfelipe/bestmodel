//! Uploads a signed benchmark report to the Submission API (plan section 12.1).
//!
//! Flow: fetch a challenge nonce, then POST the report, signature, digest,
//! nonce, client version and artifact files as multipart/form-data.
//!
//! Settlement (L02 B4/S16): when ``settle_claim_id`` is set the request must
//! carry an API bearer token (``api_token``); the platform binds the run to
//! the caller's open claim and returns ``linked_claim_id`` on success.

use reqwest::blocking::multipart::{Form, Part};
use reqwest::blocking::Client;

const NONCE_PATH: &str = "/v1/submissions/nonce";
const SUBMISSIONS_PATH: &str = "/v1/submissions";

pub struct ArtifactUpload {
    pub bytes: Vec<u8>,
}

pub struct UploadRequest {
    pub report_json: String,
    pub payload_digest: String,
    pub signature: String,
    pub challenge_nonce: String,
    pub client_version: String,
    pub artifacts: Vec<ArtifactUpload>,
    /// Open claim to settle with this run (requires ``api_token``).
    pub settle_claim_id: Option<String>,
    /// Catalog binding overrides sent as multipart form fields (Phase 0 report
    /// does not carry the binding itself).
    pub model_release_id: Option<String>,
    pub quantization_profile_id: Option<String>,
    /// Bearer token from the account's agent tokens (S13).
    pub api_token: Option<String>,
}

pub struct UploadOutcome {
    pub status_code: u16,
    pub run_id: Option<String>,
    pub linked_claim_id: Option<String>,
}

pub fn fetch_challenge_nonce(base_url: &str) -> Result<String, String> {
    let url = format!("{base_url}{NONCE_PATH}");
    let response = Client::new()
        .get(&url)
        .send()
        .map_err(|err| format!("nonce request to {url} failed: {err}"))?;
    if !response.status().is_success() {
        return Err(format!(
            "nonce request to {url} returned status {}",
            response.status()
        ));
    }
    let body: serde_json::Value = response
        .json()
        .map_err(|err| format!("nonce response from {url} is not JSON: {err}"))?;
    body["challenge_nonce"]
        .as_str()
        .map(str::to_string)
        .ok_or_else(|| format!("nonce response from {url} lacks challenge_nonce"))
}

pub fn upload_benchmark_report(
    base_url: &str,
    request: &UploadRequest,
) -> Result<UploadOutcome, String> {
    let url = format!("{base_url}{SUBMISSIONS_PATH}");
    let mut post = Client::new().post(&url).multipart(build_multipart_form(request));
    if let Some(token) = &request.api_token {
        post = post.bearer_auth(token);
    }
    let response = post
        .send()
        .map_err(|err| format!("submission request to {url} failed: {err}"))?;
    let status_code = response.status().as_u16();
    if !response.status().is_success() {
        return Ok(UploadOutcome {
            status_code,
            run_id: None,
            linked_claim_id: None,
        });
    }
    let body: serde_json::Value = response
        .json()
        .map_err(|err| format!("submission response from {url} is not JSON: {err}"))?;
    Ok(UploadOutcome {
        status_code,
        run_id: body["run_id"].as_str().map(str::to_string),
        linked_claim_id: body["linked_claim_id"].as_str().map(str::to_string),
    })
}

fn build_multipart_form(request: &UploadRequest) -> Form {
    let mut form = Form::new()
        .part("report", Part::text(request.report_json.clone()))
        .part("payload_digest", Part::text(request.payload_digest.clone()))
        .part("signature", Part::text(request.signature.clone()))
        .part(
            "challenge_nonce",
            Part::text(request.challenge_nonce.clone()),
        )
        .part("client_version", Part::text(request.client_version.clone()));
    if let Some(claim_id) = &request.settle_claim_id {
        form = form.part("settle_claim_id", Part::text(claim_id.clone()));
    }
    if let Some(model_release_id) = &request.model_release_id {
        form = form.part("model_release_id", Part::text(model_release_id.clone()));
    }
    if let Some(quantization_profile_id) = &request.quantization_profile_id {
        form = form.part(
            "quantization_profile_id",
            Part::text(quantization_profile_id.clone()),
        );
    }
    for (index, artifact) in request.artifacts.iter().enumerate() {
        let part = Part::bytes(artifact.bytes.clone()).file_name(format!("artifact_{index}"));
        form = form.part(format!("artifact_{index}"), part);
    }
    form
}
