import { describe, expect, it } from "vitest";
import { fmtRanged, hasRange } from "./format";

describe("hasRange", () => {
  it("is false with no bounds", () => {
    expect(hasRange({ low: null, high: null })).toBe(false);
    expect(hasRange({})).toBe(false);
  });
  it("is true when either bound is present", () => {
    expect(hasRange({ low: 1, high: null })).toBe(true);
    expect(hasRange({ low: null, high: 2 })).toBe(true);
  });
});

describe("fmtRanged (#760)", () => {
  it("renders a bare value with no band", () => {
    expect(fmtRanged({ value: 226, unit: "acre" })).toBe("226 acre");
  });

  it("renders a symmetric band as ± spread", () => {
    // 226 with ±20% → low 181, high 271: bounds ~equidistant (45 each).
    expect(fmtRanged({ value: 226, low: 181, high: 271, unit: "acre" })).toBe("226 ± ~45 acre");
  });

  it("renders an asymmetric band as a bracket", () => {
    expect(fmtRanged({ value: 250, low: 250, high: 300, unit: "MW" })).toBe("250 (250–300 MW)");
  });

  it("renders a one-sided band as a bracket", () => {
    expect(fmtRanged({ value: 10, high: 12, unit: "MW" })).toBe("10 (10–12 MW)");
  });

  it("returns an em dash for a null value", () => {
    expect(fmtRanged({ value: null })).toBe("—");
  });

  it("honors the decimals argument", () => {
    expect(fmtRanged({ value: 1.234, low: 1.1, high: 1.368, unit: "MGD" }, 2)).toBe("1.23 ± ~0.13 MGD");
  });
});
