//! Uploads a signed benchmark report to the Submission API (plan section 12.1).
//!
//! Flow: fetch a challenge nonce, then POST the report, signature, digest,
//! nonce, client version and artifact files as multipart/form-data.

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
}

pub struct UploadOutcome {
    pub status_code: u16,
    pub run_id: Option<String>,
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
    let form = build_multipart_form(request);
    let response = Client::new()
        .post(&url)
        .multipart(form)
        .send()
        .map_err(|err| format!("submission request to {url} failed: {err}"))?;
    let status_code = response.status().as_u16();
    if !response.status().is_success() {
        return Ok(UploadOutcome {
            status_code,
            run_id: None,
        });
    }
    let body: serde_json::Value = response
        .json()
        .map_err(|err| format!("submission response from {url} is not JSON: {err}"))?;
    let run_id = body["run_id"].as_str().map(str::to_string);
    Ok(UploadOutcome {
        status_code,
        run_id,
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
    for (index, artifact) in request.artifacts.iter().enumerate() {
        let part = Part::bytes(artifact.bytes.clone()).file_name(format!("artifact_{index}"));
        form = form.part(format!("artifact_{index}"), part);
    }
    form
}
