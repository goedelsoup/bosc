import { describe, expect, it } from "vitest";
import {
  cumulativeLengths,
  type FlowReach,
  normalizeMagnitude,
  particleCount,
  pathLength,
  pointAtFraction,
  resamplePath,
} from "./flow";

/** A unit-length horizontal path made of two equal segments. */
const line: [number, number][] = [
  [0, 0],
  [1, 0],
  [2, 0],
];

describe("cumulativeLengths / pathLength", () => {
  it("accumulates segment lengths from zero", () => {
    expect(cumulativeLengths(line)).toEqual([0, 1, 2]);
    expect(pathLength(line)).toBe(2);
  });
  it("is zero for a degenerate path", () => {
    expect(pathLength([[0, 0]])).toBe(0);
    expect(pathLength([])).toBe(0);
  });
});

describe("pointAtFraction", () => {
  it("returns the endpoints at 0 and 1", () => {
    expect(pointAtFraction(line, 0)).toEqual([0, 0]);
    expect(pointAtFraction(line, 1)).toEqual([2, 0]);
  });
  it("interpolates by arc length, not vertex index", () => {
    expect(pointAtFraction(line, 0.5)).toEqual([1, 0]); // midpoint of total length
    expect(pointAtFraction(line, 0.25)[0]).toBeCloseTo(0.5);
  });
  it("clamps out-of-range fractions", () => {
    expect(pointAtFraction(line, -1)).toEqual([0, 0]);
    expect(pointAtFraction(line, 2)).toEqual([2, 0]);
  });
});

describe("resamplePath", () => {
  it("returns exactly k evenly spaced vertices", () => {
    const r = resamplePath(line, 5);
    expect(r).toHaveLength(5);
    expect(r[0]).toEqual([0, 0]);
    expect(r[4]).toEqual([2, 0]);
    // even arc-length spacing → x = 0, 0.5, 1, 1.5, 2
    expect(r.map((p) => p[0])).toEqual([0, 0.5, 1, 1.5, 2]);
  });
  it("pads a degenerate path to a single point without throwing", () => {
    expect(resamplePath([[3, 4]], 4)).toHaveLength(4);
    expect(resamplePath([[3, 4]], 4).every((p) => p[0] === 3 && p[1] === 4)).toBe(true);
  });
});

describe("particleCount", () => {
  const reach = (over: Partial<FlowReach>): FlowReach => ({
    id: "r",
    path: line,
    speed: 0.5,
    density: 1,
    deficit: false,
    ...over,
  });
  it("scales with density", () => {
    expect(particleCount(reach({ density: 1 }), 30)).toBe(30);
    expect(particleCount(reach({ density: 0.5 }), 30)).toBe(15);
  });
  it("thins deficit reaches to a third but never below the floor", () => {
    expect(particleCount(reach({ density: 1, deficit: true }), 30)).toBe(10);
    expect(particleCount(reach({ density: 0, deficit: true }), 30)).toBe(2); // min floor
  });
});

describe("normalizeMagnitude", () => {
  it("maps value/max into [floor, 1]", () => {
    expect(normalizeMagnitude(5, 10)).toBeCloseTo(0.5);
    expect(normalizeMagnitude(100, 10)).toBe(1);
    expect(normalizeMagnitude(0, 10, 0.15)).toBe(0.15);
  });
  it("falls back to the floor on a bad max", () => {
    expect(normalizeMagnitude(5, 0, 0.2)).toBe(0.2);
    expect(normalizeMagnitude(Number.NaN, 10, 0.2)).toBe(0.2);
  });
});
