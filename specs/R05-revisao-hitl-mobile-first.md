# R05 — Revisão humana no loop (Ktor + HTMX, mobile-first): escolher o candidato no próprio celular

## Objetivo

Páginas servidas pelo orquestrador (R03) que o dono abre no S25 Ultra pela
Tailscale: lista de capturas com candidatos pendentes; página da captura com
os candidatos do s2 lado a lado com o JPEG de referência do telefone
(antes/depois por toque), botões aprovar/rejeitar por candidato e um campo
de instrução livre (guardado para o estágio generativo do R08). Toda decisão
vira linha `decision` + evento. Sem framework de front, sem build de JS:
HTMX vendorizado, CSS mobile-first (base 360 px).

## Regras

Nao invente numero, prazo ou fonte alem dos listados em Dados verificados —
a UI mostra só o que está em `candidate` e `capture`; nenhum score aparece
sem `job` de `s4-score` que o tenha produzido. NUNCA use declare const,
dados de exemplo hardcoded no template ou candidato "placeholder" fora dos
testes. Nenhum CDN em tempo de execução (a rede é a LAN/Tailscale).

## Dados verificados

- R03 expõe `GET /captures` e `GET /captures/{id}` (jobs, candidatos, eventos)
  e grava `candidate(path, kind, sha256)`.
- Referência do telefone: `manifest.files[]` com `kind: jpeg` (R02 grava o
  JPEG par do frame `reference`).
- HTMX: arquivo único `htmx.min.js` (licença BSD) vendorizado em
  `apps/orchestrator/src/main/resources/static/`; versão exata registrada
  no commit que o traz.
- Viewport do S25 Ultra: 412×915 CSS px (medido em sessão de QA 2026-09-20
  no projeto bestmodel) — base de layout 360 px cobre.
- Autenticação MVP: um token compartilhado em env `REVIEW_TOKEN`, cookie
  `rawpack_review` após `POST /login`; sem usuário/senha, sem OAuth (uma pessoa).

## Entregáveis (caminhos exatos)

- `apps/orchestrator/src/main/kotlin/run/bestmodel/rawpack/orchestrator/review/`
  - `ReviewRoutes.kt` — `GET /review` (lista), `GET /review/{capture_id}`,
    `POST /review/{capture_id}/decision` (form: `candidate_id`, `verdict`
    approve|reject, `instruction`), `GET /files/{capture_id}/{path...}`
    (serve só arquivos dentro do dir da captura; path com `..` → 404).
  - `ReviewTemplates.kt` — HTML via `kotlinx.html` ou templates Ktor; sem
    string concat de HTML com dados de usuário (escape sempre).
  - `db/Schema.kt` — tabela `decision(id, capture_id, candidate_id, verdict,
    instruction, decided_at)`; evento `decision_made`.
- `apps/orchestrator/src/main/resources/static/{htmx.min.js, review.css}`.
- Testes: `ReviewRoutesTest` (Ktor `testApplication`):
  1. sem cookie → 302 para `/login`;
  2. `GET /review/{id}` de captura com 3 candidatos renderiza 3 `<img>` com
     `src` em `/files/...` e o JPEG de referência;
  3. `POST .../decision approve` → linha `decision`, evento, redirect 303;
  4. `GET /files/{id}/../manifest.json` → 404;
  5. HTML da lista não contém string de placeholder ("lorem", "example.jpg").

## Comportamentos obrigatórios

1. Toque em um candidato alterna referência/candidato no mesmo lugar (antes/depois).
2. Uma captura pode ter no máximo um `approve` vigente; aprovar outro
   candidato rebaixa o anterior para `superseded` (coluna `status`).
3. A instrução livre é gravada mesmo com `reject` (é matéria-prima do R08).
4. Página funciona sem JS (formulários normais); HTMX só melhora.

## Verificação

VERIFICACAO: grep -q '/review' -r apps/orchestrator/src/main/kotlin && test -f apps/orchestrator/src/main/resources/static/htmx.min.js && grep -q 'decision' -r apps/orchestrator/src/main/kotlin/run/bestmodel/rawpack/orchestrator/db

## Barra

- nome: sessão real no S25 Ultra via Tailscale: abrir `/review`, aprovar um
  candidato de uma captura vinda do R02/R04.
- como fetchar: `GET /captures/{id}` após a decisão mostra `decision` e evento.
- como comparar: os 5 testes acima; depois a sessão no aparelho (screenshot
  em `docs/device/`).

## Oráculo

- comando: test -x ./gradlew && ./gradlew :apps:orchestrator:test -q --tests '*ReviewRoutesTest*'
- exit esperado: 0. Antes da implementação: Gradle falha (classe de teste
  inexistente ou projeto ausente), exit 1 sem `command not found` — vermelho
  pelo motivo certo.
