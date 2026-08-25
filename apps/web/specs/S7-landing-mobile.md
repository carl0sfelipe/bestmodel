# S7 — Landing mobile (site/m/index.html)

Depende de: S2, S3, S4 (padrões de S5/S6 ajudam; não são bloqueio).
Produz: `site/m/index.html`, `site/assets/mobile-page.mjs`, `check.mjs` alvo
`page:mobile`.

> Contexto de execução (dispatch): o workdir é a raiz do monorepo bestmodel;
> TODOS os caminhos deste spec são relativos a `apps/web/` — trabalhe
> dentro dele. Leia antes: `apps/web/PROMPT-EXECUTOR.md` e
> `apps/web/CONTRATO-GLOBAL.md`. Não invente número, prazo ou fonte além
> dos listados em "Dados verificados"; o que faltar fica [A DEFINIR]. NUNCA use stub ou `declare const` como workaround de import — importe de verdade. Oráculo verde => atualizar ESTADO.md + UM commit
> `feat(web-S7): ...`; mate qualquer servidor que subir.

## Objetivo

Portar `prototypes/mobile-landing.html` — landing mobile-first para tráfego
pago, com switcher entre as duas jornadas, bottom bar fixa com CTA e sheets de
seleção — para dados reais. Mesma lógica das páginas desktop, apresentação
comprimida.

## Dados verificados (única fonte de números)

- Estrutura do protótipo (verificada no fonte): `#main` renderizado por JS em
  painéis; jornada goal: `p-hero` (mad-lib), `p-universe` (constelação),
  `p-spectrum` (`#specTrack`), `p-td` (test drive), `p-recs` (3 recs),
  `p-cohort` ("People with {rig} are running these"), `p-prompt`; jornada
  hardware: `p-hero` detect, `p-envelope`, `p-cats`, `p-catalog`
  (`#catScroll` horizontal), `p-td`, `p-cohort`. Compartilhados: `#sheet`
  (bottom sheet), `#toast`, bottom bar `#bottomStatus` + `#mainCta`
  (`#ctaText` "See models that fit"), `#finalPanel` com eco SVG e install.
- Números exibidos: só `data/derived/*` + engine.

## Saídas exatas

`site/m/index.html`, `site/assets/mobile-page.mjs`, subcomando `page:mobile`.

## Spec

1. Manter a arquitetura do protótipo: estado central + re-render dos painéis
   por jornada; switcher no topo alterna goal/hardware sem perder seleções.
2. Sheets: picker de rig (topRigs com runCount), picker de output
   (text/code ativos; demais desabilitados §7.6), picker de modelo no
   test-drive.
3. Painéis usam engine/ui/load-data idênticos ao desktop: fit, tokS com
   basisBadge, coorte real (top 5 do rig + n), universo com contagens de
   stats.json.
4. Bottom CTA: rola para o próximo painel relevante da jornada corrente
   (comportamento do protótipo); rótulos do protótipo mantidos.
5. Performance: é página de ads — sem imagem externa, fonts com
   `display=swap` (já no protótipo), JSONs carregados uma vez; nada de
   listeners de scroll pesados além dos existentes.
6. Rodapé/final: install block `hidden` (§7.3); attributionFooter(stats).
7. `check.mjs page:mobile`: arquivo existe; contém `main`, `sheet`,
   `bottomStatus`, `mainCta`; importa engine.mjs e load-data.mjs; proibido
   `const MODELS` e contagens fake ("14,320", "2,400+", "1,247"); assets
   referenciados existem.

## O que NÃO fazer

- Não fazer versão "responsiva do desktop" — esta página é um artefato
  próprio, o protótipo mobile é a spec.
- Não adicionar formulário de e-mail/capture (não existe no protótipo).
- Não duplicar CSS que já está no theme.css.

## Verificação

```bash
node scripts/check.mjs page:mobile && node scripts/check.mjs all
python3 -m http.server 8901 --directory . &
curl -s -o /dev/null -w "%{http_code}" http://localhost:8901/site/m/index.html  # 200
```

Aprovação visual (viewport mobile ~390px): fica a cargo do orquestrador
pós-batch — registre "aprovação visual: pendente-humano" no ESTADO.md e siga
para o commit.

## ORÁCULO

- comando: cd apps/web && node scripts/check.mjs page:mobile
- exit esperado: 0 (antes do trabalho: exit 1, alvo desconhecido)
