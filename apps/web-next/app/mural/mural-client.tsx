"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { fetchSession } from "../../lib/auth";
import { API_BASE, getToken, type ApiResult } from "../../lib/social";

// The moderation desk. The old /mural was a preview that transmitted nothing:
// three hardcoded rows and a form that logged its payload to the console.
// This page is the real queue — GET /v1/reports, then confirm or dismiss —
// and for everybody else it says plainly who may moderate and why.

type ReportRow = {
  id: string;
  target_kind?: string;
  target_id?: string;
  reason_category?: string;
  reason_detail?: string | null;
  status?: string;
  reporter_handle?: string | null;
  created_at?: string;
};

type ModerationState = {
  status: string;
  rows: ReportRow[];
};

const STATUS_LABEL: Record<string, string> = {
  open: "open",
  confirmed: "confirmed",
  dismissed: "dismissed",
};

const REASON_LABEL: Record<string, string> = {
  numbers_unreal: "the numbers are not physically possible",
  wrong_hardware: "the hardware does not match",
  wrong_model: "the model does not match",
  duplicate: "it duplicates another claim",
  other: "other",
};

export default function MuralClient() {
  const [token, setTokenState] = useState<string | null>(null);
  const [handle, setHandle] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [status, setStatus] = useState("open");
  const [state, setState] = useState<ModerationState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const stored = getToken();
    setTokenState(stored);
    if (!stored) {
      setChecked(true);
      return;
    }
    fetchSession()
      .then((info) => setHandle(info?.handle ?? null))
      .catch(() => setHandle(null))
      .finally(() => setChecked(true));
  }, []);

  const load = useCallback(async (filter: string) => {
    setState(null);
    setError(null);
    const result = await fetchReports(filter);
    if (!result.ok) {
      setError(result.detail ?? "The queue could not be loaded.");
      setState({ status: filter, rows: [] });
      return;
    }
    setState({ status: filter, rows: result.data ?? [] });
  }, []);

  useEffect(() => {
    if (!token) return;
    void load(status);
  }, [token, status, load]);

  async function decide(id: string, action: "confirm" | "dismiss") {
    setBusy(id);
    setError(null);
    setNotice(null);
    let result: { ok: boolean; detail: string | null };
    try {
      const res = await fetch(`${API_BASE}/v1/reports/${encodeURIComponent(id)}/${action}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token ?? ""}` },
      });
      const text = await res.text();
      let detail: string | null = null;
      if (!res.ok) {
        try {
          const payload = JSON.parse(text) as { detail?: string };
          detail = payload.detail ?? `HTTP ${res.status}`;
        } catch {
          detail = `HTTP ${res.status}`;
        }
      }
      result = { ok: res.ok, detail };
    } catch (err) {
      const reason = err instanceof Error ? err.message : "unknown";
      result = { ok: false, detail: `Network error: ${reason}` };
    }
    setBusy(null);
    if (!result.ok) {
      setError(result.detail ?? "The moderation action could not be completed.");
      return;
    }
    setNotice(action === "confirm" ? "Report confirmed — the claim was marked refuted." : "Report dismissed.");
    await load(status);
  }

  if (!checked) {
    return (
      <main>
        <section className="page-head">
          <h1>The mural</h1>
        </section>
        <div className="skel" aria-hidden="true">
          <div className="skel-row" />
        </div>
      </main>
    );
  }

  return (
    <main>
      <section className="mural-head">
        <p className="overline">moderation</p>
        <h1 className="mural-title">The mural</h1>
        <p className="mural-frame">
          Every claim on the wall can be reported. A report never changes a claim by itself — a
          moderator reads it, confirms it or dismisses it, and only then does the claim move. A
          confirmed report is worth five points to whoever filed it, and a badge
          that says they caught it.
        </p>
      </section>

      {!token ? (
        <section className="empty">
          <p className="empty-mark">···</p>
          <h2>The queue is for moderators</h2>
          <p>
            Moderation is restricted to the handles in the server&apos;s moderator list. Sign in to
            see the queue if you moderate; otherwise report a run from the claim page and the
            community reads it.
          </p>
          <div className="actions">
            <Link className="btn primary" href="/console">
              sign in
            </Link>
            <Link className="btn" href="/claims">
              the wall
            </Link>
          </div>
        </section>
      ) : (
        <>
          <div className="ctl-bar">
            <div className="ctl-group">
              <span className="ctl-label">state</span>
              <div className="opt-row" role="group" aria-label="Report state">
                {(["open", "confirmed", "dismissed"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className="opt"
                    aria-pressed={status === value}
                    onClick={() => setStatus(value)}
                  >
                    {STATUS_LABEL[value]}
                  </button>
                ))}
              </div>
            </div>
            <div className="ctl-group">
              <span className="ctl-label">signed in as</span>
              <span className="ctl-value">{handle ? `@${handle}` : "—"}</span>
            </div>
          </div>

          {error && (
            <p className="banner" data-k="bad" role="status">
              {error}
            </p>
          )}
          {notice && (
            <p className="banner" data-k="ok" role="status">
              {notice}
            </p>
          )}

          {state === null ? (
            <div className="skel" aria-hidden="true">
              <div className="skel-row" />
              <div className="skel-row" />
            </div>
          ) : state.rows.length === 0 ? (
            <div className="empty">
              <p className="empty-mark">···</p>
              <h2>Nothing {STATUS_LABEL[state.status]}</h2>
              <p>The queue is empty for this state.</p>
            </div>
          ) : (
            <ul className="mural-queue">
              {state.rows.map((row) => (
                <li className="mural-item" key={row.id}>
                  <div className="mural-item-top">
                    <span className="mural-item-reason">
                      {REASON_LABEL[row.reason_category ?? "other"] ?? row.reason_category}
                    </span>
                    <span className="status" data-s={row.status === "confirmed" ? "refuted" : "open"}>
                      {STATUS_LABEL[row.status ?? "open"]}
                    </span>
                    <span className="claim-age">{row.created_at?.slice(0, 10) ?? ""}</span>
                  </div>
                  {row.reason_detail && <p className="mural-item-detail">{row.reason_detail}</p>}
                  <p className="mural-item-meta">
                    reported by {row.reporter_handle ? `@${row.reporter_handle}` : "a member"} ·{" "}
                    {row.target_kind === "run_claim" ? "claim" : "run"} {row.target_id}
                  </p>
                  {row.target_kind === "run_claim" && row.target_id && (
                    <Link className="wall-action" href={`/claim/${row.target_id}`}>
                      open the claim
                    </Link>
                  )}
                  {row.status === "open" && (
                    <div className="mural-item-actions">
                      <button
                        className="btn bad"
                        type="button"
                        disabled={busy === row.id}
                        onClick={() => decide(row.id, "confirm")}
                      >
                        {busy === row.id ? "working…" : "Confirm the report"}
                      </button>
                      <button
                        className="btn"
                        type="button"
                        disabled={busy === row.id}
                        onClick={() => decide(row.id, "dismiss")}
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  );
}

async function fetchReports(status: string): Promise<ApiResult<ReportRow[]>> {
  try {
    const res = await fetch(`${API_BASE}/v1/reports?status=${encodeURIComponent(status)}`, {
      headers: { Authorization: `Bearer ${getToken() ?? ""}` },
    });
    const text = await res.text();
    const payload = text ? (JSON.parse(text) as { reports?: ReportRow[] }) : {};
    if (!res.ok) {
      const detail = (payload as { detail?: string }).detail;
      return { ok: false, status: res.status, data: null, detail: detail ?? `HTTP ${res.status}` };
    }
    return { ok: true, status: res.status, data: payload.reports ?? [], detail: null };
  } catch (err) {
    const reason = err instanceof Error ? err.message : "unknown";
    return { ok: false, status: 0, data: null, detail: `Network error: ${reason}` };
  }
}
