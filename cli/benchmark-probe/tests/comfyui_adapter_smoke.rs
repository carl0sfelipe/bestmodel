use std::io::Write;
use std::process::{Command, Output, Stdio};

const RECIPE: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/recipes/wan22-flf2v-720p-81f-v1.json"
);
const RECIPE_LEFTOVER: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/tests/fixtures/recipe-leftover-marker.json"
);
const SCENARIO: &str = r#"{"model":"wan22-i2v-flf2v","width":1280,"height":720,"frames":81,"steps":20,"cfg":3.5,"shift":5.0,"seed":42,"first_image":"in/first.png","last_image":"in/last.png"}"#;

fn run_binary(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_benchmark-probe"))
        .args(args)
        .output()
        .expect("failed to spawn benchmark-probe binary")
}

fn run_binary_with_stdin(args: &[&str], stdin_data: &str) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_benchmark-probe"))
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("failed to spawn benchmark-probe binary");
    child
        .stdin
        .as_mut()
        .expect("stdin piped")
        .write_all(stdin_data.as_bytes())
        .expect("failed to write stdin");
    child.wait_with_output().expect("failed to collect output")
}

fn stdout_text(output: &Output) -> String {
    String::from_utf8_lossy(&output.stdout).into_owned()
}

fn stderr_text(output: &Output) -> String {
    String::from_utf8_lossy(&output.stderr).into_owned()
}

#[test]
fn valid_scenario_prints_plan_with_scenario_echo_and_confirmed_commands() {
    let output = run_binary(&[
        "--runtime",
        "comfyui",
        "--scenario",
        SCENARIO,
        "--recipe",
        RECIPE,
    ]);
    assert!(output.status.success(), "stderr: {}", stderr_text(&output));
    let text = stdout_text(&output);
    assert!(
        text.contains(r#""scenario":"wan22-i2v-flf2v""#),
        "missing scenario echo in output:\n{text}"
    );
    assert!(text.contains("comfy run --workflow"), "missing run command:\n{text}");
    assert!(text.contains("comfy launch --background"), "missing launch:\n{text}");
    assert!(text.contains("comfy stop"), "missing stop:\n{text}");
    assert!(text.contains("seconds_per_clip"), "missing planned metrics:\n{text}");
    assert!(text.contains("Recipe: wan22-flf2v-720p-81f-v1"));
    assert!(text.contains("dry_run"));
}

#[test]
fn empty_stdin_scenario_is_rejected() {
    let output = run_binary_with_stdin(
        &[
            "--runtime",
            "comfyui",
            "--scenario",
            "-",
            "--recipe",
            RECIPE,
        ],
        "",
    );
    assert!(!output.status.success());
    let err = stderr_text(&output);
    assert!(
        err.contains("--scenario is empty"),
        "stderr should explain empty stdin: {err}"
    );
}

#[test]
fn missing_scenario_argument_is_rejected() {
    let output = run_binary(&["--runtime", "comfyui", "--recipe", RECIPE]);
    assert!(!output.status.success());
    assert!(
        stderr_text(&output)
            .contains("missing required argument '--scenario <json|->' for --runtime comfyui"),
        "stderr: {}",
        stderr_text(&output)
    );
}

#[test]
fn missing_recipe_argument_is_rejected() {
    let output = run_binary(&["--runtime", "comfyui", "--scenario", SCENARIO]);
    assert!(!output.status.success());
    assert!(
        stderr_text(&output)
            .contains("missing required argument '--recipe <path>' for --runtime comfyui"),
        "stderr: {}",
        stderr_text(&output)
    );
}

#[test]
fn invalid_scenario_json_is_rejected() {
    let output = run_binary(&[
        "--runtime",
        "comfyui",
        "--scenario",
        "{not json",
        "--recipe",
        RECIPE,
    ]);
    assert!(!output.status.success());
    assert!(
        stderr_text(&output).contains("invalid --scenario JSON"),
        "stderr: {}",
        stderr_text(&output)
    );
}

#[test]
fn frames_not_4n_plus_1_is_rejected() {
    let scenario = SCENARIO.replace("\"frames\":81", "\"frames\":80");
    let output = run_binary(&[
        "--runtime",
        "comfyui",
        "--scenario",
        &scenario,
        "--recipe",
        RECIPE,
    ]);
    assert!(!output.status.success());
    assert!(
        stderr_text(&output).contains("4n+1"),
        "stderr: {}",
        stderr_text(&output)
    );
}

#[test]
fn corrupted_workflow_template_with_leftover_marker_is_rejected() {
    let output = run_binary(&[
        "--runtime",
        "comfyui",
        "--scenario",
        SCENARIO,
        "--recipe",
        RECIPE_LEFTOVER,
    ]);
    assert!(!output.status.success());
    let err = stderr_text(&output);
    assert!(
        err.contains("__STEPSS__") && err.contains("was not substituted"),
        "stderr should name the leftover marker: {err}"
    );
}

#[test]
fn workflow_out_writes_valid_marker_free_json() {
    let out_path = std::env::temp_dir().join("benchmark_probe_comfyui_workflow_out.json");
    let out_str = out_path.to_str().unwrap();
    let output = run_binary(&[
        "--runtime",
        "comfyui",
        "--scenario",
        SCENARIO,
        "--recipe",
        RECIPE,
        "--workflow-out",
        out_str,
    ]);
    assert!(output.status.success(), "stderr: {}", stderr_text(&output));
    let text = stdout_text(&output);
    assert!(
        text.contains(&format!("Wrote materialized workflow to {out_str}")),
        "missing write notice:\n{text}"
    );
    let workflow = std::fs::read_to_string(&out_path).expect("workflow file written");
    assert!(!workflow.contains("__"), "markers must all be substituted");
    let parsed: serde_json::Value = serde_json::from_str(&workflow).expect("valid JSON workflow");
    let nodes = parsed
        .as_object()
        .expect("workflow root is an object (API format)");
    assert!(!nodes.is_empty());
    let sampler = nodes
        .get("8")
        .and_then(|node| node.get("inputs"))
        .and_then(|inputs| inputs.get("length"))
        .and_then(|v| v.as_u64())
        .expect("sampler length input");
    assert_eq!(sampler, 81, "frames substitution must land in the sampler node");
}

#[test]
fn help_mentions_comfyui_runtime() {
    let output = run_binary(&["--help"]);
    assert!(output.status.success());
    let text = stdout_text(&output);
    assert!(text.contains("comfyui"));
    assert!(text.contains("--scenario"));
    assert!(text.contains("--recipe"));
}
