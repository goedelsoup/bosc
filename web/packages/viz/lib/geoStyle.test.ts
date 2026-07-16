import { describe, expect, it } from "vitest";
import { DEFAULT_OFF, hexToRgb, layerLabel, layersPresent, rgba, type GeoFeature } from "./geoStyle";

const FALLBACK: [number, number, number] = [120, 120, 130];

const feat = (layer: string): GeoFeature => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: [0, 0] },
  properties: { layer },
});

describe("hexToRgb", () => {
  it("parses a 6-char hex", () => {
    expect(hexToRgb("#3f51b5")).toEqual([63, 81, 181]);
    expect(hexToRgb("ffffff")).toEqual([255, 255, 255]);
    expect(hexToRgb("#000000")).toEqual([0, 0, 0]);
  });

  it("expands a 3-char shorthand", () => {
    expect(hexToRgb("#fff")).toEqual([255, 255, 255]);
    expect(hexToRgb("#abc")).toEqual([0xaa, 0xbb, 0xcc]);
  });

  it("falls back to slate grey for undefined / empty / malformed input", () => {
    expect(hexToRgb(undefined)).toEqual(FALLBACK);
    expect(hexToRgb("")).toEqual(FALLBACK);
    expect(hexToRgb("#xyzxyz")).toEqual(FALLBACK); // NaN
    expect(hexToRgb("#12345")).toEqual(FALLBACK); // wrong length (not 3 or 6)
    expect(hexToRgb("#1234567")).toEqual(FALLBACK);
  });

  it("tolerates surrounding whitespace and a missing #", () => {
    expect(hexToRgb("  #3f51b5  ")).toEqual([63, 81, 181]);
  });
});

describe("rgba", () => {
  it("appends the alpha to the parsed colour", () => {
    expect(rgba("#3f51b5", 210)).toEqual([63, 81, 181, 210]);
  });
  it("uses the fallback colour but keeps the requested alpha", () => {
    expect(rgba(undefined, 22)).toEqual([120, 120, 130, 22]);
  });
});

describe("layerLabel", () => {
  it("maps known layers to friendly names", () => {
    expect(layerLabel("rsei")).toBe("RSEI facilities");
  });
  it("passes an unknown layer through unchanged", () => {
    expect(layerLabel("mystery")).toBe("mystery");
  });
});

describe("layersPresent", () => {
  it("returns distinct layers in canonical draw order regardless of input order", () => {
    const features = [feat("roadwork"), feat("watershed"), feat("campus"), feat("roadwork")];
    expect(layersPresent(features)).toEqual(["watershed", "campus", "roadwork"]);
  });

  it("appends unknown layers after the canonical ones, first-seen", () => {
    const features = [feat("zeta"), feat("campus"), feat("alpha")];
    expect(layersPresent(features)).toEqual(["campus", "zeta", "alpha"]);
  });

  it("is empty for no features", () => {
    expect(layersPresent([])).toEqual([]);
  });
});

describe("DEFAULT_OFF", () => {
  it("hides the heavy RSEI overlay by default, nothing else", () => {
    expect(DEFAULT_OFF.has("rsei")).toBe(true);
    expect(DEFAULT_OFF.has("corridor")).toBe(false);
  });
});
