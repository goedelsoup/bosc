import { describe, expect, it } from "vitest";
import {
  AEP_OHIO_RETAIL_GWH,
  BACKUP_MW,
  GRID_PRIORS,
  annualGwh,
  equivalentHomes,
  facilityDrawModel,
  facilityDrawOutcome,
  mwPerJob,
  pctOfAepRetail,
} from "./gridLoad";
import { disclose, outcomeBand } from "./uncertainty";

describe("gridLoad — the inference chain reproduces the essay", () => {
  it("facility draw central ~348 MW, band ~303–393", () => {
    const o = facilityDrawOutcome();
    expect(Math.round(o.central)).toBe(348);
    expect(Math.round(o.low)).toBe(303);
    expect(Math.round(o.high)).toBe(393);
    expect(o.register).toBe("assumption"); // a bounded inference chain (prose [inference])
  });

  it("annual energy ~2,740 GWh ⇒ ~5.6% of AEP Ohio retail ⇒ ~260k homes", () => {
    const gwh = annualGwh(348);
    expect(Math.round(gwh / 10) * 10).toBe(2740);
    expect(Number(pctOfAepRetail(gwh).toFixed(1))).toBe(5.6);
    expect(Math.round(equivalentHomes(gwh) / 1000)).toBe(261); // ~260k
    expect(AEP_OHIO_RETAIL_GWH).toBe(48_653);
  });

  it("load-not-jobs: ~5–6 MW of IT load per promised job", () => {
    expect(mwPerJob(275)).toBeCloseTo(5.5);
    expect(BACKUP_MW).toBe(313);
  });
});

describe("gridLoad — the redaction-driven band collapses on disclosure", () => {
  it("disclosing the operating (IT) load tightens the facility-draw band", () => {
    const wide = outcomeBand(GRID_PRIORS, facilityDrawModel);
    const disclosed = disclose(GRID_PRIORS, "it_load", 275);
    const tight = outcomeBand(disclosed, facilityDrawModel);
    expect(tight.high - tight.low).toBeLessThan(wide.high - wide.low);
  });

  it("the band is non-trivial — it exists because the load is withheld", () => {
    const o = facilityDrawOutcome();
    expect(o.high - o.low).toBeGreaterThan(50); // ~90 MW of inference width
    expect(o.resolvingRecord).toMatch(/redact|per-engine|operating-load/i);
  });
});
