import { describe, expect, it } from "vitest";
import type { RecordItem } from "./feeds";
import {
  FALLBACK_CONTINGENCY_PCT,
  modeledRows,
  opcScenarioFromRecords,
  programTotal,
  sourceProgramTotal,
} from "./opcScenario";

/** A minimal `records`-feed row carrying the two real first Tetra Tech sub-estimates. */
function opcRecord(): RecordItem {
  return {
    rel: "aedg/roundabouts.summary.opc.yaml",
    group: "opc",
    title: "OPC summary",
    warnings: [],
    approximate_paths: [],
    citation: { source_kind: "extraction", verified: true },
    fields: {
      meta: { contingency_and_inflation_pct: 25, estimator: "Tetra Tech (RJS)", basis: "Conceptual" },
      sub_estimates: [
        { name: "Cole Street / Diller Road Roundabout", construction_subtotal: 1_228_174, total: 1_535_218 },
        { name: "Second Roundabout", construction_subtotal: 1_000_000, total: 1_250_000 },
      ],
    },
  } as RecordItem;
}

describe("opcScenario — extraction", () => {
  it("pulls the sub-estimates + the source contingency convention", () => {
    const s = opcScenarioFromRecords([opcRecord()]);
    expect(s).not.toBeNull();
    expect(s?.sourceContingencyPct).toBe(25);
    expect(s?.subs.map((x) => x.name)).toEqual(["Cole Street / Diller Road Roundabout", "Second Roundabout"]);
    expect(s?.subs[0].constructionSubtotal).toBe(1_228_174);
  });

  it("returns null when no OPC record is present", () => {
    expect(opcScenarioFromRecords([])).toBeNull();
  });
});

describe("opcScenario — chain of custody (no fork from the source)", () => {
  it("reproduces each source total at the source's own 25% convention", () => {
    const s = opcScenarioFromRecords([opcRecord()]);
    if (!s) throw new Error("fixture");
    const all = new Set(s.subs.map((x) => x.name));
    for (const r of modeledRows(s.subs, s.sourceContingencyPct, all)) {
      expect(r.modeledTotal).toBe(r.sourceTotal); // 1,228,174 × 1.25 = 1,535,218 (rounded)
    }
  });

  it("the modeled program total matches the source program total at 25%", () => {
    const s = opcScenarioFromRecords([opcRecord()]);
    if (!s) throw new Error("fixture");
    const all = new Set(s.subs.map((x) => x.name));
    const rows = modeledRows(s.subs, FALLBACK_CONTINGENCY_PCT, all);
    expect(programTotal(rows)).toBe(sourceProgramTotal(rows));
  });
});

describe("opcScenario — the knobs", () => {
  it("re-prices with the contingency rate", () => {
    const s = opcScenarioFromRecords([opcRecord()]);
    if (!s) throw new Error("fixture");
    const all = new Set(s.subs.map((x) => x.name));
    const rows = modeledRows(s.subs, 0, all); // 0% → the bare construction subtotal
    expect(rows[0].modeledTotal).toBe(1_228_174);
    expect(programTotal(rows)).toBe(2_228_174);
  });

  it("respects the intersection selection", () => {
    const s = opcScenarioFromRecords([opcRecord()]);
    if (!s) throw new Error("fixture");
    const one = new Set(["Second Roundabout"]);
    const rows = modeledRows(s.subs, 25, one);
    expect(rows).toHaveLength(1);
    expect(rows[0].modeledTotal).toBe(1_250_000);
  });
});
