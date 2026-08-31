// social.ts — the capture network's contract with the public API.
//
// House rules encoded here:
//   · same-origin base "" by default (the edge is expected to route /v1/*).
//     NEXT_PUBLIC_API_BASE overrides it without a code change — deploy/Caddyfile
//     currently only proxies api.bestmodel.run, so the override may be needed.
//   · the session token is READ from localStorage.bm_token. Auth is issued by
//     the console; nothing here re-implements it.
//   · every failure returns the API's own `detail` verbatim. We never invent a
//     friendlier message on top of the server's answer.

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
export const TOKEN_KEY = "bm_token";
export const CONSOLE_HREF = "/console";
export const MAX_REASON_DETAIL = 1000;

/**
 * Field caps copied from the server's own request model
 * (apps/public-api/src/schemas/claim_schemas.py). Enforced in the form so a
 * long value fails visibly at the field instead of returning a 422.
 */
export const FIELD_MAX = {
  model_release_id: 128,
  quantization_profile_id: 64,
  gpu_model_id: 64,
  note: 2000,
  source_url: 500,
  context_tokens: 10_000_000,
} as const;

// ------------------------------------------------------------------ types

export type ClaimStatus = "open" | "settled_verified" | "refuted" | "retracted";
export type ClaimSort = "recent" | "controversial" | "strongest";
export type Verdict = "plausible" | "impossible";

/** The five the API accepts. The reference build had four; wrong_model was missing. */
export type ReasonCategory =
  | "numbers_unreal"
  | "wrong_hardware"
  | "wrong_model"
  | "duplicate"
  | "other";

export const REASON_CATEGORIES: ReadonlyArray<{ value: ReasonCategory; label: string }> = [
  { value: "numbers_unreal", label: "Numbers are not physically possible" },
  { value: "wrong_hardware", label: "Hardware does not match the claim" },
  { value: "wrong_model", label: "Model does not match the claim" },
  { value: "duplicate", label: "Duplicate of an existing claim" },
  { value: "other", label: "Other" },
];

export type ClaimedMetrics = {
  decode_tok_s?: number | null;
  prefill_tok_s?: number | null;
  ttft_ms?: number | null;
  peak_vram_mib?: number | null;
};

export type PriorSnapshot = {
  pool?: { basis?: string | null; p50_decode_tok_s?: number | null; run_count?: number | null } | null;
  roofline?: { expected_decode_tok_s?: number | null } | null;
} | null;

export type Tally = {
  plausible_count?: number | null;
  impossible_count?: number | null;
  margin?: number | null;
  voter_count?: number | null;
} | null;

export type Claim = {
  id: string;
  /**
   * null means no person stands behind this row — it was imported from the
   * pool. This, NOT claimant_handle, is the test for a real contributor:
   * imports still carry a handle ("localmaxxing pool") that is a label, not
   * an account, and linking it would lead to a profile that cannot exist.
   */
  claimant_id: string | null;
  claimant_handle: string | null;
  source: string | null;
  external_ref: string | null;
  model_release_id: string;
  quantization_profile_id: string | null;
  gpu_model_id: string | null;
  context_tokens: number | null;
  claimed_metrics: ClaimedMetrics | null;
  note: string | null;
  source_url: string | null;
  status: ClaimStatus;
  prior_snapshot: PriorSnapshot;
  created_at: string;
  tally: Tally;
  /** present once a signed run settles the claim */
  benchmark_run_id?: string | null;
};

export type Reputation = { points?: number | null; tier?: string | null; updated_at?: string | null };
export type Badge = Record<string, unknown>;
export type Follow = { followers?: number | null; following?: number | null; viewer_is_following?: boolean | null };
export type Rig = { slug: string; nickname?: string | null; is_public?: boolean | null; created_at?: string | null };

export type UserProfile = {
  handle: string;
  display_name?: string | null;
  created_at?: string | null;
  reputation?: Reputation | null;
  badges?: Badge[] | null;
  follow?: Follow | null;
  rigs?: Rig[] | null;
};

export type ApiResult<T> = {
  ok: boolean;
  status: number;
  data: T | null;
  /** the server's own message, verbatim — null when the call succeeded */
  detail: string | null;
};

export type ModelRelease = {
  id: string;
  release_name: string;
  family: string;
  parameter_count_billion: number | null;
  max_context_tokens: number;
};

export type QuantizationProfile = {
  id: string;
  display_name: string;
  weight_format: string;
  weight_bits: number | null;
};

// -------------------------------------------------------------------- auth

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(TOKEN_KEY);
    return raw && raw.trim() ? raw.trim() : null;
  } catch {
    // private mode / storage blocked — treat as signed out rather than crash
    return null;
  }
}

// ------------------------------------------------------------------ fetch

function readDetail(payload: unknown, status: number): string {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail
        .map((item) => {
          if (item && typeof item === "object") {
            const loc = (item as { loc?: unknown }).loc;
            const msg = (item as { msg?: unknown }).msg;
            const where = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
            const text = typeof msg === "string" ? msg : JSON.stringify(item);
            return where ? `${where}: ${text}` : text;
          }
          return String(item);
        })
        .join(" · ");
    }
    const message = (payload as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return `HTTP ${status}`;
}

async function request<T>(
  path: string,
  init: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<ApiResult<T>> {
  const { method = "GET", body, auth = false } = init;
  const headers: Record<string, string> = {};

  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (!token) return { ok: false, status: 401, data: null, detail: "Not signed in." };
    headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : "unknown";
    return { ok: false, status: 0, data: null, detail: `Network error: ${reason}` };
  }

  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  return {
    ok: res.ok,
    status: res.status,
    data: res.ok ? (payload as T) : null,
    detail: res.ok ? null : readDetail(payload, res.status),
  };
}

// ----------------------------------------------------------------- calls

export function listClaims(params: {
  status?: ClaimStatus | "";
  sort: ClaimSort;
  limit: number;
  offset: number;
}): Promise<ApiResult<Claim[]>> {
  const query = new URLSearchParams({
    sort: params.sort,
    limit: String(params.limit),
    offset: String(params.offset),
  });
  if (params.status) query.set("status", params.status);
  return request<Claim[]>(`/v1/claims?${query.toString()}`);
}

export function getClaim(id: string): Promise<ApiResult<Claim>> {
  return request<Claim>(`/v1/claims/${encodeURIComponent(id)}`);
}

export type CreateClaimBody = {
  model_release_id: string;
  claimed_metrics: { decode_tok_s: number };
  source_url?: string;
  quantization_profile_id?: string;
  gpu_model_id?: string;
  context_tokens?: number;
  note?: string;
};

export function createClaim(body: CreateClaimBody): Promise<ApiResult<Claim>> {
  return request<Claim>("/v1/claims", { method: "POST", body, auth: true });
}

export function voteOnClaim(id: string, verdict: Verdict): Promise<ApiResult<unknown>> {
  return request(`/v1/claims/${encodeURIComponent(id)}/votes`, {
    method: "POST",
    body: { verdict },
    auth: true,
  });
}

/**
 * Reports do NOT live under /v1/claims. The API mounts them at
 * /v1/run-claims/{claim_id}/reports (apps/public-api/src/routes/report_route.py),
 * which is the path used here — verified against the route, not the brief.
 */
export function reportClaim(
  id: string,
  reason_category: ReasonCategory,
  reason_detail: string,
): Promise<ApiResult<unknown>> {
  return request(`/v1/run-claims/${encodeURIComponent(id)}/reports`, {
    method: "POST",
    body: { reason_category, reason_detail: reason_detail || null },
    auth: true,
  });
}

/**
 * The ids create accepts are opaque server ids (`model-qwen3-6-35b-a3b`,
 * `q-gguf-q4-k-m`) and create_run_claim 404s on anything it cannot resolve.
 * There is no public catalog endpoint — fetch_quantization_profiles exists in
 * the DB layer but is not published over HTTP — so the only ids we can offer
 * with confidence are the ones the feed has actually shown us.
 */
export async function fetchClaimCatalog(): Promise<{ models: string[]; quants: string[] }> {
  const result = await listClaims({ status: "", sort: "recent", limit: 100, offset: 0 });
  const rows = Array.isArray(result.data) ? result.data : [];
  const models = new Set<string>();
  const quants = new Set<string>();
  for (const row of rows) {
    if (row.model_release_id) models.add(row.model_release_id);
    if (row.quantization_profile_id) quants.add(row.quantization_profile_id);
  }
  return { models: [...models].sort(), quants: [...quants].sort() };
}

export function fetchModelReleases(): Promise<ApiResult<{ items: ModelRelease[]; count: number }>> {
  return request<{ items: ModelRelease[]; count: number }>("/v1/model-releases");
}

export function fetchQuantizationProfiles(): Promise<
  ApiResult<{ items: QuantizationProfile[]; count: number }>
> {
  return request<{ items: QuantizationProfile[]; count: number }>("/v1/quantization-profiles");
}

export async function fetchCatalog(): Promise<
  | { source: "api"; models: ModelRelease[]; quants: QuantizationProfile[] }
  | { source: "feed"; models: string[]; quants: string[] }
> {
  const [models, quants] = await Promise.all([fetchModelReleases(), fetchQuantizationProfiles()]);
  if (models.ok && quants.ok && models.data && quants.data) {
    return { source: "api", models: models.data.items, quants: quants.data.items };
  }
  const fallback = await fetchClaimCatalog();
  return { source: "feed", ...fallback };
}

export function getUser(handle: string): Promise<ApiResult<UserProfile>> {
  return request<UserProfile>(`/v1/users/${encodeURIComponent(handle)}`);
}

export function setFollow(handle: string, following: boolean): Promise<ApiResult<unknown>> {
  return request(`/v1/users/${encodeURIComponent(handle)}/follow`, {
    method: following ? "POST" : "DELETE",
    auth: true,
  });
}

// ------------------------------------------------------------- formatting

/** Extract the display host of a provenance link. Returns null when unparseable. */
export function hostOf(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export function isHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

/** Compact age derived from created_at. Never a guess — null when unparseable. */
export function ago(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return null;
  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 0) return null;
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return iso.slice(0, 10);
}

export function contextLabel(tokens: number | null | undefined): string | null {
  if (tokens == null || !Number.isFinite(Number(tokens))) return null;
  const n = Number(tokens);
  return n >= 1024 && n % 1024 === 0 ? `${n / 1024}k ctx` : `${n.toLocaleString("en-US")} ctx`;
}

export function mibToGb(mib: number | null | undefined): number | null {
  if (mib == null || !Number.isFinite(Number(mib))) return null;
  return Number(mib) / 1024;
}

export const STATUS_LABEL: Record<ClaimStatus, string> = {
  open: "open",
  settled_verified: "measured",
  refuted: "refuted",
  retracted: "retracted",
};

export const SORT_OPTIONS: ReadonlyArray<{ value: ClaimSort; label: string }> = [
  { value: "recent", label: "most recent" },
  { value: "controversial", label: "most contested" },
  { value: "strongest", label: "strongest signal" },
];

export const STATUS_OPTIONS: ReadonlyArray<{ value: ClaimStatus | ""; label: string }> = [
  { value: "", label: "all" },
  { value: "open", label: "open" },
  { value: "settled_verified", label: "verified" },
  { value: "refuted", label: "refuted" },
  { value: "retracted", label: "retracted" },
];
