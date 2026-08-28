# Contribua com o seu run

Toda célula do bestmodel nasce de alguém que rodou o modelo de verdade na placa
de verdade. Você pode contribuir de duas formas:

| Caminho | O que você precisa | Classe da célula | Entra no leaderboard? |
|---|---|---|---|
| **CLI medido** (recomendado) | rodar o `benchmark-probe` na sua máquina | `measured_signed` | Sim — direto |
| **Report manual** | só o `curl` (números que você já tem) | `reported` | Só após revisão humana |

Os números NUNCA são editados à mão por ninguém — o que você mede é o que
entra, com a sua classe de fonte declarada (veja
[Transparência de fontes](transparency.md)).

---

## Caminho 1 — CLI medido (`measured_signed`)

### Passo 1 — Instale o probe

```bash
git clone https://github.com/carl0sfelipe/bestmodel.git
cd bestmodel
cargo build -p benchmark-probe --release
export PATH="$PWD/target/release:$PATH"
```

### Passo 2 — Gere o seu comando pronto

O probe detecta seu hardware (GPU, CPU, SO) sozinho. Peça o comando:

```bash
benchmark-probe --runtime ollama --model qwen3:8b --print-command
```

Saída (uma linha, pronta para colar):

```
'benchmark-probe' '--runtime' 'ollama' '--model' 'qwen3:8b' '--prompt-tokens' '4096' '--generated-tokens' '512' '--batch-size' '1' '--context-tokens' '8192'
```

Para vídeo (ComfyUI), informe o cenário e a receita — o comando gerado roda em
modo dry-run (materializa o workflow e imprime o plano, sem executar):

```bash
benchmark-probe --runtime comfyui \
  --scenario '{"model":"wan22-i2v-flf2v","width":1280,"height":720,"frames":81,"steps":20,"cfg":3.5,"shift":5.0,"seed":42,"first_image":"in/first.png","last_image":"in/last.png"}' \
  --recipe recipes/wan22-flf2v-720p-81f-v1.json \
  --print-command
```

### Passo 3 — Rode o benchmark

Cole o comando gerado. Ao final aparecem as métricas padronizadas
(`Decode`, `Peak VRAM`, e para vídeo `seconds_per_clip`/`frames_per_s`).

### Passo 4 — Assine e envie

Rode o mesmo comando acrescentando `--sign --upload`:

```bash
benchmark-probe --runtime ollama --model qwen3:8b --sign --upload
```

- Na primeira vez o probe cria um par de chaves Ed25519 local
  (`~/.config/benchmark-probe/ed25519.pem`). A chave **fica com você**; só a
  assinatura vai para o servidor.
- O servidor valida a assinatura sobre o digest do relatório e publica a
  célula como `measured_signed` (classe de maior confiança).

Se a API não estiver no endereço padrão:

```bash
export BENCHMARK_PROBE_API_URL="https://<endereco-da-api>"
```

---

## Caminho 2 — Report manual (`reported`)

Já tem o número (ex.: do `ollama run --verbose` ou de outro benchmark) e não
quer instalar o CLI? Você pode reportá-lo — ele entra com classe `reported`
(confiança menor) e **só aparece no leaderboard depois de revisão humana**.

### Passo 1 — Registre um contribuidor (e-mail, sem senha)

```bash
curl -s -X POST https://<endereco-da-api>/v1/contributors \
  -H 'Content-Type: application/json' \
  -d '{"email": "voce@exemplo.com"}'
```

Resposta (o token aparece **uma única vez** — guarde):

```json
{"contributor_id": "…", "token": "…"}
```

### Passo 2 — Envie o report com o token

```bash
curl -s -X POST https://<endereco-da-api>/v1/submissions/reported \
  -H 'Authorization: Bearer SEU_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "model_release_id": "model-qwen25-coder-7b",
    "inference_runtime_id": "llama-cpp",
    "gpu_model_id": "gpu-rtx-3090",
    "scenario": {"prompt_tokens": 4096, "generated_tokens": 512,
                 "batch_size": 1, "context_tokens": 8192},
    "metrics": {"decode_tok_s": 35.2, "peak_vram_mib": 18000}
  }'
```

Regras:

- Sem token, ou token desconhecido → **401**.
- Cota por IP (padrão 5 reports a cada 24 h) → **429** ao exceder.
- IDs desconhecidos de modelo/runtime/GPU/receita → **400**
  (consulte o catálogo; não invente id).
- Células duplicadas (mesmo hardware+modelo+quant+runtime+cenário) → **409**.
- O report fica com `status=submitted` até revisão humana; nada vai para o
  leaderboard direto.

Para cenário de vídeo use as dimensões do cenário no lugar dos tokens:

```json
"scenario": {"width": 1280, "height": 720, "frames": 81, "steps": 20,
             "cfg": 3.5, "shift": 5.0, "seed": 42}
```

---

## O que acontece depois

1. `measured_signed` — valida assinatura + digest e publica.
2. `reported` — fila de revisão humana; aprovado, entra com badge da classe.
3. Harvesters (`harvested`) e estimativas (`derived`) não vêm de você — veja
   como auditá-los em [Transparência de fontes](transparency.md).
