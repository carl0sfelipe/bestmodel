import { basisOf, loadDerived, metricOf, topRigs } from "../lib/engine";
import { currentView } from "../lib/view-server";
import AgentView from "./_components/agent-view";
import HomeClient, { type AnswerIndex, type RigOption } from "./home-client";

/** How many rigs the selector offers — the same cutoff the wall's rig filter uses. */
const RIG_LIMIT = 24;
/** How many models a single answer shows. */
const ANSWER_LIMIT = 6;

export default async function HomePage() {
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
      // The home hero is an implicit endorsement, so the honesty ladder puts measured data first.
      idx[key].sort((a, b) => {
        const basisRank = (basis: string) => (basis === "measured" ? 0 : 1);
        return basisRank(a.basis) - basisRank(b.basis) || (b.metric?.value ?? b.tokS) - (a.metric?.value ?? a.tokS);
      });
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

  // Agent twin (S32): the honesty ladder and the pool totals as text — the
  // same snapshot the human hero renders, never a different dataset.
  if ((await currentView()) === "agent") {
    const t = stats.totals;
    const snapshot = stats.snapshotAt.slice(0, 10);
    return (
      <AgentView>
        {[
          "bestmodel.run — what do you want to run?",
          "An honest compatibility engine for local AI, built from community pool measurements.",
          "",
          "Honesty ladder: measured > reported > extrapolated > formula > no data yet.",
          "A cell without a source class never renders. Numbers are never rounded in the flattering direction.",
          "",
          `Pool snapshot ${snapshot}:`,
          `  runs    ${t.runs.toLocaleString("en-US")}`,
          `  models  ${t.models.toLocaleString("en-US")}`,
          `  rigs    ${t.rigs.toLocaleString("en-US")}`,
          "",
          "Answers the pool can give (human view renders them interactively):",
          "  can it run?      /hardware — feasibility from bandwidth and VRAM rules",
          "  how fast?        /wall — every community cell with its basis and n",
          "  is it worth it?  /track-record — trust earned by verified acts",
          "",
          "Machine surfaces:",
          "  agent twins      append ?as=agent to any route",
          "  contract         /llms.txt",
          "  CLI quickstart   docs/agent-quickstart.md in the repo (git clone, no key)",
        ].join("\n")}
      </AgentView>
    );
  }

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
