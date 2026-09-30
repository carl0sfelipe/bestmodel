import { permanentRedirect } from "next/navigation";
import { basisOf, formatContext, formatNumber, loadDerived, metricOf } from "../../../lib/engine";
import { exactSuffixMatches, sugerirSlugs } from "../../../lib/sugerir-slugs";
import { currentView } from "../../../lib/view-server";
import AgentView from "../../_components/agent-view";

export function generateStaticParams() { return loadDerived().models.map((model) => ({ slug: model.slug })); }

function searchQuery(params: Record<string, string | string[] | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const item = Array.isArray(value) ? value[0] : value;
    if (item) query.set(key, item);
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = loadDerived();
  const model = data.models.find((item) => item.slug === slug);
  if (model) return { title: model.displayName ?? "Model", description: `${model.displayName} community pool results by reference rig.` };
  const slugs = data.models.map((item) => item.slug);
  const exact = exactSuffixMatches(slug, slugs);
  if (exact.length === 1) {
    const target = data.models.find((item) => item.slug === exact[0]);
    return { title: target?.displayName ?? exact[0], robots: { index: false } };
  }
  return { title: "Model not found", description: "No catalog entry for this slug.", robots: { index: false } };
}

export default async function ModelPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params; const data = loadDerived(); const model = data.models.find((item) => item.slug === slug);
  if (!model) {
    const slugs = data.models.map((item) => item.slug);
    const exact = exactSuffixMatches(slug, slugs);
    if (exact.length === 1) permanentRedirect(`/m/${exact[0]}${searchQuery(await searchParams)}`);
    const suggestions = sugerirSlugs(slug, slugs, 5);
    if ((await currentView()) === "agent") {
      return (
        <AgentView>
          {[
            "bestmodel.run / model — not found (agent view)",
            "",
            `slug "${slug}" is not in the catalog.`,
            "",
            "closest slugs:",
            ...suggestions.map((item) => `  /m/${item}`),
          ].join("\n")}
        </AgentView>
      );
    }
    return (
      <main>
        <section className="page-head">
          <p className="kicker">404</p>
          <h1>Model not found</h1>
          <p>No catalog entry for {slug}. Closest matches:</p>
          <div className="actions">
            {suggestions.map((item) => (
              <a key={item} className="btn" href={`/m/${item}`}>{item}</a>
            ))}
          </div>
        </section>
      </main>
    );
  }
  const cells = data.pool.filter((cell) => cell.modelSlug === model.slug); const runs = cells.reduce((total, cell) => total + cell.n, 0); const median = model.medianTokS;
  const bestMetricCell = cells.map((cell) => ({ cell, metric: metricOf(cell) })).filter(({ metric }) => metric).sort((a, b) => (b.metric!.value) - (a.metric!.value))[0];
  if ((await currentView()) === "agent") {
    const answer = median != null ? `${formatNumber(median)} tok/s (model median)` : bestMetricCell ? `${formatNumber(bestMetricCell.metric!.value)} ${bestMetricCell.metric!.unit} (best measured cell: ${bestMetricCell.cell.rigKey})` : "No data yet";
    const rows = cells.map((cell) => {
      const rig = data.hardware.find((item) => item.key === cell.rigKey);
      const metric = metricOf(cell);
      return `  ${(rig?.label ?? cell.rigKey).padEnd(34)} | ${cell.bits != null ? `${cell.bits}-bit` : cell.precision ?? "-"} | ${(metric ? `${formatNumber(metric.value)} ${metric.unit}` : `${formatNumber(cell.tokSOutMedian)} tok/s`).padEnd(14)} | ${basisOf(cell).padEnd(8)} | ttft ${formatNumber(cell.ttftMsMedian, 0)}ms | vram ${formatNumber(cell.peakVramGbMedian ?? cell.peakVramGb)} GB | ctx ${formatContext(cell.maxContextTested)}`;
    });
    return (
      <AgentView>
        {[
          `bestmodel.run / model — ${model.displayName ?? model.slug} (agent view)`,
          "",
          `category ${model.category} · ${model.hfId} · ${formatNumber(runs, 0)} runs in the model record`,
          `answer: ${answer}`,
          "",
          "Honesty ladder: measured > reported > extrapolated > formula > no data yet.",
          "Empty fields stay empty — never filled with an estimate.",
          "",
          "  rig | quant | median result | basis | ttft | peak vram | max context",
          ...rows,
        ].join("\n")}
      </AgentView>
    );
  }
  return <main><section className="model-hero"><p className="kicker">community pool / model answer</p><h1>{model.displayName ?? model.slug}</h1><p>{model.category} · {model.hfId}</p><p className="answer"><strong>{median != null ? `${formatNumber(median)} tok/s` : bestMetricCell ? `${formatNumber(bestMetricCell.metric!.value)} ${bestMetricCell.metric!.unit}` : "No data yet"}</strong>{median != null ? " · model median" : bestMetricCell ? ` · best measured cell (${bestMetricCell.cell.rigKey})` : ""} · {formatNumber(runs, 0)} runs in the model record.</p></section><section className="model-table-wrap"><table><thead><tr><th>Reference rig</th><th>Quantization</th><th>Median result</th><th>Basis</th><th>TTFT (ms)</th><th>Peak VRAM</th><th>Max context</th><th>Engines</th></tr></thead><tbody>{cells.map((cell) => { const rig = data.hardware.find((item) => item.key === cell.rigKey); const metric = metricOf(cell); return <tr key={`${cell.rigKey}-${cell.bits ?? cell.category ?? "x"}`}><td>{rig?.label ?? cell.rigKey}{cell.resolution ? ` · ${cell.resolution}` : ""}</td><td>{cell.bits != null ? `${cell.bits}-bit` : cell.precision ?? "—"}</td><td>{metric ? `${formatNumber(metric.value)} ${metric.unit}` : `${formatNumber(cell.tokSOutMedian)} tok/s`}</td><td><span className={`badge basis-${basisOf(cell)}`}>{basisOf(cell)}</span></td><td>{formatNumber(cell.ttftMsMedian, 0)}</td><td>{formatNumber(cell.peakVramGbMedian ?? cell.peakVramGb)} GB</td><td>{formatContext(cell.maxContextTested)}</td><td>{(cell.engines ?? []).join(", ") || cell.pipeline || "-"}</td></tr>; })}</tbody></table></section><section className="section"><h2>Context tested</h2><p className="section-copy">The table above is the tested context for each exact rig and quantization cell. Empty fields remain empty rather than being filled with an estimate.</p><div className="actions"><a className="btn primary" href="/wall">back to The wall -&gt;</a><a className="btn" href="/console">capture / correct -&gt;</a></div></section></main>;
}
