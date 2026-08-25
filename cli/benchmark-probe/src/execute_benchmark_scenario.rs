use std::fmt;
use std::process::Command;

use crate::detect_runtime_installations::{RuntimeInstall, RuntimeInstallations};
use crate::parse_runtime_output::{parse_llama_cpp_metrics, parse_ollama_metrics, Metrics};
use crate::Runtime;

pub struct Scenario {
    pub model: String,
    pub prompt_tokens: u32,
    pub generated_tokens: u32,
    pub batch_size: u32,
    pub context_tokens: u32,
}

pub struct ScenarioResult {
    #[allow(dead_code)]
    pub stdout: String,
    pub metrics: Metrics,
}

pub enum ScenarioError {
    RuntimeNotInstalled { runtime: String, hint: String },
    SpawnFailed { runtime: String, message: String },
    ParseFailed { runtime: String, message: String },
}

impl fmt::Display for ScenarioError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ScenarioError::RuntimeNotInstalled { runtime, hint } => write!(
                f,
                "error: {runtime} is not installed on this machine.\nhint: {hint}"
            ),
            ScenarioError::SpawnFailed { runtime, message } => {
                write!(f, "error: failed to launch {runtime}: {message}")
            }
            ScenarioError::ParseFailed { runtime, message } => {
                write!(f, "error: could not parse {runtime} output: {message}")
            }
        }
    }
}

const LLAMA_CPP_INSTALL_HINT: &str = "install llama.cpp first: `brew install llama.cpp` (macOS) or build from https://github.com/ggml-org/llama.cpp, then ensure `llama-cli` is on PATH";
const OLLAMA_INSTALL_HINT: &str = "install Ollama first: `brew install --cask ollama` or https://ollama.com/download, then ensure `ollama` is on PATH";

pub fn run_scenario(
    runtime: Runtime,
    installs: &RuntimeInstallations,
    scenario: &Scenario,
) -> Result<ScenarioResult, ScenarioError> {
    match runtime {
        Runtime::Mock => run_mock_scenario(scenario),
        Runtime::LlamaCpp => run_llama_cpp_scenario(&installs.llama_cpp, scenario),
        Runtime::Ollama => run_ollama_scenario(&installs.ollama, scenario),
    }
}

fn run_mock_scenario(scenario: &Scenario) -> Result<ScenarioResult, ScenarioError> {
    let stdout = build_mock_fixture_stdout(scenario);
    let metrics = parse_llama_cpp_metrics(&stdout).map_err(|err| ScenarioError::ParseFailed {
        runtime: "mock".to_string(),
        message: err.to_string(),
    })?;
    Ok(ScenarioResult { stdout, metrics })
}

fn run_llama_cpp_scenario(
    install: &Option<RuntimeInstall>,
    scenario: &Scenario,
) -> Result<ScenarioResult, ScenarioError> {
    let Some(install) = install else {
        return Err(ScenarioError::RuntimeNotInstalled {
            runtime: "llama.cpp".to_string(),
            hint: LLAMA_CPP_INSTALL_HINT.to_string(),
        });
    };
    let prompt = build_llama_prompt(scenario.prompt_tokens);
    let output = Command::new(&install.binary_path)
        .arg("-m")
        .arg(&scenario.model)
        .arg("-p")
        .arg(prompt)
        .arg("-n")
        .arg(scenario.generated_tokens.to_string())
        .arg("-c")
        .arg(scenario.context_tokens.to_string())
        .arg("-b")
        .arg(scenario.batch_size.to_string())
        .arg("--verbose")
        .output()
        .map_err(|err| ScenarioError::SpawnFailed {
            runtime: "llama.cpp".to_string(),
            message: err.to_string(),
        })?;
    let stdout = combine_stdout_and_stderr(&output);
    let metrics = parse_llama_cpp_metrics(&stdout).map_err(|err| ScenarioError::ParseFailed {
        runtime: "llama.cpp".to_string(),
        message: err.to_string(),
    })?;
    Ok(ScenarioResult { stdout, metrics })
}

fn run_ollama_scenario(
    install: &Option<RuntimeInstall>,
    scenario: &Scenario,
) -> Result<ScenarioResult, ScenarioError> {
    let Some(install) = install else {
        return Err(ScenarioError::RuntimeNotInstalled {
            runtime: "Ollama".to_string(),
            hint: OLLAMA_INSTALL_HINT.to_string(),
        });
    };
    let prompt = build_llama_prompt(scenario.prompt_tokens);
    let output = Command::new(&install.binary_path)
        .arg("run")
        .arg(&scenario.model)
        .arg("--verbose")
        .arg(prompt)
        .output()
        .map_err(|err| ScenarioError::SpawnFailed {
            runtime: "Ollama".to_string(),
            message: err.to_string(),
        })?;
    let stdout = combine_stdout_and_stderr(&output);
    let metrics = parse_ollama_metrics(&stdout).map_err(|err| ScenarioError::ParseFailed {
        runtime: "Ollama".to_string(),
        message: err.to_string(),
    })?;
    Ok(ScenarioResult { stdout, metrics })
}

fn combine_stdout_and_stderr(output: &std::process::Output) -> String {
    format!(
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    )
}

fn build_llama_prompt(token_count: u32) -> String {
    let mut prompt = String::with_capacity((token_count as usize) * 7);
    for index in 0..token_count {
        if index > 0 {
            prompt.push(' ');
        }
        prompt.push_str("token");
    }
    prompt
}

fn build_mock_fixture_stdout(scenario: &Scenario) -> String {
    const PREFILL_TOK_S: f64 = 5000.0;
    const DECODE_TOK_S: f64 = 18.7;
    const VRAM_MIB: f64 = 21811.0;

    let prefill_ms = scenario.prompt_tokens as f64 / PREFILL_TOK_S * 1000.0;
    let decode_ms = scenario.generated_tokens as f64 / DECODE_TOK_S * 1000.0;

    format!(
        "llama_print_timings: prompt eval time = {prefill_ms:.2} ms / {:>7} tokens (     1 run, {PREFILL_TOK_S:>8.2} tokens per second)\n\
         llama_print_timings: eval time = {decode_ms:.2} ms / {:>7} runs   (     1 run, {DECODE_TOK_S:>8.2} tokens per second)\n\
         llama_print_timings: total VRAM used: {VRAM_MIB:>10.2} MiB\n",
        scenario.prompt_tokens,
        scenario.generated_tokens,
    )
}
