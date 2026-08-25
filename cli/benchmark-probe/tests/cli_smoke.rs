use std::process::{Command, Output};

fn run_binary(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_benchmark-probe"))
        .args(args)
        .output()
        .expect("failed to spawn benchmark-probe binary")
}

fn stdout_text(output: &Output) -> String {
    String::from_utf8_lossy(&output.stdout).into_owned()
}

fn stderr_text(output: &Output) -> String {
    String::from_utf8_lossy(&output.stderr).into_owned()
}

fn binary_is_installed(name: &str) -> bool {
    Command::new(name).arg("--version").output().is_ok()
}

#[test]
fn help_prints_usage_with_args_and_examples() {
    let output = run_binary(&["--help"]);
    assert!(output.status.success());
    let text = stdout_text(&output);
    assert!(text.contains("--runtime"));
    assert!(text.contains("--prompt-tokens"));
    assert!(text.contains("EXAMPLES"));
}

#[test]
fn mock_runtime_prints_plain_text_metrics() {
    let output = run_binary(&["--runtime", "mock"]);
    assert!(output.status.success(), "stderr: {}", stderr_text(&output));
    let text = stdout_text(&output);
    for field in [
        "Running mock benchmark",
        "Model:",
        "Prompt tokens:",
        "Generated tokens:",
        "TTFT:",
        "Prefill:",
        "Decode:",
        "Peak VRAM:",
    ] {
        assert!(text.contains(field), "missing '{field}' in output:\n{text}");
    }
}

#[test]
fn mock_runtime_respects_scenario_flags() {
    let output = run_binary(&[
        "--runtime",
        "mock",
        "--model",
        "fixture-model",
        "--prompt-tokens",
        "2048",
        "--generated-tokens",
        "128",
        "--batch-size",
        "8",
        "--context-tokens",
        "4096",
    ]);
    assert!(output.status.success(), "stderr: {}", stderr_text(&output));
    let text = stdout_text(&output);
    assert!(text.contains("Model: fixture-model"));
    assert!(text.contains("Prompt tokens: 2048"));
    assert!(text.contains("Generated tokens: 128"));
}

#[test]
fn unknown_runtime_is_rejected() {
    let output = run_binary(&["--runtime", "bogus"]);
    assert!(!output.status.success());
    assert!(stderr_text(&output).contains("invalid value for '--runtime'"));
}

#[test]
fn missing_runtime_argument_is_an_error() {
    let output = run_binary(&[]);
    assert!(!output.status.success());
    assert!(stderr_text(&output).contains("missing required argument '--runtime"));
}

#[test]
fn absent_runtime_reports_install_hint() {
    if binary_is_installed("llama-cli") {
        return;
    }
    let output = run_binary(&["--runtime", "llama_cpp"]);
    assert!(!output.status.success());
    let err = stderr_text(&output);
    assert!(err.contains("llama.cpp is not installed"), "stderr: {err}");
    assert!(err.contains("hint:"), "stderr: {err}");
}
