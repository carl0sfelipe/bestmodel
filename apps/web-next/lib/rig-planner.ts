// rig-planner.ts — "what will I get on hardware nobody in the pool has?"
//
// The pool answers with measured cells. When a rig has no cell for a model
// (a rented 4x B300 is the motivating case), this module gives a MODELED
// answer: a decode estimate with an explicit low/high band, a memory fit
// check at the requested context, and a prefill/TTFT estimate. Every number
// it returns carries basis "modeled" and must never be shown as measured.
//
// Pure: no next/* imports, no fetch, no Date.now(), so node --test runs it.
//
// Decode model (batch 1, one user):
//   t_step = weightBytesRead / bwEff + kvBytesRead / bwEff + layers * tLayer
//   bwEff  = per-GPU bandwidth * U_BW * (gpus when tensor-parallel, 1 when
//            layer-split: layer split runs one GPU at a time)
//   tok/s  = 1 / t_step   (x acceptance / (1 + draftCost) with MTP/spec)
// tLayer is the per-layer fixed cost (kernel launches, all-reduce, routing).
// At batch 1 on big multi-GPU rigs it DOMINATES the bandwidth term, which is
// why the "active params ratio" overstates how much faster a smaller MoE is.
// It is calibrated against pool cells (see CALIBRATION_ANCHORS).

export type Parallelism = "tensor" | "layer";

export type GpuSpec = {
  key: string;
  label: string;
  memGb: number;
  bandwidthGBs: number;
  /** Dense FP8 tensor throughput, TFLOPS (prefill estimate only). */
  fp8Tflops: number;
  interconnect: "nvlink" | "pcie";
  source: string;
};

export type ModelSpec = {
  key: string;
  label: string;
  hfId: string;
  totalParamsB: number;
  activeParamsB: number;
  layers: number;
  /** KV-cache bytes stored per context token (all layers, FP8 KV). */
  kvBytesPerToken: number;
  /** KV bytes READ per decode step that grow with context (e.g. the DSA
   *  indexer keys), per context token. Sparse attention keeps this tiny. */
  kvReadBytesPerContextToken: number;
  /** KV bytes read per step that do NOT grow with context (sparse top-k
   *  window, linear-attention state). */
  kvReadBytesFixed: number;
  /** Layers with sparse (DSA) attention, and how many carry an indexer. */
  dsaLayers: number;
  indexerLayers: number;
  mtpLayers: number;
  source: string;
};

export type QuantSpec = {
  key: string;
  label: string;
  /** Effective bits per weight including scales. */
  bitsPerWeight: number;
  engine: string;
  parallelism: Parallelism;
  note?: string;
};

export type Band = { low: number; mid: number; high: number };

export type PlanRow = {
  model: ModelSpec;
  quant: QuantSpec;
  basis: "modeled";
  fits: boolean;
  weightsGb: number;
  kvGb: number;
  needGb: number;
  usableGb: number;
  tokS: Band | null;
  tokSWithMtp: Band | null;
  ttftS: number | null;
  stepMs: { weights: number; kv: number; fixed: Band } | null;
};

// ---- constants -------------------------------------------------------------

/** Fraction of nominal HBM/GDDR bandwidth a real runtime reaches at batch 1. */
export const U_BW = 0.75;
/** Usable memory fraction per GPU (runtime, activations, fragmentation). */
export const USABLE_MEM = 0.95;
/** Per-layer fixed decode cost, seconds. low/mid/high band, see anchors. */
export const T_LAYER_S: Band = { low: 60e-6, mid: 93e-6, high: 130e-6 };
/** Layer-split engines (llama.cpp style): no all-reduce, but in the pool
 *  llama.cpp pays about the same per-layer cost as vLLM TP on these MoEs. */
export const T_LAYER_SPLIT_S: Band = { low: 70e-6, mid: 92e-6, high: 140e-6 };
/** MTP / speculative decoding: accepted tokens per verify step. */
export const MTP_ACCEPT: Band = { low: 1.6, mid: 2.0, high: 2.4 };
/** Model FLOPs utilisation during long prefill. */
export const PREFILL_MFU = 0.4;

// ---- catalog ---------------------------------------------------------------

export const GPUS: Record<string, GpuSpec> = {
  b300: {
    key: "b300", label: "B300 288GB", memGb: 288, bandwidthGBs: 8000, fp8Tflops: 5000,
    interconnect: "nvlink", source: "NVIDIA B300 spec: 288 GB HBM3e, 8 TB/s, 5 PFLOPS dense FP8",
  },
  b200: {
    key: "b200", label: "B200 192GB", memGb: 192, bandwidthGBs: 8000, fp8Tflops: 4500,
    interconnect: "nvlink", source: "NVIDIA B200 spec: 192 GB HBM3e, 8 TB/s",
  },
  h200: {
    key: "h200", label: "H200 SXM 141GB", memGb: 141, bandwidthGBs: 4800, fp8Tflops: 1979,
    interconnect: "nvlink", source: "NVIDIA H200 spec: 141 GB HBM3e, 4.8 TB/s",
  },
  "rtx-pro-6000": {
    key: "rtx-pro-6000", label: "RTX PRO 6000 Blackwell 96GB", memGb: 96, bandwidthGBs: 1792, fp8Tflops: 1000,
    interconnect: "pcie", source: "NVIDIA RTX PRO 6000 Blackwell: 96 GB GDDR7, 1792 GB/s",
  },
};

// GLM-5.3: 78 layers (3 dense + 75 MoE), DSA sparse attention with MLA cache
// (kv_lora_rank 512 + rope 64 = 576 values/token/layer), indexer top-k 2048,
// one indexer per group of 4 layers (128-dim keys), 1 MTP layer.
const GLM53_MLA = 576; // bytes/token/layer at FP8 KV
const GLM53_LAYERS = 78;
const GLM53_INDEXER_LAYERS = Math.ceil(GLM53_LAYERS / 4);

// GLM-5.3-Flash: 45 layers; 11 DSA layers (MLA 576), 34 linear-attention
// (KDA) layers with a fixed-size state; 288 experts, top-8; 1 MTP layer.
const FLASH_LAYERS = 45;
const FLASH_DSA_LAYERS = 11;
const FLASH_KDA_LAYERS = FLASH_LAYERS - FLASH_DSA_LAYERS;
const FLASH_HEADS = 64, FLASH_HEAD_DIM = 64;
const FLASH_KDA_STATE_BYTES = FLASH_KDA_LAYERS * FLASH_HEADS * FLASH_HEAD_DIM * FLASH_HEAD_DIM * 4; // fp32 state

const DSA_TOPK = 2048;
const INDEXER_KEY_BYTES = 128;

export const MODELS: Record<string, ModelSpec> = {
  "glm-5.3": {
    key: "glm-5.3", label: "GLM-5.3 (full)", hfId: "zai-org/GLM-5.3",
    totalParamsB: 753, activeParamsB: 40, layers: GLM53_LAYERS,
    kvBytesPerToken: GLM53_LAYERS * GLM53_MLA + GLM53_INDEXER_LAYERS * INDEXER_KEY_BYTES,
    kvReadBytesPerContextToken: GLM53_INDEXER_LAYERS * INDEXER_KEY_BYTES,
    kvReadBytesFixed: DSA_TOPK * GLM53_LAYERS * GLM53_MLA,
    dsaLayers: GLM53_LAYERS, indexerLayers: GLM53_INDEXER_LAYERS,
    mtpLayers: 1,
    source: "zai-org/GLM-5.3 config.json (78 layers, kv_lora_rank 512, index_topk 2048); ~753B total / ~40B active",
  },
  "glm-5.3-flash": {
    key: "glm-5.3-flash", label: "GLM-5.3-Flash", hfId: "zai-org/GLM-5.3-Flash",
    totalParamsB: 320, activeParamsB: 18, layers: FLASH_LAYERS,
    kvBytesPerToken: FLASH_DSA_LAYERS * (GLM53_MLA + INDEXER_KEY_BYTES),
    kvReadBytesPerContextToken: FLASH_DSA_LAYERS * INDEXER_KEY_BYTES,
    kvReadBytesFixed: DSA_TOPK * FLASH_DSA_LAYERS * GLM53_MLA + FLASH_KDA_STATE_BYTES,
    dsaLayers: FLASH_DSA_LAYERS, indexerLayers: FLASH_DSA_LAYERS,
    mtpLayers: 1,
    source: "zai-org/GLM-5.3-Flash config.json (45 layers, 11 DSA + 34 KDA, 288 experts top-8); 320B total / 18B active",
  },
};

export const QUANTS: Record<string, QuantSpec> = {
  bf16: { key: "bf16", label: "BF16", bitsPerWeight: 16, engine: "vLLM / SGLang", parallelism: "tensor" },
  fp8: { key: "fp8", label: "FP8 (official block FP8)", bitsPerWeight: 8.06, engine: "vLLM / SGLang", parallelism: "tensor" },
  nvfp4: { key: "nvfp4", label: "NVFP4", bitsPerWeight: 4.5, engine: "vLLM / SGLang / TRT-LLM", parallelism: "tensor" },
  "exl3-3.5": {
    key: "exl3-3.5", label: "EXL3 3.5 bpw", bitsPerWeight: 3.5, engine: "ExLlamaV3 (TP)", parallelism: "tensor",
    note: "ExLlamaV3 TP is less tuned than vLLM on datacenter GPUs; treat the band's low end as likely",
  },
  "gguf-q4km": {
    key: "gguf-q4km", label: "GGUF Q4_K_M", bitsPerWeight: 4.85, engine: "llama.cpp (layer split)", parallelism: "layer",
    note: "layer split: only one GPU reads weights at a time, bandwidth does not add up",
  },
};

// ---- calibration -----------------------------------------------------------

/** Pool cells the per-layer band was fitted on. Kept here so the test suite
 *  can prove the model still reproduces them inside its band. */
export const CALIBRATION_ANCHORS = [
  {
    what: "GLM-5.2 (same 78-layer base as 5.3) NVFP4, 4x RTX PRO 6000, vLLM",
    cell: "rtx-pro-6000-blackwell-96gb-x4 / madeby561-glm-5-2-nvfp4-reap-504b-term (n=3)",
    gpu: "rtx-pro-6000", gpus: 4, model: "glm-5.3", quant: "nvfp4", contextTokens: 2048, measuredTokS: 86.79,
  },
  {
    what: "GLM-5.3-Flash ~3-bit, 2x RTX PRO 6000, vLLM",
    cell: "rtx-pro-6000-blackwell-96gb-x2 / zai-org-glm-5-3-flash bits 3 (n=8)",
    gpu: "rtx-pro-6000", gpus: 2, model: "glm-5.3-flash", quant: "exl3-3.5", bitsOverride: 3, contextTokens: 2048, measuredTokS: 149.69,
  },
  {
    what: "GLM-5.3-Flash NVFP4, 8x B200 TP8/EP8 (Blackfrost model card, single stream)",
    cell: "external: huggingface.co/Blackfrost-AI/GLM-5.3-Flash-DERISKED-NVFP4",
    gpu: "b200", gpus: 8, model: "glm-5.3-flash", quant: "nvfp4", contextTokens: 2048, measuredTokS: 165.6,
  },
  {
    what: "GLM-5.2 GGUF ~Q4, 4x RTX PRO 6000, llama.cpp layer split",
    cell: "rtx-pro-6000-blackwell-96gb-x4 / unsloth-glm-5-2-gguf bits 4 (n=2)",
    gpu: "rtx-pro-6000", gpus: 4, model: "glm-5.3", quant: "gguf-q4km", contextTokens: 2048, measuredTokS: 39.74,
  },
] as const;

// ---- math ------------------------------------------------------------------

const GB = 1e9;
const round = (x: number, d = 1) => Math.round(x * 10 ** d) / 10 ** d;

export function weightsGb(model: ModelSpec, bitsPerWeight: number): number {
  return (model.totalParamsB * GB * bitsPerWeight) / 8 / GB;
}

export function kvGb(model: ModelSpec, contextTokens: number): number {
  return (model.kvBytesPerToken * contextTokens) / GB;
}

export function decodeStep(
  gpu: GpuSpec, gpus: number, model: ModelSpec, quant: QuantSpec, contextTokens: number, bitsOverride?: number,
) {
  const bits = bitsOverride ?? quant.bitsPerWeight;
  const tp = quant.parallelism === "tensor";
  const bwEff = gpu.bandwidthGBs * GB * U_BW * (tp ? gpus : 1);
  const weightBytes = (model.activeParamsB * GB * bits) / 8;
  const kvBytes = model.kvReadBytesFixed + model.kvReadBytesPerContextToken * contextTokens;
  const tLayer = tp ? T_LAYER_S : T_LAYER_SPLIT_S;
  const weightsS = weightBytes / bwEff;
  const kvS = kvBytes / bwEff;
  const fixed: Band = { low: model.layers * tLayer.low, mid: model.layers * tLayer.mid, high: model.layers * tLayer.high };
  // high tok/s pairs with the LOW fixed cost.
  const tokS: Band = {
    low: 1 / (weightsS + kvS + fixed.high),
    mid: 1 / (weightsS + kvS + fixed.mid),
    high: 1 / (weightsS + kvS + fixed.low),
  };
  return { weightsS, kvS, fixed, tokS };
}

/** MTP: one draft layer is cheap (~1 layer of fixed cost + its weights);
 *  the verify step costs ~a normal step; tokens per step = acceptance. */
export function withMtp(model: ModelSpec, tokS: Band): Band | null {
  if (model.mtpLayers < 1) return null;
  const draftCost = model.mtpLayers / model.layers;
  const f = (acc: number) => acc / (1 + draftCost);
  return { low: tokS.low * f(MTP_ACCEPT.low), mid: tokS.mid * f(MTP_ACCEPT.mid), high: tokS.high * f(MTP_ACCEPT.high) };
}

/** Prefill: 2*active FLOPs per token, the DSA indexer's O(n^2/2) scan
 *  (32 heads x 128 dims), and sparse attention over the top-k window. */
export function ttftSeconds(gpu: GpuSpec, gpus: number, model: ModelSpec, contextTokens: number): number {
  const n = contextTokens;
  const dense = 2 * model.activeParamsB * GB * n;
  const indexer = 2 * 32 * INDEXER_KEY_BYTES * model.indexerLayers * (n * n) / 2;
  const sparseAttn = 2 * 2 * 64 * GLM53_MLA * Math.min(DSA_TOPK, n) * model.dsaLayers * n;
  return (dense + indexer + sparseAttn) / (gpu.fp8Tflops * 1e12 * gpus * PREFILL_MFU);
}

export function planRow(
  gpu: GpuSpec, gpus: number, model: ModelSpec, quant: QuantSpec, contextTokens: number,
): PlanRow {
  const w = weightsGb(model, quant.bitsPerWeight);
  const kv = kvGb(model, contextTokens);
  const usable = gpu.memGb * USABLE_MEM * gpus;
  const need = w + kv;
  const fits = need <= usable;
  if (!fits) {
    return { model, quant, basis: "modeled", fits, weightsGb: round(w), kvGb: round(kv), needGb: round(need),
      usableGb: round(usable), tokS: null, tokSWithMtp: null, ttftS: null, stepMs: null };
  }
  const step = decodeStep(gpu, gpus, model, quant, contextTokens);
  const r = (b: Band): Band => ({ low: round(b.low, 0), mid: round(b.mid, 0), high: round(b.high, 0) });
  const mtp = withMtp(model, step.tokS);
  return {
    model, quant, basis: "modeled", fits,
    weightsGb: round(w), kvGb: round(kv), needGb: round(need), usableGb: round(usable),
    tokS: r(step.tokS),
    tokSWithMtp: mtp ? r(mtp) : null,
    ttftS: round(ttftSeconds(gpu, gpus, model, contextTokens), 1),
    stepMs: {
      weights: round(step.weightsS * 1e3, 2),
      kv: round(step.kvS * 1e3, 3),
      fixed: { low: round(step.fixed.low * 1e3, 1), mid: round(step.fixed.mid * 1e3, 1), high: round(step.fixed.high * 1e3, 1) },
    },
  };
}

export type PlanQuery = { gpu: string; gpus: number; contextTokens: number; models: string[]; quants: string[] };

export const DEFAULT_QUERY: PlanQuery = {
  gpu: "b300", gpus: 4, contextTokens: 212_000,
  models: ["glm-5.3", "glm-5.3-flash"],
  quants: ["bf16", "fp8", "nvfp4", "exl3-3.5", "gguf-q4km"],
};

export function plan(query: PlanQuery = DEFAULT_QUERY): PlanRow[] {
  const gpu = GPUS[query.gpu];
  if (!gpu) throw new Error(`unknown gpu ${query.gpu}`);
  if (!Number.isInteger(query.gpus) || query.gpus < 1 || query.gpus > 16) throw new Error(`gpus must be 1-16`);
  const rows: PlanRow[] = [];
  for (const mk of query.models) {
    const model = MODELS[mk];
    if (!model) throw new Error(`unknown model ${mk}`);
    for (const qk of query.quants) {
      const quant = QUANTS[qk];
      if (!quant) throw new Error(`unknown quant ${qk}`);
      rows.push(planRow(gpu, query.gpus, model, quant, query.contextTokens));
    }
  }
  return rows;
}

/** Parse ?gpu=b300&n=4&ctx=212000 with safe fallbacks to the default query. */
export function parsePlanQuery(params: Record<string, string | string[] | undefined>): PlanQuery {
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
  const gpu = one(params.gpu);
  const n = Number(one(params.n));
  const ctx = Number(one(params.ctx));
  return {
    ...DEFAULT_QUERY,
    gpu: gpu && GPUS[gpu] ? gpu : DEFAULT_QUERY.gpu,
    gpus: Number.isInteger(n) && n >= 1 && n <= 16 ? n : DEFAULT_QUERY.gpus,
    contextTokens: Number.isFinite(ctx) && ctx >= 1024 && ctx <= 1_048_576 ? Math.round(ctx) : DEFAULT_QUERY.contextTokens,
  };
}
