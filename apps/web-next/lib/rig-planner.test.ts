import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CALIBRATION_ANCHORS, DEFAULT_QUERY, GPUS, MODELS, QUANTS,
  decodeStep, parsePlanQuery, plan,
} from "./rig-planner.ts";

describe("rig-planner calibration", () => {
  for (const a of CALIBRATION_ANCHORS) {
    it(`reproduces the pool anchor inside its band: ${a.what}`, () => {
      const bits = "bitsOverride" in a ? a.bitsOverride : undefined;
      const s = decodeStep(GPUS[a.gpu], a.gpus, MODELS[a.model], QUANTS[a.quant], a.contextTokens, bits);
      assert.ok(
        s.tokS.low * 0.97 <= a.measuredTokS && a.measuredTokS <= s.tokS.high,
        `${a.measuredTokS} outside [${s.tokS.low.toFixed(1)}, ${s.tokS.high.toFixed(1)}]`,
      );
    });
  }
});

describe("rig-planner: Akita's 4x B300 question", () => {
  const rows = plan(DEFAULT_QUERY);
  const row = (m: string, q: string) => rows.find((r) => r.model.key === m && r.quant.key === q)!;

  it("full GLM-5.3 does not fit in BF16 on 4x B300, fits in FP8 at 212k", () => {
    assert.equal(row("glm-5.3", "bf16").fits, false);
    assert.equal(row("glm-5.3", "bf16").tokS, null);
    assert.equal(row("glm-5.3", "fp8").fits, true);
    assert.ok(row("glm-5.3", "fp8").kvGb < 15, "DSA/MLA keeps 212k KV small");
  });

  it("Flash is faster, but by less than the 40B/18B active-param ratio", () => {
    for (const q of ["fp8", "nvfp4"]) {
      const ratio = row("glm-5.3-flash", q).tokS!.mid / row("glm-5.3", q).tokS!.mid;
      assert.ok(ratio > 1.3 && ratio < 40 / 18, `ratio ${ratio}`);
    }
  });

  it("every number is labeled modeled", () => {
    assert.ok(rows.every((r) => r.basis === "modeled"));
  });

  it("context barely moves decode with sparse attention", () => {
    const short = plan({ ...DEFAULT_QUERY, contextTokens: 8192 });
    const a = short.find((r) => r.model.key === "glm-5.3" && r.quant.key === "fp8")!.tokS!.mid;
    const b = row("glm-5.3", "fp8").tokS!.mid;
    assert.ok(Math.abs(a - b) / a < 0.02);
  });
});

describe("parsePlanQuery", () => {
  it("falls back on garbage", () => {
    assert.deepEqual(parsePlanQuery({ gpu: "nope", n: "99", ctx: "x" }), DEFAULT_QUERY);
  });
  it("accepts valid overrides", () => {
    const q = parsePlanQuery({ gpu: "b200", n: "8", ctx: "131072" });
    assert.equal(q.gpu, "b200");
    assert.equal(q.gpus, 8);
    assert.equal(q.contextTokens, 131072);
  });
});
