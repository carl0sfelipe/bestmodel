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

fn main() {
    let raw_args: Vec<String> = std::env::args().skip(1).collect();
    // L03A: `lab` is the first subcommand; everything else keeps the
    // legacy flag parser untouched.
    if raw_args.first().map(|s| s.as_str()) == Some("lab") {
        cmd_lab(&raw_args[1..]);
        return;
    }
    match parse_args(&raw_args) {
        Ok(None) => {
            print_usage();
            exit(0);
        }
        Ok(Some(cli)) => {
            if let Err(code) = run(&cli) {
                exit(code);
            }
        }
        Err(message) => {
            eprintln!("error: {message}");
            eprintln!();
            print_usage();
            exit(2);
        }
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

fn parse_args(raw_args: &[String]) -> Result<Option<CliArgs>, String> {
    let mut runtime: Option<Runtime> = None;
    let mut model = String::from(DEFAULT_MODEL);
    let mut prompt_tokens = 4096u32;
    let mut generated_tokens = 512u32;
    let mut batch_size = 1u32;
    let mut context_tokens = 8192u32;
    let mut artifact_paths: Vec<PathBuf> = Vec::new();
    let mut output_path: Option<PathBuf> = None;
    let mut report_runtime: Option<String> = None;
    let mut sign = false;
    let mut upload = false;
    let mut scenario: Option<String> = None;
    let mut recipe: Option<PathBuf> = None;
    let mut workflow_out: Option<PathBuf> = None;
    let mut execute = false;
    let mut print_command = false;
    let mut settle_claim_id: Option<String> = None;
    let mut model_release_id: Option<String> = None;
    let mut quantization_profile_id: Option<String> = None;

    let mut index = 0;
    while index < raw_args.len() {
        let raw = &raw_args[index];
        if raw == "--help" || raw == "-h" {
            return Ok(None);
        }
        let (flag, inline_value) = match raw.split_once('=') {
            Some((name, value)) => (name.to_string(), Some(value.to_string())),
            None => (raw.clone(), None),
        };
        if !flag.starts_with("--") {
            return Err(format!("unexpected argument '{raw}'"));
        }

        let take_value = |index: &mut usize| -> Result<String, String> {
            if let Some(value) = inline_value.clone() {
                return Ok(value);
            }
            *index += 1;
            raw_args
                .get(*index)
                .cloned()
                .ok_or_else(|| format!("missing value for '{flag}'"))
        };

        match flag.as_str() {
            "--runtime" => {
                let value = take_value(&mut index)?;
                runtime = Some(parse_runtime(&value)?);
            }
            "--model" => model = take_value(&mut index)?,
            "--prompt-tokens" => prompt_tokens = parse_u32(&flag, &take_value(&mut index)?)?,
            "--generated-tokens" => generated_tokens = parse_u32(&flag, &take_value(&mut index)?)?,
            "--batch-size" => batch_size = parse_u32(&flag, &take_value(&mut index)?)?,
            "--context-tokens" => context_tokens = parse_u32(&flag, &take_value(&mut index)?)?,
            "--artifact" => artifact_paths.push(PathBuf::from(take_value(&mut index)?)),
            "--output" => output_path = Some(PathBuf::from(take_value(&mut index)?)),
            "--report-runtime" => report_runtime = Some(take_value(&mut index)?),
            "--scenario" => scenario = Some(take_value(&mut index)?),
            "--recipe" => recipe = Some(PathBuf::from(take_value(&mut index)?)),
            "--workflow-out" => workflow_out = Some(PathBuf::from(take_value(&mut index)?)),
            "--execute" => execute = true,
            "--print-command" => print_command = true,
            "--settle-claim" => settle_claim_id = Some(take_value(&mut index)?),
            "--model-release-id" => model_release_id = Some(take_value(&mut index)?),
            "--quantization-profile-id" => quantization_profile_id = Some(take_value(&mut index)?),
            "--sign" => sign = true,
            "--upload" => upload = true,
            other => return Err(format!("unknown argument '{other}'")),
        }
        index += 1;
    }

    let runtime = runtime.ok_or_else(|| {
        "missing required argument '--runtime <llama_cpp|ollama|comfyui|mock>'".to_string()
    })?;
    if let Runtime::ComfyUi = runtime {
        scenario.as_ref().ok_or_else(|| {
            "missing required argument '--scenario <json|->' for --runtime comfyui".to_string()
        })?;
        recipe.as_ref().ok_or_else(|| {
            "missing required argument '--recipe <path>' for --runtime comfyui".to_string()
        })?;
    }
    if settle_claim_id.is_some() && !upload {
        return Err(
            "--settle-claim requires --upload (the run must be submitted to settle the claim)"
                .to_string(),
        );
    }
    Ok(Some(CliArgs {
        runtime,
        model,
        prompt_tokens,
        generated_tokens,
        batch_size,
        context_tokens,
        artifact_paths,
        output_path,
        report_runtime,
        sign,
        upload,
        scenario,
        recipe,
        workflow_out,
        execute,
        print_command,
        settle_claim_id,
        model_release_id,
        quantization_profile_id,
    }))
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

fn parse_u32(flag: &str, value: &str) -> Result<u32, String> {
    value
        .parse::<u32>()
        .map_err(|_| format!("invalid value for '{flag}': '{value}' (expected a positive integer)"))
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
        let reparsed = parse_args(&tokens[1..]).expect("reparsed");
        let cli = reparsed.expect("some cli");
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
        let parsed = parse_args(&args(&["--runtime", "mock", "--print-command"]))
            .expect("parsed")
            .expect("some cli");
        assert!(parsed.print_command);
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

fn lab_usage() {
    println!(
        "usage: benchmark-probe lab --stub [--trials N] [--seed N] [--out DIR] [--json]\n\n\
         Runs the intelligent (TPE) search over the llama.cpp serving space.\n\
         --stub   required in L03A: deterministic SIMULATED measurements\n\
         --trials search budget (default 60)\n\
         --seed   RNG seed (default 42)\n\
         --out    labs root directory (default experiments/)\n\
         --json   machine-readable best.json on stdout"
    );
}

fn cmd_lab(args: &[String]) {
    let mut stub = false;
    let mut trials: usize = 60;
    let mut seed: u64 = 42;
    let mut out_root = PathBuf::from("experiments");
    let mut json = false;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--stub" => stub = true,
            "--trials" => {
                i += 1;
                trials = args.get(i).and_then(|v| v.parse().ok()).unwrap_or_else(|| {
                    eprintln!("lab: --trials needs a number");
                    exit(2);
                });
            }
            "--seed" => {
                i += 1;
                seed = args.get(i).and_then(|v| v.parse().ok()).unwrap_or_else(|| {
                    eprintln!("lab: --seed needs a number");
                    exit(2);
                });
            }
            "--out" => {
                i += 1;
                out_root = args.get(i).map(PathBuf::from).unwrap_or_else(|| {
                    eprintln!("lab: --out needs a directory");
                    exit(2);
                });
            }
            "--json" => json = true,
            "--help" | "-h" => {
                lab_usage();
                exit(0);
            }
            other => {
                eprintln!("lab: unknown flag {other}");
                lab_usage();
                exit(2);
            }
        }
        i += 1;
    }
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
