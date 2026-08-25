use std::fmt;
use std::sync::LazyLock;

use regex::{Captures, Regex};

pub struct Metrics {
    pub ttft_ms: f64,
    pub prefill_tok_s: f64,
    pub decode_tok_s: f64,
    pub peak_vram_mib: f64,
    pub power_watt_avg: f64,
}

#[derive(Debug, PartialEq)]
pub enum ParseError {
    MissingField(String),
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ParseError::MissingField(field) => write!(f, "missing or malformed field: {field}"),
        }
    }
}

static LLAMA_PROMPT_EVAL_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"prompt eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*\([^)]*,\s*([\d.]+)\s*tokens per second\)",
    )
    .unwrap()
});

static LLAMA_EVAL_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*runs?\s*\([^)]*,\s*([\d.]+)\s*tokens per second\)",
    )
    .unwrap()
});

static LLAMA_VRAM_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"total VRAM used:\s*([\d.]+)\s*MiB").unwrap());

static OL_LOAD_DUR_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"load duration:\s*([\d.]+)\s*(ms|s)").unwrap());

static OL_PROMPT_EVAL_COUNT_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"prompt eval count:\s*(\d+)\s*token").unwrap());

static OL_PROMPT_EVAL_DUR_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"prompt eval duration:\s*([\d.]+)\s*(ms|s)").unwrap());

static OL_EVAL_COUNT_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^[ \t]*eval count:\s*(\d+)\s*token").unwrap());

static OL_EVAL_DUR_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^[ \t]*eval duration:\s*([\d.]+)\s*(ms|s)").unwrap());

pub fn parse_llama_cpp_metrics(stdout: &str) -> Result<Metrics, ParseError> {
    let prompt = LLAMA_PROMPT_EVAL_RE.captures(stdout);
    let eval = LLAMA_EVAL_RE.captures(stdout);
    let vram = LLAMA_VRAM_RE.captures(stdout);

    let ttft_ms =
        group_float(&prompt, 1).ok_or(ParseError::MissingField("prompt eval time".to_string()))?;
    let prefill_tok_s = group_float(&prompt, 3)
        .ok_or(ParseError::MissingField("prompt eval tokens/s".to_string()))?;
    let decode_tok_s =
        group_float(&eval, 3).ok_or(ParseError::MissingField("eval tokens/s".to_string()))?;
    let peak_vram_mib =
        group_float(&vram, 1).ok_or(ParseError::MissingField("total VRAM used".to_string()))?;

    Ok(Metrics {
        ttft_ms,
        prefill_tok_s,
        decode_tok_s,
        peak_vram_mib,
        power_watt_avg: 0.0,
    })
}

fn group_float(captures: &Option<Captures<'_>>, group: usize) -> Option<f64> {
    let text = captures.as_ref()?.get(group)?.as_str();
    text.parse::<f64>().ok()
}

struct OllamaTimings {
    load_ns: u64,
    prompt_eval_count: u64,
    prompt_eval_duration_ns: u64,
    eval_count: u64,
    eval_duration_ns: u64,
}

pub fn parse_ollama_metrics(stdout: &str) -> Result<Metrics, ParseError> {
    let timings = parse_ollama_timings(stdout)?;
    let ttft_ms = (timings.load_ns + timings.prompt_eval_duration_ns) as f64 / 1_000_000.0;
    let prefill_tok_s =
        timings.prompt_eval_count as f64 * 1e9 / timings.prompt_eval_duration_ns as f64;
    let decode_tok_s = timings.eval_count as f64 * 1e9 / timings.eval_duration_ns as f64;
    Ok(Metrics {
        ttft_ms,
        prefill_tok_s,
        decode_tok_s,
        peak_vram_mib: 0.0,
        power_watt_avg: 0.0,
    })
}

fn parse_ollama_timings(stdout: &str) -> Result<OllamaTimings, ParseError> {
    let load_ns = capture_ns(&OL_LOAD_DUR_RE, stdout)
        .ok_or(ParseError::MissingField("load duration".to_string()))?;
    let prompt_eval_count = group_u64(&OL_PROMPT_EVAL_COUNT_RE, stdout, 1)
        .ok_or(ParseError::MissingField("prompt eval count".to_string()))?;
    let prompt_eval_duration_ns = capture_ns(&OL_PROMPT_EVAL_DUR_RE, stdout)
        .ok_or(ParseError::MissingField("prompt eval duration".to_string()))?;
    let eval_count = group_u64(&OL_EVAL_COUNT_RE, stdout, 1)
        .ok_or(ParseError::MissingField("eval count".to_string()))?;
    let eval_duration_ns = capture_ns(&OL_EVAL_DUR_RE, stdout)
        .ok_or(ParseError::MissingField("eval duration".to_string()))?;
    Ok(OllamaTimings {
        load_ns,
        prompt_eval_count,
        prompt_eval_duration_ns,
        eval_count,
        eval_duration_ns,
    })
}

fn capture_ns(re: &Regex, stdout: &str) -> Option<u64> {
    let captures = re.captures(stdout)?;
    let value: f64 = captures.get(1)?.as_str().parse().ok()?;
    let unit = captures.get(2)?.as_str();
    Some(duration_to_ns(value, unit))
}

fn duration_to_ns(value: f64, unit: &str) -> u64 {
    let multiplier = match unit {
        "us" => 1_000.0,
        "µs" => 1_000.0,
        "ms" => 1_000_000.0,
        "s" => 1_000_000_000.0,
        _ => 1.0,
    };
    (value * multiplier) as u64
}

fn group_u64(re: &Regex, stdout: &str, group: usize) -> Option<u64> {
    re.captures(stdout)?.get(group)?.as_str().parse().ok()
}
