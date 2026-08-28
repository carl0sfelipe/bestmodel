use std::process::exit;

use canirunit::transfer::GpuTransferSpec;
use canirunit::{suggest_with_transfer, RunEntry};
use std::collections::BTreeMap;

const VERSION: &str = env!("CARGO_PKG_VERSION");

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

struct CliArgs {
    gpu: String,
    task: String,
    runs_path: String,
    gpus_path: Option<String>,
}

fn run(cli: &CliArgs) -> Result<(), i32> {
    let runs_raw = std::fs::read_to_string(&cli.runs_path).map_err(|err| {
        eprintln!("error: unable to read runs file '{}': {err}", cli.runs_path);
        1
    })?;
    let runs: Vec<RunEntry> = serde_json::from_str(&runs_raw).map_err(|err| {
        eprintln!("error: runs file is not a JSON array of run entries: {err}");
        1
    })?;
    let specs: Option<BTreeMap<String, GpuTransferSpec>> = cli.gpus_path.as_ref().map(|path| {
        let raw = std::fs::read_to_string(path)
            .unwrap_or_else(|err| panic!("unable to read gpu specs '{path}': {err}"));
        let list: Vec<GpuTransferSpec> = serde_json::from_str(&raw)
            .unwrap_or_else(|err| panic!("gpu specs '{path}' is not valid: {err}"));
        list.into_iter().map(|spec| (spec.id.clone(), spec)).collect()
    });
    let outcome = suggest_with_transfer(&cli.gpu, &cli.task, &runs, specs.as_ref()).map_err(|message| {
        eprintln!("error: {message}");
        2
    })?;
    println!("{}", serde_json::to_string_pretty(&outcome).expect("serialize outcome"));
    if outcome.suggestions.is_empty() {
        return Err(3);
    }
    Ok(())
}

fn parse_args(raw_args: &[String]) -> Result<Option<CliArgs>, String> {
    let mut gpu: Option<String> = None;
    let mut task: Option<String> = None;
    let mut runs_path: Option<String> = None;
    let mut gpus_path: Option<String> = None;

    let mut index = 0;
    while index < raw_args.len() {
        let raw = &raw_args[index];
        if raw == "suggest" {
            index += 1;
            continue;
        }
        if raw == "--help" || raw == "-h" {
            return Ok(None);
        }
        let (flag, inline_value) = match raw.split_once('=') {
            Some((name, value)) => (name.to_string(), Some(value.to_string())),
            None => (raw.clone(), None),
        };
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
            "--gpu" => gpu = Some(take_value(&mut index)?),
            "--task" => task = Some(take_value(&mut index)?),
            "--runs" => runs_path = Some(take_value(&mut index)?),
            "--gpus" => gpus_path = Some(take_value(&mut index)?),
            other => return Err(format!("unknown argument '{other}'")),
        }
        index += 1;
    }

    let gpu = gpu.ok_or_else(|| "missing required argument '--gpu <gpu_model_id>'".to_string())?;
    let task = task.ok_or_else(|| {
        "missing required argument '--task <metric>' (decode_tok_s, seconds_per_clip, frames_per_s)".to_string()
    })?;
    let runs_path =
        runs_path.ok_or_else(|| "missing required argument '--runs <runs.json>'".to_string())?;
    Ok(Some(CliArgs { gpu, task, runs_path, gpus_path }))
}

fn print_usage() {
    println!("canirunit {VERSION}");
    println!();
    println!("Suggest the best model for a GPU from measured runs (deterministic, no LLM).");
    println!();
    println!("USAGE:");
    println!("    canirunit suggest --gpu <gpu_model_id> --task <metric> --runs <runs.json> [--gpus gpu_transfer_specs.json]");
    println!();
    println!("TASK METRICS:");
    println!("    decode_tok_s       LLM decode throughput (higher is better)");
    println!("    seconds_per_clip   video clip wall time (lower is better)");
    println!("    frames_per_s       video frames per second (higher is better)");
    println!();
    println!("    --gpus <specs.json>  Enable cross-hardware transfer when the GPU has no");
    println!("                        runs (same_arch_family / roofline_transfer, always derived);");
    println!("                        see gpu_transfer_specs.json for the format");
    println!();
    println!("EXIT CODES:");
    println!("    0 suggestions produced; 3 no runs for this GPU (match_class unknown)");
}
