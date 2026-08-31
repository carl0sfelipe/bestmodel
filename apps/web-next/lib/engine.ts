import modelsData from "../public/data/derived/models.json";
import poolData from "../public/data/derived/pool.json";
import hardwareData from "../public/data/derived/hardware.json";
import statsData from "../public/data/derived/stats.json";

export const MIN_RUNS_MEASURED = 3;

export type Model = (typeof modelsData.models)[number];
export type Cell = (typeof poolData.cells)[number] & {
  category?: "image" | "audio" | "video";
  imagesPerSec?: number;
  audioXReal?: number;
  videoFramesPerSec?: number;
  steps?: number;
  resolution?: string;
  durationS?: number;
  pipeline?: string;
  precision?: string;
};
export type Rig = (typeof hardwareData.rigs)[number];
export type Stats = typeof statsData;

export function loadDerived() {
  return { models: modelsData.models, pool: poolData.cells, hardware: hardwareData.rigs, stats: statsData };
}

export function basisOf(cell: Pick<Cell, "n">) {
  return cell.n >= MIN_RUNS_MEASURED ? "measured" : "reported";
}

export function metricOf(cell: Cell & Partial<Pick<Cell, "category" | "imagesPerSec" | "audioXReal" | "videoFramesPerSec">>) {
  if (cell.category === "image" && cell.imagesPerSec != null) return { value: cell.imagesPerSec, unit: "img/s", label: "images" };
  if (cell.category === "audio" && cell.audioXReal != null) return { value: cell.audioXReal, unit: "×real", label: "realtime" };
  if (cell.category === "video" && cell.videoFramesPerSec != null) return { value: cell.videoFramesPerSec, unit: "f/s", label: "frames" };
  return null;
}

export function joinCells() {
  const { models, pool, hardware } = loadDerived();
  const byModel = new Map(models.map((model) => [model.slug, model]));
  const byRig = new Map(hardware.map((rig) => [rig.key, rig]));
  return pool.flatMap((cell) => {
    const model = byModel.get(cell.modelSlug);
    if (!model) return [];
    return [{ cell, model, rig: byRig.get(cell.rigKey), basis: basisOf(cell) as "measured" | "reported" }];
  });
}

export function topRigs() {
  return [...loadDerived().hardware].sort((a, b) => (b.runCount ?? 0) - (a.runCount ?? 0));
}

export function formatNumber(value: number | null | undefined, digits = 1) {
  if (value == null || !Number.isFinite(Number(value))) return "-";
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function formatContext(value: number | null | undefined) {
  return value == null ? "-" : formatNumber(value, 0);
}
