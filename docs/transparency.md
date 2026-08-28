# Transparência de fontes

**Princípio:** toda célula do bestmodel declara de onde veio o número
(`source_class`), e o peso de confiança segue essa declaração. Uma medição
assinada, um report da comunidade, um dado colhido de fonte pública e uma
estimativa roofline **nunca são apresentados da mesma forma**.

**Regra do leaderboard:** só entram células com `status='validated'` **e**
`source_class` declarado. Célula sem classe nunca renderiza.

| Classe | Peso de confiança (base) | Entra no leaderboard |
|---|---|---|
| `measured_signed` | 0.9 | Direto |
| `reported` | 0.6 | Só após revisão humana |
| `harvested` | 0.4 | Só via fila de revisão |
| `derived` | 0.4 | Com badge derivado |

O peso é o fator de classe da fórmula de confiança pública (implementação de
referência: `cli/canirunit/src/lib.rs`, `source_weight`); o score final
combina ainda nº de runs, recência, variância e tier de match de hardware.

---

## `measured_signed` — medição assinada (0.9)

**O que é:** benchmark rodado pelo CLI `benchmark-probe` em hardware real,
assinado com a chave Ed25519 local de quem submeteu.

**Como é produzido:** o CLI detecta o hardware, roda o cenário padronizado,
canonicaliza o relatório (JSON com chaves ordenadas, separadores compactos),
calcula `sha256(payload)`, assina o digest e envia relatório + digest +
assinatura + artefatos.

**Como auditar:**
1. Recalcule o digest: canonialize o JSON do relatório (`sort_keys=True`,
   `separators=(',', ':')`) e faça sha256 — deve bater com o
   `payload_digest` armazenado.
2. Verifique a assinatura Ed25519 sobre o `payload_digest` com a chave
   pública confiável do projeto (offline, com `openssl` ou `cryptography`).
3. Cada artefato guarda o sha256 dos bytes enviados
   (`benchmark_artifact.sha256_digest`) — re-hash e compare.

## `reported` — report da comunidade (0.6)

**O que é:** número medido fora do probe assinado (ex.: outro benchmark) e
reportado pelo endpoint autenticado
([veja o fluxo](contribute.md#caminho-2--report-manual-reported)).

**Como é produzido:** `POST /v1/submissions/reported` com bearer token de
contribuidor; cota por IP; nasce com `status='submitted'` e assinatura
literal `'reported'` (nenhuma claim de assinatura Ed25519 é feita).

**Como auditar:**
1. O `payload_digest` é o sha256 do corpo canônico da requisição — prova *o
   que* foi submetido, não que é verdadeiro.
2. O log por IP (`reported_submission_log`) registra contribuidor, run e IP
   de cada report aceito.
3. Trate o número como claim da conta que o reportou.

## `harvested` — colhido de fonte pública (0.4)

**O que é:** medida extraída por harvester determinístico de fontes públicas
(model cards, templates de workflow).

**Como é produzido:** harvesters rodam offline contra a fonte, etapizam as
células em JSONL (`status=unverified`, nunca produção) e uma decisão humana
de revisão (arquivo de decisões commitável) promove com ids uuid5
determinísticos.

**Como auditar:**
1. Toda célula carrega `source_url` — abra a fonte exata.
2. `source_sha256` é o hash dos bytes da fonte na hora da colheita; re-baixe
   e re-hash para detectar mutação (hash diferente é rejeitado, nunca
   mesclado).
3. O staging é append-only e imutável diante da revisão; a aprovação vive em
   arquivo de decisões separado, também commitável.

## `derived` — estimativa roofline (0.4)

**O que é:** estimativa computada pelo projeto (nunca uma medição),
incluindo transferências cross-hardware a partir de uma célula medida
âncora.

**Como é produzida:** funções de estimativa do `packages/roofline-kernel`
sobre specs públicas de hardware; a sugestão cross-hardware escala o valor
medido da âncora pela razão de throughput efetivo
`eff(âncora)/eff(alvo)`.

**Como auditar:**
1. O `source_url` aponta a versão do estimador (ex.:
   `roofline:estimate_diffusion_step#v1`) — rode o estimador com as specs e
   parâmetros publicados para reproduzir o número.
2. A constante de calibração de atenção é **declarada**, não ajustada — está
   documentada no código do estimador.
3. Um valor derivado jamais pode virar `measured_signed`; essa troca é a
   linha dura de honestidade do projeto.

---

API: `GET /v1/transparency/sources` devolve estes dados em JSON.
