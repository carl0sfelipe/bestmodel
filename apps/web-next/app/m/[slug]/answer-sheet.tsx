"use client";
// AnswerSheet — the answer layer of /m/[slug]. It is a client island so the
// page can stay statically prerendered for every slug (no per-request work,
// no API call) while still answering "and on MY rig?" from the ?rig= token.
//
// The server renders the same markup with the default answer, so the static
// HTML already carries the verdict and its basis.

import { useEffect, useMemo, useState } from "react";
import { groupByRig, matchRigKey, num, pickVerdict, type SheetRow } from "./sheet";

type RigLabel = { key: string; label: string };

type Props = {
  rows: SheetRow[];
  rigLabels: RigLabel[];
};

export default function AnswerSheet({ rows, rigLabels }: Props) {
  const [rigToken, setRigToken] = useState<string | null>(null);

  useEffect(() => {
    const read = () => new URLSearchParams(window.location.search).get("rig");
    setRigToken(read());
    const onPop = () => setRigToken(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const groups = useMemo(() => groupByRig(rows), [rows]);
  const labelByKey = useMemo(() => new Map(rigLabels.map((rig) => [rig.key, rig.label])), [rigLabels]);

  const matchedKey = matchRigKey(rigToken, rows);
  const rigInPool = rigToken
    ? rigLabels.find((rig) => rig.key.toLowerCase() === rigToken.trim().toLowerCase())
    : undefined;
  const verdict = pickVerdict(rows, matchedKey);
  const askedForUnknownRig = Boolean(rigToken) && !matchedKey && !rigInPool;
  const askedForRigWithoutCell = Boolean(rigToken) && !matchedKey && Boolean(rigInPool);

  const choose = (key: string | null) => {
    setRigToken(key);
    const url = new URL(window.location.href);
    if (key) url.searchParams.set("rig", key);
    else url.searchParams.delete("rig");
    window.history.pushState({}, "", url.toString());
  };

  const row = verdict.row;
  const value = row?.metric ? num(row.metric.value) : null;
  const unit = row?.metric?.unit ?? "";

  return (
    <section className="ans-answer" aria-labelledby="ans-answer-h">
      <p className="overline" id="ans-answer-h">Answer</p>

      {row ? (
        <>
          <p className="ans-num">
            {value}
            {unit ? <small>{unit}</small> : null}
          </p>
          <p className="ans-meta">
            <span className={`badge basis-${row.basis}`}>{row.basis}</span>
            <span className="ans-meta-rig">{row.rigLabel}</span>
            <span>
              {row.quant} · {row.n} run{row.n === 1 ? "" : "s"}
              {row.metric ? ` · ${row.metric.label}` : ""}
            </span>
            {verdict.scope === "pool" ? <span>best cell in the pool</span> : <span>your rig</span>}
          </p>
        </>
      ) : (
        <>
          <p className="ans-num ans-num-none">no data yet</p>
          <p className="ans-meta">
            {askedForUnknownRig ? (
              <span>the pool has no rig named {rigToken}</span>
            ) : askedForRigWithoutCell ? (
              <span>
                no cell for this model on {rigInPool!.label} yet — the pool has runs from other
                models on it
              </span>
            ) : (
              <span>no cell carries this model in the frozen snapshot</span>
            )}
          </p>
        </>
      )}

      <nav className="ans-rigs" aria-label="pick a rig">
        <button
          type="button"
          className="ans-rig-btn"
          aria-pressed={rigToken === null}
          onClick={() => choose(null)}
        >
          best in pool
        </button>
        {groups.map((group) => (
          <button
            key={group.rigKey}
            type="button"
            className="ans-rig-btn"
            aria-pressed={matchedKey === group.rigKey}
            onClick={() => choose(group.rigKey)}
          >
            {group.rigLabel}
          </button>
        ))}
      </nav>

      <ol className="ans-ladder">
        {groups.map((group) => {
          const best = group.best;
          const value = best?.metric ? num(best.metric.value) : null;
          const fits =
            best?.peakVramGb != null && group.memoryGb != null && group.hwClass === "DISCRETE_GPU"
              ? best.peakVramGb <= group.memoryGb
              : null;
          return (
            <li key={group.rigKey} className="ans-rung">
              <span className="ans-rung-rig">
                {labelByKey.get(group.rigKey) ?? group.rigLabel}
                {group.hwClass === "CPU_ONLY" ? " · cpu only" : ""}
                {group.hwClass === "UNIFIED" ? " · unified memory" : ""}
              </span>
              {best?.metric ? (
                <span className="ans-rung-val">
                  {value} {best.metric.unit}
                </span>
              ) : (
                <span className="ans-rung-val ans-rung-none">no metric for this cell</span>
              )}
              {best ? <span className={`badge basis-${best.basis}`}>{best.basis}</span> : null}
              <span className="ans-rung-meta">
                {best ? `${best.n} run${best.n === 1 ? "" : "s"}` : ""}
                {best?.peakVramGb != null
                  ? ` · peak ${num(best.peakVramGb)} GB`
                  : best
                    ? " · peak VRAM no data yet"
                    : ""}
                {fits !== null
                  ? ` · ${fits ? "fits" : "over"} ${num(group.memoryGb, 0)} GB rig memory`
                  : group.hwClass === "DISCRETE_GPU" && group.memoryGb != null
                    ? ` · ${num(group.memoryGb, 0)} GB rig memory`
                    : ""}
                {group.cellCount > 1 ? ` · ${group.cellCount} cells` : ""}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
