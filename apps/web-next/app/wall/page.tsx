import { Suspense } from "react";
import { basisOf, formatNumber, joinCells, loadDerived, metricOf } from "../../lib/engine";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import WallClient from "./wall-client";

export const metadata = { title: "The pool", description: "Every community benchmark cell with its provenance: measured or reported." };

export default async function WallPage() {
  const snapshot = loadDerived().stats.snapshotAt.slice(0, 10);
  // Agent twin (S32): the same cells the human view renders by default
  // (sort: fastest decode, top 60) as a fixed-column text table. A
  // re-presentation of one dataset, never a different query.
  if ((await currentView()) === "agent") {
    const rows = joinCells()
      .sort(
        (a, b) =>
          (metricOf(b.cell)?.value ?? b.cell.tokSOutMedian ?? -1) -
          (metricOf(a.cell)?.value ?? a.cell.tokSOutMedian ?? -1),
      )
      .slice(0, 60);
    const lines = rows.map(({ cell, model }) => {
      const metric = metricOf(cell);
      const value = metric ? `${formatNumber(metric.value)} ${metric.unit}` : `${formatNumber(cell.tokSOutMedian)} tok/s`;
      return `  ${cell.rigKey.padEnd(34)} | ${model.slug.padEnd(38)} | ${basisOf(cell).padEnd(8)} | ${value.padEnd(14)} | n=${cell.n}`;
    });
    return (
      <AgentView>
        {[
          "bestmodel.run / pool — agent view",
          "",
          "Honesty ladder: measured > reported > extrapolated > formula > no data yet.",
          "Top 60 cells, default sort: fastest decode. Columns: rig | model | basis | value | n.",
          "Full machine surface: /llms.txt · REST API: api.bestmodel.run",
          "",
          "  rig                               | model                                  | basis    | value          | n",
          ...lines,
          "",
          "Capture or correct a number: /console (signed, Ed25519).",
        ].join("\n")}
      </AgentView>
    );
  }
  // Tabular Spec-Sheet (S45): the data table is the page — the hero is one
  // honest frame line with the snapshot date, nothing above the data.
  return (
    <main>
      <section className="sheet-head">
        <h1>The pool, cell by cell</h1>
        <p className="sheet-frame">
          pool snapshot {snapshot} · every row is a real community cell with its basis and run
          count · ranking provisional · a signed run outranks any claim
        </p>
      </section>
      <Suspense fallback={<p className="summary">reading the pool...</p>}>
        <WallClient />
      </Suspense>
    </main>
  );
}
