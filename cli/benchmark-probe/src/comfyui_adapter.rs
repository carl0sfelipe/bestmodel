use std::collections::HashSet;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::time::{Duration, Instant};

use regex::Regex;
use serde::Deserialize;

use crate::sign_submission_payload::sha256_hex;

/// Video benchmark scenario for the ComfyUI runtime (Épico 1, Story 1.1).
///
/// Mirrors the LLM `Scenario` in `execute_benchmark_scenario.rs`, but for
/// diffusion video generation: dimension/frame counts replace token counts.
#[derive(Deserialize, Debug, Clone)]
pub struct ComfyScenario {
    pub model: String,
    pub width: u32,
    pub height: u32,
    pub frames: u32,
    pub steps: u32,
    pub cfg: f64,
    #[serde(default = "default_shift")]
    pub shift: f64,
    pub seed: u64,
    pub first_image: String,
    pub last_image: String,
    #[serde(default)]
    pub prompt: String,
}

fn default_shift() -> f64 {
    5.0
}

#[derive(Deserialize, Debug)]
pub struct RecipeManifest {
    pub recipe_id: String,
    pub runtime: String,
    pub model_release: String,
    pub comfyui_min_version: String,
    pub workflow_template: String,
    #[serde(default)]
    pub provenance: String,
}

pub struct ComfyPlan {
    pub recipe_id: String,
    pub model_release: String,
    pub comfyui_min_version: String,
    pub provenance: String,
    pub scenario: ComfyScenario,
    pub workflow_json: String,
    pub template_sha256: String,
    pub workflow_sha256: String,
}

#[derive(Debug)]
pub enum ComfyPlanError {
    InvalidScenario(String),
    RecipeUnreadable { path: PathBuf, message: String },
    RecipeInvalid(String),
    TemplateUnreadable { path: PathBuf, message: String },
    LeftoverMarker(String),
    WorkflowInvalidJson(String),
    WorkflowNodeInvalid { node_id: String, reason: String },
}

impl fmt::Display for ComfyPlanError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ComfyPlanError::InvalidScenario(message) => {
                write!(f, "error: invalid scenario: {message}")
            }
            ComfyPlanError::RecipeUnreadable { path, message } => write!(
                f,
                "error: unable to read recipe '{}': {message}",
                path.display()
            ),
            ComfyPlanError::RecipeInvalid(message) => {
                write!(f, "error: invalid recipe manifest: {message}")
            }
            ComfyPlanError::TemplateUnreadable { path, message } => write!(
                f,
                "error: unable to read workflow template '{}': {message}",
                path.display()
            ),
            ComfyPlanError::LeftoverMarker(marker) => write!(
                f,
                "error: workflow template is corrupted: marker {marker} was not substituted \
                 (unknown marker or template/scenario mismatch)"
            ),
            ComfyPlanError::WorkflowInvalidJson(message) => write!(
                f,
                "error: materialized workflow is not valid JSON: {message}"
            ),
            ComfyPlanError::WorkflowNodeInvalid { node_id, reason } => write!(
                f,
                "error: workflow node '{node_id}' is not ComfyUI API-format: {reason}"
            ),
        }
    }
}

/// Markers are plain-text and substituted with `str::replace` (jinja-free,
/// zero extra dependencies). String values are JSON-escaped because the
/// markers sit inside JSON string literals in the template.
fn substitutions(scenario: &ComfyScenario) -> Vec<(String, String)> {
    vec![
        ("__MODEL__".to_string(), escape_json_string(&scenario.model)),
        ("__WIDTH__".to_string(), scenario.width.to_string()),
        ("__HEIGHT__".to_string(), scenario.height.to_string()),
        ("__FRAMES__".to_string(), scenario.frames.to_string()),
        ("__STEPS__".to_string(), scenario.steps.to_string()),
        ("__CFG__".to_string(), format_minimal_f64(scenario.cfg)),
        ("__SHIFT__".to_string(), format_minimal_f64(scenario.shift)),
        ("__SEED__".to_string(), scenario.seed.to_string()),
        (
            "__FIRST_IMAGE__".to_string(),
            escape_json_string(&scenario.first_image),
        ),
        (
            "__LAST_IMAGE__".to_string(),
            escape_json_string(&scenario.last_image),
        ),
        (
            "__PROMPT__".to_string(),
            escape_json_string(&scenario.prompt),
        ),
    ]
}

fn escape_json_string(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}

fn format_minimal_f64(value: f64) -> String {
    if value.fract() == 0.0 {
        format!("{value:.1}")
    } else {
        format!("{value}")
    }
}

fn validate_scenario(scenario: &ComfyScenario) -> Result<(), ComfyPlanError> {
    if scenario.model.trim().is_empty() {
        return Err(ComfyPlanError::InvalidScenario(
            "'model' must not be empty".to_string(),
        ));
    }
    if scenario.width == 0 || scenario.height == 0 {
        return Err(ComfyPlanError::InvalidScenario(
            "'width' and 'height' must be positive".to_string(),
        ));
    }
    if scenario.steps == 0 {
        return Err(ComfyPlanError::InvalidScenario(
            "'steps' must be positive".to_string(),
        ));
    }
    if scenario.cfg <= 0.0 {
        return Err(ComfyPlanError::InvalidScenario(
            "'cfg' must be positive".to_string(),
        ));
    }
    // Wan latent length constraint: 4n + 1 frames (81 = 4*20 + 1 ≈ 5.06 s @ 16 fps).
    if scenario.frames < 5 || (scenario.frames - 1) % 4 != 0 {
        return Err(ComfyPlanError::InvalidScenario(format!(
            "'frames' must be 4n+1 (got {}): Wan video latent length constraint",
            scenario.frames
        )));
    }
    for (label, image) in [("first_image", &scenario.first_image), ("last_image", &scenario.last_image)] {
        if image.trim().is_empty() {
            return Err(ComfyPlanError::InvalidScenario(format!(
                "'{label}' must not be empty"
            )));
        }
        if Path::new(image.as_str()).is_absolute() {
            return Err(ComfyPlanError::InvalidScenario(format!(
                "'{label}' must be a relative path inside the ComfyUI input directory (got '{image}')"
            )));
        }
        if image.split(['/', '\\']).any(|component| component == "..") {
            return Err(ComfyPlanError::InvalidScenario(format!(
                "'{label}' must not contain '..' (got '{image}')"
            )));
        }
    }
    Ok(())
}

pub fn build_plan(recipe_path: &Path, scenario: &ComfyScenario) -> Result<ComfyPlan, ComfyPlanError> {
    validate_scenario(scenario)?;

    let recipe_raw = fs::read_to_string(recipe_path).map_err(|err| ComfyPlanError::RecipeUnreadable {
        path: recipe_path.to_path_buf(),
        message: err.to_string(),
    })?;
    let manifest: RecipeManifest =
        serde_json::from_str(&recipe_raw).map_err(|err| ComfyPlanError::RecipeInvalid(err.to_string()))?;
    if manifest.runtime != "comfyui" {
        return Err(ComfyPlanError::RecipeInvalid(format!(
            "runtime must be 'comfyui' (got '{}')",
            manifest.runtime
        )));
    }
    if manifest.recipe_id.trim().is_empty() {
        return Err(ComfyPlanError::RecipeInvalid(
            "recipe_id must not be empty".to_string(),
        ));
    }

    let template_path = recipe_path
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join(&manifest.workflow_template);
    let template_raw = fs::read_to_string(&template_path).map_err(|err| ComfyPlanError::TemplateUnreadable {
        path: template_path,
        message: err.to_string(),
    })?;
    let template_sha256 = sha256_hex(template_raw.as_bytes());

    let mut workflow_json = template_raw;
    for (marker, value) in substitutions(scenario) {
        workflow_json = workflow_json.replace(&marker, &value);
    }

    let marker_regex = Regex::new(r"__[A-Z][A-Z0-9_]*__").unwrap();
    if let Some(leftover) = marker_regex.find(&workflow_json) {
        return Err(ComfyPlanError::LeftoverMarker(leftover.as_str().to_string()));
    }

    let parsed: serde_json::Value = serde_json::from_str(&workflow_json)
        .map_err(|err| ComfyPlanError::WorkflowInvalidJson(err.to_string()))?;
    let serde_json::Value::Object(nodes) = parsed else {
        return Err(ComfyPlanError::WorkflowInvalidJson(
            "root must be a JSON object mapping node ids to nodes".to_string(),
        ));
    };
    if nodes.is_empty() {
        return Err(ComfyPlanError::WorkflowInvalidJson(
            "workflow has no nodes".to_string(),
        ));
    }
    for (node_id, node) in &nodes {
        let Some(node_obj) = node.as_object() else {
            return Err(ComfyPlanError::WorkflowNodeInvalid {
                node_id: node_id.clone(),
                reason: "value must be an object".to_string(),
            });
        };
        match node_obj.get("class_type").and_then(|v| v.as_str()) {
            Some(class_type) if !class_type.trim().is_empty() => {}
            _ => {
                return Err(ComfyPlanError::WorkflowNodeInvalid {
                    node_id: node_id.clone(),
                    reason: "missing or empty 'class_type' string".to_string(),
                })
            }
        }
        if !node_obj.get("inputs").map(|v| v.is_object()).unwrap_or(false) {
            return Err(ComfyPlanError::WorkflowNodeInvalid {
                node_id: node_id.clone(),
                reason: "missing 'inputs' object".to_string(),
            });
        }
    }

    let workflow_sha256 = sha256_hex(workflow_json.as_bytes());
    Ok(ComfyPlan {
        recipe_id: manifest.recipe_id,
        model_release: manifest.model_release,
        comfyui_min_version: manifest.comfyui_min_version,
        provenance: manifest.provenance,
        scenario: scenario.clone(),
        workflow_json,
        template_sha256,
        workflow_sha256,
    })
}

/// Detects a comfy-cli installation so the plan can state whether execution
/// (Story 1.2) is possible on this machine. Purely informational: the dry-run
/// plan itself never requires the binary.
pub fn detect_comfy_cli() -> Option<String> {
    let output = std::process::Command::new("comfy").arg("--version").output().ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let line = text
        .lines()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .unwrap_or("unknown");
    Some(line.to_string())
}

pub fn print_plan(plan: &ComfyPlan, workflow_out: Option<&Path>, comfy_cli: Option<&str>) {
    let scenario = &plan.scenario;
    let workflow_display = workflow_out
        .map(|path| path.display().to_string())
        .unwrap_or_else(|| "<workflow-out path>".to_string());

    println!("ComfyUI benchmark plan (dry-run)");
    println!(
        "Recipe: {} (runtime comfyui, min ComfyUI {})",
        plan.recipe_id, plan.comfyui_min_version
    );
    println!("Model release: {}", plan.model_release);
    if !plan.provenance.is_empty() {
        println!("Provenance: {}", plan.provenance);
    }
    println!("Workflow template sha256: {}", plan.template_sha256);
    println!("Materialized workflow sha256: {}", plan.workflow_sha256);
    println!(
        "Scenario: model={} width={} height={} frames={} steps={} cfg={} shift={} seed={}",
        scenario.model,
        scenario.width,
        scenario.height,
        scenario.frames,
        scenario.steps,
        format_minimal_f64(scenario.cfg),
        format_minimal_f64(scenario.shift),
        scenario.seed
    );
    println!(
        "Images: first={} last={}",
        scenario.first_image, scenario.last_image
    );
    match comfy_cli {
        Some(version) => println!("comfy CLI on PATH: {version}"),
        None => println!(
            "comfy CLI on PATH: not found (execution requires comfy-cli >= Story 1.2; this plan ran with zero spawns)"
        ),
    }
    println!();
    println!("Commands (flags confirmed against Comfy-Org/comfy-cli cmdline.py):");
    println!("    comfy launch --background");
    println!("    comfy run --workflow {workflow_display} --wait --verbose");
    println!("    comfy stop");
    println!(
        "    comfy run --workflow {workflow_display} --print-prompt   # native dry-run: prints the API graph and exits"
    );
    println!();
    println!("Planned metrics (Story 1.2): seconds_per_clip, it_per_s, frames_per_s");
    println!();
    println!(
        "PLAN {{\"scenario\":\"{}\",\"recipe_id\":\"{}\",\"workflow_sha256\":\"{}\",\"width\":{},\"height\":{},\"frames\":{},\"steps\":{},\"dry_run\":true}}",
        escape_json_string(&scenario.model),
        escape_json_string(&plan.recipe_id),
        plan.workflow_sha256,
        scenario.width,
        scenario.height,
        scenario.frames,
        scenario.steps
    );
}

// ---------------------------------------------------------------------------
// Story 1.2 — execution metrics
//
// Metric source is the comfy-cli machine mode: `comfy --json-stream run
// --workflow <path> --wait` emits NDJSON events on stdout (progress with
// value/max per node, executed, output). Pretty mode uses rich progress bars
// (unparseable), so the executor always requests the JSON stream.

#[derive(Debug, Clone, PartialEq)]
pub struct ComfyRunMetrics {
    /// Wall time from first event to last event (submit → completion).
    pub seconds_per_clip: f64,
    /// Wall time covering the sampler's progress events (None if no sampler ran).
    pub seconds_sampling: Option<f64>,
    /// Sampler steps per second: max step / sampling window.
    pub it_per_s: Option<f64>,
    /// Clip frames per second of wall time: frames / seconds_per_clip.
    pub frames_per_s: f64,
    /// Max step reported by the sampler node.
    pub sampler_steps: Option<u32>,
    /// Peak VRAM across GPUs, MiB (nvidia-smi poller; 0.0 when unavailable).
    pub peak_vram_mib: f64,
}

/// Node classes whose `progress` events count as sampler iterations.
/// Covers KSampler variants and the Wan video sampler family
/// (WanFirstLastFrameToVideo, WanImageToVideo, WanVaceToVideo, ...).
pub fn sampler_node_ids(workflow: &serde_json::Value) -> HashSet<String> {
    let mut ids = HashSet::new();
    let Some(nodes) = workflow.as_object() else {
        return ids;
    };
    for (node_id, node) in nodes {
        let Some(class_type) = node.get("class_type").and_then(|v| v.as_str()) else {
            continue;
        };
        if class_type.contains("Sampler") || class_type.ends_with("ToVideo") {
            ids.insert(node_id.clone());
        }
    }
    ids
}

/// Extracts one NDJSON event's (type, data, node, value, max).
/// Tolerant to envelope shape: accepts both `{"type": t, "data": {...}}`
/// (stream envelope) and flattened `{"type": t, "node": n, ...}`.
fn event_fields(event: &serde_json::Value) -> Option<(String, serde_json::Value)> {
    let event_type = event
        .get("type")
        .or_else(|| event.get("event"))?
        .as_str()?
        .to_string();
    let data = event.get("data").cloned().unwrap_or_else(|| event.clone());
    Some((event_type, data))
}

fn event_node(data: &serde_json::Value) -> Option<String> {
    data.get("node")
        .map(|v| v.as_str().map(str::to_string).unwrap_or_default())
        .filter(|node| !node.is_empty())
        .or_else(|| {
            data.get("output")
                .and_then(|v| v.as_object())
                .and_then(|obj| obj.keys().next().cloned())
        })
}

/// Computes clip metrics from a timestamped NDJSON event stream.
/// `events` are (seconds_since_start, parsed_json) in arrival order.
pub fn parse_comfy_events(
    events: &[(f64, serde_json::Value)],
    sampler_nodes: &HashSet<String>,
    frames: u32,
) -> Result<ComfyRunMetrics, String> {
    let Some((first_ts, _)) = events.first() else {
        return Err("no events: empty execution stream".to_string());
    };
    let last_ts = events.last().expect("non-empty").0;
    if last_ts < *first_ts {
        return Err("events are not in timestamp order".to_string());
    }
    let seconds_per_clip = last_ts - first_ts;

    let mut sampler_first_ts: Option<f64> = None;
    let mut sampler_last_ts: Option<f64> = None;
    let mut sampler_max_step: Option<u64> = None;
    for (ts, event) in events {
        let Some((event_type, data)) = event_fields(event) else {
            continue;
        };
        if event_type != "progress" {
            continue;
        }
        let Some(node) = event_node(&data) else {
            continue;
        };
        if !sampler_nodes.contains(&node) {
            continue;
        }
        sampler_first_ts.get_or_insert(*ts);
        sampler_last_ts = Some(*ts);
        if let Some(value) = data.get("value").and_then(|v| v.as_u64()) {
            sampler_max_step = Some(sampler_max_step.unwrap_or(0).max(value));
        }
    }

    let (seconds_sampling, it_per_s, sampler_steps) = match (sampler_first_ts, sampler_last_ts, sampler_max_step)
    {
        (Some(start), Some(end), Some(max_step)) if max_step > 0 && end > start => {
            let window = end - start;
            (Some(window), Some(max_step as f64 / window), Some(max_step as u32))
        }
        _ => (None, None, None),
    };
    if seconds_per_clip <= 0.0 {
        return Err(format!(
            "implausible clip wall time: {seconds_per_clip}s (single-event stream?)"
        ));
    }
    let frames_per_s = frames as f64 / seconds_per_clip;

    Ok(ComfyRunMetrics {
        seconds_per_clip,
        seconds_sampling,
        it_per_s,
        frames_per_s,
        sampler_steps,
        peak_vram_mib: 0.0,
    })
}

/// Polls `nvidia-smi` on a background thread until the stop signal arrives;
/// reports the peak (max) memory used by the busiest GPU, in MiB.
struct VramPoller {
    stop: mpsc::Sender<()>,
    peak: mpsc::Receiver<f64>,
}

impl VramPoller {
    fn spawn(interval: Duration) -> Self {
        let (stop_tx, stop_rx) = mpsc::channel::<()>();
        let (peak_tx, peak_rx) = mpsc::channel::<f64>();
        std::thread::spawn(move || {
            let mut peak = 0.0f64;
            while stop_rx.recv_timeout(interval).is_err() {
                if let Some(sample) = sample_nvidia_vram_mib() {
                    peak = peak.max(sample);
                }
            }
            let _ = peak_tx.send(peak);
        });
        VramPoller {
            stop: stop_tx,
            peak: peak_rx,
        }
    }

    fn finish(self) -> f64 {
        let _ = self.stop.send(());
        self.peak.recv_timeout(Duration::from_secs(2)).unwrap_or(0.0)
    }
}

fn sample_nvidia_vram_mib() -> Option<f64> {
    let output = std::process::Command::new("nvidia-smi")
        .args([
            "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
        ])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    text.lines()
        .filter_map(|line| line.trim().parse::<f64>().ok())
        .fold(None::<f64>, |acc, value| Some(acc.map_or(value, |max: f64| max.max(value))))
}

pub struct ComfyExecution {
    pub metrics: ComfyRunMetrics,
    pub raw_log: String,
    pub launched_server: bool,
}

const COMFY_SERVER_URL: &str = "http://127.0.0.1:8188";

fn comfy_server_up() -> bool {
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .ok();
    let Some(client) = client else {
        return false;
    };
    client
        .get(format!("{COMFY_SERVER_URL}/system_stats"))
        .send()
        .map(|response| response.status().is_success())
        .unwrap_or(false)
}

fn spawn_comfy(args: &[&str]) -> Result<std::process::Output, String> {
    std::process::Command::new("comfy")
        .args(args)
        .output()
        .map_err(|err| {
            format!(
                "comfy-cli not found on PATH (install: pipx install comfy-cli) — spawn failed: {err}"
            )
        })
}

/// Runs the materialized workflow headlessly and measures the clip.
///
/// Flow: ensure server (probe :8188, else `comfy launch --background`), run
/// `comfy --json-stream run --workflow <path> --wait` while timestamping each
/// stdout line, poll nvidia-smi for peak VRAM, stop the server if we
/// launched it.
pub fn execute_comfy_workflow(
    workflow_path: &Path,
    sampler_nodes: &HashSet<String>,
    frames: u32,
) -> Result<ComfyExecution, String> {
    let launched_server = if comfy_server_up() {
        false
    } else {
        let output = spawn_comfy(&["launch", "--background"])?;
        if !output.status.success() {
            return Err(format!(
                "comfy launch --background failed: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        true
    };

    let poller = VramPoller::spawn(Duration::from_millis(250));
    let run_started = Instant::now();
    let mut child = std::process::Command::new("comfy")
        .args([
            "--json-stream",
            "run",
            "--workflow",
            &workflow_path.display().to_string(),
            "--wait",
            "--timeout",
            "600",
        ])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|err| format!("failed to spawn comfy run: {err}"))?;

    use std::io::BufRead;
    let mut raw_lines: Vec<String> = Vec::new();
    let mut events: Vec<(f64, serde_json::Value)> = Vec::new();
    if let Some(stdout) = child.stdout.take() {
        let reader = std::io::BufReader::new(stdout);
        for line in reader.lines() {
            let Ok(line) = line else {
                break;
            };
            let ts = run_started.elapsed().as_secs_f64();
            raw_lines.push(line.clone());
            if let Ok(event) = serde_json::from_str(&line) {
                events.push((ts, event));
            }
        }
    }
    let status = child
        .wait()
        .map_err(|err| format!("failed to wait for comfy run: {err}"))?;
    let peak_vram_mib = poller.finish();

    if launched_server {
        let _ = spawn_comfy(&["stop"]);
    }
    if !status.success() {
        return Err(format!(
            "comfy run exited with status {status}; log tail: {}",
            raw_lines.iter().rev().take(5).cloned().collect::<Vec<_>>().join(" | ")
        ));
    }

    let mut metrics =
        parse_comfy_events(&events, sampler_nodes, frames).map_err(|err| {
            format!("could not parse comfy event stream: {err}; log tail: {}", raw_lines.iter().rev().take(5).cloned().collect::<Vec<_>>().join(" | "))
        })?;
    metrics.peak_vram_mib = peak_vram_mib;
    Ok(ComfyExecution {
        metrics,
        raw_log: raw_lines.join("\n"),
        launched_server,
    })
}

pub fn print_run_metrics(plan: &ComfyPlan, metrics: &ComfyRunMetrics) {
    println!("Running ComfyUI benchmark (video)");
    println!("Recipe: {}", plan.recipe_id);
    println!("Model release: {}", plan.model_release);
    println!(
        "Clip: {}x{} {} frames, {} steps, seed {}",
        plan.scenario.width,
        plan.scenario.height,
        plan.scenario.frames,
        plan.scenario.steps,
        plan.scenario.seed
    );
    println!("Seconds per clip: {:.1} s", metrics.seconds_per_clip);
    match (metrics.it_per_s, metrics.seconds_sampling) {
        (Some(it_per_s), Some(seconds_sampling)) => {
            println!("Sampling it/s: {it_per_s:.3} ({seconds_sampling:.1} s window, {} steps)", metrics.sampler_steps.unwrap_or(0));
        }
        _ => println!("Sampling it/s: n/a (no sampler progress events)"),
    }
    println!("Frames per s: {:.2}", metrics.frames_per_s);
    if metrics.peak_vram_mib > 0.0 {
        println!("Peak VRAM: {:.1} GiB", metrics.peak_vram_mib / 1024.0);
    } else {
        println!("Peak VRAM: n/a (nvidia-smi unavailable)");
    }
}
