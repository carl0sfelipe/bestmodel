import { basisOf, loadDerived, metricOf, topRigs } from "../lib/engine";
import HomeClient, { type AnswerIndex, type RigOption } from "./home-client";

/** How many rigs the selector offers — the same cutoff the wall's rig filter uses. */
const RIG_LIMIT = 24;
/** How many models a single answer shows. */
const ANSWER_LIMIT = 6;

export default function HomePage() {
  const { models, pool, hardware, stats } = loadDerived();
  const byModel = new Map(models.map((model) => [model.slug, model]));
  const rigLabel = new Map(hardware.map((rig) => [rig.key, rig.label]));

  const rigs = topRigs()
    .filter((rig) => (rig.runCount ?? 0) > 0)
    .slice(0, RIG_LIMIT);
  const rigKeys = new Set(rigs.map((rig) => rig.key));

  // The join runs on the server against the real pool, so the browser receives
  // answers rather than a database. Every entry is a measured or reported cell —
  // nothing here is estimated, and a combination with no cell simply has no key.
  // indexAny is the same join over EVERY rig: it feeds the honest "the pool
  // does have data, just not on this rig" pointer, so cells measured on rigs
  // outside the top-24 (cloud anchors) stay visible instead of hidden.
  const build = (allowed: Set<string> | null): AnswerIndex => {
    const idx: AnswerIndex = {};
    for (const cell of pool) {
      if (allowed && !allowed.has(cell.rigKey)) continue;
      const model = byModel.get(cell.modelSlug);
      if (!model) continue;
      const metric = metricOf(cell);
      if (cell.tokSOutMedian == null && metric == null) continue;
      const key = `${cell.rigKey}|${model.category}|${cell.bits ?? 0}`;
      (idx[key] ??= []).push({
        name: model.displayName ?? model.slug,
        slug: model.slug,
        rigKey: cell.rigKey,
        rigLabel: rigLabel.get(cell.rigKey) ?? cell.rigKey,
        tokS: cell.tokSOutMedian == null ? 0 : Math.round(cell.tokSOutMedian * 10) / 10,
        metric: metric ? { value: Math.round(metric.value * 10) / 10, unit: metric.unit, label: metric.label } : null,
        n: cell.n,
        basis: basisOf(cell),
        maxContext: cell.maxContextTested ?? null,
      });
    }
    for (const key of Object.keys(idx)) {
      idx[key].sort((a, b) => (b.metric?.value ?? b.tokS) - (a.metric?.value ?? a.tokS));
      idx[key] = idx[key].slice(0, ANSWER_LIMIT);
    }
    return idx;
  };
  const index = build(rigKeys);
  const indexAny = build(null);

  const rigOptions: RigOption[] = rigs.map((rig) => ({
    key: rig.key,
    label: rig.label,
    runCount: rig.runCount ?? 0,
  }));

  return (
    <HomeClient
      index={index}
      indexAny={indexAny}
      rigs={rigOptions}
      totals={stats.totals}
      snapshotAt={stats.snapshotAt}
    />
  );
}
