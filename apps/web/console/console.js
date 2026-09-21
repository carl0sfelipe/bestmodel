/* bestmodel console — zero-dependency vanilla JS over the public API.
 *
 * Full loop without a terminal (L02 C6):
 *   register/sign in (passkey) -> browse claims -> vote -> post a claim
 *   -> see the settle command + share card.
 *
 * S34: the console reads as a small social network — a persistent identity
 * (handle · points · tier), claim cards with author → profile, basis and
 * provenance, a profile view with follow/unfollow, and notifications.
 * Every endpoint called here already ships; nothing new on the backend.
 *
 * API base is configurable for deployments:
 *   <script> window.BESTMODEL_API = "https://api.bestmodel.run"; </script>
 */

// Same-origin by default (Vercel rewrite / reverse proxy). Override in config.js.
const API_BASE = window.BESTMODEL_API || "";
const TOKEN_KEY = "bm_token";

const $ = (selector) => document.querySelector(selector);

function token() {
  return localStorage.getItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await response.text();
  let body = text;
  try {
    body = JSON.parse(text);
  } catch {
    /* non-JSON (svg/markdown) passes through */
  }
  if (!response.ok) {
    throw new Error(typeof body === "object" && body.detail ? body.detail : `${response.status}`);
  }
  return body;
}

/* ---------- views ---------- */

function show(view) {
  for (const section of document.querySelectorAll("main section")) section.hidden = true;
  $(`#view-${view}`).hidden = false;
  for (const button of document.querySelectorAll(".topbar nav [data-view]")) {
    button.classList.toggle("active", button.dataset.view === view);
  }
}

function renderSession() {
  const area = $("#session-area");
  if (token()) {
    // S31: one human, one account — link GitHub / Hugging Face to THIS account
    // instead of letting a provider login create a suffixed twin.
    area.innerHTML = `<button id="btn-link-github" class="linkish" title="link your GitHub identity to this account">link GitHub</button>
      <button id="btn-link-huggingface" class="linkish" title="link your Hugging Face identity to this account">link HF</button>
      <button id="btn-signout" class="linkish">sign out</button>`;
    $("#btn-signout").onclick = () => {
      localStorage.removeItem(TOKEN_KEY);
      CURRENT_HANDLE = null;
      renderIdentity();
      renderSession();
      show("auth");
    };
    $("#btn-link-github").onclick = () => startOauthLink("github");
    $("#btn-link-huggingface").onclick = () => startOauthLink("huggingface");
    loadIdentity().catch(() => {});
  } else {
    area.innerHTML = `<button data-view="auth">sign in</button>`;
    area.querySelector("[data-view]").onclick = () => show("auth");
  }
}

/* ---------- identity strip (S34) ---------- */

let CURRENT_HANDLE = null;
let LINKED_PROVIDERS = [];

function renderIdentity(profile) {
  const strip = $("#identity-strip");
  if (!token() || !profile) {
    strip.hidden = true;
    strip.innerHTML = "";
    return;
  }
  const points = profile.reputation?.points ?? 0;
  const tier = profile.reputation?.tier ?? "unranked";
  const linked = LINKED_PROVIDERS.map((a) => `${a.provider === "huggingface" ? "hf" : a.provider}: ${a.login}`).join(" · ");
  const has = new Set(LINKED_PROVIDERS.map((a) => a.provider));
  strip.innerHTML = `
    <button class="linkish me" data-profile="${escapeHtml(profile.handle)}" title="open your profile">@${escapeHtml(profile.handle)}</button>
    ${linked ? `<span class="muted identities">${escapeHtml(linked)}</span>` : ""}
    <span class="pts" title="reputation points">${points} pts</span>
    <span class="badge tier" title="trust tier">${escapeHtml(tier)}</span>
    <button id="btn-notifications" class="linkish" title="notifications">bell<span id="notification-count" hidden></span></button>`;
  strip.hidden = false;
  for (const button of strip.querySelectorAll("[data-profile]")) {
    button.onclick = () => openProfile(button.dataset.profile);
  }
  $("#btn-notifications").onclick = () => {
    show("notifications");
    loadNotifications().catch(() => {});
  };
  const gh = $("#btn-link-github"), hf = $("#btn-link-huggingface");
  if (gh) gh.hidden = has.has("github");
  if (hf) hf.hidden = has.has("huggingface");
  refreshNotificationCount().catch(() => {});
}

async function loadIdentity() {
  // The session token does not carry the handle client-side; the accounts
  // endpoint returns it (with or without linked providers).
  const accounts = await api("/v1/auth/oauth/accounts");
  CURRENT_HANDLE = accounts.handle ?? null;
  LINKED_PROVIDERS = accounts.accounts ?? [];
  if (!CURRENT_HANDLE) return;
  const profile = await api(`/v1/users/${encodeURIComponent(CURRENT_HANDLE)}`);
  renderIdentity(profile);
}

/* ---------- notifications (S34, existing S18 endpoints) ---------- */

async function refreshNotificationCount() {
  const count = $("#notification-count");
  if (!count || !token()) return;
  const items = await api("/v1/notifications");
  const unread = items.filter((item) => !item.read_at).length;
  count.hidden = unread === 0;
  count.textContent = unread > 0 ? String(unread) : "";
}

async function loadNotifications() {
  const list = $("#notification-list");
  list.innerHTML = "";
  const items = await api("/v1/notifications");
  if (!items.length) {
    list.innerHTML = `<li class="muted">nothing yet — follow people and vote to make the wall move</li>`;
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.className = item.read_at ? "notification read" : "notification unread";
    const payload = item.payload ?? {};
    li.innerHTML = `
      <div class="claim-head">
        <span class="badge kind">${escapeHtml(item.kind ?? "event")}</span>
        <span class="muted">${escapeHtml((item.created_at ?? "").slice(0, 10))}</span>
      </div>
      <div>${escapeHtml(typeof payload === "object" ? JSON.stringify(payload) : String(payload ?? ""))}</div>
      ${item.read_at ? "" : `<button class="linkish mark-read">mark read</button>`}`;
    const button = li.querySelector(".mark-read");
    if (button) {
      button.onclick = async () => {
        await api(`/v1/notifications/${encodeURIComponent(item.id)}/read`, { method: "POST" });
        await loadNotifications();
        await refreshNotificationCount().catch(() => {});
      };
    }
    list.append(li);
  }
}

/* ---------- profile view (S34, existing S14/S17 endpoints) ---------- */

async function openProfile(handle) {
  const profile = await api(`/v1/users/${encodeURIComponent(handle)}`);
  const reputation = profile.reputation ?? { points: 0, tier: "unranked" };
  const follow = profile.follow ?? {};
  const rigs = profile.rigs ?? [];
  const isMe = handle === CURRENT_HANDLE;
  $("#profile-body").innerHTML = `
    <div class="profile-head">
      <h1>@${escapeHtml(profile.handle)}</h1>
      <span class="badge tier">${escapeHtml(reputation.tier)}</span>
    </div>
    <p class="profile-pts"><strong>${reputation.points}</strong> reputation points · tier <strong>${escapeHtml(reputation.tier)}</strong></p>
    <p class="muted">${follow.follower_count ?? 0} followers · ${follow.following_count ?? 0} following</p>
    ${isMe ? "" : `<div class="vote-row"><button id="btn-follow" class="${follow.viewer_is_following ? "down" : "up"}">${follow.viewer_is_following ? "unfollow" : "follow"}</button></div>`}
    <h2>Rigs</h2>
    <ul class="rig-list">${rigs.length ? rigs.map((rig) => `<li><strong>${escapeHtml(rig.nickname ?? rig.slug ?? "?")}</strong> <span class="muted">${escapeHtml(rig.slug ?? "")}</span></li>`).join("") : `<li class="muted">no public rigs yet</li>`}</ul>
    <h2>Recent claims</h2>
    <ul id="profile-claims" class="claim-list"><li class="muted">loading…</li></ul>`;
  const followButton = $("#btn-follow");
  if (followButton) {
    followButton.onclick = async () => {
      await api(`/v1/users/${encodeURIComponent(handle)}/follow`, {
        method: follow.viewer_is_following ? "DELETE" : "POST",
      });
      await openProfile(handle);
    };
  }
  // The user's recent claims come from the existing claims list, filtered by
  // handle — no new endpoint (S34 contract).
  try {
    const claims = await api("/v1/claims?scope=global&sort=recent");
    const mine = claims.filter((claim) => (claim.claimant_handle ?? claim.handle) === handle).slice(0, 10);
    const list = $("#profile-claims");
    list.innerHTML = "";
    if (!mine.length) {
      list.innerHTML = `<li class="muted">no claims on the wall yet</li>`;
    } else {
      for (const claim of mine) list.append(renderClaimRow(claim));
    }
  } catch {
    /* profile still renders without the claims feed */
  }
  show("profile");
}

/* ---------- passkey ceremonies ---------- */

function b64urlToBytes(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded.padEnd(Math.ceil(padded.length / 4) * 4, "=")), (c) => c.charCodeAt(0));
}

function bytesToB64url(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function registerPasskey(handle) {
  const options = await api(`/v1/auth/passkey/register/options`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handle }),
  });
  const credential = await navigator.credentials.create({
    publicKey: publicKeyOptions(options.options),
  });
  const result = await api(`/v1/auth/passkey/register/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handle, credential: serializeCreation(credential) }),
  });
  return result;
}

async function loginPasskey(handle) {
  const options = await api(`/v1/auth/passkey/login/options`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handle }),
  });
  const assertion = await navigator.credentials.get({
    publicKey: publicKeyOptions(options.options),
  });
  const result = await api(`/v1/auth/passkey/login/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handle, credential: serializeAssertion(assertion) }),
  });
  localStorage.setItem(TOKEN_KEY, result.access_token);
  return result;
}

function publicKeyOptions(options) {
  options.challenge = b64urlToBytes(options.challenge);
  if (options.user) options.user.id = b64urlToBytes(options.user.id);
  for (const descriptor of options.excludeCredentials || []) descriptor.id = b64urlToBytes(descriptor.id);
  for (const descriptor of options.allowCredentials || []) descriptor.id = b64urlToBytes(descriptor.id);
  return options;
}

function serializeCreation(credential) {
  return {
    id: credential.id,
    rawId: bytesToB64url(credential.rawId),
    type: credential.type,
    response: {
      attestationObject: bytesToB64url(credential.response.attestationObject),
      clientDataJSON: bytesToB64url(credential.response.clientDataJSON),
    },
  };
}

function serializeAssertion(assertion) {
  return {
    id: assertion.id,
    rawId: bytesToB64url(assertion.rawId),
    type: assertion.type,
    response: {
      authenticatorData: bytesToB64url(assertion.response.authenticatorData),
      clientDataJSON: bytesToB64url(assertion.response.clientDataJSON),
      signature: bytesToB64url(assertion.response.signature),
      userHandle: assertion.response.userHandle ? bytesToB64url(assertion.response.userHandle) : null,
    },
  };
}

/* ---------- feed ---------- */

async function loadFeed() {
  const sort = $("#feed-sort").value;
  const status = $("#feed-status").value;
  const scope = $("#feed-scope").value;
  const list = $("#claim-list");
  list.innerHTML = "";

  if (scope === "following" && !token()) {
    list.innerHTML = `<li class="muted">sign in to see your following feed</li>`;
    return;
  }

  if (scope === "following") {
    // personalized typed feed: claims with tallies + account-attributed runs
    const items = await api(`/v1/feed?scope=following&sort=${sort === "strongest" ? "trending" : sort}`);
    for (const item of items) list.append(item.type === "claim" ? renderClaimRow(item, true) : renderRunRow(item));
    $("#feed-summary").textContent = `${items.length} events from people you follow`;
    return;
  }

  const query = new URLSearchParams({ scope: "global", sort });
  if (status) query.set("status", status);
  const claims = await api(`/v1/claims?${query}`);
  for (const claim of claims) list.append(renderClaimRow(claim));
  $("#feed-summary").textContent = `${claims.length} claims on the global wall`;
}

// The basis of a claim's number, in honesty-ladder vocabulary: a settled claim
// was proven by a signed run (measured); everything else is still a claim.
function claimBasis(claim) {
  if (claim.status === "settled_verified") return "measured";
  if (claim.status === "refuted") return "refuted";
  return "claimed";
}

function priorLine(claim) {
  const prior = claim.prior_snapshot?.pool?.p50_decode_tok_s;
  if (prior) return `prior: measured ${fmt(prior)} tok/s median`;
  const roofline = claim.prior_snapshot?.roofline?.expected_decode_tok_s;
  if (roofline) return `prior: formula ${fmt(roofline)} tok/s expected`;
  return "prior: no data yet";
}

function authorHandle(claim) {
  return claim.claimant_handle ?? claim.handle ?? null;
}

function renderClaimRow(claim, fromFeed = false) {
  const handle = authorHandle(claim);
  const metrics = claim.claimed_metrics ?? {};
  const tally = claim.tally ?? { margin: 0, voter_count: 0, plausible_count: 0, impossible_count: 0 };
  const li = document.createElement("li");
  li.dataset.claimId = claim.id;
  li.innerHTML = `
    <div class="claim-head">
      ${handle ? `<button class="linkish author" data-profile="${escapeHtml(handle)}">@${escapeHtml(handle)}</button>` : `<span class="muted">unattributed</span>`}
      <span class="badge ${claim.status}">${claim.status}</span>
    </div>
    <div class="claim-number">${escapeHtml(claim.model_release_id ?? "")} · <strong>${fmt(metrics.decode_tok_s)} tok/s</strong> <span class="badge basis-${claimBasis(claim)}">${claimBasis(claim)}</span></div>
    <div class="muted provenance">${escapeHtml(priorLine(claim))}${claim.source_url ? ` · <a href="${escapeHtml(claim.source_url)}" rel="noopener" target="_blank">source</a>` : claim.source ? ` · via ${escapeHtml(claim.source)}` : ""}</div>
    <div class="tally muted">▲ ${tally.plausible_count ?? 0} · ▼ ${tally.impossible_count ?? 0} · margin ${fmt(tally.margin)} · ${tally.voter_count} votes</div>`;
  for (const button of li.querySelectorAll("[data-profile]")) {
    button.onclick = (event) => {
      event.stopPropagation();
      openProfile(button.dataset.profile);
    };
  }
  li.onclick = () => openDetail(claim.id);
  return li;
}

function renderRunRow(run) {
  const li = document.createElement("li");
  li.innerHTML = `
    <div class="claim-head">
      <strong>verified run</strong>
      <span class="badge settled_verified">measured</span>
    </div>
    <div class="claim-number">${escapeHtml(run.model_release_id ?? "")} · <strong>${fmt(run.decode_tok_s)} tok/s</strong> <span class="badge basis-measured">measured</span></div>`;
  return li;
}

let CURRENT_CLAIM_ID = null;

async function openDetail(claimId) {
  CURRENT_CLAIM_ID = claimId;
  const claim = await api(`/v1/claims/${claimId}`);
  const prior = claim.prior_snapshot?.pool?.p50_decode_tok_s
    ? `measured ${fmt(claim.prior_snapshot.pool.p50_decode_tok_s)} tok/s median`
    : claim.prior_snapshot?.roofline
      ? `formula ${fmt(claim.prior_snapshot.roofline.expected_decode_tok_s)} tok/s expected`
      : "no data yet";
  const handle = authorHandle(claim);
  $("#detail-body").innerHTML = `
    <h1>${handle ? `@<button class="linkish" data-profile="${escapeHtml(handle)}">${escapeHtml(handle)}</button> · ` : ""}${escapeHtml(claim.model_release_id)}</h1>
    <p><strong>${fmt(claim.claimed_metrics.decode_tok_s)} tok/s</strong> <span class="badge basis-${claimBasis(claim)}">${claimBasis(claim)}</span> claimed — engine says: ${escapeHtml(prior)}</p>
    <p class="muted">${claim.tally.plausible_count} up / ${claim.tally.impossible_count} down · margin ${fmt(claim.tally.margin)} · ${claim.status}${claim.source_url ? ` · <a href="${escapeHtml(claim.source_url)}" rel="noopener" target="_blank">source</a>` : ""}</p>`;
  for (const button of $("#detail-body").querySelectorAll("[data-profile]")) {
    button.onclick = () => openProfile(button.dataset.profile);
  }
  $("#vote-row").hidden = !token() || claim.status !== "open";
  $("#report-row").hidden = !token();
  $("#form-report").hidden = true;
  $("#settle-box").hidden = !(token() && claim.status === "open");
  $("#settle-command").textContent =
    `benchmark-probe upload --settle-claim ${claim.id}`;
  const preview = $("#card-preview");
  preview.src = `${API_BASE}/v1/cards/claims/${claim.id}.svg`;
  preview.hidden = false;
  show("detail");
}

async function vote(verdict) {
  const claimId = location.hash.replace("#/claims/", "") || $("#settle-command").textContent.split(" ").pop();
  try {
    await api(`/v1/claims/${claimId}/votes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict }),
    });
    await openDetail(claimId);
  } catch (error) {
    alert(error.message);
  }
}

async function submitClaim(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const status = $("#claim-status");
  try {
    const payload = {
      model_release_id: form.get("model_release_id"),
      claimed_metrics: { decode_tok_s: Number(form.get("decode_tok_s")) },
    };
    for (const key of ["quantization_profile_id", "gpu_model_id"]) {
      if (form.get(key)) payload[key] = form.get(key);
    }
    if (form.get("context_tokens")) payload.context_tokens = Number(form.get("context_tokens"));
    if (form.get("note")) payload.note = form.get("note");
    if (form.get("source_url")) payload.source_url = form.get("source_url");
    const claim = await api("/v1/claims", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    status.textContent = `claim posted:\n${JSON.stringify(claim.tally)}\nshare card: /v1/cards/claims/${claim.id}.md`;
    status.hidden = false;
    await loadFeed();
  } catch (error) {
    status.textContent = `error: ${error.message}`;
    status.hidden = false;
  }
}

async function submitReport(event) {
  event.preventDefault();
  const claimId = CURRENT_CLAIM_ID;
  if (!claimId) return;
  const form = new FormData(event.target);
  const payload = { reason_category: form.get("reason_category") };
  if (form.get("reason_detail")) payload.reason_detail = form.get("reason_detail");
  const status = $("#claim-status");
  try {
    const view = await api(`/v1/run-claims/${claimId}/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("#form-report").hidden = true;
    status.textContent = `report filed (${view.reason_category}) — a moderator will review it. If confirmed: fake caught, 5 points.`;
    status.hidden = false;
  } catch (error) {
    status.textContent = `report error: ${error.message}`;
    status.hidden = false;
  }
}

function fmt(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(1) : "-";
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- wiring ---------- */

for (const button of document.querySelectorAll("[data-view]")) {
  button.addEventListener("click", () => show(button.dataset.view));
}
$("#feed-sort").addEventListener("change", loadFeed);
$("#feed-scope").addEventListener("change", loadFeed);
$("#feed-status").addEventListener("change", loadFeed);
$("#btn-refresh").addEventListener("click", loadFeed);

$("#form-register").addEventListener("submit", async (event) => {
  event.preventDefault();
  const handle = new FormData(event.target).get("handle");
  try {
    await registerPasskey(handle);
    await loginPasskey(handle); // immediate first login issues a session token
    renderSession();
    show("feed");
    await loadFeed();
  } catch (error) {
    const status = $("#auth-status");
    status.textContent = `register failed: ${error.message}`;
    status.hidden = false;
  }
});

$("#form-login").addEventListener("submit", async (event) => {
  event.preventDefault();
  const handle = new FormData(event.target).get("handle");
  try {
    await loginPasskey(handle);
    renderSession();
    show("feed");
    await loadFeed();
  } catch (error) {
    const status = $("#auth-status");
    status.textContent = `login failed: ${error.message}`;
    status.hidden = false;
  }
});

$("#form-claim").addEventListener("submit", submitClaim);
$("#btn-report-toggle").addEventListener("click", () => {
  $("#form-report").hidden = !$("#form-report").hidden;
});
$("#btn-report-cancel").addEventListener("click", () => {
  $("#form-report").hidden = true;
});
$("#form-report").addEventListener("submit", submitReport);
for (const button of document.querySelectorAll("#vote-row [data-verdict]")) {
  button.addEventListener("click", () => vote(button.dataset.verdict));
}

// S30: OAuth sign-in (GitHub / Hugging Face). The API redirects back to this
// page with the session token in the URL fragment — fragments are never sent
// to any server. Capture it once and clean the address bar.
function oauthBeginUrl(provider) {
  const redirectUri = location.origin + location.pathname;
  return `${API_BASE}/v1/auth/oauth/${provider}/begin?redirect_uri=${encodeURIComponent(redirectUri)}`;
}

// S31: link flow. The API signs a state that carries our user id; the
// callback binds the provider identity to this account and comes back with
// #linked=<provider>&login=<login>&outcome=linked|moved|already_linked.
async function startOauthLink(provider) {
  const redirectUri = location.origin + location.pathname;
  const response = await api(`/v1/auth/oauth/${provider}/link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ redirect_uri: redirectUri }),
  });
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))).detail || response.statusText;
    alert(`could not start ${provider} link: ${detail}`);
    return;
  }
  location.href = (await response.json()).authorize_url;
}

function captureOauthFragment() {
  const params = new URLSearchParams(location.hash.slice(1));
  const accessToken = params.get("auth_token");
  const authError = params.get("auth_error");
  const linked = params.get("linked");
  const linkError = params.get("link_error");
  if (accessToken) {
    localStorage.setItem(TOKEN_KEY, accessToken);
  } else if (authError) {
    const status = $("#auth-status");
    status.textContent = `oauth sign-in failed: ${authError}`;
    status.hidden = false;
  } else if (linked) {
    const outcome = params.get("outcome");
    const login = params.get("login");
    const msg = outcome === "moved"
      ? `${linked} identity ${login} moved to this account (the suffixed account it created is now empty)`
      : outcome === "already_linked"
        ? `${linked} identity ${login} was already linked`
        : `${linked} identity ${login} linked to this account`;
    setTimeout(() => alert(msg), 0);
  } else if (linkError) {
    setTimeout(() => alert(`link failed: ${linkError}`), 0);
  } else {
    return;
  }
  history.replaceState(null, "", location.pathname + location.search);
}

for (const [selector, provider] of [
  ["#oauth-github", "github"],
  ["#oauth-huggingface", "huggingface"],
]) {
  const button = document.querySelector(selector);
  if (button) button.addEventListener("click", () => {
    location.href = oauthBeginUrl(provider);
  });
}

captureOauthFragment();
renderSession();
show(token() ? "feed" : "auth");
if (token()) {
  loadFeed().catch(() => {});
  loadIdentity().catch(() => {});
}
