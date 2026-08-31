# Resultado

## Entregue

- Next.js 15 App Router and TypeScript scaffold.
- `models.json`, `pool.json`, `hardware.json`, and `stats.json` copied verbatim to `public/data/derived/`.
- Static console copied verbatim to `public/console/` and `llms.txt` copied to `public/llms.txt`.
- Typed engine with `MIN_RUNS_MEASURED = 3`, derived loading, basis classification, cell/model/rig join, top-rig ordering, and number formatters.
- Home, Hardware, The wall, model routes, Track record, Mural SAMPLE preview, Console entry, robots, and sitemap.
- Separate Wall controls for hardware, category, and sort. Each displayed pool row has a measured/reported badge.
- Responsive layout with one-column mobile grids and scroll-contained data tables.

## Divergencias encontradas

- The brief identifies the product as `bestmodel.run`, while the reference HTML and theme copy still use the legacy `can-i-run-it` wordmark and some legacy URLs/copy. The new app uses `bestmodel.run` in its application shell while retaining source data verbatim.
- The reference engine declares `API_BASE` as `https://www.localmaxxing.com/api`, while the brief specifies `https://api.bestmodel.run`. No API call was added to avoid inventing a runtime contract; the copied console remains unchanged.
- The reference page samples contain sample-specific prose and historical snapshot claims that are not in `FACTS.md`. The app uses current derived JSON values for the product pages and keeps only the mural's sample rows marked `SAMPLE`.

## Verification

- `npm run build` is the required final build check.
- The static data copies are intended to pass `diff -q` against their reference counterparts.

## claude-design mining

| Página | Elemento | Decisão | Por quê |
|---|---|---|---|
| index | Hero editorial com promessa, ações e explicação de proveniência | adotado parcialmente | Mantém a leitura da base e reforça source/basis sem importar números ou lógica da referência. |
| index | Configurador inline de intent, rig, quantização e contexto | rejeitado | A lógica e os dados do Claude Design não são fonte autorizada; a categoria do app permanece `chat|code`. |
| hardware | Contexto de máquina antes dos dados e cartões clicáveis | adotado | A base já usa cards e filtro; `runCount` continua a ordenação, com RTX 3090 no topo pelos dados oficiais. |
| hardware | Grupos/tabelas derivados de `standings.json` | rejeitado | Os JSONs do Claude Design são proibidos como fonte de números. |
| leaderboard / wall | Proveniência visível por linha e controles de leitura | adotado | O Wall mantém filtros separados de hardware, categoria e ordenação, com `measured`/`reported` por célula. |
| leaderboard / mural | Form modal com grounds, detalhe, evidência e validação | adotado | A mural usa a estrutura UX, mas somente com `numbers_unreal`, `wrong_hardware`, `duplicate`, `other`; segue SAMPLE e não faz POST. |
| leaderboard | Classes `measured_signed`, `community` e endpoint de report | rejeitado | Não são bases/categorias da API desta base; o POST real continua no console copiado. |
| track-record | Roles, atos verificados e ledger de contributors | rejeitado | `contributor-points.json` do Claude Design não pode entrar no app, e seus thresholds não estão nos fatos permitidos. |

### Entregue nesta perna

- Form de denúncia na mural com grounds reais da API, detalhe, URL de evidência, validação local, modal e badge `SAMPLE` preservado.
- `source_class`/`basis` visíveis nas linhas de prévia, sem transformar seus números em dados da API.
- Nenhum arquivo em `reference/` foi alterado e nenhum standings/contributor-points vazou para o app.

### Ficou de fora

- Standings, contributor ledger e qualquer número do Claude Design.
- Novo endpoint, POST real ou categorias inventadas.

## Perna 3

- A entrada da mural agora divide explicitamente as jornadas em duas portas independentes: `Choose your intent` e `Choose your hardware`.
- Os seis intents do protótipo foram mantidos verbatim; Chat e Code são clicáveis, enquanto Image gen, Audio, Video e Vision permanecem visíveis e honestamente disabled por falta de dados.
- A porta de hardware usa somente `topRigs` verificado, em ordem de `runCount`, com RTX 3090 24GB e `629 runs` no topo.
- Cada escolha filtra as mesmas rows SAMPLE existentes por intent ou rig, sem criar rows ou números novos; o formulário e suas categorias reais permanecem intactos.
