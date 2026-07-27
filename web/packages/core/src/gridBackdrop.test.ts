import { describe, expect, it } from "vitest";
import { buildDemandPressure, buildGridBackdrop } from "./gridBackdrop";

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
