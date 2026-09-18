use std::collections::BTreeMap;
use std::process::exit;

use canirunit::transfer::GpuTransferSpec;
use canirunit::{closest_rig_ids, rig_ids, runs_from_pool, suggest_with_transfer, PoolFile, RunEntry};

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn main() {
    let raw_args: Vec<String> = std::env::args().skip(1).collect();
    match parse_args(&raw_args) {
        Ok(None) => {
            print_usage();
            exit(0);
        }
        Ok(Some(mode)) => {
            if let Err(code) = run(mode) {
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

enum Mode {
    Suggest {
        gpu: String,
        task: String,
        runs_path: String,
        gpus_path: Option<String>,
    },
    Rigs {
        runs_path: String,
        filter: Option<String>,
    },
}

fn run(mode: Mode) -> Result<(), i32> {
    match mode {
        Mode::Suggest { gpu, task, runs_path, gpus_path } => {
            let (runs, _) = load_runs(&runs_path)?;
            let specs: Option<BTreeMap<String, GpuTransferSpec>> = gpus_path.as_ref().map(|path| {
                let raw = std::fs::read_to_string(path)
                    .unwrap_or_else(|err| panic!("unable to read gpu specs '{path}': {err}"));
                let list: Vec<GpuTransferSpec> = serde_json::from_str(&raw)
                    .unwrap_or_else(|err| panic!("gpu specs '{path}' is not valid: {err}"));
                list.into_iter().map(|spec| (spec.id.clone(), spec)).collect()
            });
            let outcome =
                suggest_with_transfer(&gpu, &task, &runs, specs.as_ref()).map_err(|message| {
                    eprintln!("error: {message}");
                    2
                })?;
            println!("{}", serde_json::to_string_pretty(&outcome).expect("serialize outcome"));
            if outcome.suggestions.is_empty() {
                let closest = closest_rig_ids(&runs, &gpu, 5);
                if !closest.is_empty() {
                    eprintln!(
                        "no data for '{gpu}' — closest rig ids in this corpus: {}",
                        closest.join(", ")
                    );
                } else {
                    eprintln!(
                        "no data for '{gpu}' and nothing similar — list what the corpus knows: canirunit rigs --runs {runs_path}"
                    );
                }
                return Err(3);
            }
            Ok(())
        }
        Mode::Rigs { runs_path, filter } => {
            let (runs, _) = load_runs(&runs_path)?;
            let ids = match &filter {
                Some(needle) => rig_ids(&runs)
                    .into_iter()
                    .filter(|id| id.to_ascii_lowercase().contains(&needle.to_ascii_lowercase()))
                    .collect::<Vec<_>>(),
                None => rig_ids(&runs),
            };
            if ids.is_empty() {
                let closest = closest_rig_ids(&runs, filter.as_deref().unwrap_or_default(), 5);
                if closest.is_empty() {
                    eprintln!(
                        "no rig id matches '{}' in '{}' — drop --filter to list them all",
                        filter.unwrap_or_default(),
                        runs_path
                    );
                } else {
                    eprintln!(
                        "no rig id contains '{}' — closest by tokens: {} (or drop --filter to list them all)",
                        filter.unwrap_or_default(),
                        closest.join(", ")
                    );
                }
                return Err(3);
            }
            for id in ids {
                println!("{id}");
            }
            Ok(())
        }
    }
}

/// Loads a runs corpus in either accepted shape (leaderboard run-entry
/// array, or derived pool snapshot). Prints its own errors; the bool-ish
/// second element carries the pool note when that shape was used.
fn load_runs(runs_path: &str) -> Result<(Vec<RunEntry>, Option<(String, usize)>), i32> {
    let runs_raw = std::fs::read_to_string(runs_path).map_err(|err| {
        eprintln!("error: unable to read runs file '{runs_path}': {err}");
        1
    })?;
    // Two accepted shapes: a JSON array of leaderboard run entries (the
    // designed export), or a derived pool snapshot ({snapshotAt, cells}) —
    // in-repo, offline, labeled `harvested`.
    match serde_json::from_str::<Vec<RunEntry>>(&runs_raw) {
        Ok(runs) => Ok((runs, None)),
        Err(_) => {
            let pool: PoolFile = serde_json::from_str(&runs_raw).map_err(|err| {
                eprintln!(
                    "error: runs file is neither a JSON array of run entries nor a pool snapshot: {err}"
                );
                1
            })?;
            let count = pool.cells.len();
            let snapshot = pool.snapshot_at.clone();
            eprintln!(
                "note: loaded pool snapshot {snapshot} ({count} cells) — every entry is source_class=harvested (community medians, not signed runs)"
            );
            Ok((runs_from_pool(&pool), Some((snapshot, count))))
        }
    }
}

fn parse_args(raw_args: &[String]) -> Result<Option<Mode>, String> {
    let mut mode: Option<&str> = None;
    let mut gpu: Option<String> = None;
    let mut task: Option<String> = None;
    let mut runs_path: Option<String> = None;
    let mut gpus_path: Option<String> = None;
    let mut filter: Option<String> = None;

    let mut index = 0;
    while index < raw_args.len() {
        let raw = &raw_args[index];
        if raw == "suggest" || raw == "rigs" {
            mode = Some(raw);
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
            "--filter" => filter = Some(take_value(&mut index)?),
            other => return Err(format!("unknown argument '{other}'")),
        }
        index += 1;
    }

    let runs_path = runs_path
        .ok_or_else(|| "missing required argument '--runs <runs.json>'".to_string())?;

    match mode.unwrap_or("suggest") {
        "rigs" => Ok(Some(Mode::Rigs { runs_path, filter })),
        _ => {
            let gpu =
                gpu.ok_or_else(|| "missing required argument '--gpu <gpu_model_id>'".to_string())?;
            let task = task.ok_or_else(|| {
                "missing required argument '--task <metric>' (decode_tok_s, seconds_per_clip, frames_per_s)".to_string()
            })?;
            Ok(Some(Mode::Suggest { gpu, task, runs_path, gpus_path }))
        }
    }
}

fn print_usage() {
    println!("canirunit {VERSION}");
    println!();
    println!("Suggest the best model for a GPU from measured runs (deterministic, no LLM).");
    println!();
    println!("USAGE:");
    println!("    canirunit suggest --gpu <gpu_model_id> --task <metric> --runs <runs.json> [--gpus gpu_transfer_specs.json]");
    println!("    canirunit rigs --runs <runs.json> [--filter <substring>]");
    println!();
    println!("    --runs accepts either a leaderboard run-entry export (JSON array)");
    println!("    or the in-repo derived pool snapshot apps/web/data/derived/pool.json");
    println!("    ({{snapshotAt, cells}} — entries load as source_class=harvested).");
    println!("    'rigs' lists the GPU ids the corpus actually knows (this is how you");
    println!("    map detected hardware, e.g. 'NVIDIA GeForce RTX 3090' -> rtx-3090-24gb).");
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
