//! Confidence function (Story 2.3, AD-5: pure, documented, no LLM).
//!
//! Every factor is declared below with its source; the properties are pinned
//! by property-style tests in `tests/confidence_property_test.rs`.
//!
//! ```text
//! confidence = clamp01(base * (0.4 + 0.6 * n_bonus) * fresh * var_pen) * tier
//! ```
//!
//! - `base`       — source-class weight table (PRD FR-3): measured_signed 0.9,
//!                  reported 0.6, harvested 0.4, derived 0.4, unknown 0.3.
//! - `n_bonus`    — 1 − e^(−n/3): saturation at ~3 independent runs; before
//!                  that only 40% of the base survives (single-run guesses are
//!                  weak evidence by design).
//! - `fresh`      — e^(−age_days/180): a run loses ~45% of its freshness
//!                  factor in 180 days (half-life ≈ 125 days).
//! - `var_pen`    — 1 − min(cv, 0.5) where cv = variance/mean; disagreements
//!                  above half the mean are clamped (max 50% penalty). A mean
//!                  ≤ 0 applies the full clamp (conservative).
//! - `tier`       — hardware match: exact 1.0, same family 0.7, roofline
//!                  transfer 0.5.

/// Canonical ordering of source classes by evidential strength (FR-3):
/// a signed measurement beats a community report beats harvested data.
pub const SOURCE_WEIGHT_ORDER: [&str; 4] = [
    "measured_signed",
    "reported",
    "harvested",
    "derived",
];

/// Source-class base weights (documented table; do not tune ad hoc).
pub fn source_weight(source_class: &str) -> f64 {
    match source_class {
        "measured_signed" => 0.9,
        "reported" => 0.6,
        "harvested" => 0.4,
        "derived" => 0.4,
        _ => 0.3,
    }
}

/// Hardware match tier for the suggestion (exact GPU vs transferred).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MatchTier {
    Exact,
    SameFamily,
    Roofline,
}

impl MatchTier {
    pub fn factor(&self) -> f64 {
        match self {
            MatchTier::Exact => 1.0,
            MatchTier::SameFamily => 0.7,
            MatchTier::Roofline => 0.5,
        }
    }
}

pub struct ConfidenceInputs {
    pub source_class: String,
    pub n_runs: usize,
    pub age_days: f64,
    pub variance: f64,
    pub mean: f64,
    pub match_tier: MatchTier,
}

pub fn confidence(inputs: &ConfidenceInputs) -> f64 {
    let base = source_weight(&inputs.source_class);
    let n_bonus = 1.0 - (-(inputs.n_runs as f64) / 3.0).exp();
    let fresh = (-(inputs.age_days.max(0.0)) / 180.0).exp();
    let coefficient_of_variation = if inputs.mean > 0.0 {
        inputs.variance.max(0.0) / inputs.mean
    } else {
        0.5
    };
    let var_pen = 1.0 - coefficient_of_variation.min(0.5);
    let raw = base * (0.4 + 0.6 * n_bonus) * fresh * var_pen;
    (raw.clamp(0.0, 1.0) * inputs.match_tier.factor() * 10_000.0).round() / 10_000.0
}

/// Deterministic pseudo-random generator for property tests (no extra
/// dependency): a 64-bit multiplicative LCG good enough for input sweeping.
pub struct Lcg(u64);

impl Lcg {
    pub fn new(seed: u64) -> Self {
        Lcg(seed | 1)
    }

    pub fn next_u64(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        self.0
    }

    pub fn next_f64(&mut self, max: f64) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64 * max
    }
}
