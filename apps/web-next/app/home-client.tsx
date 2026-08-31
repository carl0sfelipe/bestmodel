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

/** Reveals a section once it enters the viewport, like the prod narrative. */
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

function Words({ text }: { text: string }) {
  return (
    <>
      {text.split(" ").map((word, i) => (
        <span className="w" key={`${word}-${i}`}>
          {word}
          {i < text.split(" ").length - 1 ? " " : ""}
        </span>
      ))}
    </>
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
  const hero = useReveal<HTMLElement>();
  const picker = useReveal<HTMLElement>();
  const scale = useReveal<HTMLElement>();
  const honesty = useReveal<HTMLElement>();

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

  // Best cell anywhere in the pool for this exact intent (+ quantization when
  // it applies), used only to point beyond the selected rig's absence.
  const bestAnywhere = useMemo(() => {
    if (!category || !indexAny) return null;
    let top: Answer | null = null;
    for (const key of Object.keys(indexAny)) {
      const parts = key.split("|");
      if (parts[1] !== category) continue;
      if (!multimodal && parts[2] !== String(bits)) continue;
      for (const row of indexAny[key]) {
        if (!top || (row.metric?.value ?? row.tokS) > (top.metric?.value ?? top.tokS)) top = row;
      }
    }
    return top;
  }, [indexAny, category, bits, multimodal]);

  const rigLabel = rigs.find((item) => item.key === rig)?.label ?? rig;

  return (
    <main>
      {/* ---------------------------------------------------------- scene 01 */}
      <section className={`scene lead scene-reveal${picker.on ? " on" : ""}`} ref={picker.ref}>
        <p className="overline">01 — the question</p>
        <h1 className="scene-head">
          <Words text="What do you" />
          <em>
            <Words text=" want to run?" />
          </em>
        </h1>
        <p className="scene-sub">
          Intent, machine, quantization and context are four separate decisions, so they get four
          separate controls. Nothing is fused, and nothing is estimated — if the pool has never
          tested a combination, it says so.
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
              {bestAnywhere && bestAnywhere.rigLabel !== rigLabel && (
                <p className="verdict-meta">
                  Measured elsewhere in the pool:{" "}
                  <strong>
                    {(bestAnywhere.metric?.value ?? bestAnywhere.tokS).toLocaleString("en-US")}{" "}
                    {bestAnywhere.metric?.unit ?? "tok/s"}
                  </strong>{" "}
                  · {bestAnywhere.name} on {bestAnywhere.rigLabel} ·{" "}
                  <span className={`badge basis-${bestAnywhere.basis}`}>{bestAnywhere.basis}</span>{" "}
                  n={bestAnywhere.n} · <Link href={`/m/${bestAnywhere.slug}`}>details</Link>
                </p>
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
      </section>

      {/* ---------------------------------------------------------- scene 02 */}
      <section className={`scene scene-reveal${hero.on ? " on" : ""}`} ref={hero.ref}>
        <p className="overline">02 — the answer</p>
        <h2 className="scene-head">
          <Words text="Your machine already" />
          <em>
            <Words text=" has an answer." />
          </em>
        </h2>
        <p className="scene-sub">
          You just asked it. What came back is not a spec-sheet estimate — it is what{" "}
          {totals.runs.toLocaleString("en-US")} community runs on real hardware actually recorded,
          with the basis printed beside every number.
        </p>
        <div className="actions">
          <Link className="btn primary" href="/claims">
            See the wall
          </Link>
          <Link className="btn" href="/hardware">
            Start from hardware
          </Link>
        </div>
      </section>

      {/* ---------------------------------------------------------- scene 03 */}
      <section className={`scene scene-reveal${scale.on ? " on" : ""}`} ref={scale.ref}>
        <p className="overline">03 — the pool</p>
        <h2 className="scene-head">
          <Words text="Measured beats" />
          <em>
            <Words text=" reported." />
          </em>
        </h2>
        <p className="scene-sub">
          A cell becomes <em>measured</em> at three runs. Below that it stays visibly{" "}
          <em>reported</em>, and a combination nobody has tested renders as no data yet rather than
          as a plausible-looking estimate.
        </p>
        <div className="stats-grid">
          <div className="card">
            <div className="stat-value">{totals.runs.toLocaleString("en-US")}</div>
            <div className="stat-label">runs in the pool</div>
          </div>
          <div className="card">
            <div className="stat-value">{totals.models.toLocaleString("en-US")}</div>
            <div className="stat-label">models indexed</div>
          </div>
          <div className="card">
            <div className="stat-value">{totals.rigs.toLocaleString("en-US")}</div>
            <div className="stat-label">reference rigs</div>
          </div>
        </div>
        <p className="note">Frozen snapshot {snapshotAt.slice(0, 10)} — not live throughput.</p>
      </section>

      {/* ---------------------------------------------------------- scene 04 */}
      <section className={`scene scene-reveal${honesty.on ? " on" : ""}`} ref={honesty.ref}>
        <p className="overline">04 — the ladder</p>
        <h2 className="scene-head">
          <Words text="Every number" />
          <em>
            <Words text=" declares its basis." />
          </em>
        </h2>
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
          <Link className="btn" href="/wall">
            Read the pool
          </Link>
        </div>
      </section>
    </main>
  );
}
