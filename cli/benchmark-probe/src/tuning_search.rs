//! tuning_search.rs — L03A: intelligent (TPE, never brute force) search
//! over the llama.cpp serving-flag space, plus the deterministic SIM stub
//! objective that lets the whole lab loop run without a rig.
//!
//! The first real objective is llama.cpp flags on the 3090; the search is a
//! seeded public TPE implementation. This module is the ONLY place that knows
//! both the flag space and how to swap stub -> real.

use std::collections::HashSet;
use std::path::Path;

use optimizer::parameter::{CategoricalParam, IntParam, Parameter};
use optimizer::sampler::TpeSampler;
use optimizer::{Direction, Study, Trial};
use rand::Rng;
use serde::Serialize;

use crate::lab_recorder::{LabBest, LabMeta, LabRecorder};

pub const KV_CHOICES: [&str; 3] = ["f16", "q8_0", "q4_0"];
pub const FA_CHOICES: [&str; 2] = ["off", "on"];

/// Stable lab-artifact value schema. It deliberately remains independent of
/// the optimizer crate so recorded JSON stays compatible across upgrades.
#[derive(Clone, Debug, PartialEq, Serialize)]
pub enum Value {
    Int(i64),
    Real(f64),
    Cat(usize),
}

/// Stable lab-artifact dimension schema in the frozen serving-flag order.
#[derive(Clone, Debug, Serialize)]
pub enum Dim {
    Integer { low: i64, high: i64 },
    Categorical { choices: Vec<String> },
}

// ── SIM stub constants (documented fake; nothing here leaves the machine
//    as a real claim). Rig: ~30B q4 model (18 GiB weights at full
//    offload) on a 24 GiB card with ~2 GiB compute headroom => 22 GiB
//    budget; KV sizes per token realistic for GQA — the OOM corner is
//    the REAL frontier: high ngl x big ctx x f16 KV. ──
const STUB_WEIGHTS_GIB: f64 = 18.0;
const STUB_VRAM_BUDGET_GIB: f64 = 22.0;
const STUB_KV_BYTES_PER_TOKEN: [f64; 3] = [262144.0, 131072.0, 65536.0]; // f16, q8_0, q4_0
const STUB_BASE_TPS: f64 = 30.0;

/// The llama.cpp serving space (frozen dim order — see spec L03A).
pub struct LabSpace {
    dims: Vec<Dim>,
    ngl: IntParam,
    ctx: IntParam,
    threads: IntParam,
    kv_cache: CategoricalParam<usize>,
    flash_attn: CategoricalParam<usize>,
}

impl LabSpace {
    pub fn new() -> Result<LabSpace, String> {
        let dims = vec![
            Dim::Integer { low: 0, high: 999 }, // ngl (-ngl)
            Dim::Integer {
                low: 512,
                high: 32768,
            }, // ctx (-c)
            Dim::Integer { low: 1, high: 32 },  // threads (-t)
            Dim::Categorical {
                choices: KV_CHOICES.iter().map(|s| s.to_string()).collect(),
            },
            Dim::Categorical {
                choices: FA_CHOICES.iter().map(|s| s.to_string()).collect(),
            },
        ];
        Ok(LabSpace {
            dims,
            ngl: IntParam::new(0, 999).name("ngl"),
            ctx: IntParam::new(512, 32768).name("ctx"),
            threads: IntParam::new(1, 32).name("threads"),
            kv_cache: CategoricalParam::new(vec![0, 1, 2]).name("kv_cache"),
            flash_attn: CategoricalParam::new(vec![0, 1]).name("flash_attn"),
        })
    }

    pub fn dims(&self) -> &[Dim] {
        &self.dims
    }

    fn suggest(&self, trial: &mut Trial) -> Result<Vec<Value>, String> {
        Ok(vec![
            Value::Int(self.ngl.suggest(trial).map_err(|e| e.to_string())?),
            Value::Int(self.ctx.suggest(trial).map_err(|e| e.to_string())?),
            Value::Int(self.threads.suggest(trial).map_err(|e| e.to_string())?),
            Value::Cat(self.kv_cache.suggest(trial).map_err(|e| e.to_string())?),
            Value::Cat(self.flash_attn.suggest(trial).map_err(|e| e.to_string())?),
        ])
    }

    /// Uniform random draw for the test-only brute-force baseline.
    pub fn sample_uniform(&self, rng: &mut impl Rng) -> Vec<Value> {
        vec![
            Value::Int(rng.gen_range(0..=999)),
            Value::Int(rng.gen_range(512..=32768)),
            Value::Int(rng.gen_range(1..=32)),
            Value::Cat(rng.gen_range(0..KV_CHOICES.len())),
            Value::Cat(rng.gen_range(0..FA_CHOICES.len())),
        ]
    }

    /// Ready-to-paste llama-server command for a params vector.
    pub fn to_server_command(&self, params: &[Value], model: &str) -> String {
        let ints = |i: usize| -> i64 {
            match &params[i] {
                Value::Int(x) => *x,
                other => panic!("dim {i} is Integer, got {other:?}"),
            }
        };
        let cat = |i: usize| -> String {
            match &params[i] {
                Value::Cat(k) => {
                    let choices: &[&str] = if i == 3 { &KV_CHOICES } else { &FA_CHOICES };
                    choices
                        .get(*k)
                        .unwrap_or_else(|| panic!("dim {i} index {k} out of range"))
                        .to_string()
                }
                other => panic!("dim {i} is Categorical, got {other:?}"),
            }
        };
        let (ngl, ctx, threads) = (ints(0), ints(1), ints(2));
        let kv = cat(3);
        let fa = if cat(4) == "on" { " -fa" } else { "" };
        format!(
            "llama-server -m {model} -ngl {ngl} -c {ctx} -t {threads} \
             --cache-type-k {kv} --cache-type-v {kv}{fa}"
        )
    }
}

fn int_of(v: &Value) -> f64 {
    match v {
        Value::Int(x) => *x as f64,
        Value::Real(x) => *x,
        other => panic!("expected numeric dim, got {other:?}"),
    }
}

fn cat_index(v: &Value) -> usize {
    match v {
        Value::Cat(k) => *k,
        other => panic!("expected categorical dim, got {other:?}"),
    }
}

/// FNV-1a over the params — the stub's deterministic noise source. Same
/// params, same noise, forever; no RNG, no clock.
fn stub_noise(params: &[Value]) -> f64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for v in params {
        match v {
            Value::Int(x) => {
                h = (h ^ (*x as u64)).wrapping_mul(0x100000001b3);
            }
            Value::Real(x) => {
                h = (h ^ x.to_bits()).wrapping_mul(0x100000001b3);
            }
            Value::Cat(k) => {
                h = (h ^ (*k as u64)).wrapping_mul(0x100000001b3);
            }
        }
    }
    ((h % 10_000) as f64 / 10_000.0 - 0.5) * 0.04 // ±2%
}

/// DETERMINISTIC SIMULATION of llama.cpp throughput on a fixed rig
/// (~24 GiB class GPU, ~14B q4 model). NOT a real measurement; every
/// caller must mark output with SIM.
///
/// VRAM model: weights 16 GiB * ngl/999 + ctx * kv_bytes(kv_cache); over
/// the 17 GiB budget the engine OOMs -> Err(()) (a failed trial, exactly
/// like a real crash). tok/s = shaped interior optimum + <±2% noise.
pub fn stub_objective(params: &[Value]) -> Result<f64, ()> {
    let ngl = int_of(&params[0]);
    let ctx = int_of(&params[1]);
    let threads = int_of(&params[2]);
    let kv = cat_index(&params[3]);
    let fa = cat_index(&params[4]) == 1;

    let weights_gib = STUB_WEIGHTS_GIB * (ngl as f64 / 999.0);
    let kv_gib = ctx as f64 * STUB_KV_BYTES_PER_TOKEN[kv] / (1024.0 * 1024.0 * 1024.0);
    if weights_gib + kv_gib > STUB_VRAM_BUDGET_GIB {
        return Err(()); // OOM
    }

    let gpu_speedup = 3.0 + 9.0 * (ngl as f64 / 999.0).powf(0.7);
    let ctx_penalty = 1.0 / (1.0 + ctx as f64 / 16384.0);
    let kv_bonus = [1.0, 1.08, 1.15][kv];
    let fa_bonus = if fa {
        1.0 + 0.10 * ctx as f64 / 32768.0
    } else {
        1.0
    };
    // threads only help the CPU-resident share of the workload
    let threads_term =
        1.0 + 0.15 * (1.0 - ngl as f64 / 999.0) * (1.0 + threads as f64).ln() / 33f64.ln();

    Ok(STUB_BASE_TPS
        * gpu_speedup
        * ctx_penalty
        * kv_bonus
        * fa_bonus
        * threads_term
        * (1.0 + stub_noise(params)))
}

#[derive(Clone, Debug)]
pub struct LabOutcome {
    pub best_params: Vec<Value>,
    pub best_value: f64,
    pub trials: usize,
    pub lab_dir: std::path::PathBuf,
}

/// Run the intelligent lab loop: TPE over the serving space,
/// every trial recorded to `out_root/<label>/`, failed trials logged as
/// null and excluded from best. The meta marks the run as SIMULATION —
/// this is the stub-proof path; the real-objective path (L02, after the
/// owner's "sobe") extends this, it does not replace the loop.
pub fn run_lab(
    space: &LabSpace,
    max_evals: usize,
    seed: u64,
    objective: &mut impl FnMut(&Vec<Value>) -> Result<f64, ()>,
    out_root: &Path,
    label: &str,
) -> Result<LabOutcome, String> {
    let recorder = LabRecorder::create(
        out_root,
        label,
        &LabMeta {
            method: "tpe".into(),
            seed,
            max_evals,
            objective: "stub".into(),
            space: space.dims().to_vec(),
            simulation: true,
        },
    )?;
    let sampler = TpeSampler::builder()
        .gamma(0.5)
        .n_startup_trials(0)
        .seed(seed)
        .build()
        .map_err(|e| format!("create TPE sampler: {e}"))?;
    // TPE is implemented as a minimizer, so feed it -tok/s. The recorded
    // and selected value stays raw tok/s, preserving maximize semantics.
    let study: Study<f64> = Study::with_sampler(Direction::Minimize, sampler);
    let mut seen = HashSet::new();
    let mut best: Option<(Vec<Value>, f64)> = None;
    for trial in 0..max_evals {
        let mut optimizer_trial = study.ask();
        let params = unique_params(space.suggest(&mut optimizer_trial)?, &mut seen);
        let result = match objective(&params) {
            Ok(v) => {
                recorder.append(trial, &params, Some(v))?;
                if best.as_ref().is_none_or(|(_, best_value)| v > *best_value) {
                    best = Some((params.clone(), v));
                }
                Ok(-v)
            }
            Err(()) => {
                recorder.append(trial, &params, None)?;
                Err("objective failed")
            }
        };
        study.tell(optimizer_trial, result);
    }
    let (best_params, best_value) =
        best.ok_or_else(|| "no successful trial in the whole budget".to_string())?;
    let best = LabBest {
        server_command: space.to_server_command(&best_params, "MODEL.gguf"),
        params: best_params.clone(),
        value: best_value,
    };
    recorder.finish(&best)?;
    Ok(LabOutcome {
        best_params: best_params.clone(),
        best_value,
        trials: max_evals,
        lab_dir: recorder.dir().to_path_buf(),
    })
}

fn params_key(params: &[Value]) -> String {
    params
        .iter()
        .map(|value| match value {
            Value::Int(value) => format!("i{value}"),
            Value::Real(value) => format!("r{:016x}", value.to_bits()),
            Value::Cat(value) => format!("c{value}"),
        })
        .collect::<Vec<_>>()
        .join("|")
}

/// The public optimizer may legitimately re-suggest a mixed discrete point.
/// Labs promise that an evaluated point never repeats, so deterministically
/// move a duplicate to the nearest unseen threads/ctx neighbor. This leaves
/// normal TPE proposals untouched, terminates for the finite search budget,
/// and preserves seed reproducibility and the recorded five-value shape.
fn unique_params(mut params: Vec<Value>, seen: &mut HashSet<String>) -> Vec<Value> {
    if seen.insert(params_key(&params)) {
        return params;
    }

    let threads = match params[2] {
        Value::Int(value) => value,
        ref other => panic!("threads dim is Integer, got {other:?}"),
    };
    let ctx = match params[1] {
        Value::Int(value) => value,
        ref other => panic!("ctx dim is Integer, got {other:?}"),
    };
    for offset in 1..=(32 * 32_257) {
        params[2] = Value::Int(1 + (threads - 1 + offset as i64) % 32);
        params[1] = Value::Int(512 + (ctx - 512 + (offset as i64 / 32)) % 32_257);
        if seen.insert(params_key(&params)) {
            return params;
        }
    }
    unreachable!("lab budget cannot exhaust the frozen threads/ctx space")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn server_command_frozen_order() {
        let sp = LabSpace::new().unwrap();
        let cmd = sp.to_server_command(
            &[
                Value::Int(999),
                Value::Int(8192),
                Value::Int(8),
                Value::Cat(2),
                Value::Cat(1),
            ],
            "MODEL.gguf",
        );
        assert_eq!(
            cmd,
            "llama-server -m MODEL.gguf -ngl 999 -c 8192 -t 8 --cache-type-k q4_0 --cache-type-v q4_0 -fa"
        );
    }

    #[test]
    fn oom_corner_is_failed_trial() {
        // full offload + max ctx + f16 KV: over the 17 GiB budget
        let p = &[
            Value::Int(999),
            Value::Int(32768),
            Value::Int(8),
            Value::Cat(0),
            Value::Cat(1),
        ];
        assert!(stub_objective(p).is_err());
        // small ctx same flags: fits
        let p = &[
            Value::Int(999),
            Value::Int(512),
            Value::Int(8),
            Value::Cat(0),
            Value::Cat(1),
        ];
        assert!(stub_objective(p).is_ok());
    }

    #[test]
    fn stub_is_deterministic() {
        let p = vec![
            Value::Int(900),
            Value::Int(4096),
            Value::Int(8),
            Value::Cat(1),
            Value::Cat(1),
        ];
        let a = stub_objective(&p).unwrap();
        let b = stub_objective(&p).unwrap();
        assert_eq!(a, b);
    }
}
