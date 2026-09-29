---
id: 2026-09-29-wall-ignora-rig-e-404-seco
titulo: "O que roda na minha 3090?" devolve ranking global; slug adivinhado dá 404 seco
data: 2026-09-29
regra: falha-de-uso-vira-incidente
status: correção-em-PR
---

## Sintoma
- `/wall?rig=rtx-3090-24gb&as=agent` (URL indicada pelo próprio /hardware) ignora o rig: top global com tinystories em CPU a 36.715 tok/s.
- `/m/gemma-4-12b-it` e `/m/qwen3-8-27b` → 404 sem sugestão (slugs reais têm prefixo do dono).

## Causa
- Ramo agente de app/wall/page.tsx não lia searchParams (só o cliente filtrava).
- app/m/[slug]/page.tsx chamava notFound() sem sugerir.

## Correção (serviço)
Filtro puro compartilhado (lib/wall-filter.ts) aplicado antes do sort; ranking padrão sem modelos < 1B/toy; rig inexistente lista 10 parecidos. `sugerirSlugs`: sufixo exato → 308, senão página com 5 sugestões.

## Pendente
Página de sugestões responde 200 (soft-404); trocar por status 404 real.
