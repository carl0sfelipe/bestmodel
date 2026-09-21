//! S39 (`plan`): ranked model candidates for a target GPU from the catalog
//! (SOTA) + predictors — the loop's entry, realizing backlog A9. Every row
//! declares its basis on the honesty ladder:
//!
//!   measured     pool median on THIS rig with n>=3
//!   reported     pool cell on this rig with n 1-2
//!   extrapolated bandwidth-scaled from a measured cell on another rig
//!                (the site's declared method — llms.txt honesty ladder)
//!   formula      roofline: effective bandwidth / weight bytes
//!
//! Constants are PORTED, not invented: U_RUNTIME/U_QUANT come from
//! packages/roofline-kernel/src/estimate_decode_throughput.py and the Q4_K_M
//! weight_bits (4.5) from infra/seed/quantization_profiles.json. A candidate
//! with no basis never renders. No number is ever presented as measured
//! unless it is a pool median.

use serde::Deserialize;
use std::path::Path;

pub const MIN_RUNS_MEASURED: usize = 3; // same cutoff the site's engine uses
const U_RUNTIME: f64 = 0.8; // roofline-kernel estimate_decode_throughput.py
const U_QUANT: f64 = 0.9; // roofline-kernel estimate_decode_throughput.py
const Q4_K_M_WEIGHT_BITS: f64 = 4.5; // infra/seed/quantization_profiles.json
const DEFAULT_QUANT: &str = "q-gguf-q4-k-m";

/// Default data locations (repo-root CWD, the documented agent position).
/// Every input degrades gracefully: missing pool → extrapolated/formula only;
/// missing catalog → pool-only candidates.
pub const DEFAULT_POOL_PATH: &str = "apps/web/data/derived/pool.json";
pub const DEFAULT_MODELS_PATH: &str = "apps/web/data/derived/models.json";
pub const DEFAULT_HARDWARE_PATH: &str = "apps/web/data/derived/hardware.json";

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PoolFile {
    #[serde(default)]
    cells: Vec<PoolCell>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PoolCell {
    rig_key: String,
    model_slug: String,
    #[serde(default)]
    tok_s_out_median: Option<f64>,
    n: usize,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ModelsFile {
    #[serde(default)]
    models: Vec<CatalogModel>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CatalogModel {
    slug: String,
    #[serde(default)]
    display_name: Option<String>,
    #[serde(default)]
    params_b: Option<f64>,
    #[serde(default)]
    active_params_b: Option<f64>,
    #[serde(default)]
    is_moe: bool,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    median_tok_s: Option<f64>,
    #[serde(default)]
    eval_score: Option<EvalScore>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct EvalScore {
    #[serde(default)]
    score: Option<f64>,
    #[serde(default)]
    quant: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct HardwareFile {
    #[serde(default)]
    rigs: Vec<Rig>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Rig {
    key: String,
    #[serde(default)]
    mem_gb: Option<f64>,
    #[serde(default)]
    #[serde(rename = "bandwidthGBs")]
    bandwidth_gbs: Option<f64>,
}

#[derive(Debug, serde::Serialize)]
pub struct PlanCandidate {
    pub model_release_id: String,
    pub quant: String,
    /// predicted/observed decode tok/s — carries `basis`; never a guess
    pub expected: f64,
    pub basis: String,
    pub source_class: String,
    pub explanation: String,
}

#[derive(Debug, serde::Serialize)]
pub struct PlanOutcome {
    pub gpu: String,
    pub task: String,
    pub candidates: Vec<PlanCandidate>,
}

pub struct PlanError {
    pub message: String,
    pub closest_rig_ids: Vec<String>,
}

fn read_json<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<T, String> {
    let raw = std::fs::read_to_string(path)
        .map_err(|e| format!("unable to read {}: {e}", path.display()))?;
    serde_json::from_str(&raw).map_err(|e| format!("{} is not valid: {e}", path.display()))
}

fn load_optional<T: for<'de> Deserialize<'de>>(path: &str) -> Option<T> {
    // Offline fallback: a missing input removes data sources, it never
    // fabricates rows.
    read_json::<T>(Path::new(path)).ok()
}

/// Ranked plan for `--gpu <rig-id>`. Basis ladder first (measured beats
/// formula), then expected throughput, then catalog SOTA score.
pub fn plan(gpu: &str, limit: usize) -> Result<PlanOutcome, PlanError> {
    let pool: Option<PoolFile> = load_optional(DEFAULT_POOL_PATH);
    let models: Option<ModelsFile> = load_optional(DEFAULT_MODELS_PATH);
    let hardware: Option<HardwareFile> = load_optional(DEFAULT_HARDWARE_PATH);

    let rig = hardware.as_ref().and_then(|h| h.rigs.iter().find(|r| r.key == gpu));
    let rig_bw = rig.and_then(|r| r.bandwidth_gbs);
    let rig_mem = rig.and_then(|r| r.mem_gb);

    if rig.is_none() {
        // Unknown GPU: say so and suggest neighbours — never a guessed number.
        let closest = pool
            .as_ref()
            .map(|p| closest_rigs(&p.cells, gpu))
            .unwrap_or_default();
        return Err(PlanError {
            message: format!(
                "unknown gpu '{gpu}' — it is not in the hardware snapshot{}",
                if closest.is_empty() {
                    String::new()
                } else {
                    format!("; closest rig ids: {}", closest.join(", "))
                }
            ),
            closest_rig_ids: closest,
        });
    }

    let mut candidates: Vec<PlanCandidate> = Vec::new();

    // 1-2. measured / reported: pool cells on THIS rig (best cell per model).
    if let Some(pool) = &pool {
        let mut by_slug: std::collections::HashMap<&str, &PoolCell> = std::collections::HashMap::new();
        for cell in pool.cells.iter().filter(|c| c.rig_key == gpu) {
            if cell.tok_s_out_median.is_none() {
                continue;
            }
            match by_slug.get(cell.model_slug.as_str()) {
                Some(prev) if prev.n >= cell.n => {}
                _ => {
                    by_slug.insert(cell.model_slug.as_str(), cell);
                }
            }
        }
        for cell in by_slug.into_values() {
            let expected = cell.tok_s_out_median.unwrap();
            let basis = if cell.n >= MIN_RUNS_MEASURED { "measured" } else { "reported" };
            candidates.push(PlanCandidate {
                model_release_id: cell.model_slug.clone(),
                quant: DEFAULT_QUANT.to_string(),
                expected,
                basis: basis.to_string(),
                source_class: "harvested".to_string(),
                explanation: format!(
                    "pool median on {gpu} (n={}) — community medians, not a signed run",
                    cell.n
                ),
            });
        }
    }

    // Catalog models: extrapolated (bandwidth-scaled from another rig) or
    // formula (roofline) — plus the SOTA ordering signal.
    let catalog: Vec<&CatalogModel> = models
        .as_ref()
        .map(|m| m.models.iter().collect())
        .unwrap_or_default();
    let measured_slugs: std::collections::HashSet<String> =
        candidates.iter().map(|c| c.model_release_id.clone()).collect();

    for model in catalog.iter() {
        if measured_slugs.contains(model.slug.as_str()) {
            continue; // already ranked from this rig's own cells
        }
        let Some(params) = model.params_b else { continue };
        let active = if model.is_moe { model.active_params_b.unwrap_or(params) } else { params };
        if active <= 0.0 {
            continue;
        }

        // 3. extrapolated: bandwidth-scale the model's best measured median
        //    from another rig whose bandwidth is known (site-declared method).
        let anchor = pool.as_ref().and_then(|p| {
            p.cells
                .iter()
                .filter(|c| c.model_slug == model.slug && c.tok_s_out_median.is_some())
                .filter_map(|c| {
                    let bw = hardware
                        .as_ref()
                        .and_then(|h| h.rigs.iter().find(|r| r.key == c.rig_key))
                        .and_then(|r| r.bandwidth_gbs)?;
                    Some((c, bw))
                })
                .min_by_key(|(c, _)| c.rig_key.clone())
        });
        if let (Some((cell, anchor_bw)), Some(target_bw), Some(target_mem)) =
            (anchor, rig_bw, rig_mem)
        {
            let scale = target_bw / anchor_bw;
            // Fit gate at the DEFAULT_QUANT footprint (formula side).
            let weight_gib = params * Q4_K_M_WEIGHT_BITS / 8.0;
            if weight_gib <= target_mem {
                let expected = cell.tok_s_out_median.unwrap() * scale;
                candidates.push(PlanCandidate {
                    model_release_id: model.slug.clone(),
                    quant: DEFAULT_QUANT.to_string(),
                    expected,
                    basis: "extrapolated".to_string(),
                    source_class: "bandwidth_transfer".to_string(),
                    explanation: format!(
                        "measured {} tok/s on {} bandwidth-scaled {}/{} (GiB/s) — derived, never 'measured on this machine'",
                        cell.tok_s_out_median.unwrap_or(0.0),
                        cell.rig_key,
                        anchor_bw,
                        target_bw
                    ),
                });
                continue;
            }
        }

        // 4. formula: roofline decode — effective bandwidth / weight bytes.
        if let Some(target_bw) = rig_bw {
            let effective_bytes_per_s = target_bw * 1e9 * U_RUNTIME * U_QUANT;
            let weight_bytes = active * 1e9 * Q4_K_M_WEIGHT_BITS / 8.0;
            let expected = effective_bytes_per_s / weight_bytes;
            let fits = rig_mem.map(|m| params * Q4_K_M_WEIGHT_BITS / 8.0 <= m).unwrap_or(false);
            if fits {
                candidates.push(PlanCandidate {
                    model_release_id: model.slug.clone(),
                    quant: DEFAULT_QUANT.to_string(),
                    expected,
                    basis: "formula".to_string(),
                    source_class: "catalog".to_string(),
                    explanation: format!(
                        "roofline formula: {} GiB/s x U_runtime {} x U_quant {} over {}B active weights at {} bits (kernel: packages/roofline-kernel)",
                        target_bw, U_RUNTIME, U_QUANT, active, Q4_K_M_WEIGHT_BITS
                    ),
                });
            }
        }
    }

    // Rank: basis ladder first, then expected, then SOTA eval score.
    let sota = |c: &PlanCandidate| {
        catalog
            .iter()
            .find(|m| m.slug == c.model_release_id)
            .and_then(|m| m.eval_score.as_ref().and_then(|e| e.score))
            .unwrap_or(0.0)
    };
    let basis_rank = |b: &str| match b {
        "measured" => 0,
        "reported" => 1,
        "extrapolated" => 2,
        _ => 3,
    };
    candidates.sort_by(|a, b| {
        basis_rank(&a.basis)
            .cmp(&basis_rank(&b.basis))
            .then(b.expected.partial_cmp(&a.expected).unwrap_or(std::cmp::Ordering::Equal))
            .then(sota(b).partial_cmp(&sota(a)).unwrap_or(std::cmp::Ordering::Equal))
    });
    candidates.truncate(limit);

    Ok(PlanOutcome {
        gpu: gpu.to_string(),
        task: "decode_tok_s".to_string(),
        candidates,
    })
}

/// Closest known rig ids by shared tokens (mirror of canirunit's hint).
fn closest_rigs(cells: &[PoolCell], gpu: &str) -> Vec<String> {
    let mut ids: Vec<String> = cells.iter().map(|c| c.rig_key.clone()).collect();
    ids.sort();
    ids.dedup();
    let needle: Vec<char> = gpu.chars().filter(|c| c.is_ascii_alphanumeric()).collect();
    let score = |id: &str| -> usize {
        let hay: Vec<char> = id.chars().filter(|c| c.is_ascii_alphanumeric()).collect();
        needle.iter().filter(|c| hay.contains(c)).count()
    };
    let mut ranked: Vec<(usize, String)> = ids.into_iter().map(|id| (score(&id), id)).collect();
    ranked.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
    ranked.truncate(5);
    ranked.into_iter().map(|(_, id)| id).collect()
}
