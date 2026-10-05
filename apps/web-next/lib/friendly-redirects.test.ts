import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { FRIENDLY_REDIRECTS, resolveFriendlyRedirect } from "./friendly-redirects.ts";

const SOURCES = [
  "/cloud",
  "/anchors",
  "/cloud-anchor",
  "/agent",
  "/agents",
  "/api",
];

const DESTINATIONS = ["/cloud-anchors", "/llms.txt"];

describe("FRIENDLY_REDIRECTS", () => {
  it("has exactly the six expected sources", () => {
    const got = FRIENDLY_REDIRECTS.map((r) => r.source).sort();
    assert.deepEqual(got, [...SOURCES].sort());
  });

  it("every redirect is soft (permanent: false)", () => {
    for (const r of FRIENDLY_REDIRECTS) {
      assert.equal(r.permanent, false, `${r.source} must be a soft redirect`);
    }
  });

  it("every destination points at a real page", () => {
    for (const r of FRIENDLY_REDIRECTS) {
      assert.ok(DESTINATIONS.includes(r.destination), `${r.destination} is not a known destination`);
    }
  });

  it("no destination is itself a source (no loop)", () => {
    const sourceSet = new Set(SOURCES.map((s) => s.toLowerCase()));
    for (const r of FRIENDLY_REDIRECTS) {
      assert.ok(!sourceSet.has(r.destination.toLowerCase()), `${r.destination} would loop back`);
    }
  });
});

describe("resolveFriendlyRedirect", () => {
  it("resolves each exact source", () => {
    for (const r of FRIENDLY_REDIRECTS) {
      assert.equal(resolveFriendlyRedirect(r.source), r.destination);
    }
  });

  it("tolerates a trailing slash", () => {
    for (const r of FRIENDLY_REDIRECTS) {
      assert.equal(resolveFriendlyRedirect(r.source + "/"), r.destination);
    }
  });

  it("is case-insensitive", () => {
    assert.equal(resolveFriendlyRedirect("/CLOUD"), "/cloud-anchors");
    assert.equal(resolveFriendlyRedirect("/AGENT"), "/llms.txt");
    assert.equal(resolveFriendlyRedirect("/API"), "/llms.txt");
  });

  it("returns null for non-matching paths", () => {
    assert.equal(resolveFriendlyRedirect("/api/em-breve"), null);
    assert.equal(resolveFriendlyRedirect("/v1/match"), null);
    assert.equal(resolveFriendlyRedirect("/cloud-anchors"), null);
    assert.equal(resolveFriendlyRedirect("/llms.txt"), null);
    assert.equal(resolveFriendlyRedirect("/"), null);
    assert.equal(resolveFriendlyRedirect(""), null);
  });
});
