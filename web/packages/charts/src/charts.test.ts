import { describe, expect, it } from "vitest";
import {
  buildBullet,
  buildDonut,
  buildHBars,
  buildLine,
  buildSparkline,
  buildStacked,
  buildVBars,
  buildWaterfall,
  EVIDENCE_FILL,
  fmtChartVal,
  FOREST,
  niceMax,
  scalePct,
  WITHHELD_FILL,
} from "./charts";

describe("charts geometry (#306)", () => {
  it("niceMax returns a nice ceiling at or above the value", () => {
    expect(niceMax(31)).toBeGreaterThanOrEqual(31);
    expect(niceMax(8)).toBeGreaterThanOrEqual(8);
    expect(niceMax(0)).toBe(1);
    expect([10, 20, 25, 50, 100]).toContain(niceMax(31));
  });

  it("shared plot frame: VBars and Line expose the same axis extent the axed components read", () => {
    const v = buildVBars([{ label: "a", value: 1 }]);
    const l = buildLine([
      { label: "a", value: 1 },
      { label: "b", value: 2 },
    ]);
    // left edge + x-label baseline are shared; right edge matches each chart's W − R.
    expect(v.plot.left).toBe(34);
    expect(l.plot.left).toBe(34);
    expect(v.plot.labelY).toBe(188);
    expect(l.plot.labelY).toBe(188);
    // grid/baseline span exactly the plot extent (no hardcoded 348/346 drift).
    expect(v.plot.right).toBe(348);
    expect(l.plot.right).toBe(346);
    // ref lines plot within the same frame they're drawn against.
    expect(l.plot.right).toBeGreaterThan(l.plot.left);
  });

  it("scalePct: percentage of a ceiling, 1 dp, optional clamp", () => {
    expect(scalePct(25, 100)).toBe(25);
    expect(scalePct(1, 3)).toBe(33.3);
    expect(scalePct(0, 0)).toBe(0); // zero ceiling → 0, never NaN
    expect(scalePct(150, 100)).toBe(150); // unclamped overflows past 100
    expect(scalePct(150, 100, true)).toBe(100); // clamped pins to the track
    expect(scalePct(-5, 100, true)).toBe(0);
  });

  it("fmtChartVal: integers bare, fractions to 2 dp, thousands grouped", () => {
    expect(fmtChartVal(42)).toBe("42");
    expect(fmtChartVal(0.2)).toBe("0.2");
    expect(fmtChartVal(3.456)).toBe("3.46");
    expect(fmtChartVal(1234)).toBe("1,234");
    expect(fmtChartVal(1234.5)).toBe("1,234.5");
  });

  it("vertical bars: one bar per datum, peak highlighted in forest, within the plot", () => {
    const c = buildVBars([
      { label: "a", value: 6 },
      { label: "b", value: 31 },
      { label: "c", value: 13 },
    ]);
    expect(c.bars).toHaveLength(3);
    const peak = c.bars.filter((b) => b.peak);
    expect(peak).toHaveLength(1);
    expect(peak[0].value).toBe(31);
    expect(peak[0].fill).toBe(FOREST);
    for (const b of c.bars) expect(b.y + b.h).toBeCloseTo(c.baselineY, 1); // bars sit on the baseline
    expect(c.grid).toHaveLength(5);
  });

  it("horizontal bars: withheld bars get the soft fill + value labels carry the unit", () => {
    const c = buildHBars(
      [
        { label: "P2", value: 92 },
        { label: "P1", value: 5, withheld: true },
      ],
      { unit: "ac" },
    );
    expect(c.bars).toHaveLength(2);
    expect(c.bars[1].fill).toBe(WITHHELD_FILL);
    expect(c.bars[0].fill).toBe(FOREST);
    expect(c.bars[0].valLabel).toBe("92 ac");
  });

  it("line: a single polyline, a closed area, dots per point, last anchored", () => {
    const c = buildLine([
      { label: "a", value: 5 },
      { label: "b", value: 60 },
      { label: "c", value: 340 },
    ]);
    expect(c.line.startsWith("M")).toBe(true);
    expect(c.area.endsWith("Z")).toBe(true);
    expect(c.dots).toHaveLength(3);
    expect(c.last).toEqual({ x: c.dots[2].x, y: c.dots[2].y });
  });

  it("line: reference lines plot at the value's y, default to the 5·3 dash, clamp to max", () => {
    const c = buildLine(
      [
        { label: "a", value: 0 },
        { label: "b", value: 100 },
      ],
      {
        max: 100,
        refs: [
          { value: 100, label: "cap", color: "#7a2230" },
          { value: 50, label: "draw", color: "#9a6a14", dash: "4 3" },
          { value: 500, label: "over", color: "#1f6f4a" },
        ],
      },
    );
    expect(c.refLines).toHaveLength(3);
    // value === max → the top of the plot band (the line for value 100).
    expect(c.refLines[0].y).toBe(c.grid[c.grid.length - 1].y);
    expect(c.refLines[0].dash).toBe("5 3");
    expect(c.refLines[1].dash).toBe("4 3");
    // value > max clamps to the ceiling (never above the plot).
    expect(c.refLines[2].y).toBe(c.refLines[0].y);
  });

  it("bullet: ratio is measure÷limit, percentages on the shared scale", () => {
    const c = buildBullet(4.85, 0.2);
    expect(c.ratio).toBe(24.25);
    expect(c.measurePct).toBeGreaterThan(c.limitPct);
    expect(c.measurePct).toBeLessThanOrEqual(100);
  });

  it("stacked: evidence-colored segments whose widths fill the bar and sum to 100%", () => {
    const c = buildStacked([
      { label: "verified", value: 196, kind: "verified" },
      { label: "inference", value: 78, kind: "inference" },
      { label: "open", value: 44, kind: "open" },
    ]);
    expect(c.total).toBe(318);
    expect(c.segments[0].fill).toBe(EVIDENCE_FILL.verified);
    expect(c.segments[2].fill).toBe(EVIDENCE_FILL.open);
    const sumW = c.segments.reduce((s, g) => s + g.w, 0);
    expect(sumW).toBeCloseTo(354, 0); // the bar inner width
    expect(c.segments.reduce((s, g) => s + g.pct, 0)).toBeCloseTo(100, 0);
  });

  it("donut: one arc per slice, forest tints, total summed", () => {
    const c = buildDonut([
      { label: "a", value: 96 },
      { label: "b", value: 78 },
      { label: "c", value: 34 },
    ]);
    expect(c.segments).toHaveLength(3);
    expect(c.total).toBe(208);
    for (const s of c.segments) expect(s.d.startsWith("M")).toBe(true);
  });

  it("sparkline: a polyline ending at the last point's dot", () => {
    const c = buildSparkline([2, 3, 5, 4, 9, 14]);
    expect(c.path.startsWith("M")).toBe(true);
    expect(c.dot.x).toBeGreaterThan(0);
  });

  it("waterfall: base + result run from the baseline, the down delta floats with real height", () => {
    const c = buildWaterfall([
      { label: "intake", value: 7, kind: "base" },
      { label: "returned", value: 2.15, kind: "down" },
      { label: "consumed", value: 4.85, kind: "result" },
    ]);
    expect(c.bars).toHaveLength(3);
    // base + result are full bars from zero → their bottom sits on the baseline
    expect(c.bars[0].y + c.bars[0].h).toBeCloseTo(c.baselineY, 0);
    expect(c.bars[2].y + c.bars[2].h).toBeCloseTo(c.baselineY, 0);
    // the "down" (returned) band floats above the baseline, spanning 4.85→7, with real height
    expect(c.bars[1].y + c.bars[1].h).toBeLessThan(c.baselineY);
    expect(c.bars[1].h).toBeGreaterThan(1);
    expect(c.bars[1].label).toBe("−2.15");
    // connectors run from each bar to the next, except the last
    expect(c.bars[0].connectorX2).not.toBeNull();
    expect(c.bars[2].connectorX2).toBeNull();
  });
});
