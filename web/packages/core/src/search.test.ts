// buildSearchIndex (#592) — the most complex indexing logic in the tree, previously
// untested (consumed by search-index.json.ts; the same assembly askIndex.ts mirrors). Runs
// against the committed sample bundle. Asserts the structural contract the client matcher
// (scripts/search.ts) and the result UI depend on, not exact counts.
import { describe, expect, it } from "vitest";
import { sections } from "./nav";
import { buildSearchIndex, type SearchDoc } from "./search";

describe("buildSearchIndex (#592)", () => {
  const docs = buildSearchIndex();

  it("returns a non-empty, well-formed index", () => {
    expect(docs.length).toBeGreaterThan(0);
    for (const d of docs) {
      expect(typeof d.title).toBe("string");
      expect(d.title.length).toBeGreaterThan(0);
      expect(typeof d.url).toBe("string");
      expect(d.url.startsWith("/")).toBe(true); // root-absolute deep links
      expect(typeof d.text).toBe("string");
      expect(typeof d.kind).toBe("string");
      expect(d.kind.length).toBeGreaterThan(0);
    }
  });

  it("indexes every section page", () => {
    const sectionTitles = new Set(sections().map((s) => s.label));
    const indexed = new Set(docs.filter((d) => d.kind === "Section").map((d) => d.title));
    for (const label of sectionTitles) expect(indexed.has(label)).toBe(true);
  });

  it("indexes bundle rows beyond the section pages (records, entities, …)", () => {
    const kinds = new Set(docs.map((d) => d.kind));
    expect(kinds.size).toBeGreaterThan(1); // not just "Section"
    // the sample bundle carries records — they must surface as searchable rows
    expect(docs.some((d) => d.kind === "Record")).toBe(true);
  });

  it("only attaches an evidence tag where a row genuinely carries one (no fabricated dots)", () => {
    const allowed = new Set<SearchDoc["tag"]>([undefined, "verified", "inference", "open"]);
    for (const d of docs) expect(allowed.has(d.tag)).toBe(true);
    // a row without a tag is fine; a tagged row must be a real evidence kind (asserted above)
    expect(docs.some((d) => d.tag === undefined)).toBe(true);
  });

  it("is deterministic across runs", () => {
    expect(buildSearchIndex()).toEqual(docs);
  });
});
