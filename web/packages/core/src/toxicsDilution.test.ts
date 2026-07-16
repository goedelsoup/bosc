import { describe, expect, it } from "vitest";
import {
  ANNUAL_OTTAWA_7Q10,
  RSEI_DISCHARGERS,
  assimilativeOutcome,
  effluentMultiple,
  effluentPct,
  naturalAt,
  screeningConc,
} from "./toxicsDilution";

// The feed's discharge constants (buildDilution): WWTP 8.82 + campus FM-2 3.87 = 12.69
// cfs effluent; summed receiving-stream natural low flow ~1.01 cfs at the annual 7Q10.
const EFFLUENT = 12.69;
const NATURAL_ANNUAL = 1.01;

describe("toxicsDilution — the seasonal collapse", () => {
  it("reproduces ~93% effluent at the cited annual 7Q10", () => {
    const pct = effluentPct(EFFLUENT, naturalAt(ANNUAL_OTTAWA_7Q10, NATURAL_ANNUAL));
    expect(Math.round(pct)).toBe(93);
  });

  it("climbs toward 100% as the river dries, and the dilution goes to infinity at 1Q10", () => {
    const dry = effluentPct(EFFLUENT, naturalAt(0, NATURAL_ANNUAL));
    expect(dry).toBe(100); // natural → 0 → pure effluent
    expect(effluentMultiple(EFFLUENT, naturalAt(0, NATURAL_ANNUAL))).toBe(Number.POSITIVE_INFINITY);
    // summer dilutes more than the annual drought
    const summer = effluentPct(EFFLUENT, naturalAt(1.6, NATURAL_ANNUAL));
    expect(summer).toBeLessThan(93);
  });
});

describe("toxicsDilution — the RSEI screen (modeled, not measured)", () => {
  it("anchors each discharger's screening concentration at the cited 7Q10", () => {
    const ineos = RSEI_DISCHARGERS.find((d) => d.name.startsWith("INEOS"));
    expect(ineos?.conc7q10MgL).toBe(66);
    expect(screeningConc(ineos as (typeof RSEI_DISCHARGERS)[number], ANNUAL_OTTAWA_7Q10)).toBeCloseTo(66);
  });

  it("scales inversely with flow — spikes as the river dries, eases in summer", () => {
    const pcs = RSEI_DISCHARGERS.find((d) => d.name.startsWith("PCS")) as (typeof RSEI_DISCHARGERS)[number];
    expect(screeningConc(pcs, 1.6)).toBeLessThan(pcs.conc7q10MgL); // summer eases
    expect(screeningConc(pcs, 0)).toBe(Number.POSITIVE_INFINITY); // dry floor
  });

  it("marks only Lima Refining's receiving water as ECHO-cited", () => {
    const cited = RSEI_DISCHARGERS.filter((d) => d.receivingCited);
    expect(cited).toHaveLength(1);
    expect(cited[0].name).toContain("Lima Refining");
  });
});

describe("toxicsDilution — the assimilative band (UncertainOutcome)", () => {
  it("is an [open] band from summer to a pure-effluent dry floor, central at the cited 93%", () => {
    const o = assimilativeOutcome(EFFLUENT, NATURAL_ANNUAL);
    expect(o.register).toBe("open"); // the actual capacity is unmeasured
    expect(o.high).toBe(100);
    expect(o.low).toBeLessThan(o.central);
    expect(Math.round(o.central)).toBe(93);
    expect(o.resolvingRecord).toMatch(/sampling|DMR/i);
  });
});
