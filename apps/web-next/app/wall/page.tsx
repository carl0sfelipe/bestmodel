import { Suspense } from "react";
import { basisOf, formatNumber, joinCells, metricOf } from "../../lib/engine";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import WallClient from "./wall-client";

export const metadata = { title: "The wall", description: "Every community benchmark cell with its provenance: measured or reported." };

export default async function WallPage() {
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
  return <main><section className="page-head"><p className="kicker">bestmodel.run / the wall</p><h1>What the community<br />actually measures.</h1><p>Every row is a real cell from the community pool. Cells carry their run count and their basis, and ranking is provisional.</p><div className="actions"><a className="btn primary" href="/console">capture or correct a number -&gt;</a></div></section><Suspense fallback={<p className="summary">reading the pool...</p>}><WallClient /></Suspense></main>;
}
