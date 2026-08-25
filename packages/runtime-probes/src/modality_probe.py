"""L02 wave A: vision-modality probe over local VLMs via the Ollama HTTP API.

Judges one fixed screenshot through a candidate VLM and reports honest,
observed numbers: total latency, whether the response carries a recognizable
verdict (``parsable``), and the response size. ``quality_verdict`` is recorded
as observed data (the raw verdict the VLM emitted) -- never turned into a
subjective quality score.

Third-party network calls are allowed only in this module (same rule as
``ollama_probe.py``). The measurement protocol is the L01/L02 one: one
discarded warmup run, then N measured repeats per candidate with mean/std
latency. Tests never hit the network (injectable ``http_post``).
"""

from __future__ import annotations

import argparse
import base64
import json
import statistics
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[3] / "machine-local-modality-winners.json"
)

JUDGE_PROMPT = (
    "Você é um juiz de interface (UI) de um assistente local de tarefas. "
    "Julgue a imagem desta interface em exatamente 3 frases. "
    "Termine com o veredito final APROVADO ou REVISAR."
)

VERDICT_APPROVED = "APROVADO"
VERDICT_REVISE = "REVISAR"
VERDICT_UNKNOWN = "desconhecido"


def recognize_verdict(response_text: str) -> str | None:
    """Return the recognized verdict token, or ``None`` when the response
    carries no recognizable verdict (the run is then ``parsable=False``)."""
    upper = response_text.upper()
    if VERDICT_APPROVED in upper:
        return VERDICT_APPROVED
    if VERDICT_REVISE in upper:
        return VERDICT_REVISE
    return None


def extract_response_text(raw: bytes) -> str:
    """Pull the ``response`` field out of an Ollama /api/generate payload;
    fall back to the raw decoded text when it is not JSON."""
    text = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    response = payload.get("response")
    return response if isinstance(response, str) else text


@dataclass(frozen=True)
class VisionJudgmentRun:
    """One judged response.

    ``quality_verdict`` is observed data -- the raw verdict the VLM emitted --
    not a quality metric we compute.
    """

    latency_total_ms: float
    parsable: bool
    response_size_chars: int
    quality_verdict: str


@dataclass(frozen=True)
class VisionCandidateResult:
    """Aggregate of one candidate's discarded warmup + N measured runs."""

    model: str
    mean_latency_ms: float
    std_latency_ms: float
    parsable: bool
    reps: int
    observed_verdicts: tuple[str, ...]


HttpPost = Callable[[str, bytes], bytes]


def _default_http_post(url: str, body: bytes) -> bytes:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


class VisionJudgeProbe:
    """Judges one fixed screenshot through a local VLM via the Ollama HTTP API.

    ``http_post`` is injectable so tests can fake the network call.
    """

    runtime = "ollama"

    def __init__(
        self,
        model: str,
        *,
        image_base64: str,
        prompt: str = JUDGE_PROMPT,
        api_url: str = OLLAMA_API_URL,
        http_post: HttpPost | None = None,
    ) -> None:
        self.model = model
        self.image_base64 = image_base64
        self.prompt = prompt
        self.api_url = api_url
        self._http_post = http_post or _default_http_post

    def judge_once(self) -> VisionJudgmentRun:
        """Send one judgment request and measure its wall-clock latency."""
        payload = {
            "model": self.model,
            "prompt": self.prompt,
            "images": [self.image_base64],
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        start = time.perf_counter()
        raw = self._http_post(self.api_url, body)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        response_text = extract_response_text(raw)
        verdict = recognize_verdict(response_text)
        return VisionJudgmentRun(
            latency_total_ms=elapsed_ms,
            parsable=verdict is not None,
            response_size_chars=len(response_text),
            quality_verdict=verdict if verdict is not None else VERDICT_UNKNOWN,
        )

    def probe(self, reps: int = 3) -> VisionCandidateResult:
        """Run the L01/L02 protocol: one discarded warmup, then ``reps``
        measured runs. The candidate is ``parsable`` only when every measured
        run carried a recognizable verdict."""
        self.judge_once()  # warmup: never trust cold-start numbers
        latencies: list[float] = []
        verdicts: list[str] = []
        parsable_runs = 0
        for _ in range(reps):
            run = self.judge_once()
            latencies.append(run.latency_total_ms)
            verdicts.append(run.quality_verdict)
            if run.parsable:
                parsable_runs += 1
        mean = statistics.fmean(latencies)
        std = statistics.stdev(latencies) if reps > 1 else 0.0
        return VisionCandidateResult(
            model=self.model,
            mean_latency_ms=mean,
            std_latency_ms=std,
            parsable=parsable_runs == reps,
            reps=reps,
            observed_verdicts=tuple(verdicts),
        )


def select_winner(
    results: Sequence[VisionCandidateResult],
) -> VisionCandidateResult | None:
    """Winner rule (documented): a parsable candidate beats any faster
    candidate that is not parsable. Among parsable candidates, the lowest mean
    latency wins. When no candidate is parsable there is no winner (``None``)
    rather than a fabricated one, so oracfit's queue can fall back to cloud."""
    parsable = [result for result in results if result.parsable]
    if not parsable:
        return None
    return min(parsable, key=lambda result: result.mean_latency_ms)


def candidate_cell(result: VisionCandidateResult) -> dict[str, object]:
    """Per-candidate cell in the decision file. ``qualidade_veredito`` records
    the observed verdicts; it is data, not a metric."""
    return {
        "modelo": result.model,
        "latencia_media_ms": round(result.mean_latency_ms, 2),
        "latencia_std_ms": round(result.std_latency_ms, 2),
        "parsable": result.parsable,
        "reps": result.reps,
        "qualidade_veredito": list(result.observed_verdicts),
    }


def build_vision_cell(
    results: Sequence[VisionCandidateResult],
) -> dict[str, object]:
    winner = select_winner(results)
    if winner is None:
        nota = (
            "Nenhum candidato retornou um veredito reconhecivel (parsable); "
            "winner null para a fila local decidir o fallback."
        )
    else:
        nota = (
            f"Vencedor: {winner.model}. Criterio: veredito reconhecivel "
            "(parsable) primeiro, depois menor latencia media. "
            f"Latencia media {winner.mean_latency_ms:.0f} ms +/- "
            f"{winner.std_latency_ms:.0f} ms em {winner.reps} repeticoes."
        )
    return {
        "winner": winner.model if winner else None,
        "candidatos": [candidate_cell(result) for result in results],
        "nota": nota,
    }


def run_vision_probe(
    candidates: Sequence[str], *, reps: int, image_path: str | Path
) -> dict[str, object]:
    """Measure every candidate and assemble the per-modality decision document.
    The structure keys by modality so tts/asr cells can be added later."""
    image_base64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    results: list[VisionCandidateResult] = []
    for model in candidates:
        probe = VisionJudgeProbe(model, image_base64=image_base64)
        results.append(probe.probe(reps=reps))
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "hardware": "Apple M4 16GB",
        "modalidades": {"vision": build_vision_cell(results)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="modality_probe",
        description=(
            "Probe local models per modality (wave A: vision) and write "
            "machine-local-modality-winners.json."
        ),
    )
    subparsers = parser.add_subparsers(dest="modality", required=True)
    vision = subparsers.add_parser("vision", help="Vision-modality probe")
    vision.add_argument(
        "--candidates", required=True, help="Comma-separated model ids"
    )
    vision.add_argument("--reps", type=int, default=3, help="Measured repeats")
    vision.add_argument("--image", required=True, help="Path to the screenshot")
    vision.add_argument(
        "--output", default=str(DEFAULT_OUTPUT_PATH), help="Output JSON path"
    )
    args = parser.parse_args(argv)

    if args.modality != "vision":
        parser.error(
            f"modality '{args.modality}' is not implemented yet (wave A = vision)"
        )
    if args.reps < 1:
        parser.error("--reps must be >= 1")

    candidates = [
        name
        for name in (part.strip() for part in args.candidates.split(","))
        if name
    ]
    if not candidates:
        parser.error("--candidates must list at least one model")

    document = run_vision_probe(
        candidates, reps=args.reps, image_path=args.image
    )
    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
