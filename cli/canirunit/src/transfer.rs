//! Cross-hardware transfer for `canirunit suggest` (Épico 3, Story 3.2).
//!
//! When the corpus has no run measured on the requested GPU, a suggestion can
//! be TRANSFERRED from an anchor GPU that has runs for the same
//! model+recipe. For compute-bound diffusion workloads the estimator's
//! calibration constants (attention fraction, utilization) cancel in the
//! ratio, so the transfer factor is exact roofline algebra:
//!
//! ```text
//! eff(gpu)     = fp16_tflops * (2.0 if native fp8 else 1.0)
//! time_factor  = eff(anchor) / eff(target)     // slower target -> bigger time
//! rate_factor  = 1 / time_factor
//! expected_t   = expected_anchor * factor      // direction-aware
//! variance_t   = variance_anchor * factor^2
//! ```
//!
//! The fp8 doubling assumes each GPU runs its best available weight path
//! (fp8 where the silicon supports it, as the simulator does). Tier:
//! same architecture family -> `same_arch_family` (0.7), different family ->
//! `roofline_transfer` (0.5) — both carry `source_class: derived` and an
//! explanation that names the anchor and the numeric factor. A transferred
//! number is NEVER a measurement.

use std::collections::BTreeMap;

use serde::Deserialize;

use crate::confidence::{confidence, ConfidenceInputs, MatchTier};
use crate::{metric_direction, metric_value, RunEntry, Suggestion};

#[derive(Deserialize, Debug, Clone)]
pub struct GpuTransferSpec {
    pub id: String,
    pub arch_family: String,
    pub fp16_tflops: f64,
    pub memory_bandwidth_gib_s: f64,
    pub has_native_fp8: bool,
}

pub fn effective_tflops(spec: &GpuTransferSpec) -> f64 {
    spec.fp16_tflops * if spec.has_native_fp8 { 2.0 } else { 1.0 }
}

/// Time-domain factor: how many times slower the target is than the anchor.
pub fn time_factor(anchor: &GpuTransferSpec, target: &GpuTransferSpec) -> f64 {
    effective_tflops(anchor) / effective_tflops(target)
}

pub fn transfer_suggestions(
    target_id: &str,
    target_spec: &GpuTransferSpec,
    task_metric: &str,
    runs: &[RunEntry],
    specs: &BTreeMap<String, GpuTransferSpec>,
) -> Vec<TransferredSuggestion> {
    let better = match metric_direction(task_metric) {
        Some(direction) => direction,
        None => return Vec::new(),
    };

    // Anchor groups: runs of OTHER (spec-known) GPUs with this metric.
    let mut groups: BTreeMap<(String, Option<String>, String), Vec<&RunEntry>> = BTreeMap::new();
    for run in runs {
        if run.gpu_model_id == target_id || metric_value(run, task_metric).is_none() {
            continue;
        }
        if !specs.contains_key(&run.gpu_model_id) {
            continue;
        }
        groups
            .entry((run.model_release_id.clone(), run.recipe_id.clone(), run.gpu_model_id.clone()))
            .or_default()
            .push(run);
    }
    if groups.is_empty() {
        return Vec::new();
    }

    // One anchor per (model, recipe): strongest class, then most runs, then
    // alphabetical gpu id — fully deterministic.
    let mut best_anchor: BTreeMap<(String, Option<String>), (&str, &GpuTransferSpec, Vec<&RunEntry>)> =
        BTreeMap::new();
    for ((model, recipe, gpu_id), group) in &groups {
        let anchor_spec = &specs[gpu_id];
        let key = (model.clone(), recipe.clone());
        let better_anchor = match best_anchor.get(&key) {
            None => true,
            Some((_, existing_spec, existing_group)) => {
                let class_rank = |runs: &Vec<&RunEntry>| {
                    runs.iter()
                        .map(|r| crate::confidence::source_weight(&r.source_class))
                        .fold(0.0_f64, f64::max)
                };
                let incumbent = (
                    class_rank(existing_group),
                    existing_group.len(),
                    existing_spec.id.as_str(),
                );
                let challenger = (class_rank(group), group.len(), gpu_id.as_str());
                challenger > incumbent
            }
        };
        if better_anchor {
            best_anchor.insert(key, (gpu_id, anchor_spec, group.clone()));
        }
    }

    let mut suggestions: Vec<TransferredSuggestion> = Vec::new();
    for ((model_release_id, recipe_id), (anchor_gpu_id, anchor_spec, group)) in best_anchor {
        let anchor_expected: f64 = {
            let weighted: Vec<(f64, f64)> = group
                .iter()
                .map(|run| {
                    (
                        metric_value(run, task_metric).unwrap_or_default(),
                        run.trust_score.unwrap_or(1.0).max(0.01),
                    )
                })
                .collect();
            let total: f64 = weighted.iter().map(|(_, w)| w).sum();
            weighted.iter().map(|(v, w)| v * w).sum::<f64>() / total
        };
        let factor = time_factor(anchor_spec, target_spec);
        let expected = if better == "lower" {
            anchor_expected * factor
        } else {
            anchor_expected / factor
        };
        let variance = {
            let weighted: Vec<(f64, f64)> = group
                .iter()
                .map(|run| {
                    (
                        metric_value(run, task_metric).unwrap_or_default(),
                        run.trust_score.unwrap_or(1.0).max(0.01),
                    )
                })
                .collect();
            let total: f64 = weighted.iter().map(|(_, w)| w).sum();
            let spread: f64 = weighted
                .iter()
                .map(|(v, w)| w * (v - anchor_expected) * (v - anchor_expected))
                .sum::<f64>()
                / total;
            spread * factor * factor
        };
        let n_runs = group.len();
        let tier = if anchor_spec.arch_family == target_spec.arch_family {
            MatchTier::SameFamily
        } else {
            MatchTier::Roofline
        };
        let confidence_value = confidence(&ConfidenceInputs {
            source_class: "derived".to_string(),
            n_runs,
            age_days: group
                .iter()
                .map(|run| run.age_days.unwrap_or(0.0))
                .fold(0.0_f64, f64::max),
            variance,
            mean: expected,
            match_tier: tier,
        });
        let explanation = format!(
            "derived from {n_runs} run(s) on anchor {anchor_gpu_id} (recipe {}): expected \
             {task_metric} {:.2} on {target_id} via roofline transfer factor {:.3}x (anchor \
             {:.2} vs target {:.2} effective TFLOPS, {} family); NOT measured on this GPU",
            recipe_id
                .as_ref()
                .map(|id| id.as_str())
                .unwrap_or("no-recipe"),
            (expected * 100.0).round() / 100.0,
            factor,
            effective_tflops(anchor_spec),
            effective_tflops(target_spec),
            if anchor_spec.arch_family == target_spec.arch_family {
                "same architecture"
            } else {
                "different architecture"
            },
        );
        suggestions.push(TransferredSuggestion {
            suggestion: Suggestion {
                model_release_id,
                recipe_id,
                expected: (expected * 100.0).round() / 100.0,
                n_runs,
                variance: (variance * 100.0).round() / 100.0,
                source_class: "derived".to_string(),
                confidence: confidence_value,
                explanation,
            },
            anchor_gpu_id: anchor_gpu_id.to_string(),
            match_tier: tier,
        });
    }

    suggestions.sort_by(|a, b| {
        let ordering = if better == "higher" {
            b.suggestion.expected.partial_cmp(&a.suggestion.expected)
        } else {
            a.suggestion.expected.partial_cmp(&b.suggestion.expected)
        };
        ordering.unwrap_or(std::cmp::Ordering::Equal)
    });
    suggestions
}

#[derive(Debug)]
pub struct TransferredSuggestion {
    pub suggestion: Suggestion,
    pub anchor_gpu_id: String,
    pub match_tier: MatchTier,
}

