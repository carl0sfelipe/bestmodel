---
id: 2026-09-20-dogfood-llms-surf-v4-1-0-specs-do-rawpack
titulo: dogfood da release v4.1.0 do llms.surf escrevendo e despachando as specs do MVP rawpack — template oficial contradiz o check-spec; heuristicas so em portugues; gap do gauntlet le a linha errada do Gradle
data: 2026-09-20
recorrivel: sim
regra: nao — candidatas: (a) template e mecanismo em lockstep (o check-spec deveria rodar sobre o proprio artefato-template.md e reprova-lo hoje); (b) check-spec avisa quando a spec tem mais de uma secao Oraculo (so a primeira e despachavel)
status: aberto
repo: llms.surf v4.1.0 (tag 2026-09-19, clone raso em 2026-09-20) usado como orquestrador; workdir alvo = rawpack (semente) e bestmodel (S32)
interage_com: reforca 46 (crase em comando: vira 127 — o template ensina exatamente isso); reforca 32 (mecanismo declarado: check-spec existe, mas o template nao passa nele); reforca 53 (status --task funcionou como veredito canonico); toca 1 (spec curta: o multi-story em um arquivo e bulk, nao spec)
---

# Dogfood v4.1.0: escrever as specs do MVP rawpack no formato do llms.surf e despachar pelo caminho de 2 minutos

Contexto: o dono pediu (1) dogfood da ultima release do llms.surf e (2) specs
para entregar o MVP do rawpack em Kotlin. Fiz as duas coisas juntas: as
specs foram escritas PARA o dispatcher e validadas pelos gates dele
(`check-spec.sh`, `check-oracle.py`, `run normal` com o runner stub).
Ambiente: VM Linux (Ubuntu 24.04, JDK 21, sem Android SDK, sem GPU), sem
credencial de provider — so o stub. Tudo abaixo e reproduzivel com os
comandos citados.

## O que funcionou (registrar tambem, senao o diario vira so queixa)

1. **Promessa de 2 minutos**: `export ORACFIT_ROOT=$PWD DISPATCH_RUNNER=$PWD/adapters/stub/runner.sh; bin/llms-surf start`
   → `status: pass`, `attempts: 1`, `oracle_exit: 0`, ledger em
   `.dispatch/ledger/mode.jsonl`. Tempo real: **1,1 s**. Zero chave.
2. **`check-spec.sh`** reprovou a S32 do bestmodel (escrita por mim horas
   antes) por dois motivos reais: sem token "dados verificados" e crase na
   linha `- comando:`. O mecanismo pegou o autor — e o corrigido.
3. **`check-oracle.py`** classificou as 7 specs do rawpack corretamente:
   R01–R06 "falha pelo motivo certo" (exit 1, sem `command not found`); R00,
   ja concluida, "JA PASSA — nao mede nada" (exit 1). E o comportamento
   certo para story done.
4. **`run normal` com stub** sobre R03: 5 tentativas, `status: fail`,
   `oracle_exit: 1`, 6 s de parede; `llms-surf status --task r03-stub`
   devolveu o JSON canonico (regra 53 viva).
5. Single-flight por workdir e `.dispatch/` fora do git do produto: ok
   (adicionei `.dispatch/` ao `.gitignore` do rawpack — e o unico requisito
   que o workdir alvo precisa saber).

## Sintoma (o que atrapalhou)

### S1 — O template oficial ensina a crase que o check-spec proibe

`fluxos/_comum/artefato-template.md` (o que o HINT do proprio check-spec
manda ler quando falta `## Barra`) traz:

```text
- comando: `<comando shell exato, com cd embutido se precisar de outro diretório>`
- exit esperado: `<inteiro, default 0 se omitido>`
```

`bin/check-spec.sh` item 4 reprova exatamente isso ("linha 'comando:'
contem CRASE... vira substituicao no eval e gera exit 127 fantasma",
incidente 2026-08-10, regra 46). Quem copia o template recebe reprovacao
na primeira rodada. Verificado: a fixture `tests/fixtures/oracfit-smoke-normal.md`
esta certa (sem crase); o template esta errado. Custo: uma rodada de
correcao por autor novo; no meu caso, a S32 inteira (7 oraculos) tinha crase.

### S2 — Heuristicas do check-spec so casam portugues

Item 2 exige `dados verificados|contexto real|verificado\)|\(verificado`.
Uma spec em ingles com secao `## Verified data` (padrao do repo bestmodel,
cuja regra de casa e "docs em ingles") reprova; a L03A do mesmo repo so
passa porque tem "(verificado 2026-08-30" dentro de um parentese. Nao e
bug de logica, e limite declarado (o script diz que detecta ausencia, nao
qualidade) — mas o limite e de idioma, e isso nao esta escrito em lugar
nenhum. Workaround que apliquei na S32: token `(verificado 2026-09-20)` no
titulo do bloco. Mecanismo barato: acrescentar `verified data|verified
facts` a alternacao, ou documentar "specs em portugues ou com o token".

### S3 — Uma spec com N historias tem N `## Oráculo`; so o primeiro conta

A S32 do bestmodel tem sete historias e sete secoes de oraculo num arquivo.
`check-spec` passa (existe pelo menos uma), `ledger-finalize`/gauntlet
usam a primeira linha `- comando:` — as outras seis sao invisiveis ao
dispatcher. Nada avisa. Para o rawpack escrevi **um arquivo por historia**
(R00–R06) e o problema some; para a S32 fica a nota de que ela e um
indice de historias, e cada uma deve ser recortada para despacho.
Mecanismo: `check-spec` conta secoes `## Or[aá]culo` e avisa (ou reprova)
quando > 1.

### S4 — `biggest_gap` do gauntlet le a primeira linha do stderr do Gradle

Na corrida stub da R03 o feedback injetado foi
`gap: FAILURE: Build failed with an exception.` — a linha-banner do Gradle.
A linha util ("Project with path ':apps:orchestrator' could not be found")
vem depois. Um modelo real receberia feedback vazio de informacao e
tentaria de novo as cegas (mesma classe da regra 45: extrator procura o
campo errado). Mecanismo: gap = ultimas N linhas do stderr, ou primeira
linha casando `error|not found|FAILED|Exception` apos o banner; e o
runner de Gradle deveria ser tratado como caso conhecido (`-q` ja estava
ligado).

### S5 — `max_attempts: 3` no `normal.yaml`, mas o run fez 5

Com `gauntlet.until_approved: true`, quem manda e `safety_ceiling: 5`;
`max_attempts` fica decorativo. Nao e bug se for intencional, mas o
operador que le `max_attempts: 3` espera 3. Um comentario no YAML ou um
aviso no inicio do run ("until_approved: teto = 5") resolve.

### S6 — Ruido de roteamento sem credencial

Sem chave OpenRouter em arquivo, cada tentativa imprime 9 linhas
"pulando <modelo> — provider 'openrouter' sem credencial em arquivo (E5-M5)"
antes de cair no `mimo-v2.5-free`. Em 5 tentativas, 45 linhas iguais na
cara do operador; a informacao util (qual modelo serviu) fica no meio.
Mecanismo: imprimir o resumo de skip uma vez por run, nao por tentativa.

## Causa

- S1/S2/S3: o mecanismo (`check-spec.sh`) evoluiu por incidentes; o
  template e a documentacao de formato nao entraram no mesmo lockstep
  (regra 32 fala em declarar mecanismo, nao em manter o exemplo
  canonico passando no mecanismo). Nao existe teste que rode o check
  sobre o template.
- S4: extrator de gap generico sobre stderr; Gradle e o primeiro runner
  cujo stderr comeca com banner.
- S5/S6: sao escolhas de produto sem aviso ao operador.

## Correcao aplicada

Neste dogfood (repo rawpack + bestmodel), nao no llms.surf:

- rawpack: 7 specs (R00–R06) escritas ja no formato correto (sem crase,
  token portugues, uma historia por arquivo, oraculos guardados por
  `test -x`/`test -f` para falharem sem stderr). Todas passam em
  `check-spec.sh`; R01–R06 passam em `check-oracle.py` como "falha pelo
  motivo certo"; R00 tem oraculo verde (7 testes Kotlin, `BUILD SUCCESSFUL`).
- bestmodel S32: corrigir crase e token (linha, em PR #12).
- Este diario, para o promote cycle decidir S1–S3.

## Pode acontecer de novo?

Sim, a cada autor novo de spec (humano ou modelo) que parta do template:
S1 e deterministico. S3 aparece sempre que alguem escrever "epico" num
arquivo. S4 aparece em todo oraculo cuja ferramenta tem banner (Gradle,
Maven, cargo com warnings antes do erro). Protecao: teste de CI que roda
`bin/check-spec.sh fluxos/_comum/artefato-template.md` (hoje reprovaria) e
contagem de secoes Oraculo no check.
