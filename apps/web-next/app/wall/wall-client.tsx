"use client";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { basisOf, formatContext, formatNumber, joinCells, loadDerived, metricOf, topRigs } from "../../lib/engine";

export default function WallClient() {
  const query = useSearchParams();
  const [rig, setRig] = useState(query.get("rig") ?? "all");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState("toks");
  const rows = joinCells().filter((row) => rig === "all" || row.cell.rigKey === rig).filter((row) => category === "all" || row.model.category === category).sort((a, b) => sort === "runs" ? b.cell.n - a.cell.n : sort === "context" ? (b.cell.maxContextTested ?? 0) - (a.cell.maxContextTested ?? 0) : (metricOf(b.cell)?.value ?? b.cell.tokSOutMedian ?? -1) - (metricOf(a.cell)?.value ?? a.cell.tokSOutMedian ?? -1)).slice(0, 60);
  const categories = [...new Set(loadDerived().models.map((model) => model.category))];
  // Tabular Spec-Sheet (S45): one row per cell, every column on screen — the
  // same fields the agent twin prints (rig | model | basis | value | n), plus
  // the context/bits the human filters on. Nothing estimated renders.
  return (
    <section aria-live="polite">
      <div className="toolbar">
        <label><span className="sr-only">hardware</span><select className="select" value={rig} onChange={(event) => setRig(event.target.value)}><option value="all">all hardware</option>{topRigs().filter((item) => item.runCount).slice(0, 24).map((item) => <option key={item.key} value={item.key}>{item.label} · {item.runCount} runs</option>)}</select></label>
        <label><span className="sr-only">category</span><select className="select" value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">all categories</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><span className="sr-only">sort</span><select className="select" value={sort} onChange={(event) => setSort(event.target.value)}><option value="toks">sort: fastest decode</option><option value="runs">sort: most runs</option><option value="context">sort: context tested</option></select></label>
      </div>
      <p className="summary">
        {rows.length} cells shown · {rows.filter((row) => basisOf(row.cell) === "measured").length} measured · {rows.filter((row) => basisOf(row.cell) === "reported").length} reported · MIN_RUNS_MEASURED = 3 · <a className="wall-action" href="/console">capture or correct a number -&gt;</a>
      </p>
      <div className="sheet-wrap">
        <table className="sheet">
          <thead>
            <tr><th aria-label="rank">#</th><th>model</th><th>rig</th><th>basis</th><th>value</th><th>n</th><th>ctx</th><th>bits</th></tr>
          </thead>
          <tbody>
            {rows.map(({ cell, model, rig: hardware }, index) => {
              const metric = metricOf(cell);
              return (
                <tr key={`${cell.rigKey}-${cell.modelSlug}-${cell.bits}`}>
                  <td className="rank">{index + 1}</td>
                  <td className="sheet-model">{model.displayName ?? model.slug}<span className="sheet-cat">{model.category}</span></td>
                  <td className="sheet-rig">{hardware?.label ?? cell.rigKey}</td>
                  <td><span className={`badge basis-${basisOf(cell)}`}>{basisOf(cell)}</span></td>
                  <td className="sheet-val">{metric ? `${formatNumber(metric.value)} ${metric.unit}` : `${formatNumber(cell.tokSOutMedian)} tok/s`}</td>
                  <td className="sheet-n">{cell.n}</td>
                  <td>{formatContext(cell.maxContextTested)}</td>
                  <td>{cell.bits != null ? `${cell.bits}-bit` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note">Rows are community cells (medians), ranked provisionally. A signed run outranks any claim.</p>
    </section>
  );
}
