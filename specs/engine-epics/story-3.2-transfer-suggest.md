# Story 3.2 — Transferência cross-hardware no suggest [Épico 3]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Número transferido NUNCA é medição: source_class='derived', explicação cita
  GPU âncora, fator numérico e disclaimer "NOT measured on this GPU".
- Runs exatos da própria GPU SEMPRE vencem a transferência (nunca sombrear
  medição com derivação).
- Sem --gpus (ou GPU sem specs) o comportamento da 2.2 permanece: unknown.
- Não invente spec de GPU (gpu_transfer_specs.json documenta fonte catálogo +
  família/datasheet), nem fator fora da álgebra roofline.

## Dados verificados (copie SEM ALTERAR)
- Fator (workload compute-bound, calibração CANCELA na razão):
  eff(gpu) = fp16_tflops × (2 se fp8 nativo senão 1); time_factor =
  eff(âncora)/eff(alvo); métrica de taxa usa 1/time_factor; variância escala
  fator². Assunção declarada: cada GPU roda seu melhor caminho de pesos
  (igual ao simulador 3.1).
- Specs (catálogo gpu_model + família de arquitetura datasheet): 3090
  ampere 35.58 sem fp8 (sm86); 4090 ada 82.58 fp8 (sm89); 4080 ada 48.74
  fp8; 4070-ti-super ada 44.1 fp8; 5090 blackwell 104.8 fp8.
- Tiers (confidence.rs 2.3): same_arch_family = SameFamily 0.7;
  roofline_transfer = Roofline 0.5.
- Células derived da simulação 3.1 (provenância dos fixtures): 4090 =
  2957.815 s/clipe (fp8); 3090 direto = 13729.981 s (fp16-compute).
- PROPRIEDADE FORTE: transferir 4090→3090 deve reproduzir o estimador direto
  da 3090 com erro < 0,1% (fator 165.16/35.58 = 4.642; 2957.815×4.642 ≈
  13729.9).

## ENTREGÁVEIS
1. `cli/canirunit/src/transfer.rs`: GpuTransferSpec, effective_tflops,
   time_factor, transfer_suggestions (âncora única por (model, recipe):
   classe mais forte → mais runs → id alfabético, determinístico; variância×
   fator²; tier por família), TransferredSuggestion.
2. `suggest_with_transfer` no lib.rs: exato vence; sem specs/sem âncora →
   unknown preservado; match_class same_arch_family | roofline_transfer;
   explicação de outcome com disclaimer.
3. CLI: flag opcional `--gpus gpu_transfer_specs.json` (fixture curada com
   as 5 GPUs acima).
4. `tests/transfer_test.rs` (8): propriedade <0,1% vs estimador; explicação
   com âncora+fator 4.64+disclaimer; same_arch_family (4070ti←4090);
   métrica de taxa inverte direção; exato nunca sombreado; sem specs =
   unknown + API 3-arg intacta; fp8 só em silício nativo; e2e CLI com/sem
   --gpus (exit 3).

## COMMIT
cli/canirunit + specs/ com identidade dev@local.

## VERIFICAÇÃO
cargo test do crate verde; oráculo abaixo verde.

## Oraculo
- comando: cd ~/Work/CanIRunIt && export PATH="$HOME/.cargo/bin:$PATH" && cd cli/canirunit && cargo test -q --test transfer_test 2>&1 | grep -q 'test result: ok. 8 passed' && cd ~/Work/CanIRunIt && cargo build -q -p canirunit && ./target/debug/canirunit suggest --gpu gpu-rtx-3090 --task seconds_per_clip --runs cli/canirunit/tests/fixtures/runs-derived-4090.json --gpus cli/canirunit/gpu_transfer_specs.json | grep -q '"match_class": "roofline_transfer"' && ./target/debug/canirunit suggest --gpu gpu-rtx-3090 --task seconds_per_clip --runs cli/canirunit/tests/fixtures/runs-derived-4090.json --gpus cli/canirunit/gpu_transfer_specs.json | grep -q 'factor 4.64' && cd cli/canirunit && cargo test -q 2>&1 | grep -q 'test result: ok. 6 passed'
