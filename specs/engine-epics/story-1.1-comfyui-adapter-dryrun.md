# Story 1.1 — Adapter `--runtime comfyui` (dry-run + plan) [Épico 1, vídeo-gen]

REGRAS DE OURO (violar qualquer uma = reprovação imediata):
- NUNCA use declare const nem placeholder/fantasma: implementação real no código Rust existente.
- Nenhuma dependência nova no Cargo.toml (regex/serde/serde_json já existem).
- ZERO invocação de processo externo no modo dry-run (nenhum spawn de comfy/nvidia-smi
  obrigatório para o plan sair — spawn opcional apenas para detectar `comfy` no PATH).
- NÃO inventar flags do comfy-cli: os comandos impressos no plano DEVEM ser exatamente os
  confirmados em fonte primária (cmdline.py do Comfy-Org/comfy-cli, 26/08/2026):
  `comfy launch --background`, `comfy run --workflow <path> --wait --verbose`,
  `comfy stop`, `comfy run --print-prompt` (dry-run nativo).
- Não invente número, prazo, flag, nome de nó ou fonte além dos listados abaixo.

## Dados verificados (copie SEM ALTERAR)
- comfy-cli (fonte: github.com/Comfy-Org/comfy-cli, comfy_cli/cmdline.py, lido 26/08/2026):
  `comfy launch --background`; `comfy run --workflow <path>` aceita formato API E UI;
  `--wait` bloqueia até completar; `--verbose` loga execução; `--print-prompt` imprime o
  grafo API e sai; `--timeout <s>` (default 120) é timeout por evento, não wall-clock;
  `comfy stop`; `comfy run` é async por default e devolve prompt_id.
- Wan 2.2 FLF2V (fontes: docs.comfy.org/tutorials/video/wan/wan2_2; comfy.org/workflows;
  PSA r/StableDiffusion 1me4306): par MoE high_noise/low_noise 14B; umt5_xxl fp8;
  wan_2.1_vae; `WanFirstLastFrameToVideo` nativo exige ComfyUI ≥ 0.3.48; length = 4n+1
  (81 frames ≈ 5,06 s @ 16 fps latente); cenário base 1280×720/81f/20 steps/CFG 3.5/shift ~5.
- sha256 do template e do workflow materializado: computados pelo próprio código (sha2).

## Contexto (BMAD: epics.md Épico 1 / ARCHITECTURE-SPINE §2)

O CLI `benchmark-probe` (Rust, `cli/benchmark-probe/`) hoje mede LLM (llama_cpp/ollama/mock).
O Épico 1 adiciona vídeo: cenário JSON + recipe (template de workflow ComfyUI com marcadores)
→ workflow materializado por substituição determinística (`str::replace`, jinja-free) →
validação estrutural do workflow (formato API do ComfyUI) → plano imprimível.

Esta story é SOMENTE o dry-run/plan (a execução headless real é a Story 1.2).

## ENTREGÁVEIS

1. `cli/benchmark-probe/src/comfyui_adapter.rs` (novo módulo):
   - `ComfyScenario` (serde Deserialize): model, width, height, frames, steps, cfg,
     shift (default 5.0), seed, first_image, last_image, prompt (default "").
   - `RecipeManifest` (serde): recipe_id, runtime ("comfyui"), model_release,
     comfyui_min_version, workflow_template (caminho relativo ao dir do recipe), provenance.
   - `build_plan(recipe_path, scenario)`: lê manifest → lê template → substitui marcadores
     `__MODEL__ __WIDTH__ __HEIGHT__ __FRAMES__ __STEPS__ __CFG__ __SHIFT__ __SEED__
     __FIRST_IMAGE__ __LAST_IMAGE__ __PROMPT__` → valida → devolve ComfyPlan com sha256
     do template e do workflow materializado.
   - Validações determinísticas (qualquer violação = erro com mensagem no stderr, exit ≠ 0):
     a) scenario: width>0, height>0, steps>0, cfg>0; frames ≥ 5 e (frames-1) % 4 == 0
        (restrição documentada Wan: length = 4n+1);
     b) first_image/last_image: não-vazias, sem componente `..`, não absolutas;
     c) após substituição, NENHUM marcador `__[A-Z][A-Z0-9_]*__` residual no workflow;
     d) workflow materializado parseia como JSON objeto (formato API ComfyUI);
     e) todo nó (valor do objeto raiz) tem `class_type` (string não-vazia) e `inputs` (objeto);
     f) ≥ 1 nó.
   - `print_plan`: texto plano (recipe, shas, cenário) + linha única
     `PLAN {"scenario":"<model>","recipe_id":"...","workflow_sha256":"...","dry_run":true}`
     + bloco "Commands:" com as 4 linhas do comfy confirmadas em fonte primária
     + "Planned metrics: seconds_per_clip, it_per_s, frames_per_s".
2. `Runtime::ComfyUi` em `lib.rs` (engine_name "comfyui", label "ComfyUI") + aceito em
   `parse_runtime` do main.rs.
3. Flags novos no main.rs: `--scenario <json|->` (inline JSON; `-` lê stdin; stdin vazio ou
   JSON inválido = erro exit ≠ 0) e `--recipe <path>`; `--runtime comfyui` EXIGE ambos;
   `--workflow-out <path>` opcional grava o workflow materializado (para Story 1.2/CI).
   Roteamento: comfyui não passa pelo run_scenario de LLM (early-return depois do plan).
4. Recipe seed de verdade: `cli/benchmark-probe/recipes/wan22-flf2v-720p-81f-v1.json` +
   `cli/benchmark-probe/recipes/workflows/wan22-flf2v-api.json.tpl` (esqueleto API-format
   com UNETLoader high/low noise, CLIPLoader umt5, VAELoader wan_2.1, 2× LoadImage,
   2× CLIPTextEncode, WanFirstLastFrameToVideo, VAEDecode, SaveAnimatedWEBP;
   provenance declarado: "skeleton-from-docs; substituir por export real no Story 1.4").
5. Fixtures de corrupção: `cli/benchmark-probe/tests/fixtures/recipe-leftover-marker.json`
   apontando para `workflow-leftover.tpl` que contém marcador `__STEPSS__` (typo) →
   substituição não cobre → marcador residual → exit ≠ 0.
6. Teste de integração `cli/benchmark-probe/tests/comfyui_adapter_smoke.rs` cobrindo as
   mesmas 3 direções do oráculo + frames inválidos + scenario JSON inválido + help.

## COMMIT
commitar tudo em `cli/benchmark-probe/` + `specs/story-1.1-comfyui-adapter-dryrun.md`
com identidade `-c user.name="Carlos Felipe" -c user.email="dev@local"`.

## VERIFICAÇÃO
cargo test verde (suite nova + suite antiga sem regressão) e o oráculo abaixo verde.

## Oraculo
- comando: cd cli/benchmark-probe && cargo build -q && B=../../target/debug/benchmark-probe && R=recipes/wan22-flf2v-720p-81f-v1.json && S='{"model":"wan22-i2v-flf2v","width":1280,"height":720,"frames":81,"steps":20,"cfg":3.5,"shift":5.0,"seed":42,"first_image":"in/first.png","last_image":"in/last.png"}' && "$B" --runtime comfyui --scenario "$S" --recipe "$R" | tee /tmp/s11_plan.out | grep -qF '"scenario":"wan22-i2v-flf2v"' && grep -qF 'comfy run --workflow' /tmp/s11_plan.out && grep -qF 'seconds_per_clip' /tmp/s11_plan.out && (printf '' | "$B" --runtime comfyui --scenario - --recipe "$R" >/dev/null 2>&1; test $? -ne 0) && ("$B" --runtime comfyui --scenario "$S" --recipe tests/fixtures/recipe-leftover-marker.json >/dev/null 2>&1; test $? -ne 0) && cargo test -q --test comfyui_adapter_smoke 2>&1 | grep -q 'test result: ok. 9 passed'
