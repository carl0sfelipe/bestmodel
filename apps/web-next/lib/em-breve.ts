// em-breve.ts — typed catalog of features that do not exist yet.
// Pure: no next/* imports, so the page, the 501 API, and node --test share it.

export type FeatureEmBreve = {
  slug: string;
  titulo: string;
  oQueFaz: string;
  comoAjudar: string[];
};

export const FEATURES_EM_BREVE: readonly FeatureEmBreve[] = [
  {
    slug: "comparar-duas-gpus",
    titulo: "Comparar duas GPUs",
    oQueFaz:
      "Coloca duas GPUs lado a lado no mesmo modelo, mesma quantização e o mesmo protocolo. Você vê tok/s, VRAM e TTFT de cada placa, com a base (measured ou reported) à vista. Ainda não há essa vista no site; o pool já tem células, falta o cruzamento.",
    comoAjudar: [
      "Abra uma issue com o par de GPUs e o modelo que você quer cruzar.",
      "Envie a sua medição pelo formulário de captura.",
      "Rode o mesmo modelo nas duas placas via llms.surf e traga os números.",
    ],
  },
  {
    slug: "melhor-modelo-por-tarefa",
    titulo: "Melhor modelo por tarefa",
    oQueFaz:
      "Você pergunta qual é o melhor modelo de código na sua GPU e recebe a célula medida do pool, não uma fórmula. A resposta declara a base: measured, reported, ou ainda sem dados. A pergunta livre por tarefa ainda não está no ar.",
    comoAjudar: [
      "Abra uma issue com a tarefa (código, chat, áudio) e a GPU que você tem.",
      "Envie a sua medição pelo formulário de captura.",
      "Rode a tarefa com um modelo local via llms.surf.",
    ],
  },
  {
    slug: "rodar-na-nuvem",
    titulo: "Rodar na nuvem",
    oQueFaz:
      "Quando a sua máquina não segura o modelo, o bestmodel cloud aluga uma GPU e corre o mesmo protocolo. O número volta com a placa, a quantização e a base. Esse caminho ainda não existe.",
    comoAjudar: [
      "Abra uma issue com o modelo que não cabe na sua máquina.",
      "Envie a sua medição pelo formulário de captura.",
      "Rode a tarefa com um modelo local via llms.surf enquanto a nuvem não existe.",
    ],
  },
];

export function featureEmBreve(slug: string): FeatureEmBreve | null {
  return FEATURES_EM_BREVE.find((item) => item.slug === slug) ?? null;
}

export function issueUrlEmBreve(slug: string): string {
  return `https://github.com/carl0sfelipe/bestmodel/issues/new?title=${encodeURIComponent(slug)}`;
}
