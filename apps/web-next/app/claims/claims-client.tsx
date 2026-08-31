"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Banner, ClaimCard, EmptyState, Skeleton } from "../../components/claim-parts";
import {
  listClaims,
  SORT_OPTIONS,
  STATUS_OPTIONS,
  type Claim,
  type ClaimSort,
  type ClaimStatus,
} from "../../lib/social";

const PAGE_SIZE = 25;

export default function ClaimsClient() {
  const [status, setStatus] = useState<ClaimStatus | "">("");
  const [sort, setSort] = useState<ClaimSort>("recent");
  const [rows, setRows] = useState<Claim[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [paging, setPaging] = useState(false);
  const [exhausted, setExhausted] = useState(false);

  // Guards against a slow first page landing after the filters already moved on.
  const runId = useRef(0);

  const fetchPage = useCallback(
    async (offset: number, nextStatus: ClaimStatus | "", nextSort: ClaimSort) => {
      const id = ++runId.current;
      const result = await listClaims({ status: nextStatus, sort: nextSort, limit: PAGE_SIZE, offset });
      if (id !== runId.current) return;

      if (!result.ok) {
        setError(result.detail);
        setLoading(false);
        setPaging(false);
        return;
      }

      const batch = Array.isArray(result.data) ? result.data : [];
      setError(null);
      setRows((prev) => (offset === 0 ? batch : prev.concat(batch)));
      setExhausted(batch.length < PAGE_SIZE);
      setLoading(false);
      setPaging(false);
    },
    [],
  );

  useEffect(() => {
    setLoading(true);
    setExhausted(false);
    void fetchPage(0, status, sort);
  }, [status, sort, fetchPage]);

  const measured = rows.filter((row) => row.status === "settled_verified").length;
  const sourced = rows.filter((row) => row.source_url).length;

  return (
    <section aria-live="polite">
      {/* UX LAW: status and ordering are different questions and get different
          groups. They are never fused into one control. */}
      <div className="ctl-bar">
        <div className="ctl-group">
          <span className="ctl-label" id="lbl-status">
            status
          </span>
          <div className="opt-row" role="group" aria-labelledby="lbl-status">
            {STATUS_OPTIONS.map((option) => (
              <button
                key={option.value || "all"}
                type="button"
                className="opt"
                aria-pressed={status === option.value}
                onClick={() => setStatus(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="ctl-group">
          <label className="ctl-label" htmlFor="claims-sort">
            ordering
          </label>
          <select
            id="claims-sort"
            className="select"
            value={sort}
            onChange={(event) => setSort(event.target.value as ClaimSort)}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                sort: {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <Banner kind="bad">
          <b>the wall could not be loaded</b> — {error}
        </Banner>
      )}

      {loading ? (
        <Skeleton rows={3} />
      ) : rows.length === 0 && !error ? (
        <EmptyState
          title="The wall is empty — be the first to capture a run."
          body="No claim has been captured yet. Somewhere out there a number is sitting in a comment thread with nothing behind it. Bring it here and it gets a source, a tally, and a path to proof."
          action={
            <Link className="btn primary" href="/submit">
              Capture a run
            </Link>
          }
        />
      ) : (
        <>
          <p className="summary">
            {rows.length} captured · {sourced} carry an external source · {measured} settled by a
            signed run
          </p>

          <div className="claim-list">
            {rows.map((claim) => (
              <ClaimCard key={claim.id} claim={claim} modelName={claim.model_release_id} />
            ))}
          </div>

          {!exhausted && (
            <div className="actions">
              <button
                type="button"
                className="btn"
                disabled={paging}
                onClick={() => {
                  setPaging(true);
                  void fetchPage(rows.length, status, sort);
                }}
              >
                {paging ? "Loading…" : "Load more"}
              </button>
            </div>
          )}

          <p className="note">
            A claim is what someone says. A signed run is what the pool can verify — and it outranks
            every claim on this page.
          </p>
        </>
      )}
    </section>
  );
}
