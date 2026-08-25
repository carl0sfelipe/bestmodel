#!/usr/bin/env node
// S19 oracle: the console must support the full loop without a terminal.
// Validates structure + every API touchpoint the loop needs.
// Run: node scripts/check-console.mjs

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const html = await readFile(new URL("../console/index.html", import.meta.url), "utf8");
const js = await readFile(new URL("../console/console.js", import.meta.url), "utf8");

test("console page wires the stylesheet and script", () => {
  assert.match(html, /href="console\.css"/);
  assert.match(html, /src="console\.js" type="module"/);
});

test("passkey ceremonies are wired to the auth endpoints", () => {
  for (const endpoint of [
    "/v1/auth/passkey/register/options",
    "/v1/auth/passkey/register/verify",
    "/v1/auth/passkey/login/options",
    "/v1/auth/passkey/login/verify",
  ]) {
    assert.ok(js.includes(endpoint), `missing ${endpoint}`);
  }
  assert.match(js, /navigator\.credentials\.create/);
  assert.match(js, /navigator\.credentials\.get/);
});

test("browse + vote + claim endpoints are all present", () => {
  for (const endpoint of ["/v1/claims?", "/votes", "/v1/cards/claims/", "/v1/feed"]) {
    assert.ok(js.includes(endpoint), `missing ${endpoint}`);
  }
});

test("settle command is surfaced without a terminal requirement", () => {
  assert.match(js, /--settle-claim/);
  assert.ok(html.includes("Prove it"));
});

test("honesty ladder is visible in the UI", () => {
  assert.match(html, /measured &gt; reported &gt; extrapolated &gt; formula &gt; no data yet/);
});
