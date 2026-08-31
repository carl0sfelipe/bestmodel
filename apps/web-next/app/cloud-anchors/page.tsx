import { basisOf, loadDerived, metricOf } from "../../lib/engine";

export default function CloudAnchorsPage() {
  const { models, pool, hardware } = loadDerived();
  const modelBySlug = new Map(models.map((model) => [model.slug, model]));
  const hardwareByKey = new Map(hardware.map((rig) => [rig.key, rig]));

  // Cloud is marked by the fragile label suffix; there is no cloud boolean field.
  const cloudKeys = new Set(hardware.filter((rig) => rig.label.endsWith("(modal)")).map((rig) => rig.key));
  const anchors = pool
    .filter((cell) => cloudKeys.has(cell.rigKey))
    .map((cell) => ({ cell, model: modelBySlug.get(cell.modelSlug), rig: hardwareByKey.get(cell.rigKey) }))
    .filter((anchor) => anchor.model && anchor.rig);

  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / cloud anchors</p>
        <h1>Runs that anchor the scale.</h1>
        <p>Measured runs on rented GPUs, outside the community hardware pool, to anchor the scale.</p>
      </section>

      <section className="section">
        <div className="wall-list">
          {anchors.map(({ cell, model, rig }) => {
            const metric = metricOf(cell);
            return (
              <article className="wall-row" key={`${cell.rigKey}-${cell.modelSlug}-${cell.bits ?? cell.category}`}>
                <div className="wall-head">
                  <strong className="wall-model">{model!.displayName ?? model!.slug}</strong>
                  <span className="badge">{model!.category}</span>
                  <span className="badge basis-measured">{basisOf(cell)}</span>
                </div>
                <div className="wall-speed">
                  {metric ? `${metric.value} ${metric.unit}` : `${cell.tokSOutMedian} tok/s`}
                </div>
                <p className="wall-meta">
                  {rig!.label} · {cell.bits != null ? `${cell.bits}-bit · ` : ""}basis {basisOf(cell)} · n={cell.n}
                </p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="section">
        <h2>A10 × L4</h2>
        <p className="section-copy">
          Same model, same 4-bit quantization, n=3 on both sides: decode moved from 44.76 to 75.83 tok/s, or 1.69×,
          while memory bandwidth moved from 300 to 600 GB/s, or 2.0×. The gain is sub-linear relative to bandwidth,
          consistent with memory-limited decode without being proportional to it.
        </p>
      </section>
    </main>
  );
}
