//! `canirunit suggest` — best-model suggestions from measured runs (Épico 2).
//!
//! Pure, deterministic ranking over a local JSON export of leaderboard runs.
//! No LLM anywhere in the recommendation path (AD-5): every number carries a
//! template-generated explanation stating how many runs back it, their
//! variance and where the runs came from.

pub mod confidence;
pub mod transfer;

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

pub use confidence::{confidence, source_weight, ConfidenceInputs, MatchTier};

/// One run entry, leaderboard-shaped (superset of GET /v1/leaderboard fields).
#[derive(Deserialize, Debug, Clone)]
pub struct RunEntry {
    pub run_id: String,
    pub gpu_model_id: String,
    pub model_release_id: String,
    #[serde(default)]
    pub recipe_id: Option<String>,
    #[serde(default = "default_source_class")]
    pub source_class: String,
    #[serde(default)]
    pub trust_score: Option<f64>,
    /// Age of the run in days at export time (filled by the API/harvester;
    /// 0 keeps the freshness factor at 1.0 for locally exported fixtures).
    #[serde(default)]
    pub age_days: Option<f64>,
    #[serde(default)]
    pub decode_tok_s: Option<f64>,
    #[serde(default)]
    pub seconds_per_clip: Option<f64>,
    #[serde(default)]
    pub frames_per_s: Option<f64>,
}

fn default_source_class() -> String {
    "measured_signed".to_string()
}

#[derive(Serialize, Debug, PartialEq)]
pub struct Suggestion {
    pub model_release_id: String,
    pub recipe_id: Option<String>,
    pub expected: f64,
    pub n_runs: usize,
    pub variance: f64,
    pub source_class: String,
    pub confidence: f64,
    pub explanation: String,
}

#[derive(Serialize, Debug, PartialEq)]
pub struct SuggestOutcome {
    pub match_class: String,
    pub gpu_model_id: String,
    pub task_metric: String,
    pub better: String,
    pub suggestions: Vec<Suggestion>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub explanation: Option<String>,
}

/// Direction of each supported task metric. Higher is better for throughput
/// metrics; lower is better for latency metrics.
pub(crate) fn metric_direction(metric: &str) -> Option<&'static str> {
    match metric {
        "decode_tok_s" | "prefill_tok_s" | "frames_per_s" | "it_per_s" => Some("higher"),
        "ttft_ms" | "seconds_per_clip" => Some("lower"),
        _ => None,
    }
}

pub(crate) fn metric_value(run: &RunEntry, metric: &str) -> Option<f64> {
    match metric {
        "decode_tok_s" => run.decode_tok_s,
        "seconds_per_clip" => run.seconds_per_clip,
        "frames_per_s" => run.frames_per_s,
        _ => None,
    }
}

pub fn suggest(gpu_model_id: &str, task_metric: &str, runs: &[RunEntry]) -> Result<SuggestOutcome, String> {
    let Some(better) = metric_direction(task_metric) else {
        return Err(format!(
            "unsupported task metric '{task_metric}' (supported: decode_tok_s, seconds_per_clip, frames_per_s)"
        ));
    };

    let mut groups: BTreeMap<(String, Option<String>), Vec<&RunEntry>> = BTreeMap::new();
    for run in runs {
        if run.gpu_model_id == gpu_model_id && metric_value(run, task_metric).is_some() {
            groups
                .entry((run.model_release_id.clone(), run.recipe_id.clone()))
                .or_default()
                .push(run);
        }
    }

    if groups.is_empty() {
        return Ok(SuggestOutcome {
            match_class: "unknown".to_string(),
            gpu_model_id: gpu_model_id.to_string(),
            task_metric: task_metric.to_string(),
            better: better.to_string(),
            suggestions: Vec::new(),
            explanation: Some(format!(
                "no measured runs for gpu '{gpu_model_id}' with metric '{task_metric}' in the corpus; \
                 be the first to publish a signed run (benchmark-probe) or a recipe cell"
            )),
        });
    }

    let mut suggestions: Vec<Suggestion> = groups
        .into_iter()
        .map(|((model_release_id, recipe_id), group)| {
            let weighted: Vec<(f64, f64)> = group
                .iter()
                .map(|run| {
                    let value = metric_value(run, task_metric).unwrap_or_default();
                    let weight = run.trust_score.unwrap_or(1.0).max(0.01);
                    (value, weight)
                })
                .collect();
            let total_weight: f64 = weighted.iter().map(|(_, w)| w).sum();
            let expected: f64 =
                weighted.iter().map(|(v, w)| v * w).sum::<f64>() / total_weight;
            let variance: f64 = weighted
                .iter()
                .map(|(v, w)| w * (v - expected) * (v - expected))
                .sum::<f64>()
                / total_weight;
            let source_class = strongest_class(&group);
            let n_runs = group.len();
            let age_days = group
                .iter()
                .map(|run| run.age_days.unwrap_or(0.0))
                .fold(0.0_f64, f64::max);
            let confidence_value = confidence(&ConfidenceInputs {
                source_class: source_class.clone(),
                n_runs,
                age_days,
                variance,
                mean: expected,
                match_tier: MatchTier::Exact,
            });
            let explanation = format!(
                "{n_runs} run(s) of {model_release_id}{} on {gpu_model_id}: expected \
                 {task_metric} {:.2} ({better} is better), weighted mean over runs with \
                 variance {:.2}; source: {source_class}",
                recipe_id
                    .as_ref()
                    .map(|id| format!(" (recipe {id})"))
                    .unwrap_or_default(),
                (expected * 100.0).round() / 100.0,
                (variance * 100.0).round() / 100.0,
            );
            Suggestion {
                model_release_id,
                recipe_id,
                expected: (expected * 100.0).round() / 100.0,
                n_runs,
                variance: (variance * 100.0).round() / 100.0,
                source_class: source_class.to_string(),
                confidence: confidence_value,
                explanation,
            }
        })
        .collect();

    suggestions.sort_by(|a, b| {
        let ordering = if better == "higher" {
            b.expected.partial_cmp(&a.expected)
        } else {
            a.expected.partial_cmp(&b.expected)
        };
        ordering.unwrap_or(std::cmp::Ordering::Equal)
    });

    Ok(SuggestOutcome {
        match_class: "exact_gpu".to_string(),
        gpu_model_id: gpu_model_id.to_string(),
        task_metric: task_metric.to_string(),
        better: better.to_string(),
        suggestions,
        explanation: None,
    })
}

/// The strongest source class in a group decides how the whole group is
/// labeled (a single signed run outranks any amount of harvested rows).
fn strongest_class(group: &[&RunEntry]) -> String {
    let mut best = "derived".to_string();
    let mut best_weight = -1.0;
    for run in group {
        let weight = source_weight(&run.source_class);
        if weight > best_weight {
            best_weight = weight;
            best = run.source_class.clone();
        }
    }
    best
}

/// Full suggestion flow with cross-hardware transfer (Story 3.2): exact runs
/// always win; only when the GPU has no runs does the roofline transfer kick
/// in, labeled `derived` with the anchor and factor named in the explanation.
pub fn suggest_with_transfer(
    gpu_model_id: &str,
    task_metric: &str,
    runs: &[RunEntry],
    specs: Option<&std::collections::BTreeMap<String, transfer::GpuTransferSpec>>,
) -> Result<SuggestOutcome, String> {
    let exact = suggest(gpu_model_id, task_metric, runs)?;
    if exact.match_class == "exact_gpu" {
        return Ok(exact);
    }
    let Some(specs) = specs else {
        return Ok(exact);
    };
    let Some(target_spec) = specs.get(gpu_model_id) else {
        return Ok(exact);
    };
    let transferred = transfer::transfer_suggestions(gpu_model_id, target_spec, task_metric, runs, specs);
    if transferred.is_empty() {
        return Ok(exact);
    }
    let match_class = match transferred[0].match_tier {
        confidence::MatchTier::SameFamily => "same_arch_family".to_string(),
        _ => "roofline_transfer".to_string(),
    };
    Ok(SuggestOutcome {
        match_class,
        gpu_model_id: gpu_model_id.to_string(),
        task_metric: task_metric.to_string(),
        better: exact.better,
        suggestions: transferred
            .into_iter()
            .map(|entry| entry.suggestion)
            .collect(),
        explanation: Some(format!(
            "no runs measured on {gpu_model_id}; numbers transferred by roofline ratio from \
             anchor GPUs — always derived, never measured on this machine"
        )),
    })
}
