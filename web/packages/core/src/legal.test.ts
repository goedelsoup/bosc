import { describe, expect, it } from "vitest";
import { LEGAL, hasLegalDoc, legalOwner, scopedLegal } from "./legal";

// The legal-history facet was the one record surface with no bundle feed between it and the
// corpus, so nothing scoped it: Fort Wayne (Indiana) and Urbana each served all fifteen of Lima's
// Allen-County-OH pages, byte-identical, an Ohio legislative hearing among them (#1886).
// `scopedLegal` is the missing seam — the peer of `scopedReference` (#1260).

describe("scopedLegal", () => {
  it("keeps the whole published set on the build whose corpus it came from", () => {
    expect(scopedLegal("lima")).toHaveLength(LEGAL.length);
  });

  it("gives a peer NONE of the reference build's filings", () => {
    for (const peer of ["fort-wayne", "urbana", "troy-piqua"]) {
      expect(scopedLegal(peer)).toEqual([]);
    }
  });

  it("names the specific leaks the issue found", () => {
    const fw = new Set(scopedLegal("fort-wayne").map((d) => d.slug));
    // An Ohio Select-Committee hearing under an Indiana watershed point.
    expect(fw.has("hearing-am")).toBe(false);
    // Allen-County-OH public-records artifacts read as if they were the peer's own.
    expect(fw.has("withholding-map")).toBe(false);
    expect(fw.has("corpus-completeness-audit")).toBe(false);
  });

  it("partitions the set — every doc belongs to exactly one site", () => {
    const owners = new Set(LEGAL.map(legalOwner));
    const total = [...owners].reduce((n, slug) => n + scopedLegal(slug).length, 0);
    expect(total).toBe(LEGAL.length);
  });
});

describe("hasLegalDoc", () => {
  it("guards a deep link into the facet — true only for the owning site", () => {
    // The hydrology page cross-links the water-balance memo; on a peer that link would 404 into
    // the reference build's record, so the page asks first.
    expect(hasLegalDoc("lima", "water-balance-screen")).toBe(true);
    expect(hasLegalDoc("fort-wayne", "water-balance-screen")).toBe(false);
  });

  it("is false for a slug that isn't published at all", () => {
    expect(hasLegalDoc("lima", "not-a-published-doc")).toBe(false);
  });
});
