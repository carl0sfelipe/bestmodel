// sheet.ts — pure shapes and selection rules for the model answer sheet
// (/m/[slug]). Deliberately dependency-free: the server page and the client
// island both import it, so it must never drag the derived snapshot (or
// next/*) into the browser bundle.
//
// Honesty rules encoded here:
//   - every number carries a basis (measured when a cell has 3+ runs,
//     reported below that);
//   - a cell without a metric never becomes a zero or an empty string —
//     it reads "no metric for this cell";
//   - a missing measurement reads "no data yet", never a plausible-looking
//     number.

export type Basis = "measured" | "reported";

export type SheetMetric = {
  value: number;
  unit: string;
  label: string;
  higherIsBetter: boolean;
};

/** One pool cell of one model, flattened for display. */
export type SheetRow = {
  rigKey: string;
  rigLabel: string;
  hwClass: string;
  memoryGb: number | null;
  bits: number | null;
  quant: string;
  n: number;
  basis: Basis;
  metric: SheetMetric | null;
  /** true when the cell carries no metric at all (not a zero). */
  noMetric: boolean;
  ttftMs: number | null;
  peakVramGb: number | null;
  maxContext: number | null;
  engines: string[];
};

/** Model-level facts, all read from the frozen snapshot. */
export type SheetFacts = {
  runCount: number;
  medianTokS: number | null;
  sourceClass: string | null;
  vram: { bits: number; gb: number; n: number; basis: Basis }[];
  maxContextTested: number | null;
  evalScore: { score: number; count: number; quant: string | null; mixedQuants: boolean } | null;
  cellCount: number;
  rigCount: number;
  snapshotAt: string;
};

export type SheetModel = {
  slug: string;
  displayName: string;
  hfId: string | null;
  category: string;
  family: string | null;
  paramsB: number | null;
  activeParamsB: number | null;
  isMoE: boolean;
};

export type SheetRig = {
  rigKey: string;
  rigLabel: string;
  hwClass: string;
  memoryGb: number | null;
  cellCount: number;
  best: SheetRow | null;
};

export const NO_METRIC = "no metric for this cell";
export const NO_DATA = "no data yet";
export const NO_CELLS = "no data yet";

/** en-US number formatting; null stays null so callers choose their own label. */
export function num(value: number | null | undefined, digits = 1): string | null {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function count(value: number | null | undefined): string | null {
  return num(value, 0);
}

/** Basis of a run count: 3+ runs is measured, fewer is reported. */
export function basisOfRuns(n: number): Basis {
  return n >= 3 ? "measured" : "reported";
}

/**
 * Best row of a set: a measured cell outranks a reported one, then the
 * better metric wins. Returns null when nothing in the set carries a metric —
 * the caller must then say so instead of showing a number.
 */
export function pickBest(rows: SheetRow[]): SheetRow | null {
  const withMetric = rows.filter((row) => row.metric !== null);
  if (!withMetric.length) return null;
  const measured = withMetric.filter((row) => row.basis === "measured");
  const pool = measured.length ? measured : withMetric;
  let best = pool[0]!;
  for (const row of pool.slice(1)) {
    const better = row.metric!.higherIsBetter
      ? row.metric!.value > best.metric!.value
      : row.metric!.value < best.metric!.value;
    if (better) best = row;
  }
  return best;
}

/** Verdict for a rig, or the best the pool has when no rig was asked about. */
export function pickVerdict(rows: SheetRow[], rigKey: string | null): { row: SheetRow | null; scope: "rig" | "pool" } {
  if (!rigKey) return { row: pickBest(rows), scope: "pool" };
  const scoped = rows.filter((row) => row.rigKey === rigKey);
  if (!scoped.length) return { row: null, scope: "rig" };
  return { row: pickBest(scoped), scope: "rig" };
}

/** One entry per rig that ran this model, fastest first. */
export function groupByRig(rows: SheetRow[]): SheetRig[] {
  const map = new Map<string, SheetRow[]>();
  for (const row of rows) {
    const list = map.get(row.rigKey);
    if (list) list.push(row);
    else map.set(row.rigKey, [row]);
  }
  const groups: SheetRig[] = [];
  for (const [rigKey, group] of map) {
    const first = group[0]!;
    groups.push({
      rigKey,
      rigLabel: first.rigLabel,
      hwClass: first.hwClass,
      memoryGb: first.memoryGb,
      cellCount: group.length,
      best: pickBest(group),
    });
  }
  groups.sort((a, b) => {
    if (!a.best && !b.best) return a.rigLabel.localeCompare(b.rigLabel);
    if (!a.best) return 1;
    if (!b.best) return -1;
    const ai = a.best.metric!.higherIsBetter;
    const delta = ai
      ? b.best.metric!.value - a.best.metric!.value
      : a.best.metric!.value - b.best.metric!.value;
    return delta !== 0 ? delta : a.rigLabel.localeCompare(b.rigLabel);
  });
  return groups;
}

/** Rig key lookup that tolerates case and the label form used in /hardware links. */
export function matchRigKey(token: string | null | undefined, rows: SheetRow[]): string | null {
  const key = token?.trim().toLowerCase() ?? "";
  if (!key) return null;
  const byKey = rows.find((row) => row.rigKey.toLowerCase() === key);
  if (byKey) return byKey.rigKey;
  const byLabel = rows.find((row) => row.rigLabel.toLowerCase() === key);
  return byLabel ? byLabel.rigKey : null;
}
