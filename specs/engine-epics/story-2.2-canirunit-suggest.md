# Story 2.2 — `canirunit suggest` (exact_gpu) [Épico 2]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- ZERO LLM no caminho da recomendação (AD-5): explicação é template
  determinístico; todo número da saída deriva matematicamente dos runs de entrada.
- 0 runs ⇒ classe `unknown` + explicação honesta (NUNCA inventar sugestão).
- Nenhuma dependência nova além de serde/serde_json (já no workspace).
- Não invente número, fórmula, peso ou fonte além dos listados.

## Dados verificados (copie SEM ALTERAR)
- Peso base por classe (PRD FR-3, refinado na Story 2.3): measured_signed 0.9,
  reported 0.6, harvested 0.4, derived 0.4, desconhecida 0.3.
- Confiança v1 = base × (0.4 + 0.6 × (1 − e^(−n/3))) — documentada no código
  como v1, estendida (freshness/variância/match tier) na Story 2.3.
- Direção das métricas: decode_tok_s/prefill_tok_s/frames_per_s/it_per_s =
  maior melhor; ttft_ms/seconds_per_clip = menor melhor.
- Média PONDERADA por trust_score do run (default 1.0 quando ausente).

## ENTREGÁVEIS
1. `cli/canirunit` (lib+bin, membro do workspace): `RunEntry` (shape
   leaderboard), `suggest(gpu, métrica, runs) -> SuggestOutcome` função pura;
   agrupamento por (model_release_id, recipe_id); expectativa = média ponderada
   por trust; variância ponderada; classe do grupo = mais forte presente;
   ranking pela direção da métrica; explicação template com n_runs, variância e
   fonte; match_class exact_gpu | unknown.
2. CLI `canirunit suggest --gpu --task --runs <runs.json>`; exit 3 quando
   unknown (script-friendly); saída JSON pretty.
3. Fixtures: runs-3090.json (3 runs LLM com trusts 0.5/1.0/0.5 sobre
   88/92/96 → esperado EXATO 92.0, variância 8.0; + 1 run vídeo com recipe;
   + 1 run 4090 que NUNCA vaza) e runs-empty.json.
4. Testes: média ponderada exata; variância exata; vídeo lower-is-better com
   recipe_id; unknown honesto; métrica inválida erro; e2e CLI verde + exit 3.

## COMMIT
cli/canirunit + Cargo.toml workspace + specs/ com identidade dev@local.

## VERIFICAÇÃO
cargo test -q no crate verde; oráculo abaixo verde.

## Oraculo
- comando: cd ~/Work/CanIRunIt && export PATH="$HOME/.cargo/bin:$PATH" && cargo build -q -p canirunit && B=target/debug/canirunit && "$B" suggest --gpu gpu-rtx-3090 --task decode_tok_s --runs cli/canirunit/tests/fixtures/runs-3090.json | grep -q '"expected": 92.0' && "$B" suggest --gpu gpu-rtx-3090 --task seconds_per_clip --runs cli/canirunit/tests/fixtures/runs-3090.json | grep -q 'wan22-flf2v-720p-81f-v1' && ("$B" suggest --gpu gpu-rtx-5090 --task decode_tok_s --runs cli/canirunit/tests/fixtures/runs-empty.json >/tmp/s22.out; test $? -eq 3) && grep -q '"match_class": "unknown"' /tmp/s22.out && cd cli/canirunit && cargo test -q 2>&1 | grep -q 'test result: ok. 6 passed'
