# Story 1.2 — Execução headless real + métricas de vídeo [Épico 1]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real no código Rust existente.
- Nenhuma dependência nova no Cargo.toml (reqwest/serde_json/std já cobrem tudo).
- NÃO reutilizar campos tok/s para vídeo (AD-1 do PRD): segundos/clipe, it/s de sampling e
  frames/s vivem SÓ nos campos novos `seconds_per_clip`/`it_per_s`/`frames_per_s`.
- Report LLM (schema 0.9.0) deve permanecer BYTE-IDÊNTICO: campos novos são Option com
  skip_serializing_if — `--runtime mock --output` NÃO pode conter "seconds_per_clip".
- Não invente número, flag, formato de evento ou fonte além dos listados abaixo.

## Dados verificados (copie SEM ALTERAR)
- Fonte do formato de eventos: github.com/Comfy-Org/comfy-cli, comfy_cli/command/run/execution.py
  (lido 26/08/2026): modo máquina = eventos NDJSON; `progress` carrega value/max por nó
  (throttle 10 Hz); `--verbose` é no-op em modo máquina; pretty mode usa rich bars (não
  parseável). Envelope aceito: {"type": t, "data": {...}} (tolerante a flatten).
- comfy-cli flags (cmdline.py): `comfy --json-stream run --workflow <p> --wait --timeout <s>`
  (timeout default 120 é POR EVENTO, não wall-clock); `comfy launch --background`; `comfy stop`.
- ComfyUI default: servidor em http://127.0.0.1:8188; /system_stats responde 200 quando vivo.
- nvidia-smi VRAM: `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits` (MiB por GPU).

## ENTREGÁVEIS
1. `comfyui_adapter.rs`: `ComfyRunMetrics` (seconds_per_clip, seconds_sampling, it_per_s,
   frames_per_s, sampler_steps, peak_vram_mib); `parse_comfy_events` (função pura sobre
   [(ts, evento)]); `sampler_node_ids` (class_type contém "Sampler" ou termina em
   "ToVideo" — cobre WanFirstLastFrameToVideo e KSampler*, exclui VAEDecode);
   `execute_comfy_workflow` (probe :8188 → launch --background se preciso → run
   --json-stream --wait com timestamps por linha → poller nvidia-smi 250ms pico → stop
   se fomos nós que lançamos); `print_run_metrics` em Plain Text.
2. `MetricFields` + 3 campos Option (skip_serializing_if) — reports LLM inalterados.
3. main.rs: flag `--execute`; run_comfy_plan com caminho de execução + report de vídeo
   (ScenarioFields zerados; campos de vídeo Some(...); artifact runtime_stdout do evidence).
4. Fixture congelada `tests/fixtures/comfy-events.ndjson` (11 eventos; janela sampler
   1.5→3.5s, 20 steps, clip 0→4s, 81 frames) e `tests/comfyui_metrics.rs` com números
   EXATOS: seconds_per_clip=4.0, seconds_sampling=2.0, it_per_s=10.0, frames_per_s=20.25,
   sampler_steps=20; VAEDecode/UNETLoader fora dos samplers; stream sem sampler → wall só;
   stream vazio/1-evento → erro.
5. GAP declarado: o envelope NDJSON real do comfy-cli (--json-stream) será gravado e
   conferido no rig na Story 1.4 (validação de log real); o parser é tolerante a envelope
   {"type","data"} e flatten por causa disso.

## COMMIT
commitar cli/benchmark-probe/ + specs/story-1.2-comfyui-execution-metrics.md
com identidade dev@local.

## VERIFICAÇÃO
cargo test verde (suítes novas + antigas) e oráculo abaixo verde. Smoke real 320×320/25f
(tempo real > 0) acontece no rig na Story 1.4 — nesta máquina, --execute sem comfy-cli
deve falhar LIMPO (exit ≠ 0, mensagem dizendo que comfy-cli não está no PATH).

## Oraculo
- comando: cd cli/benchmark-probe && cargo build -q && B=../../target/debug/benchmark-probe && S='{"model":"wan22-i2v-flf2v","width":1280,"height":720,"frames":81,"steps":20,"cfg":3.5,"seed":42,"first_image":"in/first.png","last_image":"in/last.png"}' && cargo test -q --test comfyui_metrics 2>&1 | grep -q 'test result: ok. 5 passed' && ("$B" --runtime comfyui --execute --scenario "$S" --recipe recipes/wan22-flf2v-720p-81f-v1.json >/dev/null 2>&1; test $? -ne 0) && rm -f /tmp/s12_mock.json && "$B" --runtime mock --output /tmp/s12_mock.json >/dev/null 2>&1 && ! grep -q seconds_per_clip /tmp/s12_mock.json && grep -q peak_vram_mib /tmp/s12_mock.json && cargo test -q 2>&1 | grep -c 'test result: ok' | grep -qx '8'
