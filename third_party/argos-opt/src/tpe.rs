//! Tree-structured Parzen Estimator (ask/tell form).
//!
//! Minimizes. Classic TPE loop (Bergstra et al.): split the observed
//! successes into good/bad by loss quantile, build a per-dimension
//! generative model of the good set, draw `n_candidates` points from it,
//! keep the one maximizing log P(good) − log P(bad).
//!
//! Behaviors the lab relies on (all covered by tests):
//! - deterministic: one seeded PCG32 drives every decision;
//! - never re-proposes a point (successful OR failed) — dedup is keyed on
//!   the canonical JSON of the params vector;
//! - failed trials never enter the models and can never win `best()`;
//! - `n_startup_trials` random points before the first model-based ask.

use std::collections::HashSet;

use serde::{Deserialize, Serialize};

use crate::log::{TrialLog, TrialResult};
use crate::rng::Rng;
use crate::space::{params_key, Dim, Space, Value};

/// Tuning knobs. `Default` is the configuration the L03A lab runs with.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TpeConfig {
    /// Random asks before the first model-based ask.
    pub n_startup_trials: usize,
    /// Candidates drawn from the good model per ask; best density ratio wins.
    pub n_candidates: usize,
    /// Fraction of successful observations kept in the "good" set.
    pub gamma: f64,
    /// Weight of the uniform component mixed into each Parzen model
    /// (keeps the search from freezing onto a point).
    pub prior_mix: f64,
    /// KDE bandwidth floor, as a fraction of each dimension's span. Without
    /// a floor the bandwidth collapses as points cluster and the search
    /// freezes terminally (measured on the original crate's sphere demo).
    pub bandwidth_floor_frac: f64,
    /// Laplace smoothing added to each categorical count.
    pub cat_smoothing: f64,
    /// Exploration half-life (in successful trials) for the bandwidth's
    /// exponential component: `span * exp(-n/explore_tau)`. Early on this
    /// keeps candidate steps wide no matter how tightly the lucky startup
    /// points cluster (measured: without it the search freezes on the
    /// startup champion and improves ~0.1% per 10 evals); as trials
    /// accumulate it decays away and the good-set spread + floor govern.
    pub explore_tau: f64,
    /// Cap on dedup resampling attempts before ask() gives up and returns
    /// the raw draw (only reachable in near-exhausted tiny spaces).
    pub max_sample_attempts: usize,
}

impl Default for TpeConfig {
    fn default() -> TpeConfig {
        TpeConfig {
            n_startup_trials: 5,
            n_candidates: 48,
            gamma: 0.25,
            prior_mix: 0.15,
            bandwidth_floor_frac: 0.001,
            cat_smoothing: 1.0,
            explore_tau: 25.0,
            max_sample_attempts: 1000,
        }
    }
}

#[derive(Clone, Debug)]
struct Observation {
    params: Vec<Value>,
    loss: f64,
}

/// One dimension's Parzen model over the good (or bad) split.
#[derive(Clone, Debug)]
enum SideModel {
    /// Numeric dims: weighted 1-D Gaussian KDE + uniform prior component.
    Numeric {
        lo: f64,
        hi: f64,
        mus: Vec<f64>,
        weights: Vec<f64>, // normalized, sums to 1
        bandwidth: f64,
        prior_mix: f64,
    },
    /// Categorical dims: Laplace-smoothed empirical distribution.
    Categorical { p: Vec<f64> },
}

struct DimModel {
    good: SideModel,
    bad: SideModel,
}

/// The optimizer. `new` / `ask` / `tell` / `best` is the lab loop;
/// `resume` rebuilds state from a saved `TrialLog`.
#[derive(Clone, Debug)]
pub struct Optimizer {
    space: Space,
    config: TpeConfig,
    rng: Rng,
    observed: Vec<Observation>,
    seen: HashSet<String>,
}

impl Optimizer {
    pub fn new(space: Space, seed: u64, config: TpeConfig) -> Optimizer {
        Optimizer {
            space,
            config,
            rng: Rng::new(seed),
            observed: Vec::new(),
            seen: HashSet::new(),
        }
    }

    /// Rebuilds an optimizer from a log. Every entry must belong to the
    /// space; successful entries replay into the models, all entries go
    /// into the no-repeat set. The RNG starts fresh from `seed`, so the
    /// resumed ask sequence is deterministic given (space, seed, config,
    /// log) — and never repeats anything the log already contains.
    pub fn resume(
        space: Space,
        seed: u64,
        config: TpeConfig,
        log: &TrialLog,
    ) -> Result<Optimizer, String> {
        let mut opt = Optimizer::new(space.clone(), seed, config);
        for (i, e) in log.trials.iter().enumerate() {
            if !space.contains(&e.params) {
                return Err(format!(
                    "log entry {i} does not belong to this space: {:?}",
                    e.params
                ));
            }
            opt.tell(e.params.clone(), e.result.clone());
        }
        Ok(opt)
    }

    pub fn space(&self) -> &Space {
        &self.space
    }

    pub fn config(&self) -> &TpeConfig {
        &self.config
    }

    /// Number of successful observations so far.
    pub fn n_observed(&self) -> usize {
        self.observed.len()
    }

    /// Ask the next point to evaluate. Deterministic for a fixed
    /// (seed, config, tell history).
    pub fn ask(&mut self) -> Vec<Value> {
        if self.observed.len() < self.config.n_startup_trials {
            return self.sample_fresh();
        }
        // Models are rebuilt from scratch each ask: n is small, this is
        // not a hot loop, and it keeps ask() a pure function of state.
        let models = self.build_models();
        let mut best: Option<(Vec<Value>, f64)> = None;
        for _ in 0..self.config.n_candidates {
            let params = self.sample_from_models(&models);
            if self.seen.contains(&params_key(&params)) {
                continue;
            }
            let score = self.score(&params, &models);
            if best.as_ref().map(|(_, s)| score > *s).unwrap_or(true) {
                best = Some((params, score));
            }
        }
        match best {
            Some((params, _)) => {
                self.seen.insert(params_key(&params));
                params
            }
            // Every candidate was a repeat (or the space is exhausted):
            // fall back to rejection sampling; in a degenerate fully
            // exhausted space this returns a repeat by design.
            None => self.sample_fresh(),
        }
    }

    /// Report the outcome for a point (any point — typically the last
    /// `ask`). `Value(loss)`: lower is better; non-finite losses are
    /// treated as `Failed`. `Failed`: recorded as seen (never re-proposed),
    /// excluded from models and from `best()`. Points outside the space
    /// are ignored defensively.
    pub fn tell(&mut self, params: Vec<Value>, result: TrialResult) {
        if !self.space.contains(&params) {
            return;
        }
        self.seen.insert(params_key(&params));
        match result {
            TrialResult::Value(loss) if loss.is_finite() => {
                self.observed.push(Observation { params, loss });
            }
            _ => {}
        }
    }

    /// Lowest-loss successful trial so far, if any. First one wins ties.
    pub fn best(&self) -> Option<(Vec<Value>, f64)> {
        let mut best: Option<(&Observation, f64)> = None;
        for o in &self.observed {
            if best.map(|(_, l)| o.loss < l).unwrap_or(true) {
                best = Some((o, o.loss));
            }
        }
        best.map(|(o, l)| (o.params.clone(), l))
    }

    /// Convenience driver: asks up to `max_evals` points, feeding each to
    /// `f`. Returns the number of SUCCESSFUL evaluations (failed trials
    /// still consume budget, exactly like the lab loop).
    pub fn run(
        &mut self,
        max_evals: usize,
        f: &mut dyn FnMut(&[Value]) -> TrialResult,
    ) -> usize {
        let mut successes = 0;
        for _ in 0..max_evals {
            let params = self.ask();
            let result = f(&params);
            if matches!(result, TrialResult::Value(_)) {
                successes += 1;
            }
            self.tell(params, result);
        }
        successes
    }

    /// Rejection-sample a fresh uniform point not seen before.
    fn sample_fresh(&mut self) -> Vec<Value> {
        let mut last = None;
        for _ in 0..self.config.max_sample_attempts {
            let p = self.space.sample(&mut self.rng);
            if self.seen.insert(params_key(&p)) {
                return p;
            }
            last = Some(p);
        }
        last.expect("at least one draw happens in the loop")
    }

    fn build_models(&self) -> Vec<DimModel> {
        // Stable sort: equal losses keep observation order, so the split
        // is deterministic.
        let mut order: Vec<&Observation> = self.observed.iter().collect();
        order.sort_by(|a, b| a.loss.partial_cmp(&b.loss).unwrap_or(std::cmp::Ordering::Equal));
        let n_good = ((order.len() as f64) * self.config.gamma).ceil() as usize;
        let n_good = n_good.clamp(1, order.len());
        let (good, bad) = order.split_at(n_good);

        self.space
            .dims()
            .iter()
            .enumerate()
            .map(|(i, dim)| DimModel {
                good: self.side_model(dim, i, good),
                bad: self.side_model(dim, i, bad),
            })
            .collect()
    }

    fn side_model(&self, dim: &Dim, idx: usize, side: &[&Observation]) -> SideModel {
        match dim {
            Dim::Categorical { choices } => {
                let k = choices.len();
                let mut counts = vec![0usize; k];
                for o in side {
                    if let Value::Cat(c) = o.params[idx] {
                        counts[c] += 1;
                    }
                }
                let s = self.config.cat_smoothing;
                let total = side.len() as f64 + s * k as f64;
                SideModel::Categorical {
                    p: counts.into_iter().map(|c| (c as f64 + s) / total).collect(),
                }
            }
            Dim::Continuous { low, high } => {
                self.numeric_model(*low, *high, idx, side)
            }
            Dim::Integer { low, high } => {
                self.numeric_model(*low as f64, *high as f64, idx, side)
            }
        }
    }

    fn numeric_model(
        &self,
        lo: f64,
        hi: f64,
        idx: usize,
        side: &[&Observation],
    ) -> SideModel {
        let span = (hi - lo).max(1.0);
        let xs: Vec<f64> = side
            .iter()
            .map(|o| match o.params[idx] {
                Value::Real(x) => x,
                Value::Int(x) => x as f64,
                Value::Cat(_) => unreachable!("dim type/value mismatch"),
            })
            .collect();
        // Linear decreasing weights: earlier (better-loss) points weigh more
        // for choosing WHICH mixture component to sample from.
        let n = xs.len() as f64;
        let raw: Vec<f64> = xs.iter().enumerate().map(|(i, _)| n - i as f64).collect();
        let wsum: f64 = raw.iter().sum();
        let weights: Vec<f64> = raw.iter().map(|w| w / wsum).collect();

        // Bandwidth = max(flat good-set spread, decaying exploration
        // component, floor). The mixture may favor the best points, but
        // the step size must stay tied to how spread the whole side is,
        // plus a schedule-bounded exploration term so a lucky-tight
        // startup cannot freeze the search on its champion.
        let flat_mean: f64 = xs.iter().sum::<f64>() / n;
        let flat_var: f64 =
            xs.iter().map(|x| (x - flat_mean) * (x - flat_mean)).sum::<f64>() / n;
        let explore = span * (-n / self.config.explore_tau).exp();
        let floor = self.config.bandwidth_floor_frac * span;
        let bandwidth = flat_var.sqrt().max(explore).max(floor);

        SideModel::Numeric {
            lo,
            hi,
            mus: xs,
            weights,
            bandwidth,
            prior_mix: self.config.prior_mix,
        }
    }

    fn sample_from_models(&mut self, models: &[DimModel]) -> Vec<Value> {
        let mut params = Vec::with_capacity(models.len());
        for (idx, model) in models.iter().enumerate() {
            let v = match (&model.good, &self.space.dims()[idx]) {
                (SideModel::Numeric { lo, hi, mus, weights, bandwidth, prior_mix }, dim) => {
                    let x = if self.rng.next_f64() < *prior_mix {
                        self.rng.next_range(*lo, *hi)
                    } else {
                        let u = self.rng.next_f64();
                        let mut acc = 0.0;
                        let mut comp = mus.len() - 1;
                        for (i, w) in weights.iter().enumerate() {
                            acc += w;
                            if u < acc {
                                comp = i;
                                break;
                            }
                        }
                        (mus[comp] + self.rng.normal() * *bandwidth).clamp(*lo, *hi)
                    };
                    match dim {
                        Dim::Integer { .. } => Value::Int(x.round() as i64),
                        _ => Value::Real(x),
                    }
                }
                (SideModel::Categorical { p }, _) => {
                    let u = self.rng.next_f64();
                    let mut acc = 0.0;
                    let mut k = p.len() - 1;
                    for (i, pi) in p.iter().enumerate() {
                        acc += pi;
                        if u < acc {
                            k = i;
                            break;
                        }
                    }
                    Value::Cat(k)
                }
            };
            params.push(v);
        }
        params
    }

    /// log P(params | good) − log P(params | bad), summed over dimensions.
    fn score(&self, params: &[Value], models: &[DimModel]) -> f64 {
        let mut s = 0.0;
        for (idx, model) in models.iter().enumerate() {
            match (&model.good, &model.bad) {
                (SideModel::Numeric { .. }, SideModel::Numeric { .. }) => {
                    let x = match params[idx] {
                        Value::Real(x) => x,
                        Value::Int(x) => x as f64,
                        Value::Cat(_) => 0.0,
                    };
                    s += numeric_log_pdf(&model.good, x) - numeric_log_pdf(&model.bad, x);
                }
                (SideModel::Categorical { p: pg }, SideModel::Categorical { p: pb }) => {
                    if let Value::Cat(k) = params[idx] {
                        s += pg[k].ln() - pb[k].ln();
                    }
                }
                _ => {}
            }
        }
        s
    }
}

const SQRT_2PI: f64 = 2.506628274631000502415765284811;

/// Log density of a numeric Parzen side at `x`: a uniform prior component
/// with weight `prior_mix` over the span, plus the weighted Gaussian KDE.
fn numeric_log_pdf(m: &SideModel, x: f64) -> f64 {
    let SideModel::Numeric {
        lo,
        hi,
        mus,
        weights,
        bandwidth,
        prior_mix,
    } = m
    else {
        return 0.0;
    };
    let span = hi - lo;
    if span <= 0.0 {
        return 0.0; // degenerate dimension: point mass, neutral score
    }
    let gauss: f64 = mus
        .iter()
        .zip(weights)
        .map(|(mu, w)| {
            let z = (x - mu) / bandwidth;
            w * (-0.5 * z * z).exp() / (bandwidth * SQRT_2PI)
        })
        .sum();
    let mix = prior_mix / span + (1.0 - prior_mix) * gauss;
    mix.max(f64::MIN_POSITIVE).ln()
}
