# cli/benchmark-probe — Map

Rust CLI: the measurement agent a user's machine (or their AI agent) runs.
Workspace member of the root Cargo workspace — binaries land in repo-root
`target/`, not here. Non-interactive by design (agent-friendly); plain-text
user output + machine-readable artifacts.

| Module | Content |
|---|---|
| `main.rs` | arg parsing (flags, no subcommands yet), orchestration, usage text |
| `lib.rs` | exposes modules + `Runtime` enum for integration tests |
| `collect_system_topology.rs` | GPU/CPU/OS fingerprint — macOS via sysctl/system_profiler; **Linux gap (backlog A4)** |
| `detect_runtime_installations.rs` | PATH scan for llama-cli/ollama + versions |
| `execute_benchmark_scenario.rs` | scenario → engine run; mock mode built-in |
| `parse_runtime_output.rs` | engine stdout → Metrics (mirror of packages/runtime-probes logic) |
| `sign_submission_payload.rs` | report build, canonical JSON, SHA-256 digest, Ed25519 sign; **PKCS8 v1 PEM hand-encoded (decision D6 — don't "modernize" back to crate default)** |
| `upload_benchmark_report.rs` | nonce fetch + multipart POST |
| `tests/cli_smoke.rs` | drives the real binary end-to-end |

Key flags: `--runtime mock|llama_cpp|ollama`, `--output <path>` (writes report
+ .digest + .signature + .artifact_0.txt), `--report-runtime <engine>` (override
reported engine, e.g. mock rehearsals), `--artifact`, `--sign`, `--upload`.
Env: `BENCHMARK_PROBE_KEY_PATH` (default ~/.config/benchmark-probe/ed25519.pem),
`BENCHMARK_PROBE_API_URL` (default http://localhost:8000).

Future = CLI v2 Local Lab (spec specs/en/L01-cli-v2-local-lab.md): plan → lab →
report → contribute commands; borrow llama-optimus/throughput-lab/picchio
patterns (docs/research-2026-08.md).
## Settlement uploads (S16/S21)

`--settle-claim <id>` binds the uploaded run to one of the account's open
claims. It requires `--upload` and `BENCHMARK_PROBE_API_TOKEN` (an agent
token from `POST /v1/auth/tokens`); anonymous uploads never settle. The API
responds with `linked_claim_id`; settlement completes server-side only after
the intake worker validates the run.


## Change checklist

- `build_video_report`/`build_video_evidence` (main.rs) re-declaram o shape de
  cenário/métricas de vídeo: campo novo no contrato ⇒ `domain-schema`
  (benchmark_report/scenario/metrics) + main.rs + evidence keys do worker na
  mesma commit — o NDJSON precisa das linhas `metric <chave> <valor>` que o
  worker exige, senão a run morre em `missing_evidence`.
- Canonical JSON / digest / assinatura: o serviço verifica sha256 do JSON
  canonizado (sort_keys, separators) + Ed25519 sobre o digest STRING — mexer
  aqui quebra a verificação no API; o formato §9.3 é pinado por testes.
- PEM PKCS8 v1 é hand-encoded por decisão D6 — não "modernize" com default de
  crate.
