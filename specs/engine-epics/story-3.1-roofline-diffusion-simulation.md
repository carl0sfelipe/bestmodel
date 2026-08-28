# Story 3.1 — Estimador roofline de difusão + simulação da Story 1.4 [Épico 3]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Célula simulada NUNCA é measured_signed: source_class='derived' com
  source_url='roofline:estimate_diffusion_step#v1' — honestidade de fonte é
  inegociável.
- Toda constante de calibração é nomeada e documentada (nenhum número mágico);
  gaps declarados no código, não escondidos.
- Determinismo total: ids uuid5 (re-run = upsert no mesmo id, nunca duplica).
- Não invente spec de GPU (ler do catálogo gpu_model), nem número além dos listados.

## Dados verificados (copie SEM ALTERAR)
- Catálogo (infra/seed/gpu_models.json, fonte do script): gpu-rtx-3090 =
  936 GB/s, fp16 35.58 TFLOPS (35.6 na fixture de teste, convergem), 24576
  MiB; gpu-rtx-4090 = 1008 GB/s, fp16 82.58 TFLOPS (convenção com acumulador
  FP32 — a fixture de teste usa 165 dense; documento por quê).
- Roofline: t_step = max(FLOPs/(fp16·dtype·U_COMPUTE), W_bytes/(BW·U_MEMORY));
  T = (W/8)(H/8)((F-1)/4+1) = 160·90·21 = 302400 p/ 720p81f;
  FLOPs = 2·N·T + 4·f_attn·L·T²·d; U_COMPUTE=0.5; U_MEMORY=0.8;
  f_attn=0.05 CALIBRAÇÃO (refit contra células reais da 1.4).
- FP8 dobra compute SÓ em silício nativo (4090 sm89 sim; 3090 sm86 NÃO —
  gotcha ANEXO-A); pesos 3090 = Q8 GGUF dequant fp16.
- Banda de plausibilidade (fonte: pesquisa 27/08 community): 720p81f20steps
  fp16 em 1×3090 = 2–8h; 4090 fp8 = 15–60min.
- Wan 2.2 14B arquitetura (40L, hidden 5120, 14B ativa, 2025-07) = GAP
  DECLARADO: conferir config.json do HF antes de exposição pública.

## ENTREGÁVEIS
1. `packages/roofline-kernel/src/estimate_diffusion_step.py`: DiffusionWorkload,
   derive_latent_tokens, derive_step_flops, estimate_seconds_per_step (roofline
   max), estimate_seconds_per_clip (declara exclusão de text-encoder+VAE).
2. Fixture RTX_3090 em tests/hardware_fixtures.py + 8 testes (tokens/flops/
   segundos hand-computed EXATOS; ratio 3090/4090 = 165/35.6 banda 3.0–5.5;
   fp8 nativo 2× no 4090 e NEUTRO no 3090; plausibilidade 2–8h e 15–60min;
   linear em steps; GPU sem fp16 rejeitada).
3. `infra/scripts/simulate_video_cells.py` (simulação da 1.4): lê specs do
   catálogo, roda o estimador p/ 3090 (Q8/fp16-compute) e 4090 (fp8), upsert
   idempotente (uuid5) de model_release wan22 + cenário vídeo + hardware +
   run validated/derived com escalares; exporta runs JSON leaderboard-shaped
   (--export) para o `canirunit suggest`.
4. Fix colateral pago pela simulação: is_feasible aceita peak None (célula
   vídeo sem métrica LLM não pode ser "inviável") + teste.

## COMMIT
packages/ + infra/ + specs/ com identidade dev@local.

## VERIFICAÇÃO
Oráculo abaixo verde (loop completo reproduzível: PG limpo → derived cells →
suggest mostra derived com recipe e horas plausíveis).

## Oraculo
- comando: docker rm -f canirunit-migtest-pg >/dev/null 2>&1; sleep 2; docker run -d --rm --name canirunit-migtest-pg -e POSTGRES_USER=inference_vein -e POSTGRES_PASSWORD=inference_vein -e POSTGRES_DB=inference_vein -p 5439:5432 postgres:16-alpine >/dev/null && sleep 5 && cd ~/Work/CanIRunIt && export DATABASE_URL="postgresql://inference_vein:inference_vein@localhost:5439/inference_vein" && export PATH="$HOME/.cargo/bin:$PATH" && uv run python infra/scripts/migrate.py >/dev/null && uv run python infra/seed/load_seed.py >/dev/null && uv run python infra/scripts/simulate_video_cells.py --export /tmp/s31_runs.json | grep -q 'gpu-rtx-3090: 3.8' && cargo build -q -p canirunit && ./target/debug/canirunit suggest --gpu gpu-rtx-3090 --task seconds_per_clip --runs /tmp/s31_runs.json | grep -q '"source_class": "derived"' && ./target/debug/canirunit suggest --gpu gpu-rtx-3090 --task seconds_per_clip --runs /tmp/s31_runs.json | grep -q 'wan22-flf2v-720p-81f-v1' && uv run pytest -q 2>&1 | tail -1 | grep -qE '^[0-9]+ passed' && docker exec canirunit-migtest-pg psql -U inference_vein -d inference_vein -t -A -c "SELECT count(*) FROM benchmark_run WHERE source_class='derived';" | grep -qx 2 && docker rm -f canirunit-migtest-pg >/dev/null && echo ORACULO-3.1-VERDE
