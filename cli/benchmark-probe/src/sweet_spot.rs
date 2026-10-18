//! Sweet-spot finder for llama.cpp: the largest context that keeps EVERY
//! layer on the GPU, per KV-cache type, then measured decode/prefill at
//! several context depths.
//!
//! Why "fully on GPU" is the hard constraint (measured 2026-10-17, RTX 5050
//! 8 GB, Bonsai 2 27B PTQ1_0, llama-bench tg64): ngl 99 -> 42.1 tok/s,
//! 2 layers on CPU -> 23.4, 4 layers -> 19.0. A spilled layer costs ~9 ms per
//! token there, far more than its RAM bandwidth explains (low-bit CPU kernels
//! are compute-bound). So context is the knob that bends, never layers.
//!
//! Sources stay honest: `max_gpu_ctx` is llama.cpp's own memory model
//! (llama-fit-params, a formula); every tok/s number is a llama-bench
//! measurement on this machine. Nothing is extrapolated.

use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Serialize;

/// Preference order when several KV types reach the requested context.
pub const KV_TYPES_BY_QUALITY: [&str; 3] = ["f16", "q8_0", "q4_0"];

const BENCH_PROMPT_TOKENS: u64 = 512;
const BENCH_GEN_TOKENS: u64 = 64;
/// Headroom kept between the deepest measured depth and the fitted context.
const DEPTH_HEADROOM_TOKENS: u64 = 1024;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DepthPoint {
    pub depth: u64,
    pub prefill_tok_s: Option<f64>,
    pub decode_tok_s: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct KvCandidate {
    pub kv_type: String,
    /// None = not even the minimum fit context keeps every layer on the GPU.
    pub max_gpu_ctx: Option<u64>,
    pub points: Vec<DepthPoint>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Recommendation {
    pub kv_type: String,
    pub ctx: u64,
    pub reason: String,
    pub server_command: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SweetSpotReport {
    pub model: String,
    pub ubatch: u32,
    pub fit_margin_mib: u32,
    pub min_ctx: u64,
    pub candidates: Vec<KvCandidate>,
    pub recommended: Option<Recommendation>,
}

pub struct SweetSpotRun {
    pub model: PathBuf,
    pub bin_dir: PathBuf,
    pub kv_types: Vec<String>,
    pub ubatch: u32,
    pub fit_margin_mib: u32,
    pub min_ctx: u64,
    pub threads: Option<u32>,
    pub measure: bool,
}

/// `llama-fit-params` prints the fitted CLI arguments as its last stdout
/// line, e.g. `-c 93952 -ngl 99`. A fit only counts when every layer stayed
/// on the GPU (`-ngl 99` as requested, or `-1` = all).
pub fn parse_fit_ctx(stdout: &str) -> Option<u64> {
    let line = stdout.lines().rev().find(|l| l.trim_start().starts_with("-c "))?;
    let tokens: Vec<&str> = line.split_whitespace().collect();
    let value_after = |flag: &str| {
        tokens
            .iter()
            .position(|t| *t == flag)
            .and_then(|i| tokens.get(i + 1))
            .copied()
    };
    match value_after("-ngl") {
        Some("99") | Some("-1") | None => {}
        Some(_) => return None,
    }
    value_after("-c")?.parse().ok()
}

/// llama-bench `-o jsonl`: one object per test; prefill rows have
/// `n_gen == 0`, decode rows have `n_prompt == 0`. Grouped by `n_depth`.
pub fn parse_bench_jsonl(raw: &str) -> Vec<DepthPoint> {
    let mut points: Vec<DepthPoint> = Vec::new();
    for line in raw.lines().filter(|l| !l.trim().is_empty()) {
        let Ok(row) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };
        let (Some(depth), Some(n_prompt), Some(n_gen), Some(ts)) = (
            row["n_depth"].as_u64(),
            row["n_prompt"].as_u64(),
            row["n_gen"].as_u64(),
            row["avg_ts"].as_f64(),
        ) else {
            continue;
        };
        let idx = match points.iter().position(|p| p.depth == depth) {
            Some(i) => i,
            None => {
                points.push(DepthPoint { depth, prefill_tok_s: None, decode_tok_s: None });
                points.len() - 1
            }
        };
        if n_gen == 0 && n_prompt > 0 {
            points[idx].prefill_tok_s = Some(ts);
        } else if n_prompt == 0 && n_gen > 0 {
            points[idx].decode_tok_s = Some(ts);
        }
    }
    points.sort_by_key(|p| p.depth);
    points
}

/// Depths 0, 1/4, 1/2 and 3/4 of the fitted context (rounded down to 1024),
/// never deeper than the context minus the bench prompt/gen and headroom.
pub fn depth_plan(max_ctx: u64) -> Vec<u64> {
    let ceiling = max_ctx.saturating_sub(BENCH_PROMPT_TOKENS + BENCH_GEN_TOKENS + DEPTH_HEADROOM_TOKENS);
    let mut depths: Vec<u64> = [0u64, max_ctx / 4, max_ctx / 2, max_ctx * 3 / 4]
        .iter()
        .map(|d| (d / 1024 * 1024).min(ceiling))
        .collect();
    depths.dedup();
    depths
}

pub fn server_command(model: &str, kv_type: &str, ctx: u64, ubatch: u32) -> String {
    format!(
        "llama-server -m {model} -c {ctx} -ngl 99 -fa on -ctk {kv_type} -ctv {kv_type} -ub {ubatch} -np 1 --jinja"
    )
}

/// Highest-precision KV type whose fully-on-GPU context reaches `min_ctx`,
/// run at that type's maximum context. When none reaches it, the largest
/// context wins and the reason says so — the CLI never pretends.
pub fn choose(
    candidates: &[KvCandidate],
    min_ctx: u64,
    model: &str,
    ubatch: u32,
) -> Option<Recommendation> {
    let rank = |kv: &str| KV_TYPES_BY_QUALITY.iter().position(|k| *k == kv).unwrap_or(usize::MAX);
    let mut fitted: Vec<(&KvCandidate, u64)> = candidates
        .iter()
        .filter_map(|c| c.max_gpu_ctx.map(|ctx| (c, ctx)))
        .collect();
    fitted.sort_by_key(|(c, _)| rank(&c.kv_type));

    let (pick, reason) = match fitted.iter().find(|(_, ctx)| *ctx >= min_ctx) {
        Some(&(c, ctx)) => (
            (c, ctx),
            format!("highest-precision KV cache whose fully-on-GPU context ({ctx}) reaches --min-ctx {min_ctx}"),
        ),
        None => {
            let &(c, ctx) = fitted.iter().max_by_key(|(_, ctx)| *ctx)?;
            (
                (c, ctx),
                format!(
                    "no KV type reaches --min-ctx {min_ctx} fully on GPU; largest is {ctx}. \
                     Spilling layers to CPU is measured at ~9 ms/token per layer on low-bit models — \
                     lower --min-ctx, use a smaller quant, or accept the spill knowingly"
                ),
            )
        }
    };
    Some(Recommendation {
        kv_type: pick.0.kv_type.clone(),
        ctx: pick.1,
        reason,
        server_command: server_command(model, &pick.0.kv_type, pick.1, ubatch),
    })
}

pub fn render_text(report: &SweetSpotReport) -> String {
    let mut out = String::new();
    out.push_str(&format!("sweet spot for {} (ubatch {}, fit margin {} MiB)\n", report.model, report.ubatch, report.fit_margin_mib));
    out.push_str("max_gpu_ctx: llama-fit-params (formula) · tok/s: llama-bench (measured here)\n\n");
    for c in &report.candidates {
        match c.max_gpu_ctx {
            Some(ctx) => out.push_str(&format!("KV {:<5} max context fully on GPU: {ctx}\n", c.kv_type)),
            None => out.push_str(&format!("KV {:<5} does not fit fully on GPU\n", c.kv_type)),
        }
        for p in &c.points {
            let fmt = |v: Option<f64>| v.map(|x| format!("{x:>7.1}")).unwrap_or_else(|| "      -".to_string());
            out.push_str(&format!(
                "  depth {:>7}   prefill {} tok/s   decode {} tok/s\n",
                p.depth,
                fmt(p.prefill_tok_s),
                fmt(p.decode_tok_s)
            ));
        }
    }
    match &report.recommended {
        Some(r) => out.push_str(&format!(
            "\nrecommended: KV {} at context {}\n  why: {}\n  run: {}\n",
            r.kv_type, r.ctx, r.reason, r.server_command
        )),
        None => out.push_str("\nno configuration keeps every layer on the GPU (honest no-data)\n"),
    }
    out
}

/// Locates the llama.cpp tools: an explicit directory, else the directory
/// of `llama-bench` on PATH.
pub fn resolve_bin_dir(explicit: Option<&Path>) -> Result<PathBuf, String> {
    let dir = match explicit {
        Some(d) => d.to_path_buf(),
        None => std::env::var_os("PATH")
            .and_then(|path| {
                std::env::split_paths(&path).find(|d| d.join("llama-bench").is_file())
            })
            .ok_or_else(|| "llama-bench not found on PATH; pass --llama-bin <dir>".to_string())?,
    };
    for tool in ["llama-fit-params", "llama-bench"] {
        if !dir.join(tool).is_file() {
            return Err(format!("{tool} not found in {}", dir.display()));
        }
    }
    Ok(dir)
}

pub fn run(cfg: &SweetSpotRun) -> Result<SweetSpotReport, String> {
    let model = cfg.model.display().to_string();
    let mut candidates = Vec::new();
    for kv in &cfg.kv_types {
        let max_gpu_ctx = fit_ctx(cfg, kv)?;
        let points = match (cfg.measure, max_gpu_ctx) {
            (true, Some(ctx)) => bench_depths(cfg, kv, &depth_plan(ctx))?,
            _ => Vec::new(),
        };
        candidates.push(KvCandidate { kv_type: kv.clone(), max_gpu_ctx, points });
    }
    let recommended = choose(&candidates, cfg.min_ctx, &model, cfg.ubatch);
    Ok(SweetSpotReport {
        model,
        ubatch: cfg.ubatch,
        fit_margin_mib: cfg.fit_margin_mib,
        min_ctx: cfg.min_ctx,
        candidates,
        recommended,
    })
}

fn fit_ctx(cfg: &SweetSpotRun, kv: &str) -> Result<Option<u64>, String> {
    let output = Command::new(cfg.bin_dir.join("llama-fit-params"))
        .arg("-m").arg(&cfg.model)
        .args(["-ngl", "99", "-fa", "on", "-np", "1", "-ctk", kv, "-ctv", kv])
        .args(["-ub", &cfg.ubatch.to_string(), "-fitt", &cfg.fit_margin_mib.to_string()])
        .output()
        .map_err(|e| format!("llama-fit-params: {e}"))?;
    Ok(parse_fit_ctx(&String::from_utf8_lossy(&output.stdout)))
}

fn bench_depths(cfg: &SweetSpotRun, kv: &str, depths: &[u64]) -> Result<Vec<DepthPoint>, String> {
    let depth_list: Vec<String> = depths.iter().map(u64::to_string).collect();
    let mut cmd = Command::new(cfg.bin_dir.join("llama-bench"));
    cmd.arg("-m").arg(&cfg.model)
        .args(["-ngl", "99", "-fa", "1", "-r", "1", "-o", "jsonl", "-ctk", kv, "-ctv", kv])
        .args(["-ub", &cfg.ubatch.to_string()])
        .args(["-p", &BENCH_PROMPT_TOKENS.to_string(), "-n", &BENCH_GEN_TOKENS.to_string()])
        .args(["-d", &depth_list.join(",")]);
    if let Some(t) = cfg.threads {
        cmd.args(["-t", &t.to_string()]);
    }
    let output = cmd.output().map_err(|e| format!("llama-bench: {e}"))?;
    if !output.status.success() {
        return Err(format!(
            "llama-bench failed for KV {kv}: {}",
            String::from_utf8_lossy(&output.stderr).lines().last().unwrap_or("")
        ));
    }
    Ok(parse_bench_jsonl(&String::from_utf8_lossy(&output.stdout)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fit_ctx_requires_every_layer_on_gpu() {
        assert_eq!(parse_fit_ctx("noise\n-c 93952 -ngl 99\n"), Some(93952));
        assert_eq!(parse_fit_ctx("-c 93952 -ngl -1 -ot \"blk\\.64\\.=CPU\"\n"), Some(93952));
        // fit had to drop layers: that is a spill, not a fit
        assert_eq!(parse_fit_ctx("-c 114688 -ngl 44\n"), None);
        assert_eq!(parse_fit_ctx("no fitted line\n"), None);
    }

    #[test]
    fn bench_rows_group_by_depth() {
        let raw = concat!(
            r#"{"n_prompt":512,"n_gen":0,"n_depth":0,"avg_ts":617.9}"#, "\n",
            r#"{"n_prompt":0,"n_gen":64,"n_depth":0,"avg_ts":41.4}"#, "\n",
            r#"{"n_prompt":0,"n_gen":64,"n_depth":8192,"avg_ts":37.1}"#, "\n",
            "not json\n",
        );
        let points = parse_bench_jsonl(raw);
        assert_eq!(points.len(), 2);
        assert_eq!(points[0], DepthPoint { depth: 0, prefill_tok_s: Some(617.9), decode_tok_s: Some(41.4) });
        assert_eq!(points[1].prefill_tok_s, None);
        assert_eq!(points[1].decode_tok_s, Some(37.1));
    }

    #[test]
    fn depth_plan_stays_inside_the_fitted_context() {
        assert_eq!(depth_plan(93952), vec![0, 23488 / 1024 * 1024, 46976 / 1024 * 1024, 70464 / 1024 * 1024]);
        for d in depth_plan(4096) {
            assert!(d + 512 + 64 <= 4096);
        }
    }

    fn cand(kv: &str, ctx: Option<u64>) -> KvCandidate {
        KvCandidate { kv_type: kv.to_string(), max_gpu_ctx: ctx, points: vec![] }
    }

    #[test]
    fn choose_prefers_precision_then_falls_back_to_largest_context() {
        let cands = [cand("q4_0", Some(93952)), cand("q8_0", Some(52224)), cand("f16", Some(27648))];
        let r = choose(&cands, 32768, "m.gguf", 128).unwrap();
        assert_eq!((r.kv_type.as_str(), r.ctx), ("q8_0", 52224));

        let r = choose(&cands, 86000, "m.gguf", 128).unwrap();
        assert_eq!((r.kv_type.as_str(), r.ctx), ("q4_0", 93952));
        assert!(r.server_command.contains("-c 93952") && r.server_command.contains("-ctk q4_0"));

        let r = choose(&cands, 200000, "m.gguf", 128).unwrap();
        assert_eq!(r.kv_type, "q4_0");
        assert!(r.reason.contains("no KV type reaches"));

        assert!(choose(&[cand("f16", None)], 4096, "m.gguf", 128).is_none());
    }
}
