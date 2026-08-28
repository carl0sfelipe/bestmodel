# Story 2.3 — Confiança documentada: função pura + testes de propriedade [Épico 2]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real.
- Função PURA (AD-5): idade entra como DADO (age_days no run), nunca relógio
  do sistema — determinismo absoluto.
- Nenhuma dependência nova (sweeps pseudo-aleatórios via LCG próprio).
- Não invente número, fator, peso ou fonte além dos listados.

## Dados verificados (copie SEM ALTERAR)
- Fórmula do SPINE §4 (aprovada): confidence = clamp01(base × (0.4+0.6·n_bonus)
  × fresh × var_pen) × tier; n_bonus = 1−e^(−n/3); fresh = e^(−age/180);
  var_pen = 1−min(cv, 0.5), cv = variância/média; tiers exact 1.0 /
  same_family 0.7 / roofline 0.5.
- Pesos base (FR-3): measured_signed 0.9 | reported 0.6 | harvested 0.4 |
  derived 0.4 | desconhecida 0.3. Ordem canônica em SOURCE_WEIGHT_ORDER.
- mean ≤ 0 ⇒ cv no teto 0.5 (conservador, documentado no código).

## ENTREGÁVEIS
1. `cli/canirunit/src/confidence.rs`: tabela documentada, MatchTier,
   ConfidenceInputs, `confidence()` pura (arredondada 4 casas), Lcg p/ sweeps.
2. lib.rs: RunEntry += age_days (Option, default 0 = fixture fresco; exportador
  /harvester preenche); suggest() usa a função COMPLETA (idade = mais antigo do
   grupo, conservador; tier Exact; substitui a v1 da 2.2).
3. `tests/confidence_property_test.rs` (quickcheck-style via Lcg, 200–1000
   casos por propriedade): monotonamente não-decrescente em n_runs; não-crescente
   em variância; não-crescente em idade; limitada em [0,1]; exact ≥ family ≥
   roofline; ordem de classes medida > reportada > colhida > desconhecida.

## COMMIT
cli/canirunit + specs/ com identidade dev@local.

## VERIFICAÇÃO
cargo test do crate verde (6 suggest + 6 property); oráculo abaixo verde.

## Oraculo
- comando: cd ~/Work/CanIRunIt && export PATH="$HOME/.cargo/bin:$PATH" && cd cli/canirunit && cargo test -q 2>&1 | grep -q 'test result: ok. 6 passed' && cargo test -q --test confidence_property_test 2>&1 | grep -q 'test result: ok. 6 passed' && cargo test -q --test suggest_test 2>&1 | grep -q 'test result: ok. 6 passed'
