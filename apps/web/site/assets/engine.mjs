// S3 — fit & speed engine. Pure: no DOM, no fetch, no Date.now().
// Rules and constants: CONTRATO-GLOBAL.md §5-§6. Every number carries a basis.

export const API_BASE = "https://www.localmaxxing.com/api";
export const THROTTLE_MS = 350;
export const MIN_RUNS_MEASURED = 3;
export const USABLE_DISCRETE = 0.90, USABLE_UNIFIED = 0.75;
export const GB_PER_B_PER_BIT = 0.15, CTX_ALLOWANCE_GB = 2.0;
export const FIT_TIGHT = 0.12, FIT_OK = 0.35;
export const ATTRIBUTION = "community pool data via localmaxxing.com public API";

const BASIS_WEIGHT = { measured: 3, reported: 2, extrapolated: 1 };
const round2 = (x) => Math.round(x * 100) / 100;

export function quantBits(quantString) {
  if (!quantString) return null;
  const q = quantString.trim();
  if (/^(fp16|bf16|f16)$/i.test(q)) return 16;
  if (/^fp8$/i.test(q)) return 8;
  if (/^(awq|gptq)$/i.test(q)) return 4;
  const digit = q.match(/[1-8]/);
  return digit ? Number(digit[0]) : null;
}

export function usableMemGb(rig) {
  if (rig?.memGb == null) return null;
  const fraction = rig.hwClass === "UNIFIED" ? USABLE_UNIFIED : USABLE_DISCRETE;
  return rig.memGb * fraction;
}

export function vramNeededGb(model, bits) {
  if (bits == null) return null;
  const measured = model?.vramMeasuredGb?.[String(bits)];
  if (measured && measured.n >= 2) return { gb: measured.gb, basis: "measured" };
  if (model?.paramsB == null) return null; // MoE uses TOTAL params: weights are resident
  return { gb: round2(GB_PER_B_PER_BIT * bits * model.paramsB + CTX_ALLOWANCE_GB), basis: "formula" };
}

export function fitClass(rig, model, bits) {
  const usable = usableMemGb(rig);
  const need = vramNeededGb(model, bits);
  if (usable == null || need == null) return null;
  if (need.gb > usable) return "no";
  const headroom = (usable - need.gb) / usable;
  if (headroom < FIT_TIGHT) return "tight";
  if (headroom < FIT_OK) return "ok";
  return "head";
}

export function estimateTokS(rig, model, bits, cells, rigs) {
  if (bits == null) return null;
  const exact = cells.find((c) => c.rigKey === rig.key && c.modelSlug === model.slug && c.bits === bits);
  if (exact) {
    return { value: exact.tokSOutMedian, basis: exact.n >= MIN_RUNS_MEASURED ? "measured" : "reported", n: exact.n };
  }
  if (rig.bandwidthGBs == null) return null;
  const bwByKey = new Map(rigs.map((r) => [r.key, r.bandwidthGBs]));
  const sources = cells
    .filter((c) => c.modelSlug === model.slug && c.bits === bits && c.rigKey !== rig.key && bwByKey.get(c.rigKey) != null)
    .sort((a, b) => b.n - a.n || a.rigKey.localeCompare(b.rigKey));
  if (!sources.length) return null;
  const src = sources[0];
  return {
    value: round2(src.tokSOutMedian * (rig.bandwidthGBs / bwByKey.get(src.rigKey))),
    basis: "extrapolated", n: src.n,
  };
}

export function topPicks(rig, models, cells, rigs, k) {
  const bitsByModel = new Map();
  for (const cell of cells) {
    if (!bitsByModel.has(cell.modelSlug)) bitsByModel.set(cell.modelSlug, new Set());
    bitsByModel.get(cell.modelSlug).add(cell.bits);
  }
  const picks = [];
  for (const model of models) {
    let best = null;
    for (const bits of [...(bitsByModel.get(model.slug) ?? [])].sort((a, b) => a - b)) {
      const fit = fitClass(rig, model, bits);
      if (fit !== "ok" && fit !== "head") continue;
      const est = estimateTokS(rig, model, bits, cells, rigs);
      if (!est) continue;
      const candidate = { model, bits, fit, est };
      if (!best || better(candidate, best)) best = candidate;
    }
    if (best) picks.push(best);
  }
  picks.sort((a, b) => (better(a, b) ? -1 : 1));
  return picks.slice(0, k);
}

function better(a, b) {
  const dw = BASIS_WEIGHT[a.est.basis] - BASIS_WEIGHT[b.est.basis];
  if (dw !== 0) return dw > 0;
  if (a.est.value !== b.est.value) return a.est.value > b.est.value;
  const slugCmp = a.model.slug.localeCompare(b.model.slug);
  if (slugCmp !== 0) return slugCmp < 0;
  return a.bits < b.bits;
}
