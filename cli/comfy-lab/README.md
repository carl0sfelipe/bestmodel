# bestmodel-comfy — prompt pack

Pré-plano executável da vertical de **diffusion/imagem** do Can I Run It:
probe de hardware e lab de medição usando o ComfyUI local como runtime
(127.0.0.1:8188), analisador de workflow ("roda nesta máquina?" antes de
executar) e node pack de instrumentação instalável em `custom_nodes/`.

É o equivalente para imagem do `cli/benchmark-probe` (LLMs): mesmas ideias de
receita congelada, gravação reproduzível e base declarada — sem upload no v1
(contribute depende do Track D no backlog do monorepo).

## Como usar

Executor: leia `PROMPT-EXECUTOR.md` e siga o protocolo (contrato -> ESTADO ->
uma sessão por vez, oráculo vermelho -> verde, um commit por sessão).

S1–S3 rodam sem ComfyUI instalado (fixtures). S4+ exige o servidor local com
pelo menos um modelo — instalação é responsabilidade do workspace ComfyUI
(BMAD "Fábrica de Imagens", EPIC-01).
