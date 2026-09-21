use std::io::Read;
use std::path::PathBuf;
use std::process::exit;

use benchmark_probe::comfyui_adapter::{
    build_plan, detect_comfy_cli, execute_comfy_workflow, print_plan, print_run_metrics,
    sampler_node_ids, ComfyRunMetrics, ComfyScenario,
};
use benchmark_probe::execute_benchmark_scenario::{run_scenario, Scenario};
use benchmark_probe::parse_runtime_output::Metrics;
use benchmark_probe::sign_submission_payload::{
    generate_run_id, payload_digest, resolve_key_path, sha256_hex, sign_payload_digest,
    ArtifactEntry, BenchmarkReportPayload, MetricFields, ScenarioFields, ScenarioPayload,
    VideoScenarioFields, SCHEMA_VERSION,
};
use benchmark_probe::upload_benchmark_report::{
    fetch_challenge_nonce, upload_benchmark_report, ArtifactUpload, UploadRequest,
};
use benchmark_probe::{collect_system_topology, detect_runtime_installations, Runtime};
use clap::{Parser, Subcommand};

const VERSION: &str = env!("CARGO_PKG_VERSION");
const DEFAULT_MODEL: &str = "default-model";
const API_URL_ENV_VAR: &str = "BENCHMARK_PROBE_API_URL";
const API_TOKEN_ENV_VAR: &str = "BENCHMARK_PROBE_API_TOKEN";
const DEFAULT_API_URL: &str = "http://localhost:8000";

struct CliArgs {
    runtime: Runtime,
    model: String,
    prompt_tokens: u32,
    generated_tokens: u32,
    batch_size: u32,
    context_tokens: u32,
    artifact_paths: Vec<PathBuf>,
    output_path: Option<PathBuf>,
    report_runtime: Option<String>,
    sign: bool,
    upload: bool,
    scenario: Option<String>,
    recipe: Option<PathBuf>,
    workflow_out: Option<PathBuf>,
    execute: bool,
    print_command: bool,
    settle_claim_id: Option<String>,
    model_release_id: Option<String>,
    quantization_profile_id: Option<String>,
}

// S37: clap is the parser (uniform --help/--version, subcommand tree for
// lab + the L05 commands). The legacy validation MESSAGES are re-emitted
// post-parse so pinned smoke tests keep their exact stderr contract.
#[derive(Debug, Parser)]
#[command(
    name = "benchmark-probe",
    version,
    propagate_version = true,
    about = "Local LLM hardware benchmark probe: detects system topology, detects installed runtimes, runs a standardized benchmark scenario, and prints plain-text metrics.",
    after_help = "ENVIRONMENT:\n    BENCHMARK_PROBE_KEY_PATH   Ed25519 key path (default: ~/.config/benchmark-probe/ed25519.pem)\n    BENCHMARK_PROBE_API_URL    Submission API base URL (default: http://localhost:8000)\n    BENCHMARK_PROBE_API_TOKEN  Account bearer token (agent token) - required by --settle-claim\n\nEXAMPLES:\n    benchmark-probe --runtime mock\n    benchmark-probe --runtime mock --sign\n    benchmark-probe --runtime llama_cpp --model qwen2.5-coder-32b-q4_k_m.gguf --upload\n    benchmark-probe --runtime mock --upload --settle-claim 7d1e... # prove your claim\n    benchmark-probe --runtime ollama --model qwen2.5-coder:32b\n    benchmark-probe --runtime comfyui --scenario '{\"model\":\"wan22-i2v-flf2v\",\"width\":1280,\"height\":720,\"frames\":81,\"steps\":20,\"cfg\":3.5,\"shift\":5.0,\"seed\":42,\"first_image\":\"in/first.png\",\"last_image\":\"in/last.png\"}' --recipe recipes/wan22-flf2v-720p-81f-v1.json --workflow-out /tmp/wan22.json\n\nSEE ALSO:\n    canirunit - offline pool query: best-model suggestions from measured runs.\n\nEXIT CODES:\n    0 success · 2 usage error · 1 runtime failure"
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Command>,

    /// Runtime to benchmark: llama_cpp, ollama, comfyui, or mock (comfyui also requires --scenario and --recipe)
    #[arg(long)]
    runtime: Option<String>,
    /// Model name or GGUF path
    #[arg(long, default_value = DEFAULT_MODEL)]
    model: String,
    /// Prompt (prefill) token count
    #[arg(long, default_value_t = 4096)]
    prompt_tokens: u32,
    /// Tokens to generate
    #[arg(long, default_value_t = 512)]
    generated_tokens: u32,
    /// Prefill batch size
    #[arg(long, default_value_t = 1)]
    batch_size: u32,
    /// Context window size
    #[arg(long, default_value_t = 8192)]
    context_tokens: u32,
    /// Attach a file as an upload artifact (repeatable)
    #[arg(long = "artifact")]
    artifact_paths: Vec<PathBuf>,
    /// Write the signed report files (report, .digest, .signature, .artifact_0.txt)
    #[arg(long = "output")]
    output_path: Option<PathBuf>,
    /// Override the runtime declared in the report (e.g. llama_cpp)
    #[arg(long = "report-runtime")]
    report_runtime: Option<String>,
    /// Sign the report with the local Ed25519 key
    #[arg(long)]
    sign: bool,
    /// Sign and upload the report to the Submission API
    #[arg(long)]
    upload: bool,
    /// (comfyui) Video scenario JSON inline, or '-' to read stdin
    #[arg(long)]
    scenario: Option<String>,
    /// (comfyui) Recipe manifest with the workflow template
    #[arg(long)]
    recipe: Option<PathBuf>,
    /// (comfyui) Write the materialized workflow JSON to this path
    #[arg(long = "workflow-out")]
    workflow_out: Option<PathBuf>,
    /// (comfyui) Run the workflow headlessly and measure the clip
    #[arg(long)]
    execute: bool,
    /// Print an equivalent, re-runnable command line and exit
    #[arg(long = "print-command")]
    print_command: bool,
    /// Settle one of your open claims with this run (requires --upload and a token)
    #[arg(long = "settle-claim")]
    settle_claim_id: Option<String>,
    /// Catalog model binding override (e.g. model-qwen3-8b)
    #[arg(long = "model-release-id")]
    model_release_id: Option<String>,
    /// Catalog quantization binding override (e.g. q-gguf-q4-k-m)
    #[arg(long = "quantization-profile-id")]
    quantization_profile_id: Option<String>,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// TPE search over the llama.cpp serving space (L03A: --stub only, SIM)
    Lab {
        /// required in L03A: deterministic SIMULATED measurements
        #[arg(long)]
        stub: bool,
        /// search budget
        #[arg(long, default_value_t = 60)]
        trials: usize,
        /// RNG seed
        #[arg(long, default_value_t = 42)]
        seed: u64,
        /// labs root directory
        #[arg(long, default_value = "experiments")]
        out: PathBuf,
        /// machine-readable best.json on stdout
        #[arg(long)]
        json: bool,
    },
    /// Ranked model candidates for a GPU from catalog SOTA + predictors (S39)
    Plan {
        /// Rig id from the hardware snapshot (e.g. rtx-3090-24gb)
        #[arg(long)]
        gpu: String,
        /// Emit the stable machine object instead of the text table
        #[arg(long)]
        json: bool,
    },
    /// Measured-vs-predicted table over a lab directory (S40)
    Report {
        /// Lab label under experiments/ (default: latest finished)
        #[arg(long)]
        label: Option<String>,
        /// Stable machine object
        #[arg(long)]
        json: bool,
        /// Markdown table document
        #[arg(long)]
        markdown: bool,
    },
}

/// Lab invocation as parsed by clap (same defaults the manual parser had).
struct LabConfig {
    stub: bool,
    trials: usize,
    seed: u64,
    out_root: PathBuf,
    json: bool,
}

fn main() {
    let cli = Cli::parse();
    match cli.command {
        Some(Command::Lab { stub, trials, seed, out, json }) => {
            cmd_lab(LabConfig { stub, trials, seed, out_root: out, json });
        }
        Some(Command::Plan { gpu, json }) => cmd_plan(&gpu, json),
        Some(Command::Report { label, json, markdown }) => cmd_report(label.as_deref(), json, markdown),
        None => match build_cli_args(&cli) {
            Ok(args) => {
                if let Err(code) = run(&args) {
                    exit(code);
                }
            }
            Err(message) => {
                eprintln!("error: {message}");
                eprintln!();
                print_usage();
                exit(2);
            }
        },
    }
}

/// Reproduces the legacy parser's validation order and exact messages
/// (pinned by tests/cli_smoke.rs) on top of the clap-parsed values.
fn build_cli_args(cli: &Cli) -> Result<CliArgs, String> {
    let runtime = parse_runtime(
        cli.runtime
            .as_deref()
            .ok_or_else(|| "missing required argument '--runtime <llama_cpp|ollama|comfyui|mock>'".to_string())?,
    )?;
    if let Runtime::ComfyUi = runtime {
        cli.scenario.as_ref().ok_or_else(|| {
            "missing required argument '--scenario <json|->' for --runtime comfyui".to_string()
        })?;
        cli.recipe.as_ref().ok_or_else(|| {
            "missing required argument '--recipe <path>' for --runtime comfyui".to_string()
        })?;
    }
    if cli.settle_claim_id.is_some() && !cli.upload {
        return Err(
            "--settle-claim requires --upload (the run must be submitted to settle the claim)"
                .to_string(),
        );
    }
    Ok(CliArgs {
        runtime,
        model: cli.model.clone(),
        prompt_tokens: cli.prompt_tokens,
        generated_tokens: cli.generated_tokens,
        batch_size: cli.batch_size,
        context_tokens: cli.context_tokens,
        artifact_paths: cli.artifact_paths.clone(),
        output_path: cli.output_path.clone(),
        report_runtime: cli.report_runtime.clone(),
        sign: cli.sign,
        upload: cli.upload,
        scenario: cli.scenario.clone(),
        recipe: cli.recipe.clone(),
        workflow_out: cli.workflow_out.clone(),
        execute: cli.execute,
        print_command: cli.print_command,
        settle_claim_id: cli.settle_claim_id.clone(),
        model_release_id: cli.model_release_id.clone(),
        quantization_profile_id: cli.quantization_profile_id.clone(),
    })
}

fn cmd_plan(gpu: &str, json: bool) {
    const LIMIT: usize = 12;
    match benchmark_probe::plan_candidates::plan(gpu, LIMIT) {
        Ok(outcome) => {
            if json {
                println!("{}", serde_json::to_string_pretty(&outcome).expect("serialize plan"));
            } else {
                println!("plan for {} (task: decode_tok_s) — every row declares its basis", outcome.gpu);
                println!("  {:<44} {:<14} {:>10}  {}", "model", "quant", "expected", "basis");
                for c in &outcome.candidates {
                    println!("  {:<44} {:<14} {:>8.1}  {}", c.model_release_id, c.quant, c.expected, c.basis);
                }
                println!("honesty ladder: measured > reported > extrapolated > formula > no data yet.");
            }
        }
        Err(e) => {
            eprintln!("error: {}", e.message);
            exit(3);
        }
    }
}

fn cmd_report(label: Option<&str>, json: bool, markdown: bool) {
    use benchmark_probe::report_lab;
    let root = PathBuf::from(report_lab::DEFAULT_LAB_ROOT);
    let report = match report_lab::load_report(&root, label) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("error: {e}");
            exit(2);
        }
    };
    if json {
        println!("{}", serde_json::to_string_pretty(&report).expect("serialize report"));
    } else if markdown {
        print!("{}", report_lab::render_markdown(&report));
    } else {
        print!("{}", report_lab::render_text(&report));
    }
}

fn run(cli: &CliArgs) -> Result<(), i32> {
    if cli.print_command {
        println!("{}", build_command_line(cli));
        return Ok(());
    }

    let topology = collect_system_topology::collect_system_topology();
    print_topology(&topology);

    if let Runtime::ComfyUi = cli.runtime {
        return run_comfy_plan(cli, &topology);
    }

    let installs = detect_runtime_installations::detect_runtime_installations();
    let scenario = Scenario {
        model: cli.model.clone(),
        prompt_tokens: cli.prompt_tokens,
        generated_tokens: cli.generated_tokens,
        batch_size: cli.batch_size,
        context_tokens: cli.context_tokens,
    };

    let result = run_scenario(cli.runtime, &installs, &scenario).map_err(|err| {
        eprintln!("{err}");
        1
    })?;

    let runtime_version = match cli.runtime {
        Runtime::LlamaCpp => installs
            .llama_cpp
            .as_ref()
            .and_then(|i| i.version.as_deref()),
        Runtime::Ollama => installs.ollama.as_ref().and_then(|i| i.version.as_deref()),
        Runtime::Mock => Some("mock-1.0.0"),
        Runtime::ComfyUi => unreachable!("comfyui is handled by run_comfy_plan before this point"),
    };
    print_metrics(cli.runtime, &scenario, &result.metrics, runtime_version);

    if !cli.sign && !cli.upload && cli.output_path.is_none() {
        return Ok(());
    }

    let fingerprint = hardware_fingerprint(&topology);
    let evidence = build_evidence_content(&result.metrics);
    let report = build_report(
        cli,
        &scenario,
        &result.metrics,
        runtime_version,
        &fingerprint,
        cli.output_path.is_some(),
        &evidence,
    );
    let canonical = canonical_or_exit(&report);
    let digest = payload_digest(&canonical);
    let key_path = resolve_key_path();
    let signing_key = benchmark_probe::sign_submission_payload::load_or_create_signing_key(
        &key_path,
    )
    .map_err(|err| {
        eprintln!("error: {err}");
        1
    })?;
    let signature = sign_payload_digest(&signing_key, &digest);
    if let Some(path) = &cli.output_path {
        write_report_files(path, &canonical, &digest, &signature, &evidence)?;
        println!();
        println!("Wrote report files next to {}", path.display());
    }
    if cli.sign {
        print_signature_block(&canonical, &digest, &signature, &key_path);
    }
    if cli.upload {
        submit_report(cli, &canonical, &digest, &signature)?;
    }
    Ok(())
}

fn run_comfy_plan(
    cli: &CliArgs,
    topology: &collect_system_topology::SystemTopology,
) -> Result<(), i32> {
    let scenario_raw = match cli.scenario.as_deref() {
        Some("-") => {
            let mut buffer = String::new();
            if let Err(err) = std::io::stdin().read_to_string(&mut buffer) {
                eprintln!("error: unable to read --scenario from stdin: {err}");
                return Err(2);
            }
            buffer
        }
        Some(json) => json.to_string(),
        None => {
            eprintln!("error: --runtime comfyui requires --scenario <json|->");
            return Err(2);
        }
    };
    if scenario_raw.trim().is_empty() {
        eprintln!("error: --scenario is empty (stdin gave no JSON)");
        return Err(2);
    }
    let scenario: ComfyScenario = serde_json::from_str(scenario_raw.trim()).map_err(|err| {
        eprintln!("error: invalid --scenario JSON: {err}");
        2
    })?;
    let Some(recipe_path) = cli.recipe.as_ref() else {
        eprintln!("error: --runtime comfyui requires --recipe <path>");
        return Err(2);
    };
    let plan = build_plan(recipe_path, &scenario).map_err(|err| {
        eprintln!("{err}");
        1
    })?;

    if !cli.execute {
        if let Some(out_path) = &cli.workflow_out {
            std::fs::write(out_path, &plan.workflow_json).map_err(|err| {
                eprintln!("error: unable to write '{}': {err}", out_path.display());
                1
            })?;
            println!("Wrote materialized workflow to {}", out_path.display());
            println!();
        }
        let comfy_cli = detect_comfy_cli();
        print_plan(&plan, cli.workflow_out.as_deref(), comfy_cli.as_deref());
        return Ok(());
    }

    // --execute: real headless run (Story 1.2).
    let workflow_out = cli.workflow_out.clone().unwrap_or_else(|| {
        std::env::temp_dir().join(format!("benchmark-probe-comfyui-{}.json", std::process::id()))
    });
    std::fs::write(&workflow_out, &plan.workflow_json).map_err(|err| {
        eprintln!("error: unable to write '{}': {err}", workflow_out.display());
        1
    })?;
    let workflow: serde_json::Value = serde_json::from_str(&plan.workflow_json)
        .map_err(|err| {
            eprintln!("error: internal: materialized workflow lost validity: {err}");
            1
        })?;
    let samplers = sampler_node_ids(&workflow);
    let execution =
        execute_comfy_workflow(&workflow_out, &samplers, plan.scenario.frames).map_err(|err| {
            eprintln!("error: {err}");
            1
        })?;
    if cli.workflow_out.is_none() {
        let _ = std::fs::remove_file(&workflow_out);
    }
    print_run_metrics(&plan, &execution.metrics);

    if !cli.sign && !cli.upload && cli.output_path.is_none() {
        return Ok(());
    }
    let fingerprint = hardware_fingerprint(topology);
    let comfy_version = detect_comfy_cli().unwrap_or_else(|| "unknown".to_string());
    let evidence = build_video_evidence(&execution.metrics);
    let report = build_video_report(&plan, &execution.metrics, &fingerprint, &comfy_version, &evidence);
    let canonical = canonical_or_exit(&report);
    let digest = payload_digest(&canonical);
    let key_path = resolve_key_path();
    let signing_key = benchmark_probe::sign_submission_payload::load_or_create_signing_key(&key_path)
        .map_err(|err| {
            eprintln!("error: {err}");
            1
        })?;
    let signature = sign_payload_digest(&signing_key, &digest);
    if let Some(path) = &cli.output_path {
        write_report_files(path, &canonical, &digest, &signature, &evidence)?;
        println!();
        println!("Wrote report files next to {}", path.display());
    }
    if cli.sign {
        print_signature_block(&canonical, &digest, &signature, &key_path);
    }
    if cli.upload {
        submit_report(cli, &canonical, &digest, &signature)?;
    }
    Ok(())
}

fn build_video_report(
    plan: &benchmark_probe::comfyui_adapter::ComfyPlan,
    metrics: &ComfyRunMetrics,
    fingerprint: &str,
    comfy_version: &str,
    evidence: &str,
) -> BenchmarkReportPayload {
    BenchmarkReportPayload {
        schema_version: SCHEMA_VERSION.to_string(),
        run_id: generate_run_id(),
        runtime: "comfyui".to_string(),
        runtime_version: comfy_version.to_string(),
        hardware_fingerprint: fingerprint.to_string(),
        scenario: ScenarioPayload::Video(VideoScenarioFields {
            scenario_kind: "video",
            width: plan.scenario.width,
            height: plan.scenario.height,
            frames: plan.scenario.frames,
            steps: plan.scenario.steps,
            cfg: plan.scenario.cfg,
            shift: plan.scenario.shift,
            seed: plan.scenario.seed,
        }),
        metrics: MetricFields {
            ttft_ms: 0.0,
            prefill_tok_s: 0.0,
            decode_tok_s: 0.0,
            peak_vram_mib: metrics.peak_vram_mib,
            power_watt_avg: 0.0,
            seconds_per_clip: Some(metrics.seconds_per_clip),
            it_per_s: metrics.it_per_s,
            frames_per_s: Some(metrics.frames_per_s),
        },
        artifacts: vec![ArtifactEntry {
            artifact_kind: "runtime_stdout".to_string(),
            sha256: sha256_hex(evidence.as_bytes()),
        }],
        recipe_id: Some(plan.recipe_id.clone()),
    }
}

fn build_video_evidence(metrics: &ComfyRunMetrics) -> String {
    format!(
        "metric seconds_per_clip {:.3}\nmetric it_per_s {:.3}\nmetric frames_per_s {:.3}\nmetric peak_vram_mib {:.0}\n",
        metrics.seconds_per_clip,
        metrics.it_per_s.unwrap_or(0.0),
        metrics.frames_per_s,
        metrics.peak_vram_mib
    )
}

fn build_report(
    cli: &CliArgs,
    scenario: &Scenario,
    metrics: &Metrics,
    runtime_version: Option<&str>,
    fingerprint: &str,
    use_evidence_artifact: bool,
    evidence: &str,
) -> BenchmarkReportPayload {
    let artifacts = if use_evidence_artifact {
        vec![ArtifactEntry {
            artifact_kind: "runtime_stdout".to_string(),
            sha256: sha256_hex(evidence.as_bytes()),
        }]
    } else {
        cli.artifact_paths
            .iter()
            .enumerate()
            .map(|(index, path)| ArtifactEntry {
                artifact_kind: artifact_kind_for_index(index),
                sha256: sha256_hex(&read_artifact_or_exit(path)),
            })
            .collect()
    };
    BenchmarkReportPayload {
        schema_version: SCHEMA_VERSION.to_string(),
        run_id: generate_run_id(),
        runtime: cli
            .report_runtime
            .clone()
            .unwrap_or_else(|| cli.runtime.engine_name().to_string()),
        runtime_version: runtime_version.unwrap_or("unknown").to_string(),
        hardware_fingerprint: fingerprint.to_string(),
        scenario: ScenarioPayload::Llm(ScenarioFields {
            prompt_tokens: scenario.prompt_tokens,
            generated_tokens: scenario.generated_tokens,
            batch_size: scenario.batch_size,
            context_tokens: scenario.context_tokens,
        }),
        metrics: MetricFields {
            ttft_ms: metrics.ttft_ms,
            prefill_tok_s: metrics.prefill_tok_s,
            decode_tok_s: metrics.decode_tok_s,
            peak_vram_mib: metrics.peak_vram_mib,
            power_watt_avg: metrics.power_watt_avg,
            seconds_per_clip: None,
            it_per_s: None,
            frames_per_s: None,
        },
        artifacts,
        recipe_id: None,
    }
}

/// Story 5.1: tokens of an equivalent, re-runnable invocation of this probe.
/// Excludes network/signing flags on purpose — the printed command must be
/// safe to run anywhere (the contribution docs explain adding --sign --upload).
fn command_tokens(cli: &CliArgs) -> Vec<String> {
    let mut tokens = vec![
        "benchmark-probe".to_string(),
        "--runtime".to_string(),
        cli.runtime.engine_name().to_string(),
        "--model".to_string(),
        cli.model.clone(),
        "--prompt-tokens".to_string(),
        cli.prompt_tokens.to_string(),
        "--generated-tokens".to_string(),
        cli.generated_tokens.to_string(),
        "--batch-size".to_string(),
        cli.batch_size.to_string(),
        "--context-tokens".to_string(),
        cli.context_tokens.to_string(),
    ];
    for artifact in &cli.artifact_paths {
        tokens.push("--artifact".to_string());
        tokens.push(artifact.display().to_string());
    }
    if let Some(report_runtime) = &cli.report_runtime {
        tokens.push("--report-runtime".to_string());
        tokens.push(report_runtime.clone());
    }
    if let Some(scenario) = &cli.scenario {
        tokens.push("--scenario".to_string());
        tokens.push(scenario.clone());
    }
    if let Some(recipe) = &cli.recipe {
        tokens.push("--recipe".to_string());
        tokens.push(recipe.display().to_string());
    }
    if let Some(workflow_out) = &cli.workflow_out {
        tokens.push("--workflow-out".to_string());
        tokens.push(workflow_out.display().to_string());
    }
    tokens
}

/// Single shell-safe line: every token single-quoted so any model name, path
/// or JSON scenario survives a copy-paste into sh/bash.
fn build_command_line(cli: &CliArgs) -> String {
    command_tokens(cli)
        .iter()
        .map(|token| shell_quote(token))
        .collect::<Vec<String>>()
        .join(" ")
}

fn shell_quote(value: &str) -> String {
    let mut quoted = String::with_capacity(value.len() + 2);
    quoted.push('\'');
    for ch in value.chars() {
        if ch == '\'' {
            quoted.push_str("'\\''");
        } else {
            quoted.push(ch);
        }
    }
    quoted.push('\'');
    quoted
}

fn artifact_kind_for_index(index: usize) -> String {
    if index == 0 {
        "runtime_stdout".to_string()
    } else {
        format!("supplement_{index}")
    }
}

fn read_artifact_or_exit(path: &PathBuf) -> Vec<u8> {
    match std::fs::read(path) {
        Ok(bytes) => bytes,
        Err(err) => {
            eprintln!("error: unable to read artifact '{}': {err}", path.display());
            exit(1);
        }
    }
}

fn hardware_fingerprint(topology: &collect_system_topology::SystemTopology) -> String {
    let gpu_names: Vec<&str> = topology.gpus.iter().map(|gpu| gpu.name.as_str()).collect();
    let summary = format!(
        "{}|{}|{}|{}",
        gpu_names.join(","),
        topology.cpu_model,
        topology.os_name,
        topology.os_version
    );
    format!("sha256:{}", sha256_hex(summary.as_bytes()))
}

fn canonical_or_exit(report: &BenchmarkReportPayload) -> String {
    match benchmark_probe::sign_submission_payload::canonicalize_report(report) {
        Ok(canonical) => canonical,
        Err(err) => {
            eprintln!("error: unable to canonicalize report: {err}");
            exit(1);
        }
    }
}

fn build_evidence_content(metrics: &Metrics) -> String {
    format!(
        "metric ttft_ms {:.3}\nmetric prefill_tok_s {:.3}\nmetric decode_tok_s {:.3}\nmetric peak_vram_mib {:.0}\nmetric power_watt_avg {:.1}\n",
        metrics.ttft_ms,
        metrics.prefill_tok_s,
        metrics.decode_tok_s,
        metrics.peak_vram_mib,
        metrics.power_watt_avg
    )
}

fn write_report_files(
    path: &PathBuf,
    canonical: &str,
    digest: &str,
    signature: &str,
    evidence: &str,
) -> Result<(), i32> {
    let write = |target: std::path::PathBuf, content: &str| -> Result<(), i32> {
        std::fs::write(&target, content).map_err(|err| {
            eprintln!("error: unable to write {}: {err}", target.display());
            1
        })
    };
    write(path.clone(), canonical)?;
    write(path.with_extension("digest"), digest)?;
    write(path.with_extension("signature"), signature)?;
    write(path.with_extension("artifact_0.txt"), evidence)?;
    Ok(())
}

fn print_signature_block(
    canonical: &str,
    digest: &str,
    signature: &str,
    key_path: &std::path::Path,
) {
    println!();
    println!("Report (contract {SCHEMA_VERSION}):");
    println!("{canonical}");
    println!("Payload digest: {digest}");
    println!("Signature: {signature}");
    println!("Key: {}", key_path.display());
}

fn submit_report(
    cli: &CliArgs,
    canonical: &str,
    digest: &str,
    signature: &str,
) -> Result<(), i32> {
    let base_url = std::env::var(API_URL_ENV_VAR).unwrap_or_else(|_| DEFAULT_API_URL.to_string());
    let api_token = match std::env::var(API_TOKEN_ENV_VAR) {
        Ok(token) => Some(token),
        Err(_) if cli.settle_claim_id.is_none() => None,
        Err(_) => {
            eprintln!(
                "error: --settle-claim requires an API token; set {API_TOKEN_ENV_VAR} \
                 to an agent token (POST /v1/auth/tokens)"
            );
            return Err(1);
        }
    };
    let challenge_nonce = fetch_challenge_nonce(&base_url).map_err(|err| {
        eprintln!("error: {err}");
        1
    })?;
    let artifacts: Vec<ArtifactUpload> = if cli.output_path.is_some() {
        let evidence_path = cli.output_path.as_ref().unwrap().with_extension("artifact_0.txt");
        vec![ArtifactUpload {
            bytes: read_artifact_or_exit(&evidence_path),
        }]
    } else {
        cli.artifact_paths
            .iter()
            .map(|path| ArtifactUpload {
                bytes: read_artifact_or_exit(path),
            })
            .collect()
    };
    let request = UploadRequest {
        report_json: canonical.to_string(),
        payload_digest: digest.to_string(),
        signature: signature.to_string(),
        challenge_nonce: challenge_nonce.clone(),
        client_version: VERSION.to_string(),
        artifacts,
        settle_claim_id: cli.settle_claim_id.clone(),
        model_release_id: cli.model_release_id.clone(),
        quantization_profile_id: cli.quantization_profile_id.clone(),
        api_token,
    };
    let outcome = upload_benchmark_report(&base_url, &request).map_err(|err| {
        eprintln!("error: {err}");
        1
    })?;
    if outcome.status_code < 200 || outcome.status_code >= 300 {
        eprintln!(
            "error: submission rejected with HTTP status {}",
            outcome.status_code
        );
        return Err(1);
    }
    let run_id = outcome.run_id.unwrap_or_default();
    println!();
    println!(
        "Uploaded report; status {} run_id {run_id}",
        outcome.status_code
    );
    println!("Challenge nonce: {challenge_nonce}");
    Ok(())
}

fn parse_runtime(value: &str) -> Result<Runtime, String> {
    match value {
        "llama_cpp" => Ok(Runtime::LlamaCpp),
        "ollama" => Ok(Runtime::Ollama),
        "mock" => Ok(Runtime::Mock),
        "comfyui" => Ok(Runtime::ComfyUi),
        other => Err(format!(
            "invalid value for '--runtime': '{other}' (expected one of: llama_cpp, ollama, comfyui, mock)"
        )),
    }
}

fn print_topology(topology: &collect_system_topology::SystemTopology) {
    if let Some(gpu) = topology.gpus.first() {
        let vram = gpu
            .vram_mib
            .map(|mib| format!(" ({:.0} GiB)", mib as f64 / 1024.0))
            .unwrap_or_default();
        println!("GPU: {}{}", gpu.name, vram);
    }
    if !topology.cpu_model.is_empty() {
        println!("CPU: {}", topology.cpu_model);
    }
    let os = if topology.os_version.is_empty() {
        topology.os_name.clone()
    } else {
        format!("{} {}", topology.os_name, topology.os_version)
    };
    println!("OS: {os}");
    println!();
}

fn print_metrics(
    runtime: Runtime,
    scenario: &Scenario,
    metrics: &Metrics,
    runtime_version: Option<&str>,
) {
    println!("Running {} benchmark", runtime.label());
    if let Some(version) = runtime_version {
        println!("Runtime version: {version}");
    }
    println!("Model: {}", scenario.model);
    println!("Prompt tokens: {}", scenario.prompt_tokens);
    println!("Generated tokens: {}", scenario.generated_tokens);
    println!("TTFT: {:.0} ms", metrics.ttft_ms);
    println!("Prefill: {:.0} tok/s", metrics.prefill_tok_s);
    println!("Decode: {:.1} tok/s", metrics.decode_tok_s);
    println!("Peak VRAM: {:.1} GiB", metrics.peak_vram_mib / 1024.0);
}

fn print_usage() {
    println!("benchmark-probe {VERSION}");
    println!();
    println!(
        "Local LLM hardware benchmark probe: detects system topology, detects installed runtimes,"
    );
    println!("runs a standardized benchmark scenario, and prints plain-text metrics.");
    println!();
    println!("USAGE:");
    println!("    benchmark-probe --runtime <llama_cpp|ollama|comfyui|mock> [OPTIONS]");
    println!();
    println!("REQUIRED:");
    println!("    --runtime <runtime>    Runtime to benchmark: llama_cpp, ollama, comfyui, or mock");
    println!("                           comfyui also requires --scenario and --recipe (video dry-run)");
    println!();
    println!("OPTIONS:");
    println!("    --model <model>            Model name or GGUF path (default: {DEFAULT_MODEL})");
    println!("    --prompt-tokens <n>        Prompt (prefill) token count (default: 4096)");
    println!("    --generated-tokens <n>     Tokens to generate (default: 512)");
    println!("    --batch-size <n>           Prefill batch size (default: 1)");
    println!("    --context-tokens <n>       Context window size (default: 8192)");
    println!("    --scenario <json|->        (comfyui) Video scenario JSON inline, or '-' to read stdin");
    println!("    --recipe <path>            (comfyui) Recipe manifest with the workflow template");
    println!("    --workflow-out <path>      (comfyui) Write the materialized workflow JSON to this path");
    println!("    --execute                  (comfyui) Run the workflow headlessly and measure the clip");
    println!("    --print-command            Print an equivalent, re-runnable command line and exit");
    println!("    --artifact <path>          Attach a file as an upload artifact (repeatable)");
    println!("    --output <path>            Write the signed report files (report, .digest, .signature, .artifact_0.txt)");
    println!("    --report-runtime <engine>  Override the runtime declared in the report (e.g. llama_cpp)");
    println!("    --sign                     Sign the report with the local Ed25519 key");
    println!("    --upload                   Sign and upload the report to the Submission API");
    println!("    --settle-claim <id>        Settle one of your open claims with this run (requires --upload and a token)");
    println!("    --model-release-id <id>    Catalog model binding override (e.g. model-qwen3-8b)");
    println!("    --quantization-profile-id <id>  Catalog quantization binding override (e.g. q-gguf-q4-k-m)");
    println!("    -h, --help                 Print this help and exit");
    println!();
    println!("ENVIRONMENT:");
    println!("    BENCHMARK_PROBE_KEY_PATH   Ed25519 key path (default: ~/.config/benchmark-probe/ed25519.pem)");
    println!("    BENCHMARK_PROBE_API_URL    Submission API base URL (default: {DEFAULT_API_URL})");
    println!("    BENCHMARK_PROBE_API_TOKEN  Account bearer token (agent token) - required by --settle-claim");
    println!();
    println!("EXAMPLES:");
    println!("    benchmark-probe --runtime mock");
    println!("    benchmark-probe --runtime mock --sign");
    println!(
        "    benchmark-probe --runtime llama_cpp --model qwen2.5-coder-32b-q4_k_m.gguf --upload"
    );
    println!("    benchmark-probe --runtime mock --upload --settle-claim 7d1e... # prove your claim");
    println!("    benchmark-probe --runtime ollama --model qwen2.5-coder:32b");
    println!(
        "    benchmark-probe --runtime comfyui --scenario '{{\"model\":\"wan22-i2v-flf2v\",\"width\":1280,\"height\":720,\"frames\":81,\"steps\":20,\"cfg\":3.5,\"shift\":5.0,\"seed\":42,\"first_image\":\"in/first.png\",\"last_image\":\"in/last.png\"}}' --recipe recipes/wan22-flf2v-720p-81f-v1.json --workflow-out /tmp/wan22.json"
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(tokens: &[&str]) -> Vec<String> {
        tokens.iter().map(|t| t.to_string()).collect()
    }

    fn base_cli() -> CliArgs {
        CliArgs {
            runtime: Runtime::Mock,
            model: "test-model".to_string(),
            prompt_tokens: 4096,
            generated_tokens: 512,
            batch_size: 1,
            context_tokens: 8192,
            artifact_paths: vec![],
            output_path: None,
            report_runtime: None,
            sign: false,
            upload: false,
            scenario: None,
            recipe: None,
            workflow_out: None,
            execute: false,
            print_command: false,
            settle_claim_id: None,
            model_release_id: None,
            quantization_profile_id: None,
        }
    }

    #[test]
    fn print_command_round_trips_through_parse_args() {
        let mut cli = base_cli();
        cli.runtime = Runtime::Ollama;
        cli.model = "qwen2.5-coder:32b".to_string();
        cli.report_runtime = Some("ollama".to_string());
        let line = build_command_line(&cli);
        assert!(line.starts_with("'benchmark-probe'"));

        let tokens: Vec<String> = line
            .split(' ')
            .map(|quoted| unquote_token(quoted))
            .collect();
        let clap_cli = Cli::try_parse_from(&tokens).expect("reparsed through clap");
        let cli = build_cli_args(&clap_cli).expect("validated");
        assert!(matches!(cli.runtime, Runtime::Ollama));
        assert_eq!(cli.model, "qwen2.5-coder:32b");
        assert_eq!(cli.prompt_tokens, 4096);
        assert_eq!(cli.context_tokens, 8192);
        assert_eq!(cli.report_runtime.as_deref(), Some("ollama"));
        assert!(!cli.sign && !cli.upload && !cli.execute);
    }

    #[test]
    fn shell_quote_escapes_embedded_quotes() {
        assert_eq!(shell_quote("plain"), "'plain'");
        assert_eq!(shell_quote("it's"), "'it'\\''s'");
        assert_eq!(shell_quote(""), "''");
    }

    #[test]
    fn comfyui_command_carries_scenario_and_recipe() {
        let mut cli = base_cli();
        cli.runtime = Runtime::ComfyUi;
        cli.scenario = Some("{\"width\":1280}".to_string());
        cli.recipe = Some(PathBuf::from("recipes/wan22-flf2v-720p-81f-v1.json"));
        let tokens = command_tokens(&cli);
        let line = tokens.join(" ");
        assert!(line.contains("--scenario"));
        assert!(line.contains("{\"width\":1280}"));
        assert!(line.contains("--recipe"));
        assert!(line.contains("recipes/wan22-flf2v-720p-81f-v1.json"));
        // The generated command must stay a dry-run: --execute is never emitted.
        assert!(!tokens.iter().any(|token| token == "--execute"));
    }

    #[test]
    fn print_command_flag_parses_without_other_flags() {
        let clap_cli = Cli::try_parse_from(args(&["benchmark-probe", "--runtime", "mock", "--print-command"]))
            .expect("parsed");
        assert!(clap_cli.print_command);
        assert_eq!(clap_cli.runtime.as_deref(), Some("mock"));
    }

    /// Minimal inverse of `shell_quote` for round-trip assertions above.
    fn unquote_token(quoted: &str) -> String {
        let body = quoted
            .strip_prefix('\'')
            .and_then(|rest| rest.strip_suffix('\''))
            .expect("shell-quoted token");
        body.replace("'\\''", "'")
    }
}

// ── L03A: `lab` — TPE search over llama.cpp serving flags (stub proof) ──

fn cmd_lab(cfg: LabConfig) {
    let LabConfig { stub, trials, seed, out_root, json } = cfg;
    if !stub {
        eprintln!("lab: only --stub is available in L03A — the real objective lands when the owner brings the 3090 up (SIM)");
        exit(2);
    }

    let space = match benchmark_probe::tuning_search::LabSpace::new() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("lab: {e}");
            exit(2);
        }
    };
    // millis: two labs in the same second must not collide (labs are
    // immutable once recorded)
    let label = format!(
        "{}-stub",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0)
    );
    let mut objective = |p: &Vec<argos_opt::Value>| {
        benchmark_probe::tuning_search::stub_objective(p)
    };
    let outcome = match benchmark_probe::tuning_search::run_lab(
        &space, trials, seed, &mut objective, &out_root, &label,
    ) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("lab: {e}");
            exit(1);
        }
    };
    let command = space.to_server_command(&outcome.best_params, "MODEL.gguf");
    if json {
        let best_path = outcome.lab_dir.join("best.json");
        let text = std::fs::read_to_string(&best_path).unwrap_or_else(|e| {
            eprintln!("lab: read {}: {e}", best_path.display());
            exit(1);
        });
        print!("{text}");
        return;
    }
    println!("SIM — SIMULATED measurements (stub); not a benchmark claim");
    println!("trials:          {}", outcome.trials);
    println!("best tok/s:      {:.1}", outcome.best_value);
    println!("server command:  {command}");
    println!("lab dir:         {}", outcome.lab_dir.display());
}
