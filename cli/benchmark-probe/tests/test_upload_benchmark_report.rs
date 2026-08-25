use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use benchmark_probe::upload_benchmark_report::{
    fetch_challenge_nonce, upload_benchmark_report, ArtifactUpload, UploadRequest,
};

struct MockSubmissionServer {
    base_url: String,
    captured_bodies: Arc<Mutex<Vec<Vec<u8>>>>,
    post_status: u16,
}

impl MockSubmissionServer {
    fn start(post_status: u16) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind mock server");
        let address = listener.local_addr().expect("local addr");
        let captured_bodies = Arc::new(Mutex::new(Vec::new()));
        let bodies_for_thread = Arc::clone(&captured_bodies);
        std::thread::spawn(move || {
            listener.set_nonblocking(false).expect("blocking listener");
            for stream in listener.incoming() {
                let Ok(mut stream) = stream else { continue };
                let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
                let (request_line, body) = match read_request(&mut stream) {
                    Ok(parsed) => parsed,
                    Err(_) => continue,
                };
                let response = route(&request_line, &body, post_status, &bodies_for_thread);
                let _ = stream.write_all(response.as_bytes());
            }
        });
        MockSubmissionServer {
            base_url: format!("http://{address}"),
            captured_bodies,
            post_status,
        }
    }
}

fn read_request(stream: &mut TcpStream) -> std::io::Result<(String, Vec<u8>)> {
    let mut header_bytes: Vec<u8> = Vec::new();
    let mut chunk = [0u8; 1];
    while !header_bytes.ends_with(b"\r\n\r\n") {
        let read_count = stream.read(&mut chunk)?;
        if read_count == 0 {
            break;
        }
        header_bytes.extend_from_slice(&chunk);
    }
    let header_text = String::from_utf8_lossy(&header_bytes).into_owned();
    let request_line = header_text.lines().next().unwrap_or_default().to_string();
    let content_length = header_text
        .lines()
        .find_map(|line| {
            let (name, value) = line.split_once(':')?;
            if name.eq_ignore_ascii_case("content-length") {
                value.trim().parse::<usize>().ok()
            } else {
                None
            }
        })
        .unwrap_or(0);
    let mut body = vec![0u8; content_length];
    stream.read_exact(&mut body)?;
    Ok((request_line, body))
}

fn route(
    request_line: &str,
    body: &[u8],
    post_status: u16,
    captured_bodies: &Arc<Mutex<Vec<Vec<u8>>>>,
) -> String {
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or_default();
    let path = parts.next().unwrap_or_default();
    match (method, path) {
        ("GET", "/v1/submissions/nonce") => {
            json_response(200, r#"{"challenge_nonce":"nonce-abc-123"}"#)
        }
        ("POST", "/v1/submissions") => {
            captured_bodies.lock().expect("lock").push(body.to_vec());
            if post_status == 202 {
                json_response(202, r#"{"run_id":"test-run-42"}"#)
            } else {
                json_response(post_status, r#"{"detail":"rejected"}"#)
            }
        }
        _ => json_response(404, r#"{"detail":"not found"}"#),
    }
}

fn json_response(status: u16, body: &str) -> String {
    format!(
        "HTTP/1.1 {status} OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    )
}

fn sample_request(nonce: &str) -> UploadRequest {
    UploadRequest {
        report_json: r#"{"schema_version":"0.9.0"}"#.to_string(),
        payload_digest: "sha256:digest".to_string(),
        signature: "signature-hex".to_string(),
        challenge_nonce: nonce.to_string(),
        client_version: "0.1.0".to_string(),
        artifacts: vec![ArtifactUpload {
            bytes: b"artifact zero payload".to_vec(),
        }],
    }
}

#[test]
fn nonce_endpoint_returns_challenge_nonce() {
    let server = MockSubmissionServer::start(202);
    let nonce = fetch_challenge_nonce(&server.base_url).expect("fetch nonce");
    assert_eq!(nonce, "nonce-abc-123");
}

#[test]
fn successful_upload_submits_all_fields_and_artifacts() {
    let server = MockSubmissionServer::start(202);
    let nonce = fetch_challenge_nonce(&server.base_url).expect("fetch nonce");
    let outcome =
        upload_benchmark_report(&server.base_url, &sample_request(&nonce)).expect("upload");
    assert_eq!(outcome.status_code, 202);
    assert_eq!(outcome.run_id.as_deref(), Some("test-run-42"));

    let bodies = server.captured_bodies.lock().expect("lock");
    let body_text = String::from_utf8_lossy(&bodies[0]).into_owned();
    assert!(body_text.contains(r#"{"schema_version":"0.9.0"}"#));
    assert!(body_text.contains("sha256:digest"));
    assert!(body_text.contains("signature-hex"));
    assert!(body_text.contains("nonce-abc-123"));
    assert!(body_text.contains("0.1.0"));
    assert!(body_text.contains("name=\"artifact_0\""));
    assert!(body_text.contains("artifact zero payload"));
    assert_eq!(server.post_status, 202);
}

#[test]
fn non_2xx_response_reports_failure_status() {
    let server = MockSubmissionServer::start(500);
    let outcome = upload_benchmark_report(&server.base_url, &sample_request("nonce-abc-123"))
        .expect("upload");
    assert_eq!(outcome.status_code, 500);
    assert!(outcome.run_id.is_none());
}
