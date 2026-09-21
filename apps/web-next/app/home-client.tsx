"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

export type Answer = {
  name: string;
  slug: string;
  rigKey?: string;
  rigLabel?: string;
  tokS: number;
  metric: { value: number; unit: string; label: string } | null;
  n: number;
  basis: "measured" | "reported";
  maxContext: number | null;
};
export type AnswerIndex = Record<string, Answer[]>;
export type RigOption = { key: string; label: string; runCount: number };

/** The six from the approved prototype. Only text has pool data; the rest are
    visible and honestly disabled rather than quietly dropped. */
const INTENTS = [
  { id: "chat", name: "Chat", glyph: "▭", desc: "text generation · reasoning", category: "chat" },
  { id: "code", name: "Code", glyph: "<", desc: "completion · refactor", category: "code" },
  { id: "image", name: "Image gen", glyph: "▦", desc: "text → image", category: "image" },
  { id: "audio", name: "Audio", glyph: "∿", desc: "speech ↔ text", category: "audio" },
  { id: "video", name: "Video", glyph: "▶", desc: "generation · animation", category: "video" },
  { id: "vision", name: "Vision", glyph: "◉", desc: "image understanding", category: null },
] as const;

const BITS = [4, 5, 6, 8, 16] as const;

const CONTEXTS = [
  { value: 0, label: "any" },
  { value: 4096, label: "4k" },
  { value: 8192, label: "8k" },
  { value: 16384, label: "16k" },
  { value: 32768, label: "32k" },
] as const;

/** Reveals a section once it enters the viewport — a plain reduced-motion-safe
    fade. The per-word stagger reveal retired with the S43 craft pass (L06 D6:
    it read as a template tell, and it delayed the answer for no reason). */
function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setOn(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setOn(true);
            observer.disconnect();
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, on };
}

/** The hand-built ecosystem diagram, reinstated from the frozen archive
    (S43 / L06 D4) and redrawn to what ships today: every node below is a real
    component of this repo — community pool (data/derived), the Rust CLI loop
    (lab · plan · report · contribute), signed Ed25519 capture (/submit +
    intake), the REST API (apps/public-api), the agent twins (?as=agent +
    llms.txt) and the roofline predictors (packages/roofline-kernel). No
    planned or invented nodes appear. */
function Ecosystem() {
  const nodes: Array<{
    x: number;
    y: number;
    r?: number;
    name: string;
    sub: string;
    lx: number;
    ly: number;
    anchor: "start" | "middle" | "end";
  }> = [
    { x: 140, y: 100, name: "community pool", sub: "measured cells", lx: 140, ly: 48, anchor: "middle" },
    { x: 680, y: 90, name: "Rust CLI", sub: "lab · plan · report · contribute", lx: 680, ly: 38, anchor: "middle" },
    { x: 720, y: 320, name: "REST API", sub: "api.bestmodel.run/v1", lx: 728, ly: 372, anchor: "end" },
    { x: 540, y: 400, name: "predictors", sub: "roofline kernel", lx: 540, ly: 440, anchor: "middle" },
    { x: 240, y: 410, name: "agent twins", sub: "?as=agent · llms.txt", lx: 240, ly: 440, anchor: "middle" },
    { x: 80, y: 290, name: "signed capture", sub: "Ed25519 runs · /submit", lx: 72, ly: 340, anchor: "start" },
  ];
  return (
    <svg className="eco-svg" viewBox="0 0 800 460" role="img" aria-label="Diagram of the bestmodel.run loop: community pool, Rust CLI, REST API, roofline predictors, agent twins and signed capture, all feeding the engine.">
      {nodes.map((node) => (
        <line key={`ln-${node.name}`} className="eco-line" x1="400" y1="225" x2={node.x} y2={node.y} />
      ))}
      <circle className="eco-node center" cx="400" cy="225" r="46" />
      <text className="eco-core-lbl" x="400" y="222" textAnchor="middle">bestmodel.run</text>
      <text className="eco-sub" x="400" y="240" textAnchor="middle">engine</text>
      {nodes.map((node) => (
        <g key={`nd-${node.name}`}>
          <circle className="eco-node" cx={node.x} cy={node.y} r="26" />
          <text className="eco-lbl" x={node.lx} y={node.ly} textAnchor={node.anchor}>{node.name}</text>
          <text className="eco-sub" x={node.lx} y={node.ly + 15} textAnchor={node.anchor}>{node.sub}</text>
        </g>
      ))}
    </svg>
  );
}

export default function HomeClient({
  index,
  indexAny,
  rigs,
  totals,
  snapshotAt,
}: {
  index: AnswerIndex;
  /** Same join across EVERY rig — feeds the honest cross-rig pointer when the
      selected rig has no cell, so cloud anchors stay visible on the home. */
  indexAny?: AnswerIndex;
  rigs: RigOption[];
  totals: { runs: number; models: number; rigs: number };
  snapshotAt: string;
}) {
  const bench = useReveal<HTMLElement>();
  const ladder = useReveal<HTMLElement>();
  const eco = useReveal<HTMLElement>();

  const [intent, setIntent] = useState<string>("chat");
  const [rig, setRig] = useState<string>(rigs[0]?.key ?? "");
  const [bits, setBits] = useState<number>(4);
  const [context, setContext] = useState<number>(0);

  const category = INTENTS.find((item) => item.id === intent)?.category ?? null;
  const multimodal = category === "image" || category === "audio" || category === "video";

  // Which quantizations this rig + intent actually has cells for. Unavailable
  // ones stay visible but disabled — the absence is information.
  const availableBits = useMemo(() => {
    const set = new Set<number>();
    if (!category || !rig) return set;
    for (const bit of BITS) {
      if (index[`${rig}|${category}|${bit}`]?.length) set.add(bit);
    }
    return set;
  }, [index, rig, category]);

  const answers = useMemo(() => {
    if (!category || !rig) return [];
    // Multimodal cells carry no bits — they land under the 0 key and skip the
    // context floor, which is a text-only question.
    if (multimodal) return index[`${rig}|${category}|0`] ?? [];
    const rows = index[`${rig}|${category}|${bits}`] ?? [];
    if (!context) return rows;
    return rows.filter((row) => row.maxContext != null && row.maxContext >= context);
  }, [index, rig, category, bits, context, multimodal]);

  const best = answers[0] ?? null;

  // Claims tier (owner decision 2026-09-18): when this rig+intent has no
  // cell, surface the strongest community claims for the same intent
  // (+quantization) measured on OTHER rigs — always labeled unvalidated,
  // always credited, never presented as this rig's number.
  const claims = useMemo(() => {
    if (!category || !indexAny) return [];
    const seen = new Map<string, Answer>();
    for (const key of Object.keys(indexAny)) {
      const parts = key.split("|");
      if (parts[1] !== category) continue;
      if (!multimodal && parts[2] !== String(bits)) continue;
      for (const row of indexAny[key]) {
        if (row.rigKey === rig) continue; // a claim is someone ELSE's number
        const prev = seen.get(row.slug);
        if (!prev || (row.metric?.value ?? row.tokS) > (prev.metric?.value ?? prev.tokS)) {
          seen.set(row.slug, row);
        }
      }
    }
    return [...seen.values()]
      .sort((a, b) => (b.metric?.value ?? b.tokS) - (a.metric?.value ?? a.tokS))
      .slice(0, 3);
  }, [indexAny, category, bits, multimodal, rig]);

  const rigLabel = rigs.find((item) => item.key === rig)?.label ?? rig;

  return (
    <main>
      {/* --------------------------------------------- workbench (the hero) */}
      <section className={`bench scene-reveal${bench.on ? " on" : ""}`} ref={bench.ref}>
        <p className="bench-frame">
          <span className="t">$ bestmodel.run — workbench</span>
          <span>pool snapshot {snapshotAt.slice(0, 10)}</span>
          <span>
            {totals.runs.toLocaleString("en-US")} runs · {totals.models.toLocaleString("en-US")}{" "}
            models · {totals.rigs.toLocaleString("en-US")} rigs
          </span>
          <span>every number declares its basis</span>
        </p>
        <h1 className="bench-head">What do you want to run?</h1>
        <p className="bench-sub">
          Intent, machine, quantization and context are four separate decisions, so they get four
          separate controls. Nothing is fused and nothing is estimated — a combination the pool
          has never tested says so.
        </p>

        <div className="mad">
          <div className="mad-group">
            <span className="mad-label" id="lbl-intent">
              <b>01</b> what you want to run
            </span>
            <div className="opt-row" role="group" aria-labelledby="lbl-intent">
              {INTENTS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="opt"
                  aria-pressed={intent === item.id}
                  disabled={item.id === "vision"}
                  title={item.id === "vision" ? "no community data yet" : item.desc}
                  onClick={() => setIntent(item.id)}
                >
                  <span aria-hidden="true">{item.glyph}</span>
                  {item.name}
                  {item.id === "vision" && <span className="why">no data</span>}
                </button>
              ))}
            </div>
          </div>

          <div className="mad-group">
            <label className="mad-label" htmlFor="pick-rig">
              <b>02</b> the machine
            </label>
            <select
              id="pick-rig"
              className="select"
              value={rig}
              onChange={(event) => setRig(event.target.value)}
            >
              {rigs.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label} · {option.runCount} runs
                </option>
              ))}
            </select>
            <span className="opt-note">Ordered by how much the community has tested it.</span>
          </div>

          {!multimodal && <div className="mad-group">
            <span className="mad-label" id="lbl-quant">
              <b>03</b> quantization
            </span>
            <div className="opt-row" role="group" aria-labelledby="lbl-quant">
              {BITS.map((bit) => {
                const has = availableBits.has(bit);
                return (
                  <button
                    key={bit}
                    type="button"
                    className="opt"
                    aria-pressed={bits === bit}
                    disabled={!has}
                    title={has ? undefined : "no tested cell at this quantization"}
                    onClick={() => setBits(bit)}
                  >
                    {bit}-bit
                  </button>
                );
              })}
            </div>
          </div>}

          {!multimodal && <div className="mad-group">
            <span className="mad-label" id="lbl-ctx">
              <b>04</b> context floor
            </span>
            <div className="opt-row" role="group" aria-labelledby="lbl-ctx">
              {CONTEXTS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className="opt"
                  aria-pressed={context === option.value}
                  onClick={() => setContext(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <span className="opt-note">Filters to cells community-tested at least this far.</span>
          </div>}
        </div>

        <div className="verdict" aria-live="polite">
          {!category ? (
            <>
              <p className="verdict-none">No community data for this modality yet.</p>
              <p className="verdict-meta">
                The pool is text inference only. Image, audio, video and vision stay listed so the
                gap is visible rather than hidden.
              </p>
            </>
          ) : !best ? (
            <>
              <p className="verdict-none">No data yet for this combination.</p>
              <p className="verdict-meta">
                {multimodal
                  ? `Nobody has submitted a ${intent} run on ${rigLabel}`
                  : `Nobody has submitted a ${bits}-bit ${intent} run on ${rigLabel}`}
                {!multimodal && context
                  ? ` tested to ${context.toLocaleString("en-US")} tokens`
                  : ""}
                . That is an absence, not a zero — <Link href="/submit">capture one</Link> and it
                stops being empty.
              </p>
              {claims.length > 0 && (
                <div className="verdict-claims">
                  <p className="verdict-meta">
                    <strong>claim · unvalidated</strong> — same intent measured on other rigs in the
                    community pool (orientation only, never this machine&apos;s number · via
                    localmaxxing community pool):
                  </p>
                  {claims.map((row) => (
                    <div className="verdict-row" key={row.slug}>
                      <Link className="name" href={`/m/${row.slug}`}>
                        {row.name}
                      </Link>
                      <span className="v">
                        {(row.metric?.value ?? row.tokS).toLocaleString("en-US")}{" "}
                        {row.metric?.unit ?? "tok/s"}
                      </span>
                      <span className="v">on {row.rigLabel}</span>
                      <span className={`badge basis-${row.basis}`}>{row.basis}</span>
                      <span className="v">n={row.n}</span>
                    </div>
                  ))}
                  <p className="verdict-meta">
                    Run this rig? <Link href="/submit">Claim it with a capture</Link> and the claim
                    becomes a cell.
                  </p>
                </div>
              )}
            </>
          ) : (
            <>
              <p className="verdict-num">
                {(best.metric?.value ?? best.tokS).toLocaleString("en-US")}
                <small>{best.metric?.unit ?? "tok/s"} · {best.name}</small>
              </p>
              <p className="verdict-meta">
                <span className={`badge basis-${best.basis}`}>{best.basis}</span> · n={best.n} ·{" "}
                {multimodal
                  ? `${best.metric?.label ?? intent} on ${rigLabel}`
                  : `${bits}-bit on ${rigLabel}`}
                {best.maxContext
                  ? ` · community-tested up to ${best.maxContext.toLocaleString("en-US")} tokens`
                  : multimodal
                    ? ""
                    : " · context untested"}
              </p>

              {answers.length > 1 && (
                <div className="verdict-list">
                  {answers.slice(1).map((row) => (
                    <div className="verdict-row" key={row.slug}>
                      <Link className="name" href={`/m/${row.slug}`}>
                        {row.name}
                      </Link>
                      <span className="v">{(row.metric?.value ?? row.tokS).toLocaleString("en-US")} {row.metric?.unit ?? "tok/s"}</span>
                      <span className={`badge basis-${row.basis}`}>{row.basis}</span>
                      <span className="v">n={row.n}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <p className="bench-source">
          The verdict above is the pool answering, live from {totals.runs.toLocaleString("en-US")}{" "}
          community runs on real hardware. Frozen snapshot {snapshotAt.slice(0, 10)} — basis printed
          beside every number, ranking provisional.{" "}
          <Link href="/wall">Read the pool yourself</Link> or{" "}
          <Link href="/hardware">start from hardware</Link>.
        </p>
      </section>

      {/* ------------------------------------------------------ the ladder */}
      <section className={`scene scene-reveal${ladder.on ? " on" : ""}`} ref={ladder.ref}>
        <h2 className="craft-head">Every number declares its basis</h2>
        <div className="term">
          <div>
            <span className="p">$</span> basis --explain
          </div>
          <div>
            <span className="ok">measured</span> median of ≥3 single-stream runs on this exact cell
          </div>
          <div>
            <span className="am">reported</span> 1–2 runs · real, but thin
          </div>
          <div>
            <span className="am">claim (unvalidated)</span> best community claim for the same
            intent on another rig · orientation only, always labeled
          </div>
          <div>
            <span className="p">extrapolated</span> scaled by memory bandwidth · never shown as
            measured
          </div>
          <div>
            <span className="p">no data yet</span> nobody has run it · we say so
          </div>
        </div>
        <div className="actions">
          <Link className="btn primary" href="/submit">
            Capture a run
          </Link>
          <Link className="btn" href="/claims">
            See the wall
          </Link>
        </div>
      </section>

      {/* ------------------------------------------- the loop (hand-drawn) */}
      <section className={`scene scene-reveal${eco.on ? " on" : ""}`} ref={eco.ref}>
        <h2 className="craft-head">The loop that feeds the engine</h2>
        <p className="craft-sub">
          Nothing on this diagram is planned — every node is a component that ships in the repo
          today, and the engine is only as honest as the loop that feeds it.
        </p>
        <Ecosystem />
      </section>
    </main>
  );
}
