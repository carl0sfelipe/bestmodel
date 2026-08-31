import { basisOf, loadDerived, metricOf, topRigs } from "../lib/engine";
import HomeClient, { type AnswerIndex, type RigOption } from "./home-client";

/** How many rigs the selector offers — the same cutoff the wall's rig filter uses. */
const RIG_LIMIT = 24;
/** How many models a single answer shows. */
const ANSWER_LIMIT = 6;

export default function HomePage() {
  const { models, pool, stats } = loadDerived();
  const byModel = new Map(models.map((model) => [model.slug, model]));

  const rigs = topRigs()
    .filter((rig) => (rig.runCount ?? 0) > 0)
    .slice(0, RIG_LIMIT);
  const rigKeys = new Set(rigs.map((rig) => rig.key));

  // The join runs on the server against the real pool, so the browser receives
  // answers rather than a database. Every entry is a measured or reported cell —
  // nothing here is estimated, and a combination with no cell simply has no key.
  const index: AnswerIndex = {};
  for (const cell of pool) {
    if (!rigKeys.has(cell.rigKey)) continue;
    const model = byModel.get(cell.modelSlug);
    if (!model) continue;
    const metric = metricOf(cell);
    if (cell.tokSOutMedian == null && metric == null) continue;
    const key = `${cell.rigKey}|${model.category}|${cell.bits ?? 0}`;
    (index[key] ??= []).push({
      name: model.displayName ?? model.slug,
      slug: model.slug,
      tokS: cell.tokSOutMedian == null ? 0 : Math.round(cell.tokSOutMedian * 10) / 10,
      metric: metric ? { value: Math.round(metric.value * 10) / 10, unit: metric.unit, label: metric.label } : null,
      n: cell.n,
      basis: basisOf(cell),
      maxContext: cell.maxContextTested ?? null,
    });
  }
  for (const key of Object.keys(index)) {
    index[key].sort((a, b) => (b.metric?.value ?? b.tokS) - (a.metric?.value ?? a.tokS));
    index[key] = index[key].slice(0, ANSWER_LIMIT);
  }

  const rigOptions: RigOption[] = rigs.map((rig) => ({
    key: rig.key,
    label: rig.label,
    runCount: rig.runCount ?? 0,
  }));

  return (
    <HomeClient
      index={index}
      rigs={rigOptions}
      totals={stats.totals}
      snapshotAt={stats.snapshotAt}
    />
  );
}
