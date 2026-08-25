"""Pure-function stdout parsing for llama.cpp and Ollama runtimes.

These functions only consume text (and embedded JSON); they never launch
third-party processes and apply to any runtime format.
"""

import json
import re

_TIMING_FIELDS = (
    "load_ns",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)

_UNIT_TO_NS = {"us": 1e3, "µs": 1e3, "ms": 1e6, "s": 1e9}


class StdoutParseError(ValueError):
    """Raised when runtime stdout is malformed or missing required fields."""

    def __init__(self, runtime: str, missing: list[str]) -> None:
        self.runtime = runtime
        self.missing = list(missing)
        super().__init__(
            f"cannot parse {runtime} stdout: missing or malformed field(s): "
            f"{', '.join(self.missing)}"
        )


_LLAMA_PROMPT_EVAL_RE = re.compile(
    r"prompt eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*"
    r"\([^)]*,\s*([\d.]+)\s*tokens per second\)"
)
_LLAMA_EVAL_RE = re.compile(
    r"eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*runs?\s*"
    r"\([^)]*,\s*([\d.]+)\s*tokens per second\)"
)
_LLAMA_VRAM_RE = re.compile(r"total VRAM used:\s*([\d.]+)\s*MiB")


def parse_llama_cpp_metrics(stdout: str) -> dict[str, float]:
    """Parse llama-cli ``--verbose`` stdout into the standard metric dict.

    TTFT is taken as the prompt (prefill) eval time: the first generated token
    is emitted right after the full prompt has been processed.
    """
    prompt_match = _LLAMA_PROMPT_EVAL_RE.search(stdout)
    eval_match = _LLAMA_EVAL_RE.search(stdout)
    vram_match = _LLAMA_VRAM_RE.search(stdout)

    ttft_ms = float(prompt_match.group(1)) if prompt_match else None
    prefill_tok_s = float(prompt_match.group(3)) if prompt_match else None
    decode_tok_s = float(eval_match.group(3)) if eval_match else None
    peak_vram_mib = (
        int(round(float(vram_match.group(1)))) if vram_match else None
    )

    missing = [
        name
        for name, value in (
            ("prompt eval time", ttft_ms),
            ("prompt eval tokens/s", prefill_tok_s),
            ("eval tokens/s", decode_tok_s),
            ("total VRAM used", peak_vram_mib),
        )
        if value is None
    ]
    if missing:
        raise StdoutParseError("llama_cpp", missing)

    return {
        "ttft_ms": ttft_ms,
        "prefill_tok_s": prefill_tok_s,
        "decode_tok_s": decode_tok_s,
        "peak_vram_mib": peak_vram_mib,
        "power_watt_avg": 0.0,
    }


_JSON_TIMINGS_RE = re.compile(r'\{[^{}]*"load_ns"[^{}]*\}')
_OL_LOAD_DUR_RE = re.compile(r"load duration:\s*([\d.]+)\s*(ms|s)")
_OL_PROMPT_EVAL_COUNT_RE = re.compile(r"prompt eval count:\s*(\d+)\s*token")
_OL_PROMPT_EVAL_DUR_RE = re.compile(
    r"prompt eval duration:\s*([\d.]+)\s*(ms|s)"
)
_OL_EVAL_COUNT_RE = re.compile(r"(?<!prompt )eval count:\s*(\d+)\s*token")
_OL_EVAL_DUR_RE = re.compile(r"(?<!prompt )eval duration:\s*([\d.]+)\s*(ms|s)")


def _duration_to_ns(value: str, unit: str) -> int:
    return int(float(value) * _UNIT_TO_NS[unit])


def parse_ollama_timings(stdout: str) -> dict[str, int]:
    """Extract ``load_ns``/``prompt_eval_count``/``prompt_eval_duration``/
    ``eval_count``/``eval_duration`` from Ollama output.

    A JSON ``timings`` block (as emitted by ``/api/generate``) is preferred;
    the human-readable ``ollama run --verbose`` lines are used as a fallback.
    """
    json_match = _JSON_TIMINGS_RE.search(stdout)
    if json_match:
        try:
            payload = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            payload = {}
        timings = {field: payload.get(field) for field in _TIMING_FIELDS}
        if all(value is not None for value in timings.values()):
            return timings

    load_match = _OL_LOAD_DUR_RE.search(stdout)
    prompt_count = _OL_PROMPT_EVAL_COUNT_RE.search(stdout)
    prompt_dur = _OL_PROMPT_EVAL_DUR_RE.search(stdout)
    eval_count = _OL_EVAL_COUNT_RE.search(stdout)
    eval_dur = _OL_EVAL_DUR_RE.search(stdout)

    timings = {
        "load_ns": (
            _duration_to_ns(*load_match.groups()) if load_match else None
        ),
        "prompt_eval_count": (
            int(prompt_count.group(1)) if prompt_count else None
        ),
        "prompt_eval_duration": (
            _duration_to_ns(*prompt_dur.groups()) if prompt_dur else None
        ),
        "eval_count": int(eval_count.group(1)) if eval_count else None,
        "eval_duration": _duration_to_ns(*eval_dur.groups()) if eval_dur else None,
    }

    missing = [field for field, value in timings.items() if value is None]
    if missing:
        raise StdoutParseError("ollama", missing)
    return timings


def parse_ollama_metrics(stdout: str) -> dict[str, float]:
    """Convert Ollama timings into the standard metric dict.

    ``peak_vram_mib``/``power_watt_avg`` are not reported in Ollama stdout and
    are left as zero sentinels; adapters should fill them from external sensors.
    """
    timings = parse_ollama_timings(stdout)
    ttft_ms = (
        timings["load_ns"] + timings["prompt_eval_duration"]
    ) / 1_000_000.0
    prefill_tok_s = (
        timings["prompt_eval_count"] * 1e9 / timings["prompt_eval_duration"]
    )
    decode_tok_s = timings["eval_count"] * 1e9 / timings["eval_duration"]
    return {
        "ttft_ms": ttft_ms,
        "prefill_tok_s": prefill_tok_s,
        "decode_tok_s": decode_tok_s,
        "peak_vram_mib": 0,
        "power_watt_avg": 0.0,
    }
