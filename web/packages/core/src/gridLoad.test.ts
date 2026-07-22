import { describe, expect, it } from "vitest";
import {
  AEP_OHIO_RETAIL_GWH,
  BACKUP_MW,
  GRID_PRIORS,
  annualGwh,
  equivalentHomes,
  facilityDrawModel,
  facilityDrawOutcome,
  gridPriorsFromFacility,
  mwPerJob,
  pctOfAepRetail,
} from "./gridLoad";
import { central, disclose, outcomeBand, priorCentral } from "./uncertainty";

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

describe("gridLoad — the IT-load prior is feed-sourced (#1632)", () => {
  it("builds the it_load prior from the facility feed's disclosed range", () => {
    const priors = gridPriorsFromFacility(275, 250, 300);
    const it = priors.find((p) => p.key === "it_load");
    expect(it && central(it.dist)).toBe(275);
    expect(it?.dist).toMatchObject({ kind: "triangular", low: 250, high: 300 });
    // The PUE prior is carried through unchanged, so the draw model still resolves.
    expect(priors.find((p) => p.key === "pue")).toBeDefined();
  });

  it("Lima's feed values reproduce the essay band (one sourced representation)", () => {
    // Lima's facility feed carries 250/275/300 — identical to the hardcoded GRID_PRIORS, so
    // sourcing from the feed leaves the numbers put; /basin sums the same 275.
    const o = facilityDrawOutcome(gridPriorsFromFacility(275, 250, 300));
    expect(Math.round(o.central)).toBe(348);
    expect(Math.round(o.low)).toBe(303);
    expect(Math.round(o.high)).toBe(393);
    expect(priorCentral(gridPriorsFromFacility(275, 250, 300), "it_load")).toBe(275);
  });

  it("a wider disclosed MW range widens the facility-draw band", () => {
    const narrow = facilityDrawOutcome(gridPriorsFromFacility(275, 260, 290));
    const wide = facilityDrawOutcome(gridPriorsFromFacility(275, 200, 350));
    expect(wide.high - wide.low).toBeGreaterThan(narrow.high - narrow.low);
  });

  it("a load with no disclosed range collapses to a point (no NaN)", () => {
    const o = facilityDrawOutcome(gridPriorsFromFacility(275));
    expect(Number.isFinite(o.central)).toBe(true);
    expect(o.central).toBeCloseTo(348, 0);
  });
});
