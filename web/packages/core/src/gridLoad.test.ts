import { describe, expect, it } from "vitest";
import { buildGridBaseline } from "./gridBackdrop";
import {
  type BackupRecord,
  GRID_PRIORS,
  annualGwh,
  backupRegister,
  equivalentHomes,
  facilityDrawModel,
  facilityDrawOutcome,
  fmtBackupMw,
  gridPriorsFromFacility,
  mwPerJob,
  pctOfUtilityRetail,
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

  it("load-not-jobs: ~5–6 MW of IT load per promised job", () => {
    expect(mwPerJob(275, 50)).toBeCloseTo(5.5);
  });
});

// The E2 drift guard (#1642). The essay's headline share used to rest on
// `AEP_OHIO_RETAIL_GWH = 48_653` — a literal hand-copied from the EIA pull the Python tier
// already did, with nothing tying the two together. Now the denominator comes from the committed
// `grid` feed, and this test is the tie: if the reference data moves, the assertion moves with it
// (it derives the expectation from the feed) but the *essay's* published figure is pinned, so a
// drift big enough to change what the site says fails here instead of shipping silently.
describe("gridLoad — the load baseline is feed-sourced, not a second copy (#1642)", () => {
  const baseline = buildGridBaseline("lima");

  it("Lima's grid feed supplies the utility denominator", () => {
    expect(baseline).not.toBeNull();
    expect(baseline?.utilityLabel).toMatch(/AEP Ohio/);
    expect(baseline?.utilityRetailGwh).toBeGreaterThan(0);
    expect(baseline?.utilityCite).toMatch(/EIA/i);
  });

  it("the essay's ~5.6%-of-retail headline reproduces off the feed", () => {
    if (baseline === null) throw new Error("Lima's bundle must carry the grid feed");
    const gwh = annualGwh(348);
    expect(Math.round(gwh / 10) * 10).toBe(2740);
    // The published figure, computed from the reference data rather than a duplicate of it.
    expect(Number(pctOfUtilityRetail(gwh, baseline.utilityRetailGwh).toFixed(1))).toBe(5.6);
  });

  it("the equivalent-homes readout uses the demand-pressure feed's own household figure", () => {
    if (baseline?.householdKwhYr == null) throw new Error("Lima must carry a household figure");
    // ~10,500 kWh/household/yr — the same cited value the demand-pressure feed divides by, so the
    // report and that feed can never disagree about how big a household is.
    expect(baseline.householdKwhYr).toBeGreaterThan(5_000);
    expect(Math.round(equivalentHomes(annualGwh(348), baseline.householdKwhYr) / 1000)).toBe(261);
  });

  it("a site with no grid feed yields no baseline — it never inherits Lima's utility", () => {
    // Coshocton is a registered stub with no committed floor data at all.
    expect(buildGridBaseline("coshocton")).toBeNull();
  });
});

// The #1771 grades. `gridLoad.ts` holds the model — how a backup record RENDERS — while the
// record itself is read from the `facility` feed by `gridBackdrop.buildBackupRecord` (tested
// there, against the committed bundles). These pin the two rules that keep a per-site record
// honest: the record's own `~` marker survives to the page, and a figure this platform derived
// never renders under the register a disclosed one gets.
describe("gridLoad — the backup figure renders at the grade its record earns (#1771)", () => {
  const lima: BackupRecord = {
    backupMw: 313,
    totalBasis: "cited",
    approximate: true,
    nEngines: 114,
    perEngineMw: 2.75,
    ratingBasis: "draft_only",
    cite: "the ~313 MW backup total (4132514.epa.yaml) over the draft's ~2,750 ekW",
  };

  it("a cited total over a document-grade rating is [verified] — the draft is a document", () => {
    expect(backupRegister(lima)).toBe("verified");
    expect(backupRegister({ ...lima, ratingBasis: "disclosed" })).toBe("verified");
  });

  it("a back-derived rating pulls the total down to an assumption, cited or not", () => {
    // Fort Wayne: 34 engines are verbatim, but the permit states heat input, not an electrical
    // rating — so the MW resting on it is the platform's inference and must not read [verified].
    expect(backupRegister({ ...lima, ratingBasis: "derived" })).toBe("assumption");
  });

  it("a total this platform multiplied out is an assumption, however good the rating", () => {
    expect(backupRegister({ ...lima, totalBasis: "derived", approximate: false })).toBe("assumption");
  });

  it("keeps the record's ~ marker — the site's headline is ~313 MW, never 313.5", () => {
    expect(fmtBackupMw(lima)).toBe("~313 MW");
    // A derived total prints its real product, with no marker it did not earn.
    expect(fmtBackupMw({ ...lima, backupMw: 313.5, totalBasis: "derived", approximate: false })).toBe(
      "313.5 MW",
    );
    expect(fmtBackupMw({ ...lima, backupMw: 102, totalBasis: "derived", approximate: false })).toBe("102 MW");
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
