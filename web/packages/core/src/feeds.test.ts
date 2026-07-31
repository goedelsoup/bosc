// Shared provenance helpers in `feeds.ts` — the one renderer for a citation's page locator (#1584).

import { describe, expect, it } from "vitest";
import { evidenceKind, formatCitedPages } from "./feeds";

describe("formatCitedPages", () => {
  it("renders one page as `p.` and a span as `pp.`", () => {
    expect(formatCitedPages(17, null)).toBe("p. 17");
    expect(formatCitedPages(17, [17, 18])).toBe("pp. 17-18");
    expect(formatCitedPages(1, [1, 2, 3, 4, 5, 6, 7, 8])).toBe("pp. 1-8");
  });

  it("collapses a non-contiguous read into runs rather than a false range", () => {
    // data/extracted/oepa/2PE00000.npdes.yaml reads 9 pages of one permit in 4 runs; rendering
    // that as "1-93" would claim 84 pages the extraction never opened.
    expect(formatCitedPages(1, [1, 2, 3, 4, 37, 40, 84, 85, 93])).toBe("pp. 1-4, 37, 40, 84-85, 93");
  });

  it("ignores a span that says nothing `page` doesn't, and normalizes a raw feed value", () => {
    expect(formatCitedPages(7, [7])).toBe("p. 7");
    expect(formatCitedPages(7, [8, 7, 7])).toBe("pp. 7-8");
  });

  it("returns null rather than inventing a locator the source never carried", () => {
    expect(formatCitedPages(null, null)).toBeNull();
    expect(formatCitedPages(undefined, [])).toBeNull();
    expect(formatCitedPages(0, [0, -2])).toBeNull();
  });
});

describe("evidenceKind", () => {
  it("keys the badge off the bundle's own derived `verified` flag", () => {
    expect(evidenceKind({ verified: true })).toBe("verified");
    expect(evidenceKind({ verified: false })).toBe("inference");
    expect(evidenceKind(null)).toBe("inference");
  });
});
