import { describe, expect, it } from "vitest";
import { buildBalanceSheet } from "./balanceSheet";

// The feed's discharge constants (buildDilution): WWTP 8.82 + FM-2 3.87 = 12.69 cfs
// effluent; ~1.01 cfs summed natural low flow at the annual 7Q10.
const sheet = buildBalanceSheet(12.69, 1.01, "lima");

describe("balanceSheet — composes every narrative's band (#273)", () => {
  it("has one row per quantitative narrative, each carrying a register + resolving record", () => {
    expect(sheet.rows.map((r) => r.outcome.key)).toEqual([
      "econ_net_subsidy",
      "grid_facility_draw",
      "toxics_effluent_share",
    ]);
    for (const r of sheet.rows) {
      expect(["verified", "assumption", "open"]).toContain(r.outcome.register);
      expect(r.outcome.resolvingRecord).toBeTruthy(); // the mandamus tie-in
      expect(r.outcome.low).toBeLessThanOrEqual(r.outcome.central);
      expect(r.outcome.central).toBeLessThanOrEqual(r.outcome.high);
    }
  });

  it("does not fork the narratives — toxics central reproduces the cited ~93%", () => {
    const toxics = sheet.rows.find((r) => r.outcome.key === "toxics_effluent_share");
    expect(Math.round(toxics?.outcome.central ?? 0)).toBe(93);
  });

  it("aggregates the withheld records that would collapse the bands", () => {
    // The econ ledger alone drives several (building share, jobs, equipment, school comp).
    expect(sheet.resolvingRecords.length).toBeGreaterThanOrEqual(4);
    expect(sheet.resolvingRecords.every((s) => s.length > 0)).toBe(true);
    expect(new Set(sheet.resolvingRecords).size).toBe(sheet.resolvingRecords.length); // deduped
  });

  it("scopes each band's companion link to the given site, not Lima (#1145)", () => {
    const peer = buildBalanceSheet(12.69, 1.01, "fort-wayne");
    for (const r of peer.rows) {
      expect(r.href.startsWith("/network/fort-wayne/reports/")).toBe(true);
    }
  });

  it("monetizes the public exposure as the economic net-subsidy band", () => {
    expect(sheet.econExposure.low).toBeLessThan(sheet.econExposure.central);
    expect(sheet.econExposure.central).toBeLessThan(sheet.econExposure.high);
    expect(sheet.econExposure.high).toBeGreaterThan(30_000_000); // tens of millions
  });
});
