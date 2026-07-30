import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// The economic row's band comes from the `economics-scenarios` feed now (#1665), so this suite is
// bundle-backed. Pin WATERMARK_BUNDLE_DIR at the committed `web/sites` fixtures before importing
// anything that reads a bundle.
process.env.WATERMARK_BUNDLE_DIR ??= resolve(fileURLToPath(new URL(".", import.meta.url)), "../../../sites");

const { buildBalanceSheet } = await import("./balanceSheet");
const { runWithSite } = await import("./bundle");
const { netSubsidyOutcomeFromFeed } = await import("./econScenarios");

// The feed's discharge constants (buildDilution): WWTP 8.82 + FM-2 3.87 = 12.69 cfs
// effluent; ~1.01 cfs summed natural low flow at the annual 7Q10.
const sheet = runWithSite("lima", () =>
  buildBalanceSheet(12.69, 1.01, "lima", null, netSubsidyOutcomeFromFeed()),
);

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
    const e = sheet.econExposure;
    if (e === null) throw new Error("Lima's sheet must price its CRA exposure");
    expect(e.low).toBeLessThan(e.central);
    expect(e.central).toBeLessThan(e.high);
    expect(e.high).toBeGreaterThan(30_000_000); // tens of millions
  });
});

// The peer's economic row is absent because its bundle carries no `economics-scenarios` feed —
// the gate is the instrument on the record, not the slug (#1642 E4, sharpened by #1665).
describe("balanceSheet — a peer's sheet omits what its record doesn't hold (#1642 E4)", () => {
  const peer = runWithSite("fort-wayne", () =>
    buildBalanceSheet(12.69, 1.01, "fort-wayne", null, netSubsidyOutcomeFromFeed()),
  );

  it("drops the economic row rather than pricing Allen County's CRA under another name", () => {
    expect(peer.rows.map((r) => r.outcome.key)).toEqual(["grid_facility_draw", "toxics_effluent_share"]);
    expect(peer.econExposure).toBeNull();
  });

  it("still composes the bands it can source, with their resolving records", () => {
    expect(peer.rows.length).toBeGreaterThan(0);
    expect(peer.resolvingRecords.length).toBeGreaterThan(0);
    for (const r of peer.rows) expect(r.outcome.resolvingRecord).toBeTruthy();
  });
});
