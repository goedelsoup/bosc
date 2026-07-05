import { describe, expect, it } from "vitest";
import {
  bilinear,
  cellValue,
  contourLevels,
  type FieldGrid,
  gridFromSamples,
  gridToWorld,
  marchingSquares,
  mix,
  normalize,
  rampAt,
  segmentToWorld,
  valueExtent,
} from "./field";

/** 2×2 unit cell: row 0 (north) = [0, 10], row 1 (south) = [20, 30]. */
const cell: FieldGrid = { width: 2, height: 2, values: [0, 10, 20, 30] };

describe("bilinear", () => {
  it("returns exact corner values", () => {
    expect(bilinear(cell, 0, 0)).toBe(0);
    expect(bilinear(cell, 1, 0)).toBe(10);
    expect(bilinear(cell, 0, 1)).toBe(20);
    expect(bilinear(cell, 1, 1)).toBe(30);
  });

  it("averages at the cell center", () => {
    expect(bilinear(cell, 0.5, 0.5)).toBeCloseTo(15);
  });

  it("interpolates along an edge", () => {
    expect(bilinear(cell, 0.5, 0)).toBeCloseTo(5); // between 0 and 10
    expect(bilinear(cell, 0, 0.5)).toBeCloseTo(10); // between 0 and 20
  });

  it("clamps out-of-range coordinates to the edge", () => {
    expect(bilinear(cell, -5, -5)).toBe(0);
    expect(bilinear(cell, 9, 9)).toBe(30);
  });

  it("returns NaN when a contributing corner is no-data", () => {
    const holed: FieldGrid = { width: 2, height: 2, values: [0, Number.NaN, 20, 30] };
    expect(Number.isNaN(bilinear(holed, 0.5, 0.5))).toBe(true);
    // A query wholly on the good corner still clamps onto the NaN cell's footprint,
    // so any interior sample is NaN — but the exact good corner is finite.
    expect(bilinear(holed, 0, 1)).toBe(20);
  });
});

describe("cellValue", () => {
  it("clamps integer indices to the grid", () => {
    expect(cellValue(cell, -1, -1)).toBe(0);
    expect(cellValue(cell, 5, 5)).toBe(30);
  });
});

describe("valueExtent / normalize", () => {
  it("ignores NaN samples", () => {
    const g: FieldGrid = { width: 2, height: 2, values: [5, Number.NaN, Number.NaN, 25] };
    expect(valueExtent(g)).toEqual([5, 25]);
  });

  it("returns [0,0] for an all-empty grid", () => {
    expect(valueExtent({ width: 1, height: 1, values: [Number.NaN] })).toEqual([0, 0]);
  });

  it("normalizes and clamps", () => {
    expect(normalize(15, 0, 30)).toBeCloseTo(0.5);
    expect(normalize(-5, 0, 30)).toBe(0);
    expect(normalize(99, 0, 30)).toBe(1);
    expect(normalize(5, 10, 10)).toBe(0); // zero-width range
  });
});

describe("colormap", () => {
  const low: [number, number, number] = [0, 0, 0];
  const mid: [number, number, number] = [100, 100, 100];
  const high: [number, number, number] = [200, 200, 200];

  it("mixes component-wise", () => {
    expect(mix(low, high, 0.5)).toEqual([100, 100, 100]);
  });

  it("hits the ramp endpoints and knot", () => {
    expect(rampAt(0, low, mid, high)).toEqual(low);
    expect(rampAt(0.5, low, mid, high)).toEqual(mid);
    expect(rampAt(1, low, mid, high)).toEqual(high);
  });

  it("interpolates within each ramp half", () => {
    expect(rampAt(0.25, low, mid, high)).toEqual([50, 50, 50]);
    expect(rampAt(0.75, low, mid, high)).toEqual([150, 150, 150]);
  });

  it("clamps out-of-range t", () => {
    expect(rampAt(-1, low, mid, high)).toEqual(low);
    expect(rampAt(2, low, mid, high)).toEqual(high);
  });
});

describe("marchingSquares", () => {
  it("draws a horizontal isoline through a vertical gradient", () => {
    // row 0 = [0, 0], row 1 = [2, 2]; level 1 crosses both vertical edges at row 0.5.
    const g: FieldGrid = { width: 2, height: 2, values: [0, 0, 2, 2] };
    const segs = marchingSquares(g, 1);
    expect(segs).toHaveLength(1);
    const [p, q] = segs[0];
    // Endpoints are the left and right edge crossings at mid-height, in some order.
    const pts = [p, q].sort((m, n) => m[0] - n[0]);
    expect(pts[0][0]).toBeCloseTo(0);
    expect(pts[0][1]).toBeCloseTo(0.5);
    expect(pts[1][0]).toBeCloseTo(1);
    expect(pts[1][1]).toBeCloseTo(0.5);
  });

  it("returns nothing when the whole grid is below the level", () => {
    expect(marchingSquares(cell, 100)).toEqual([]);
  });

  it("returns nothing when the whole grid is above the level", () => {
    expect(marchingSquares(cell, -100)).toEqual([]);
  });

  it("skips cells that touch a no-data corner", () => {
    const g: FieldGrid = { width: 2, height: 2, values: [0, 0, 2, Number.NaN] };
    expect(marchingSquares(g, 1)).toEqual([]);
  });

  it("emits two segments for a saddle", () => {
    // Diagonal high corners, low off-diagonal → index 10, a saddle.
    const g: FieldGrid = { width: 2, height: 2, values: [2, 0, 0, 2] };
    expect(marchingSquares(g, 1)).toHaveLength(2);
  });
});

describe("contourLevels", () => {
  it("spaces interior levels, excluding the endpoints", () => {
    expect(contourLevels(0, 4, 3)).toEqual([1, 2, 3]);
  });

  it("returns [] for a degenerate range or non-positive count", () => {
    expect(contourLevels(5, 5, 3)).toEqual([]);
    expect(contourLevels(0, 4, 0)).toEqual([]);
  });
});

describe("gridToWorld / segmentToWorld", () => {
  it("returns grid coordinates when there is no geo-reference", () => {
    expect(gridToWorld(cell, 0.5, 1)).toEqual([0.5, 1]);
  });

  it("maps to lng/lat with row 0 at the north edge", () => {
    const geo: FieldGrid = { ...cell, bounds: [-84, 40, -83, 41] };
    expect(gridToWorld(geo, 0, 0)).toEqual([-84, 41]); // NW corner
    expect(gridToWorld(geo, 1, 1)).toEqual([-83, 40]); // SE corner
    expect(gridToWorld(geo, 0.5, 0.5)).toEqual([-83.5, 40.5]); // center
  });

  it("projects a segment's endpoints", () => {
    const geo: FieldGrid = { ...cell, bounds: [-84, 40, -83, 41] };
    expect(
      segmentToWorld(geo, [
        [0, 0],
        [1, 1],
      ]),
    ).toEqual([
      [-84, 41],
      [-83, 40],
    ]);
  });
});

describe("gridFromSamples", () => {
  it("assembles a regular lattice with north-up rows and west-left columns", () => {
    const g = gridFromSamples([
      { x: -84, y: 41, value: 1 }, // NW
      { x: -83, y: 41, value: 2 }, // NE
      { x: -84, y: 40, value: 3 }, // SW
      { x: -83, y: 40, value: 4 }, // SE
    ]);
    expect(g.width).toBe(2);
    expect(g.height).toBe(2);
    expect(Array.from(g.values)).toEqual([1, 2, 3, 4]);
    expect(g.bounds).toEqual([-84, 40, -83, 41]);
  });

  it("returns an empty grid for no samples", () => {
    expect(gridFromSamples([])).toEqual({ width: 0, height: 0, values: [] });
  });

  it("throws when the samples are not a regular lattice", () => {
    expect(() =>
      gridFromSamples([
        { x: 0, y: 0, value: 1 },
        { x: 1, y: 0, value: 2 },
        { x: 0, y: 1, value: 3 },
      ]),
    ).toThrow(/regular/);
  });
});
