"use client";

import { useMemo, useState } from "react";
import { basisOf, formatNumber, loadDerived } from "../../lib/engine";

type Rig = ReturnType<typeof loadDerived>["hardware"][number];

type Entry = {
  rig: Rig;
  cells: number;
  models: number;
  measured: number;
  reported: number;
};

const SORTS = [
  { id: "runs", label: "runs" },
  { id: "models", label: "models tried" },
  { id: "mem", label: "memory" },
] as const;

const CLASSES = [
  { id: "all", label: "every class" },
  { id: "DISCRETE_GPU", label: "discrete GPU" },
  { id: "UNIFIED", label: "unified memory" },
  { id: "CPU_ONLY", label: "CPU only" },
] as const;

export default function HardwareIndex({ snapshotAt }: { snapshotAt: string }) {
  const [sort, setSort] = useState<(typeof SORTS)[number]["id"]>("runs");
  const [classFilter, setClassFilter] = useState<string>("all");
  const [query, setQuery] = useState("");

  const { entries, poolCells, maxRuns, maxModels } = useMemo(() => {
    const { hardware, pool } = loadDerived();
    const byRig = new Map<string, { cells: number; models: Set<string>; measured: number; reported: number }>();
    for (const cell of pool) {
      let bucket = byRig.get(cell.rigKey);
      if (!bucket) {
        bucket = { cells: 0, models: new Set<string>(), measured: 0, reported: 0 };
        byRig.set(cell.rigKey, bucket);
      }
      bucket.cells += 1;
      bucket.models.add(cell.modelSlug);
      if (basisOf(cell) === "measured") bucket.measured += 1;
      else bucket.reported += 1;
    }
    const rows: Entry[] = hardware.map((rig) => {
      const bucket = byRig.get(rig.key);
      return {
        rig,
        cells: bucket?.cells ?? 0,
        models: bucket?.models.size ?? 0,
        measured: bucket?.measured ?? 0,
        reported: bucket?.reported ?? 0,
      };
    });
    return {
      entries: rows,
      poolCells: pool.length,
      maxRuns: Math.max(...rows.map((row) => row.rig.runCount ?? 0)),
      maxModels: Math.max(...rows.map((row) => row.models)),
    };
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = entries.filter((entry) => {
      if (classFilter !== "all" && entry.rig.hwClass !== classFilter) return false;
      if (!needle) return true;
      return (
        entry.rig.label.toLowerCase().includes(needle) ||
        entry.rig.key.toLowerCase().includes(needle)
      );
    });
    const sorted = [...filtered];
    if (sort === "runs") sorted.sort((a, b) => (b.rig.runCount ?? 0) - (a.rig.runCount ?? 0));
    else if (sort === "models")
      sorted.sort((a, b) => b.models - a.models || (b.rig.runCount ?? 0) - (a.rig.runCount ?? 0));
    else sorted.sort((a, b) => (b.rig.memGb ?? 0) - (a.rig.memGb ?? 0));
    return sorted;
  }, [entries, sort, classFilter, query]);

  const shownRuns = visible.reduce((sum, entry) => sum + (entry.rig.runCount ?? 0), 0);

  return (
    <section aria-live="polite">
      <div className="ctl-bar">
        <div className="ctl-group">
          <span className="ctl-label" id="hw-sort-label">
            order by
          </span>
          <div className="opt-row" role="group" aria-labelledby="hw-sort-label">
            {SORTS.map((option) => (
              <button
                key={option.id}
                type="button"
                className="opt"
                aria-pressed={sort === option.id}
                onClick={() => setSort(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="ctl-group">
          <span className="ctl-label" id="hw-class-label">
            hardware class
          </span>
          <div className="opt-row" role="group" aria-labelledby="hw-class-label">
            {CLASSES.map((option) => (
              <button
                key={option.id}
                type="button"
                className="opt"
                aria-pressed={classFilter === option.id}
                onClick={() => setClassFilter(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="ctl-group">
          <label className="ctl-label" htmlFor="hw-q">
            find a machine
          </label>
          <div className="f">
            <input
              id="hw-q"
              type="search"
              value={query}
              placeholder="label or key"
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>
      </div>

      <p className="summary">
        {visible.length} of {entries.length} machines listed · {formatNumber(poolCells, 0)} pool cells
        behind the model counts · {formatNumber(shownRuns, 0)} runs across the machines in view ·
        snapshot {snapshotAt}
      </p>

      {visible.length === 0 ? (
        <div className="empty">
          <p className="empty-mark">— — —</p>
          <h2>No machine matches</h2>
          <p>
            The catalogue holds {entries.length} rigs from the frozen snapshot. Widen the class filter
            or clear the search to see them.
          </p>
        </div>
      ) : (
        <ol className="hw-index">
          {visible.map((entry, position) => {
            const { rig } = entry;
            const runs = rig.runCount ?? 0;
            const runPct = maxRuns ? Math.round((runs / maxRuns) * 100) : 0;
            const modelPct = maxModels ? Math.round((entry.models / maxModels) * 100) : 0;
            return (
              <li className="hw-entry" key={rig.key}>
                <span className="hw-ord">{String(position + 1).padStart(3, "0")}</span>

                <div className="hw-id">
                  <h2 className="hw-name">
                    <a href={`/wall?rig=${encodeURIComponent(rig.key)}`}>{rig.label}</a>
                  </h2>
                  <p className="hw-key">{rig.key}</p>
                  <p className="hw-class">{rig.hwClass}</p>
                </div>

                <div className="hw-load">
                  <p className="hw-figure">
                    <strong>{formatNumber(runs, 0)}</strong> runs
                  </p>
                  <div className="hw-bar" aria-hidden="true">
                    <i style={{ width: `${runPct}%` }} />
                  </div>
                  <p className="hw-pct">{runPct}% of the busiest machine</p>
                </div>

                <div className="hw-spec">
                  <p className="hw-figure">
                    <strong>{formatNumber(rig.memGb, 2)}</strong> GB
                  </p>
                  <p className="hw-pct">
                    {rig.gpuCount} GPU{rig.gpuCount === 1 ? "" : "s"} ·{" "}
                    {rig.bandwidthGBs == null
                      ? "bandwidth no data yet"
                      : `${formatNumber(rig.bandwidthGBs)} GB/s`}
                  </p>
                </div>

                <div className="hw-reach">
                  <p className="hw-figure">
                    <strong>{entry.cells ? entry.models : "—"}</strong> models tried
                  </p>
                  <div className="hw-bar reach" aria-hidden="true">
                    <i style={{ width: `${modelPct}%` }} />
                  </div>
                  <p className="hw-pct">{modelPct}% of the most-tried machine</p>
                </div>

                <dl className="hw-figs">
                  <div>
                    <dt>measured</dt>
                    <dd>{entry.cells ? entry.measured : "—"}</dd>
                  </div>
                  <div>
                    <dt>reported</dt>
                    <dd>{entry.cells ? entry.reported : "—"}</dd>
                  </div>
                  <div>
                    <dt>pool cells</dt>
                    <dd>{entry.cells ? entry.cells : "—"}</dd>
                  </div>
                </dl>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
