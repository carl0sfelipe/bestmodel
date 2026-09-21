use std::collections::BTreeMap;
use std::process::exit;

use canirunit::transfer::GpuTransferSpec;
use canirunit::{closest_rig_ids, rig_ids, runs_from_pool, suggest_with_transfer, PoolFile, RunEntry};
use clap::{Parser, Subcommand};

// S37: clap tree over the existing rigs/suggest subcommands, identical flags.
#[derive(Debug, Parser)]
#[command(
    name = "canirunit",
    version,
    propagate_version = true,
    arg_required_else_help = true,
    about = "Suggest the best model for a GPU from measured runs (deterministic, no LLM).",
    after_help = "--runs accepts either a leaderboard run-entry export (JSON array) or the in-repo derived pool snapshot apps/web/data/derived/pool.json ({snapshotAt, cells} — entries load as source_class=harvested).
'rigs' lists the GPU ids the corpus actually knows (this is how you map detected hardware, e.g. 'NVIDIA GeForce RTX 3090' -> rtx-3090-24gb).

TASK METRICS:
    decode_tok_s       LLM decode throughput (higher is better)
    seconds_per_clip   video clip wall time (lower is better)
    frames_per_s       video frames per second (higher is better)

--gpus <specs.json> enables cross-hardware transfer when the GPU has no runs (same_arch_family / roofline_transfer, always derived); see gpu_transfer_specs.json for the format.

SEE ALSO:
    benchmark-probe - measure your hardware and capture signed runs.

EXIT CODES:
    0 suggestions produced · 2 usage error · 3 no runs for this GPU (match_class unknown)"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Rank models for a GPU from the measured corpus
    Suggest {
        /// GPU / rig model id (e.g. rtx-3090-24gb)
        #[arg(long)]
        gpu: String,
        /// Metric: decode_tok_s, seconds_per_clip or frames_per_s
        #[arg(long)]
        task: String,
        /// Runs JSON: run-entry array or derived pool snapshot
        #[arg(long)]
        runs: String,
        /// GPU transfer specs (enables cross-hardware transfer)
        #[arg(long)]
        gpus: Option<String>,
    },
    /// List the rig ids the corpus actually knows
    Rigs {
        /// Runs JSON: run-entry array or derived pool snapshot
        #[arg(long)]
        runs: String,
        /// Substring filter on rig ids
        #[arg(long)]
        filter: Option<String>,
    },
}

fn main() {
    let cli = Cli::parse();
    let mode = match cli.command {
        Command::Suggest { gpu, task, runs, gpus } => {
            Mode::Suggest { gpu, task, runs_path: runs, gpus_path: gpus }
        }
        Command::Rigs { runs, filter } => Mode::Rigs { runs_path: runs, filter },
    };
    if let Err(code) = run(mode) {
        exit(code);
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
