# R04 — Estágios reais atrás do contrato: s1-fuse (HDR+ / MFSR) e s2-develop (darktable-cli / vkdt)

## Objetivo

Os primeiros estágios que tocam pixel, cada um como `stages/<id>/<impl>/run`
(CONTRACT.md v1): `s1-fuse/python-hdrplus` (align + merge do burst → DNG
linear 16-bit "nosso"), `s1-fuse/python-mfsr` (Handheld Multi-Frame
Super-Resolution, CUDA, 2×), `s2-develop/darktable` (N looks XMP →
`candidates/<look>.jpg`), `s2-develop/vkdt` (opcional, GPU). Todo estágio
suporta `--params` com `{"dry_run": true}` para o CI provar o contrato sem
GPU; a execução real é a barra na máquina da 3090.

## Regras

Nao invente numero, prazo ou fonte alem dos listados em Dados verificados —
PSNR, tempos e "qualidade" só entram em `bench/results/` medidos; a spec não
promete número. NUNCA use declare const, stub de saída (JPEG vazio, TIFF
preto) ou `ok: true` sem arquivo real como workaround fora do `dry_run`
declarado. Nunca escreva dentro de `--in`.

## Dados verificados

- Contrato e schema: `stages/CONTRACT.md`, `$defs/StageResult` (R00).
- Implementações de referência públicas (verificado 2026-09-20):
  `amonod/hdrplus-python` (AGPL-3.0; modos `align`, `merge`, `finish`, `full`;
  entrada: pasta com `.dng` + `reference_frame.txt`); `Jamy-L/Handheld-Multi-Frame-Super-Resolution`
  (Numba CUDA; `run_handheld.py --impath <burst> --outpath out.png`; aceita
  `.dng`; flag de pós-processamento desligável "para plugar o próprio ISP").
  Dados de teste: IPOL 2021.336 publica um burst de 10 DNG (`test data.zip`).
- `darktable-cli <input> <xmp> <output> --out-ext tiff|jpg --core --library :memory:`
  (manual oficial); `--style` exige `--core --configdir`. `vkdt-cli -g graph.cfg`
  (README vkdt). Nenhum dos dois existe nesta máquina de spec.
- Fixture atual `fixtures/pack-minimal` tem frames **placeholder** — inútil
  para pixel. Esta story adiciona `fixtures/fetch-burst-ipol.sh` (baixa o
  zip do IPOL para `fixtures/burst-ipol/`, gitignored) e
  `fixtures/params-dry-run.json` = `{"dry_run": true}`.
- Licenças: hdrplus-python é AGPL — roda como processo separado atrás do
  contrato, nunca linkado no app Kotlin.

## Entregáveis (caminhos exatos)

- `stages/s1-fuse/python-hdrplus/{run, requirements.txt, README.md}` — `run`
  cria/ativa venv em `.venv/`, chama hdrplus-python `align`+`merge`, converte
  `merged_bayer.npy` + metadados do DNG de referência em `merged.dng` (via
  `pidng` ou escritor próprio) e escreve `result.json` com
  `outputs:[{path:"merged.dng", kind:"raw_dng_merged"}]`.
- `stages/s1-fuse/python-mfsr/{run, requirements.txt}` — idem com MFSR,
  saída `merged_2x.tiff` (linear 16-bit), `gpu_s` medido.
- `stages/s2-develop/darktable/{run, looks/*.xmp}` — 3 looks mínimos
  (`neutral.xmp`, `filmic.xmp`, `punchy.xmp`) criados no darktable do dono e
  exportados; saída `candidates/<look>.jpg`, `kind: candidate_jpeg`.
- `stages/s2-develop/vkdt/run` — opcional; se `vkdt-cli` ausente, `result.json`
  com `ok:false`, `notes:"vkdt-cli not installed"`.
- `stages/lint.py` — para cada `stages/s*/*/run`: executável, aceita
  `--params fixtures/params-dry-run.json`, escreve `result.json` válido
  (validação com `jsonschema` Python contra o mesmo `pack.schema.json`).
- `bench/run.sh <stage> <impl> <pack-dir>` — roda o estágio, copia
  `result.json` para `bench/results/<data>/<stage>-<impl>.json`.
- `pipeline.json` ganha `s1-fuse` (impl `python-hdrplus`, `gpu:false`) e
  `s2-develop` (impl `darktable`, `input: previous`).

## Comportamentos obrigatórios

1. `dry_run` nunca importa numpy/torch/darktable — só escreve o `result.json`.
2. Execução real: `merged.dng` abre com `rawpy` e tem o mesmo `raw_pattern`
   do frame de referência (teste em `stages/s1-fuse/python-hdrplus/test_run.py`,
   marcado `skip` sem `fixtures/burst-ipol`).
3. s2 produz **≥ 3** candidatos por captura ou falha com `notes` explicando
   qual look quebrou.
4. `bench/results/` guarda o `result.json` de cada execução real: é a
   única fonte para qualquer afirmação futura de tempo ou qualidade.

## Verificação

VERIFICACAO: test -f fixtures/params-dry-run.json && grep -q '"dry_run"' fixtures/params-dry-run.json && test -f stages/lint.py && grep -q 'candidate_jpeg' -r stages/s2-develop

## Barra

- nome: burst IPOL 2021.336 (10 DNG públicos) processado ponta a ponta.
- como fetchar: `bash fixtures/fetch-burst-ipol.sh`.
- como comparar: `bench/run.sh s1-fuse python-hdrplus fixtures/burst-ipol`
  → `ok:true` + `merged.dng` legível; `bench/run.sh s2-develop darktable
  <out do s1>` → 3 JPEGs. Na 3090, o mesmo para `python-mfsr` com `gpu_s`.

## Oráculo

- comando: test -f stages/lint.py && python3 stages/lint.py
- exit esperado: 0 = todo `run` existente passa no dry-run com `result.json`
  válido (roda em CI sem GPU). Antes da implementação: exit 1 pelo `test -f`
  (sem stderr) — vermelho pelo motivo certo. A execução real é barra, não oráculo.
