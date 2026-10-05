#!/usr/bin/env node
// Smoke test for a nonprod stack (dev|stag), run against the gate.
// Node 22+ only (global fetch, no dependencies).
//
//   node deploy/nonprod/smoke.mjs dev
//   BASE_URL=http://dev.bestmodel.run GATE_PASSWORD=... node deploy/nonprod/smoke.mjs stag
//
// Gate auth: GATE_PASSWORD env var, else /data/bestmodel/nonprod/<env>/gate-password.
// BASE_URL override: default http://<env>.bestmodel.run (the gate publishes no
// port, so ship.sh runs this inside the project network against gate:80).

import { readFileSync } from "node:fs";

const envName = process.argv[2];
if (envName !== "dev" && envName !== "stag") {
  console.error("usage: smoke.mjs dev|stag");
  process.exit(2);
}

const baseUrl = (process.env.BASE_URL ?? `http://${envName}.bestmodel.run`).replace(/\/+$/, "");

let gatePassword = process.env.GATE_PASSWORD ?? "";
if (!gatePassword) {
  const passwordFile = `/data/bestmodel/nonprod/${envName}/gate-password`;
  try {
    gatePassword = readFileSync(passwordFile, "utf8").trim();
  } catch {
    console.error(`no gate password: set GATE_PASSWORD or create ${passwordFile}`);
    process.exit(2);
  }
}
if (!gatePassword) {
  console.error("empty gate password");
  process.exit(2);
}

const basic = (user, pass) => `Basic ${Buffer.from(`${user}:${pass}`).toString("base64")}`;

let failures = 0;
let count = 0;

function check(ok, name, detail = "") {
  count += 1;
  if (ok) {
    console.log(`ok   ${count} - ${name}`);
  } else {
    failures += 1;
    console.error(`FAIL ${count} - ${name}${detail ? `: ${detail}` : ""}`);
  }
}

async function get(path, { auth = true } = {}) {
  const headers = auth ? { authorization: basic("orbe", gatePassword) } : {};
  const res = await fetch(`${baseUrl}${path}`, {
    headers,
    redirect: "manual",
    signal: AbortSignal.timeout(30_000),
  });
  const text = await res.text();
  return { res, text };
}

try {
  const { res } = await get("/", { auth: false });
  check(res.status === 401, "gate rejects unauthenticated requests", `expected 401, got ${res.status}`);
} catch (err) {
  check(false, "gate rejects unauthenticated requests", String(err));
}

let root;
try {
  root = await get("/");
  check(root.res.status === 200, "GET / returns 200", `got ${root.res.status}`);
} catch (err) {
  root = null;
  check(false, "GET / returns 200", String(err));
}

const robots = root?.res.headers.get("x-robots-tag") ?? "";
check(robots.toLowerCase().includes("noindex"), "gate sends X-Robots-Tag noindex", `got "${robots}"`);

try {
  const { res, text } = await get("/llms.txt");
  check(res.status === 200, "GET /llms.txt returns 200", `got ${res.status}`);
  check(text.includes("bestmodel.run"), "llms.txt mentions bestmodel.run", "substring not found");
} catch (err) {
  check(false, "GET /llms.txt returns 200", String(err));
  check(false, "llms.txt mentions bestmodel.run", String(err));
}

try {
  const { res, text } = await get("/wall?as=agent");
  check(res.status === 200, "GET /wall?as=agent returns 200", `got ${res.status}`);
  check(text.includes("Honesty ladder"), "wall agent view renders Honesty ladder", "substring not found");
} catch (err) {
  check(false, "GET /wall?as=agent returns 200", String(err));
  check(false, "wall agent view renders Honesty ladder", String(err));
}

try {
  const { res, text } = await get("/v1/leaderboard");
  if (res.status !== 200) {
    check(false, "GET /v1/leaderboard returns 200 JSON with runs", `expected 200, got ${res.status}`);
  } else {
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      check(false, "GET /v1/leaderboard returns 200 JSON with runs", `not JSON: ${text.slice(0, 120)}`);
      data = undefined;
    }
    if (data !== undefined) {
      check(Array.isArray(data.runs), "GET /v1/leaderboard returns 200 JSON with runs", `"runs" is not an array`);
    }
  }
} catch (err) {
  check(false, "GET /v1/leaderboard returns 200 JSON with runs", String(err));
}

console.log(failures === 0 ? `smoke ${envName}: all checks passed` : `smoke ${envName}: ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
