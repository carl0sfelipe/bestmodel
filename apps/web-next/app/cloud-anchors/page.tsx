import { basisOf, formatNumber, loadDerived, metricOf, MIN_RUNS_MEASURED, type Cell } from "../../lib/engine";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import log from "./anchor-log.json";
import "./cloud-anchors.css";

export const metadata = {
  title: "Cloud anchors",
  description:
    "One rented session, two cards, every number with its basis and its date. Reference points for placing your own GPU on the same scale.",
};

/**
 * The anchor log (app/cloud-anchors/anchor-log.json) is the raw run record
 * of the 2026-08-31 anchor session: 19 runs on two rented cards, with the
 * host's driver and torch build, the timestamp of every run and the value
 * each run produced. It is the repo file anchors-modal-2026-08-31.jsonl with
 * two normalizations applied: the hardware strings are reduced to the GPU
 * model, and the rental host's name is dropped, because the site publishes
 * no cloud plans, prices or provider options. The sha256 of the untouched
 * source file travels with it so the copy is checkable.
 *
 * Cells are aggregated here the way the pool aggregates them: median of the
 * runs, n = number of runs. basis follows the site ladder — measured needs
 * MIN_RUNS_MEASURED runs or more.
 */
type AnchorRun = {
  kind?: string;
  category?: string;
  pipeline?: string;
  precision?: string;
  bits?: number;
  modelSlug: string;
  rigKey: string;
  gpuName?: string;
  torch?: string;
  tokSOutMedian?: number | null;
  tokSPrefillMedian?: number | null;
  ttftMsMedian?: number | null;
  wallS?: number;
  imagesPerSec?: number;
  audioXReal?: number;
  peakVramGb?: number;
  durationS?: number;
  steps?: number;
  resolution?: string;
  maxContextTested?: number;
  engines?: string[];
  hw: string;
  driver: string;
  ts: string;
  rep?: number;
};

type AnchorRig = {
  key: string;
  label: string;
  gpuName: string;
  memGb: number;
  gpuCount: number;
  bandwidthGBs: number;
  bandwidthBasis: string;
  formFactor: string;
};

type AnchorCell = {
  rigKey: string;
  modelSlug: string;
  displayName: string;
  kind: "text" | "image" | "audio" | "video";
  value: number;
  unit: string;
  label: string;
  n: number;
  basis: "measured" | "reported";
  quant: string;
  engine: string;
  peakVramGb: number;
  maxContextTested: number | null;
  extra: string;
  measuredAt: string;
  spread: number;
  prefill: { value: number; n: number } | null;
  ttftMs: { value: number; n: number } | null;
};

type AnchorModel = { slug: string; displayName: string; category: string };

const runs = log.runs as AnchorRun[];
const rigs = log.rigs as AnchorRig[];
const models = log.models as AnchorModel[];

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return NaN;
  const mid = Math.floor(sorted.length / 2);
  const value = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  return Math.round(value * 100) / 100;
}

/** Ratios print with both decimals: 2.00x, not 2x. */
function ratioText(value: number): string {
  return value.toFixed(2);
}

/** Value of one run, in the unit the intent catalog names for that modality. */
function runValue(run: AnchorRun): { value: number; unit: string; label: string } | null {
  const category = run.kind === "text" ? "chat" : run.category;
  if (!category) return null;
  if (category === "chat" || category === "code") {
    if (run.tokSOutMedian == null) return null;
    return { value: run.tokSOutMedian, unit: "tok/s", label: "decode" };
  }
  const metric = metricOf({ category, ...run } as unknown as { category: string });
  if (!metric) return null;
  return { value: metric.value, unit: metric.unit, label: metric.label };
}

function cellKey(run: AnchorRun): string {
  return `${run.rigKey}|${run.modelSlug}|${run.kind === "text" ? `bits-${run.bits}` : run.category}`;
}

/**
 * A secondary series inside a cell, with the count of runs that carried it.
 * The text reps of the anchor session record prefill and TTFT on the first
 * repetition only, so this series has its own n and never inherits the
 * cell's.
 */
function series(group: AnchorRun[], pick: (run: AnchorRun) => number | null | undefined) {
  const values = group.map(pick).filter((value): value is number => value != null && !Number.isNaN(value));
  if (!values.length) return null;
  return { value: median(values), n: values.length };
}

function buildCells(): AnchorCell[] {
  const groups = new Map<string, AnchorRun[]>();
  for (const run of runs) {
    const key = cellKey(run);
    const bucket = groups.get(key);
    if (bucket) bucket.push(run);
    else groups.set(key, [run]);
  }
  const cells: AnchorCell[] = [];
  for (const group of groups.values()) {
    const first = group[0];
    const measured = group.map(runValue).filter((row): row is { value: number; unit: string; label: string } => row != null);
    if (!measured.length) continue;
    const value = median(measured.map((row) => row.value));
    const spread = Math.max(...measured.map((row) => row.value)) - Math.min(...measured.map((row) => row.value));
    const model = models.find((row) => row.slug === first.modelSlug);
    const text = first.kind === "text";
    cells.push({
      rigKey: first.rigKey,
      modelSlug: first.modelSlug,
      displayName: model?.displayName ?? first.modelSlug,
      kind: text ? "text" : ((first.category as AnchorCell["kind"]) ?? "text"),
      value,
      unit: measured[0].unit,
      label: measured[0].label,
      n: group.length,
      basis: basisOf({ n: group.length } as Pick<Cell, "n">),
      quant: text ? `${first.bits}-bit` : (first.precision ?? "—"),
      engine: text ? (first.engines ?? []).join(", ") : (first.pipeline ?? "—"),
      peakVramGb: median(group.map((run) => run.peakVramGb ?? NaN).filter((v) => !Number.isNaN(v))),
      maxContextTested: first.maxContextTested ?? null,
      extra: text
        ? `context ${first.maxContextTested ?? 0} · peak VRAM ${formatNumber(median(group.map((run) => run.peakVramGb ?? NaN).filter((v) => !Number.isNaN(v))), 2)} GB`
        : first.resolution
          ? `${first.resolution} · ${first.steps ?? 1} step · peak VRAM ${formatNumber(median(group.map((run) => run.peakVramGb ?? NaN).filter((v) => !Number.isNaN(v))), 2)} GB`
          : `peak VRAM ${formatNumber(median(group.map((run) => run.peakVramGb ?? NaN).filter((v) => !Number.isNaN(v))), 2)} GB`,
      measuredAt: group.map((run) => run.ts).sort().at(-1) ?? "",
      spread,
      prefill: text ? series(group, (run) => run.tokSPrefillMedian) : null,
      ttftMs: text ? series(group, (run) => run.ttftMsMedian) : null,
    });
  }
  return cells.sort((a, b) => a.rigKey.localeCompare(b.rigKey) || a.modelSlug.localeCompare(b.modelSlug));
}

const cells = buildCells();
const byRig = new Map<string, AnchorCell[]>();
for (const cell of cells) {
  const bucket = byRig.get(cell.rigKey);
  if (bucket) bucket.push(cell);
  else byRig.set(cell.rigKey, [cell]);
}

// The pool snapshot: which anchor cells the site currently publishes, and
// which anchor runs are not in it. Cross-checked, never asserted in prose.
const { pool, stats, hardware } = loadDerived();
// Rigs in the pool whose own label names an SXM module, counted so the
// form-factor note below can be checked against the catalogue rather than
// asserted.
const sxmRigCount = hardware.filter((rig) => rig.label.includes("SXM")).length;
const poolCell = (cell: AnchorCell) =>
  pool.find(
    (row) =>
      row.rigKey === cell.rigKey &&
      row.modelSlug === cell.modelSlug &&
      (cell.kind === "text" ? row.bits === Number(cell.quant.replace("-bit", "")) : row.category === cell.kind),
  );

// The pair: one model, one quantization, measured on both cards.
const pairModel = "unsloth-llama-3-1-8b-instruct-gguf";
const pairCells = cells.filter((cell) => cell.modelSlug === pairModel);
const pairLow = pairCells.find((cell) => cell.rigKey === "l4-24gb");
const pairHigh = pairCells.find((cell) => cell.rigKey === "a10-24gb");
const decodeRatio = pairLow && pairHigh ? pairHigh.value / pairLow.value : null;
const bwRatio = pairLow && pairHigh ? (rigs.find((r) => r.key === "a10-24gb")?.bandwidthGBs ?? 0) / (rigs.find((r) => r.key === "l4-24gb")?.bandwidthGBs ?? 0) : null;

const snapshotAt = stats.snapshotAt.slice(0, 10);
const logDate = log.source.logDate;
const publishedCells = cells.filter((cell) => poolCell(cell));

export default async function CloudAnchorsPage() {
  if ((await currentView()) === "agent") {
    const lines = cells.map((cell) => {
      const rig = rigs.find((row) => row.key === cell.rigKey);
      return `  ${(rig?.label ?? cell.rigKey).padEnd(22)} | ${cell.displayName.padEnd(34)} | ${cell.quant.padEnd(8)} | ${cell.basis.padEnd(8)} | ${`${formatNumber(cell.value, 2)} ${cell.unit}`.padEnd(14)} | n=${cell.n}`;
    });
    return (
      <AgentView>
        {[
          "bestmodel.run / cloud anchors — agent view",
          "",
          `Rented hardware measured by the maintainer, log ${logDate}. ${log.source.runs} runs,`,
          "two cards. Not community hardware. Honesty ladder: measured > reported >",
          "extrapolated > formula > no data yet.",
          "",
          "Reading conditions:",
          "  1. hardware rented by the maintainer, dated and hashed, not community submissions",
          "  2. the host image sets driver and torch; the log records what it knows of the stack",
          "  3. form factor and bandwidth are vendor specs, not pool measurements",
          "  4. the lowest reading of each multimodal batch is its first; every cell here is a median",
          "  5. the log is silent on disk state, host load and any rental terms",
          "",
          "  card                  | model                            | quant    | basis    | value          | n",
          ...lines,
          "",
          "Pair to interpolate from (same model, same quant, same engine, both cards):",
          "  Llama 3.1 8B Instruct GGUF 4-bit on llama.cpp:",
          `    L4  ${formatNumber(pairLow?.value, 2)} tok/s (n=${pairLow?.n})`,
          `    A10 ${formatNumber(pairHigh?.value, 2)} tok/s (n=${pairHigh?.n})`,
          `  decode ${ratioText(decodeRatio ?? NaN)}x against a ${ratioText(bwRatio ?? NaN)}x vendor bandwidth ratio.`,
          "  A bracket to interpolate inside, not a coefficient to multiply by.",
          "",
          `Source log: anchor run log ${logDate}. sha256 ${log.source.sha256}.`,
          `Frozen pool snapshot ${snapshotAt} carries ${publishedCells.length} of ${cells.length} anchor cells.`,
          "The site publishes no cloud plans, prices or provider options. Anchors are reference points.",
        ].join("\n")}
      </AgentView>
    );
  }

  const imageCell = cells.find((cell) => cell.kind === "image");
  const audioCell = cells.find((cell) => cell.kind === "audio");
  const firstImageSample = runs.find((run) => run.imagesPerSec != null)?.imagesPerSec ?? NaN;
  const firstAudioSample = runs.find((run) => run.audioXReal != null)?.audioXReal ?? NaN;

  return (
    <main>
      <section className="page-head an-head">
        <p className="kicker">bestmodel.run / cloud anchors</p>
        <h1>One session, two rented cards, dated.</h1>
        <p>
          The pool measures cards people own. These two the maintainer rented, paid for once and
          dated. One session on {logDate}, {log.source.runs} jobs, and the record kept. Every number
          below carries its own basis, its own run count and its own date, so a reader can place a
          GPU they own next to a GPU they will never own.
        </p>
        <div className="figs">
          <div className="fig">
            <span className="v">{formatNumber(rigs.length, 0)}</span>
            <span className="k">rented cards measured</span>
          </div>
          <div className="fig">
            <span className="v">{formatNumber(cells.length, 0)}</span>
            <span className="k">anchor cells</span>
          </div>
          <div className="fig">
            <span className="v">{formatNumber(log.source.runs, 0)}</span>
            <span className="k">runs in the log</span>
          </div>
          <div className="fig">
            <span className="v">{logDate}</span>
            <span className="k">log date</span>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>Terms of an anchor</h2>
        <p className="section-copy">
          Five things a reader has to hold before an anchor number means anything. Without them an
          anchor reads like a community cell, and it is not one.
        </p>
        <ol className="an-cond">
          <li>
            <span className="an-cond-n">01</span>
            <span>
              <span className="an-cond-k">Whose card</span>
              <p>
                Hardware the community does not own. The maintainer rented both cards for the
                session on {logDate}; the runs are the maintainer's own, dated and hashed, not a
                community submission and not a claim.
              </p>
            </span>
          </li>
          <li>
            <span className="an-cond-n">02</span>
            <span>
              <span className="an-cond-k">Whose stack</span>
              <p>
                The host image decides the driver and the torch build. The multimodal runs record
                both: {runs.find((run) => run.torch)?.torch}, driver{" "}
                {runs.find((run) => run.driver)?.driver}. The text runs record the engine, llama.cpp,
                and leave the stack unstated. Nobody tuned any of it, and the log says which parts
                of the stack it knows.
              </p>
            </span>
          </li>
          <li>
            <span className="an-cond-n">03</span>
            <span>
              <span className="an-cond-k">Form factor is a spec</span>
              <p>
                Both cards are PCIe add-in boards. The memory bandwidth quoted for each,{" "}
                {rigs.map((rig) => `${formatNumber(rig.bandwidthGBs, 0)} GB/s`).join(" and ")}, is a
                vendor figure rather than a pool measurement: it is the yardstick for reading the
                numbers, not one of them. The pool also holds {sxmRigCount} SXM-module rigs, and a
                number measured on a PCIe board does not transfer to an SXM module without a step in
                between.
              </p>
            </span>
          </li>
          <li>
            <span className="an-cond-n">04</span>
            <span>
              <span className="an-cond-k">The first sample is not the median</span>
              <p>
                The lowest reading of each multimodal batch is the first one recorded. On the image
                job that run read {formatNumber(firstImageSample, 2)} img/s against a{" "}
                {formatNumber(imageCell?.value, 2)} img/s median; on the audio job it read{" "}
                {formatNumber(firstAudioSample, 2)}×real against {formatNumber(audioCell?.value, 2)}×real.
                Every cell here is a median over its runs for that reason, and the spread column
                shows how wide the batch was.
              </p>
            </span>
          </li>
          <li>
            <span className="an-cond-n">05</span>
            <span>
              <span className="an-cond-k">What the log is silent on</span>
              <p>
                A rented card is not a card at home, and the log is deliberately silent on the three
                differences that matter: whether weights sat on a local disk or were fetched per run,
                whether the machine carried other work at the time, and how the card was attached
                beyond the vendor form factor. Nothing here is a claim about the rental host. Take
                an anchor as a bound on a scale, and read it against the community cell on the
                hardware you actually own.
              </p>
            </span>
          </li>
        </ol>
      </section>

      <section className="section">
        <h2>The two cards</h2>
        <p className="section-copy">
          Each card is one clause of the anchor: what it is, and what it produced. Cells carry the
          median of their runs, the basis the site ladder gives that count — measured once a cell
          reaches {MIN_RUNS_MEASURED} runs, reported below that — and the date of the run that
          produced it.
        </p>

        {rigs.map((rig, index) => (
          <article className="an-clause" key={rig.key}>
            <div className="an-clause-top">
              <span className="an-ord">CLAUSE {index === 0 ? "I" : "II"}</span>
              <h3 className="an-clause-name">{rig.label}</h3>
            </div>
            <dl className="an-clause-spec">
              <div>
                <dt>form</dt>
                <dd>{rig.formFactor} · vendor spec</dd>
              </div>
              <div>
                <dt>memory</dt>
                <dd>{formatNumber(rig.memGb, 0)} GB</dd>
              </div>
              <div>
                <dt>gpus</dt>
                <dd>{rig.gpuCount}</dd>
              </div>
              <div>
                <dt>bandwidth</dt>
                <dd>
                  {formatNumber(rig.bandwidthGBs, 0)} GB/s · {rig.bandwidthBasis}
                </dd>
              </div>
              <div>
                <dt>runs</dt>
                <dd>
                  {formatNumber(runs.filter((run) => run.rigKey === rig.key).length, 0)}
                </dd>
              </div>
            </dl>

            <div className="an-measures">
              {(byRig.get(rig.key) ?? []).map((cell) => (
                <div className="an-measure" key={`${cell.rigKey}-${cell.modelSlug}-${cell.quant}`}>
                  <div className="an-m-model">
                    <strong>{cell.displayName}</strong>
                    <span>
                      {cell.quant}
                      {cell.engine !== cell.modelSlug && ` · ${cell.engine}`} · {cell.label}
                    </span>
                  </div>
                  <div className="an-m-value">
                    {formatNumber(cell.value, 2)}
                    <small>{cell.unit}</small>
                  </div>
                  <div className="an-m-basis">
                    <span className={`badge basis-${cell.basis}`}>{cell.basis}</span>
                    <span className="an-m-n">
                      n={cell.n} · {cell.measuredAt.slice(0, 10)}
                    </span>
                  </div>
                  <div className="an-m-extra">
                    <span>{cell.extra}</span>
                    {cell.prefill && (
                      <span>
                        prefill <b>{formatNumber(cell.prefill.value)} tok/s</b> (n={cell.prefill.n})
                      </span>
                    )}
                    {cell.ttftMs && (
                      <span>
                        ttft <b>{formatNumber(cell.ttftMs.value, 0)} ms</b> (n={cell.ttftMs.n})
                      </span>
                    )}
                    <span>
                      spread <b>{formatNumber(cell.spread, 2)} {cell.unit}</b>
                    </span>
                    <span>
                      in pool snapshot <b>{poolCell(cell) ? "yes" : "no"}</b>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      {pairLow && pairHigh && (
        <section className="section">
          <h2>One model, two cards</h2>
          <p className="section-copy">
            Llama 3.1 8B Instruct GGUF at 4-bit, on llama.cpp, on both cards, three runs each. This
            is the pair a reader interpolates from: same model, same quantization, same engine,
            different memory bandwidth.
          </p>
          <div className="an-pair">
            <div className="an-pair-side" data-k="low">
              <div className="an-pair-rig">{rigs.find((rig) => rig.key === pairLow.rigKey)?.label}</div>
              <div className="an-pair-val">
                {formatNumber(pairLow.value, 2)}
                <small>tok/s</small>
              </div>
              <div className="an-pair-meta">
                n={pairLow.n} · {pairLow.basis} · {pairLow.measuredAt.slice(0, 10)}
              </div>
            </div>
            <div className="an-pair-side" data-k="high">
              <div className="an-pair-rig">{rigs.find((rig) => rig.key === pairHigh.rigKey)?.label}</div>
              <div className="an-pair-val">
                {formatNumber(pairHigh.value, 2)}
                <small>tok/s</small>
              </div>
              <div className="an-pair-meta">
                n={pairHigh.n} · {pairHigh.basis} · {pairHigh.measuredAt.slice(0, 10)}
              </div>
            </div>
          </div>
          <div className="an-ratio">
            <div>
              <span className="v">{ratioText(decodeRatio ?? NaN)}×</span>
              <span className="k">decode gain</span>
            </div>
            <div>
              <span className="v">{ratioText(bwRatio ?? NaN)}×</span>
              <span className="k">vendor bandwidth ratio</span>
            </div>
            <div>
              <span className="v">{ratioText((decodeRatio ?? 0) / (bwRatio || 1))}×</span>
              <span className="k">of the bandwidth ratio</span>
            </div>
          </div>
          <p className="an-note section-copy">
            Decode moved {ratioText(decodeRatio ?? NaN)}× while quoted memory bandwidth moved{" "}
            {ratioText(bwRatio ?? NaN)}×. The gain is sub-linear against bandwidth, which is
            what memory-bound decode looks like when it is not purely proportional to it. Two
            points on a curve, not the curve: treat the pair as a bracket to interpolate inside,
            never as a coefficient to multiply by.
          </p>
        </section>
      )}

      <section className="section">
        <h2>Where the anchors stand</h2>
        <p className="section-copy">
          The frozen pool snapshot of {snapshotAt} carries {publishedCells.length} of the{" "}
          {cells.length} anchor cells:{" "}
          {publishedCells
            .map((cell) => `${cell.displayName} on ${rigs.find((rig) => rig.key === cell.rigKey)?.label ?? cell.rigKey}`)
            .join(", ") || "none"}
          . The rest of that session stayed in the log. The wall of community cells is at /wall; the
          machine catalogue is at /hardware.
        </p>
        <p className="an-source">
          source: anchor run log {logDate}, {log.source.runs} runs, {log.source.window} · sha256{" "}
          {log.source.sha256} · measured by the maintainer on hardware rented for the session ·
          hardware strings reduced to the GPU model and the rental host's name dropped
        </p>
        <div className="actions">
          <a className="btn primary" href="/wall">
            the measured pool -&gt;
          </a>
          <a className="btn" href="/hardware">
            reference rigs -&gt;
          </a>
        </div>
      </section>

      <section className="section">
        <h2>What an anchor is not</h2>
        <p className="section-copy">
          No plan, no price, no provider list, no way to buy compute from this page. bestmodel.run
          measures hardware people own and publishes the numbers with their basis. The anchors are
          reference points bought once to calibrate that scale against hardware outside the
          community pool, and they stay on the site as dated measurements, not as an offering.
        </p>
      </section>
    </main>
  );
}
