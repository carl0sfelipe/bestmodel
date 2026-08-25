use std::path::PathBuf;
use std::process::exit;

use benchmark_probe::execute_benchmark_scenario::{run_scenario, Scenario};
use benchmark_probe::parse_runtime_output::Metrics;
use benchmark_probe::sign_submission_payload::{
    generate_run_id, payload_digest, resolve_key_path, sha256_hex, sign_payload_digest,
    ArtifactEntry, BenchmarkReportPayload, MetricFields, ScenarioFields, SCHEMA_VERSION,
};
use benchmark_probe::upload_benchmark_report::{
    fetch_challenge_nonce, upload_benchmark_report, ArtifactUpload, UploadRequest,
};
use benchmark_probe::{collect_system_topology, detect_runtime_installations, Runtime};

const VERSION: &str = env!("CARGO_PKG_VERSION");
const DEFAULT_MODEL: &str = "default-model";
const API_URL_ENV_VAR: &str = "BENCHMARK_PROBE_API_URL";
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
}

fn main() {
    let raw_args: Vec<String> = std::env::args().skip(1).collect();
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
    let topology = collect_system_topology::collect_system_topology();
    print_topology(&topology);

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
        scenario: ScenarioFields {
            prompt_tokens: scenario.prompt_tokens,
            generated_tokens: scenario.generated_tokens,
            batch_size: scenario.batch_size,
            context_tokens: scenario.context_tokens,
        },
        metrics: MetricFields {
            ttft_ms: metrics.ttft_ms,
            prefill_tok_s: metrics.prefill_tok_s,
            decode_tok_s: metrics.decode_tok_s,
            peak_vram_mib: metrics.peak_vram_mib,
            power_watt_avg: metrics.power_watt_avg,
        },
        artifacts,
    }
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
            "--sign" => sign = true,
            "--upload" => upload = true,
            other => return Err(format!("unknown argument '{other}'")),
        }
        index += 1;
    }

    let runtime = runtime.ok_or_else(|| {
        "missing required argument '--runtime <llama_cpp|ollama|mock>'".to_string()
    })?;
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
    }))
}

fn parse_runtime(value: &str) -> Result<Runtime, String> {
    match value {
        "llama_cpp" => Ok(Runtime::LlamaCpp),
        "ollama" => Ok(Runtime::Ollama),
        "mock" => Ok(Runtime::Mock),
        other => Err(format!(
            "invalid value for '--runtime': '{other}' (expected one of: llama_cpp, ollama, mock)"
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
    println!("    benchmark-probe --runtime <llama_cpp|ollama|mock> [OPTIONS]");
    println!();
    println!("REQUIRED:");
    println!("    --runtime <runtime>    Runtime to benchmark: llama_cpp, ollama, or mock");
    println!();
    println!("OPTIONS:");
    println!("    --model <model>            Model name or GGUF path (default: {DEFAULT_MODEL})");
    println!("    --prompt-tokens <n>        Prompt (prefill) token count (default: 4096)");
    println!("    --generated-tokens <n>     Tokens to generate (default: 512)");
    println!("    --batch-size <n>           Prefill batch size (default: 1)");
    println!("    --context-tokens <n>       Context window size (default: 8192)");
    println!("    --artifact <path>          Attach a file as an upload artifact (repeatable)");
    println!("    --output <path>            Write the signed report files (report, .digest, .signature, .artifact_0.txt)");
    println!("    --report-runtime <engine>  Override the runtime declared in the report (e.g. llama_cpp)");
    println!("    --sign                     Sign the report with the local Ed25519 key");
    println!("    --upload                   Sign and upload the report to the Submission API");
    println!("    -h, --help                 Print this help and exit");
    println!();
    println!("ENVIRONMENT:");
    println!("    BENCHMARK_PROBE_KEY_PATH   Ed25519 key path (default: ~/.config/benchmark-probe/ed25519.pem)");
    println!("    BENCHMARK_PROBE_API_URL    Submission API base URL (default: {DEFAULT_API_URL})");
    println!();
    println!("EXAMPLES:");
    println!("    benchmark-probe --runtime mock");
    println!("    benchmark-probe --runtime mock --sign");
    println!(
        "    benchmark-probe --runtime llama_cpp --model qwen2.5-coder-32b-q4_k_m.gguf --upload"
    );
    println!("    benchmark-probe --runtime ollama --model qwen2.5-coder:32b");
}
