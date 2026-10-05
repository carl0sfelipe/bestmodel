// wall-filter.ts — shared pool filter for the human wall and the agent twin.
// Pure: filter before sort. Default ranking drops toys / <1B models; an
// unknown rig is a structured miss (closest rig keys), not an empty top-60.

import { suggestRigs } from "./suggest-slugs.ts";

export const DEFAULT_RANKING_MIN_PARAMS_B = 1;

export type WallFilter = {
  rig?: string | null;
  category?: string | null;
};

export type WallFilterRow = {
  cell: { rigKey: string };
  model: {
    slug: string;
    category: string;
    paramsB?: number | null;
    displayName?: string | null;
    hfId?: string | null;
  };
};

export function normalizeWallToken(value: string | null | undefined): string {
  const token = value?.trim().toLowerCase() ?? "";
  return token === "" || token === "all" ? "all" : token;
}

export function isToyOrTinyMarked(model: WallFilterRow["model"]): boolean {
  if (model.category === "toy") return true;
  const hay = [model.slug, model.displayName ?? "", model.hfId ?? ""]
    .join(" ")
    .toLowerCase()
    .replace(/[/.]+/g, "-");
  if (hay.includes("tinystories") || hay.includes("tiny-stories")) return true;
  if (/(^|-)stories-|-stories($|-)/.test(hay)) return true;
  if (typeof model.hfId === "string" && model.hfId.toLowerCase().endsWith("/models-moved")) return true;
  return /(^|[^a-z])toy([^a-z]|$)/.test(hay);
}

export function isDefaultRankingExcluded(model: WallFilterRow["model"]): boolean {
  if (model.paramsB != null && model.paramsB < DEFAULT_RANKING_MIN_PARAMS_B) return true;
  return isToyOrTinyMarked(model);
}

export function filterWallRows<T extends WallFilterRow>(rows: readonly T[], filters: WallFilter = {}): T[] {
  const rig = normalizeWallToken(filters.rig);
  const category = normalizeWallToken(filters.category);
  return rows.filter((row) => {
    if (rig !== "all" && row.cell.rigKey.toLowerCase() !== rig) return false;
    if (category !== "all" && row.model.category.toLowerCase() !== category) return false;
    if (isDefaultRankingExcluded(row.model)) return false;
    return true;
  });
}

export type RigMiss = { queried: string; similar: string[] };

export function formatRigMiss(miss: RigMiss): string[] {
  return [
    "bestmodel.run / pool — agent view",
    "",
    `rig not found: ${miss.queried}`,
    "",
    "Closest rig keys:",
    ...miss.similar.map((key) => `  ${key}`),
  ];
}

export function unknownRig(
  rig: string | null | undefined,
  knownKeys: readonly string[],
): RigMiss | null {
  const key = normalizeWallToken(rig);
  if (key === "all") return null;
  if (knownKeys.some((item) => item.toLowerCase() === key)) return null;
  return { queried: key, similar: suggestRigs(key, knownKeys, 10) };
}
