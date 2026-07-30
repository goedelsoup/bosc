import { describe, expect, it } from "vitest";
import { buildBackupRecord, buildDemandPressure, buildGridBackdrop } from "./gridBackdrop";

// The grid backdrop reads the committed per-site bundles (`web/sites/<slug>/`), so these run
// against real reference data — which is the point: the feed exists so the presentation tier
// stops carrying its own copy of these figures.

describe("gridBackdrop — the reference build's cited service chain (#1642 E1)", () => {
  const b = buildGridBackdrop("lima");

  it("renders the full five-link chain, every link cited", () => {
    expect(b).not.toBeNull();
    expect(b?.chain.map((r) => r.key)).toEqual([
      "utility",
      "holding_company",
      "balancing_authority",
      "rto",
      "retail_regulator",
    ]);
    for (const row of b?.chain ?? []) {
      expect(row.value.length).toBeGreaterThan(0);
      // "Cited, never asserted" — the whole reason these are CitedFacts and not strings.
      expect(row.cite.length).toBeGreaterThan(0);
      expect(row.label.length).toBeGreaterThan(0);
    }
  });

  it("identifies Lima's chain: AEP Ohio → AEP → PJM, PUCO-regulated", () => {
    const by = new Map((b?.chain ?? []).map((r) => [r.key, r.value]));
    expect(by.get("utility")).toMatch(/AEP Ohio/);
    expect(by.get("holding_company")).toMatch(/American Electric Power/);
    expect(by.get("balancing_authority")).toMatch(/PJM/);
    expect(by.get("rto")).toMatch(/PJM/);
    expect(by.get("retail_regulator")).toMatch(/PUCO/);
  });

  it("carries the utility / BA / state denominators, none of them zero", () => {
    const keys = (b?.denominators ?? []).map((d) => d.key);
    expect(keys).toContain("utility");
    expect(keys).toContain("ba");
    expect(keys).toContain("state"); // Lima has a campus, so the state row is pulled
    for (const d of b?.denominators ?? []) {
      expect(d.gwh).toBeGreaterThan(0);
      expect(d.cite.length).toBeGreaterThan(0);
    }
  });

  it("expresses the disclosed campus as a share of each denominator", () => {
    expect(b?.campus).not.toBeNull();
    expect(b?.campus?.loadMw).toBeGreaterThan(0);
    expect(b?.campus?.annualGwh).toBeGreaterThan(0);
    for (const d of b?.denominators ?? []) {
      expect(d.sharePct).not.toBeNull();
      expect(d.sharePct ?? 0).toBeGreaterThan(0);
    }
  });
});

describe("gridBackdrop — the backdrop describes the place, not the campus (#1642)", () => {
  it("a facility-less peer carries the chain with NO fabricated campus share", () => {
    // WPAFB has floor data (so a grid feed) and no disclosed data-center facility.
    const b = buildGridBackdrop("wpafb");
    expect(b).not.toBeNull();
    expect(b?.chain.length).toBe(5);
    expect(b?.utilityName.length).toBeGreaterThan(0);
    // The honest empty: no campus ⇒ no share column, and no state denominator (it is pulled
    // only for the share). The utility/BA figures — properties of the place — still stand.
    expect(b?.campus).toBeNull();
    for (const d of b?.denominators ?? []) expect(d.sharePct).toBeNull();
    expect((b?.denominators ?? []).map((d) => d.key)).not.toContain("state");
    expect((b?.denominators ?? []).length).toBeGreaterThan(0);
  });

  it("a site with no grid feed returns null — the caller locks, never borrows", () => {
    expect(buildGridBackdrop("coshocton")).toBeNull();
  });
});

describe("gridBackdrop — the demand-pressure feed is finally readable (#1642 E2)", () => {
  it("Lima's sensitivity carries its EIA-cited headline and its caveats", () => {
    const dp = buildDemandPressure("lima");
    expect(dp).not.toBeNull();
    expect(dp?.area).toBe("OH");
    expect(dp?.demand_share_pct.value ?? 0).toBeGreaterThan(0);
    expect(dp?.households_equivalent.value ?? 0).toBeGreaterThan(0);
    expect(dp?.state_retail_sales_gwh.source).toBe("connector");
    // The stylized band must arrive labelled as such — the page must not headline it.
    expect(dp?.transmission_coefficient.source).toBe("assumption");
    expect((dp?.caveats ?? []).length).toBeGreaterThan(0);
    expect((dp?.caveats ?? []).join(" ")).toMatch(/stylized|screening/i);
  });

  it("Fort Wayne carries its own per-state sensitivity, not Ohio's (#1642 E3)", () => {
    // E3 generated this dataset: Fort Wayne had a disclosed facility and a computable share but no
    // committed demand-pressure.yaml, so its facility read under-reported. Indiana denominators.
    const dp = buildDemandPressure("fort-wayne");
    expect(dp).not.toBeNull();
    expect(dp?.area).toBe("IN");
    expect(dp?.state_retail_sales_gwh.citation).toMatch(/IN-ALL/);
    expect(dp?.demand_share_pct.value ?? 0).toBeGreaterThan(0);
  });

  it("a facility-less site has no sensitivity to read", () => {
    expect(buildDemandPressure("wpafb")).toBeNull();
  });
});

// The #1771 drift guard. Lima's 313 MW / 114 gensets / 2,750 ekW lived in `gridLoad.ts` as TS
// literals duplicating `SiteFacility.genset_*`, with nothing pinning the copies together and a
// `site === "lima"` branch that refused Fort Wayne's real fleet. These read the committed bundles,
// so if a profile figure moves, the assertion moves with it — while the site's PUBLISHED headline
// (~313 MW, marker and all) is pinned, so a change big enough to restate it fails here.
describe("gridBackdrop — the backup record is feed-sourced, not a second copy (#1771)", () => {
  it("Lima's record is the CITED ~313 MW, not the components' 313.5 product", () => {
    const r = buildBackupRecord("lima");
    expect(r).not.toBeNull();
    expect(r?.backupMw).toBe(313);
    expect(r?.totalBasis).toBe("cited");
    expect(r?.approximate).toBe(true); // the record says "~313 MW"; the tilde is data
    expect(r?.nEngines).toBe(114);
    expect(r?.perEngineMw).toBe(2.75);
    // The rating survives only on the draft the issued permit redacts — the report's whole subject.
    expect(r?.ratingBasis).toBe("draft_only");
    expect(r?.cite).toMatch(/313 MW/);
    // The distinction the cited field exists for: deriving would have published this instead.
    expect((r?.nEngines ?? 0) * (r?.perEngineMw ?? 0)).toBe(313.5);
  });

  it("Fort Wayne gets its OWN record — 34 engines, derived, no longer null", () => {
    const r = buildBackupRecord("fort-wayne");
    expect(r).not.toBeNull();
    expect(r?.nEngines).toBe(34);
    expect(r?.backupMw).toBeCloseTo(102, 5);
    // No total is on that permit, so the figure is this platform's product — and says so, twice:
    // the total is derived and the per-engine rating under it is back-derived from heat input.
    expect(r?.totalBasis).toBe("derived");
    expect(r?.ratingBasis).toBe("derived");
    expect(r?.approximate).toBe(false); // a derived product carries no transcription marker
    expect(r?.cite.length).toBeGreaterThan(0);
  });

  it("a facility with no disclosed gensets is null — it never inherits Lima's fleet", () => {
    // Urbana's facility is site-plan-grounded (floor area, no air permit); WPAFB is a federal
    // enclave, which is forbidden genset fields at the type level; Coshocton has no feed at all.
    expect(buildBackupRecord("urbana")).toBeNull();
    expect(buildBackupRecord("wpafb")).toBeNull();
    expect(buildBackupRecord("coshocton")).toBeNull();
  });
});
