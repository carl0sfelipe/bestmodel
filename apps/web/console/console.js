/* bestmodel console — zero-dependency vanilla JS over the public API.
 *
 * Full loop without a terminal (L02 C6):
 *   register/sign in (passkey) -> browse claims -> vote -> post a claim
 *   -> see the settle command + share card.
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
    area.innerHTML = `<button id="btn-signout" class="linkish">sign out</button>`;
    $("#btn-signout").onclick = () => {
      localStorage.removeItem(TOKEN_KEY);
      renderSession();
      show("auth");
    };
  } else {
    area.innerHTML = `<button data-view="auth">sign in</button>`;
    area.querySelector("[data-view]").onclick = () => show("auth");
  }
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
    return;
  }

  const query = new URLSearchParams({ scope: "global", sort });
  if (status) query.set("status", status);
  const claims = await api(`/v1/claims?${query}`);
  for (const claim of claims) list.append(renderClaimRow(claim));
}

function renderClaimRow(claim, fromFeed = false) {
  const handle = claim.handle ?? "?";
  const metrics = claim.claimed_metrics ?? {};
  const tally = claim.tally ?? { margin: 0, voter_count: 0 };
  const li = document.createElement("li");
  li.dataset.claimId = claim.id;
  li.innerHTML = `
    <div class="claim-head">
      <strong>@${escapeHtml(handle)}</strong>
      <span class="badge ${claim.status}">${claim.status}</span>
    </div>
    <div>${escapeHtml(claim.model_release_id ?? "")} · ${fmt(metrics.decode_tok_s)} tok/s claimed</div>
    <div class="muted">margin ${fmt(tally.margin)} · ${tally.voter_count} votes</div>`;
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
    <div>${escapeHtml(run.model_release_id ?? "")} · ${fmt(run.decode_tok_s)} tok/s</div>`;
  return li;
}

async function openDetail(claimId) {
  const claim = await api(`/v1/claims/${claimId}`);
  const prior = claim.prior_snapshot?.pool?.p50_decode_tok_s
    ? `measured ${fmt(claim.prior_snapshot.pool.p50_decode_tok_s)} tok/s median`
    : claim.prior_snapshot?.roofline
      ? `formula ${fmt(claim.prior_snapshot.roofline.expected_decode_tok_s)} tok/s expected`
      : "no data yet";
  $("#detail-body").innerHTML = `
    <h1>@${escapeHtml(claim.handle ?? "?")} · ${escapeHtml(claim.model_release_id)}</h1>
    <p><strong>${fmt(claim.claimed_metrics.decode_tok_s)} tok/s</strong> claimed — engine says: ${escapeHtml(prior)}</p>
    <p class="muted">${claim.tally.plausible_count} up / ${claim.tally.impossible_count} down · margin ${fmt(claim.tally.margin)} · ${claim.status}</p>`;
  $("#vote-row").hidden = !token() || claim.status !== "open";
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
for (const button of document.querySelectorAll("#vote-row [data-verdict]")) {
  button.addEventListener("click", () => vote(button.dataset.verdict));
}

renderSession();
show(token() ? "feed" : "auth");
if (token()) loadFeed().catch(() => {});
