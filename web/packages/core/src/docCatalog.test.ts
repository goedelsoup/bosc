import { describe, expect, it } from "vitest";
import {
  type CatalogRow,
  compareDocs,
  type DocData,
  inCatalogScope,
  matchesCatalogRow,
  matchesDoc,
  rowExtraction,
} from "./docCatalog";

const row = (over: Partial<DocData> = {}): DocData => ({
  collection: "Recorder",
  name: "amazon deed 2025.pdf", // glue stores data-name lowercased
  type: "pdf",
  access: "published",
  extraction: "extracted",
  size: "1024",
  ...over,
});

describe("matchesDoc (#725)", () => {
  it("matches everything on an empty query + no filters", () => {
    expect(matchesDoc(row(), "", {})).toBe(true);
  });

  it("searches name and collection case-insensitively", () => {
    expect(matchesDoc(row(), "DEED", {})).toBe(true); // name
    expect(matchesDoc(row(), "recorder", {})).toBe(true); // collection
    expect(matchesDoc(row(), "npdes", {})).toBe(false);
  });

  it("applies column filters as exact matches, ANDed together", () => {
    expect(matchesDoc(row(), "", { type: "pdf" })).toBe(true);
    expect(matchesDoc(row(), "", { type: "image" })).toBe(false);
    expect(matchesDoc(row(), "", { collection: "Recorder", access: "published" })).toBe(true);
    expect(matchesDoc(row(), "", { collection: "Recorder", access: "absent" })).toBe(false);
  });

  it("an empty filter value means 'all' (ignored)", () => {
    expect(matchesDoc(row(), "", { type: "", access: "" })).toBe(true);
  });

  it("filters on extraction status (#1898) — the fifth facet", () => {
    expect(matchesDoc(row(), "", { extraction: "extracted" })).toBe(true);
    expect(matchesDoc(row(), "", { extraction: "catalogued" })).toBe(false);
    const unread = row({ extraction: "catalogued" });
    expect(matchesDoc(unread, "", { extraction: "catalogued" })).toBe(true);
    expect(matchesDoc(unread, "", { extraction: "extracted" })).toBe(false);
    // ANDed with the rest, like every other column.
    expect(matchesDoc(row(), "deed", { extraction: "extracted", type: "pdf" })).toBe(true);
    expect(matchesDoc(row(), "deed", { extraction: "extracted", type: "image" })).toBe(false);
  });

  it("combines text and filters", () => {
    expect(matchesDoc(row(), "deed", { type: "pdf" })).toBe(true);
    expect(matchesDoc(row(), "deed", { type: "image" })).toBe(false);
  });
});

describe("compareDocs (#725)", () => {
  it("sorts text columns lexically", () => {
    const a = row({ name: "a.pdf" });
    const b = row({ name: "b.pdf" });
    expect(compareDocs(a, b, "name", false)).toBeLessThan(0);
    expect(compareDocs(b, a, "name", false)).toBeGreaterThan(0);
  });

  it("sorts size numerically, not lexically", () => {
    const small = row({ size: "9" });
    const big = row({ size: "1024" });
    // numeric: 9 < 1024
    expect(compareDocs(small, big, "size", true)).toBeLessThan(0);
    // lexical would wrongly put "1024" before "9"
    expect(compareDocs(small, big, "size", false)).toBeGreaterThan(0);
  });

  it("treats a missing key as empty", () => {
    expect(compareDocs(row(), row(), "missing", false)).toBe(0);
  });
});

// The whole-listing half (#1887) — what a facet means on a production the current page shows one
// seventh of. This is the path the acceptance criterion rides on: filtering must reach every row
// of the listing, not the 150 the SSR page happens to carry.
const catRow = (over: Partial<CatalogRow> = {}): CatalogRow => ({
  n: "WPCLF Application.pdf",
  c: "legal",
  k: "prr-mandamus",
  f: "prr-production-2026-07-24-sanitary/11",
  t: "pdf",
  a: "dev-only",
  s: 1555723,
  x: "",
  e: 1,
  r: "finance/legal-prr-mandamus-hume-road-wpclf-award-yaml/",
  ...over,
});

describe("inCatalogScope (#1887)", () => {
  const scope = { collection: "legal", container: "prr-mandamus", looseOnly: false };

  it("keeps a container landing to its own container", () => {
    expect(inCatalogScope(catRow(), scope)).toBe(true);
    expect(inCatalogScope(catRow({ k: "web-vendor-audit" }), scope)).toBe(false);
    expect(inCatalogScope(catRow({ c: "permits", k: "prr-mandamus" }), scope)).toBe(false);
  });

  it("takes the whole collection when no container is named", () => {
    const whole = { collection: "legal", container: "", looseOnly: false };
    expect(inCatalogScope(catRow(), whole)).toBe(true);
    expect(inCatalogScope(catRow({ k: "" }), whole)).toBe(true);
  });

  it("`looseOnly` keeps the 'outside a production' table from widening to the collection", () => {
    const loose = { collection: "legal", container: "", looseOnly: true };
    expect(inCatalogScope(catRow(), loose)).toBe(false);
    expect(inCatalogScope(catRow({ k: "" }), loose)).toBe(true);
  });
});

describe("rowExtraction / matchesCatalogRow (#1898)", () => {
  it("reads an absent `e` as catalogued, never as a defined zero", () => {
    expect(rowExtraction(catRow())).toBe("extracted");
    expect(rowExtraction(catRow({ e: 2 }))).toBe("extracted");
    expect(rowExtraction(catRow({ e: undefined, r: undefined }))).toBe("catalogued");
  });

  it("filters the whole listing on extraction status", () => {
    const read = catRow();
    const unread = catRow({ n: "minutes.pdf", e: undefined, r: undefined });
    expect(matchesCatalogRow(read, "", { extraction: "extracted" })).toBe(true);
    expect(matchesCatalogRow(read, "", { extraction: "catalogued" })).toBe(false);
    expect(matchesCatalogRow(unread, "", { extraction: "catalogued" })).toBe(true);
    expect(matchesCatalogRow(unread, "", { extraction: "extracted" })).toBe(false);
  });

  it("ANDs extraction with the other facets and the search box", () => {
    const read = catRow();
    expect(matchesCatalogRow(read, "wpclf", { extraction: "extracted", type: "pdf" })).toBe(true);
    expect(matchesCatalogRow(read, "wpclf", { extraction: "extracted", type: "image" })).toBe(false);
    expect(matchesCatalogRow(read, "nothing", { extraction: "extracted" })).toBe(false);
    expect(matchesCatalogRow(read, "", { extraction: "extracted", access: "published" })).toBe(false);
  });

  it("matches the file name only — the collection is already the scope", () => {
    expect(matchesCatalogRow(catRow(), "APPLICATION", {})).toBe(true);
    expect(matchesCatalogRow(catRow(), "legal", {})).toBe(false);
  });

  it("selects a folder's whole subtree, not just its direct files", () => {
    const r = catRow();
    expect(matchesCatalogRow(r, "", {}, "prr-production-2026-07-24-sanitary")).toBe(true);
    expect(matchesCatalogRow(r, "", {}, "prr-production-2026-07-24-sanitary/11")).toBe(true);
    // A sibling branch, and a prefix that isn't a path boundary, must both miss.
    expect(matchesCatalogRow(r, "", {}, "prr-production-2026-07-24-sanitary/12")).toBe(false);
    expect(matchesCatalogRow(r, "", {}, "prr-production-2026-07-24-sanit")).toBe(false);
  });

  it("an empty query, filter or folder means 'all'", () => {
    expect(matchesCatalogRow(catRow(), "  ", { type: "", extraction: "" }, "")).toBe(true);
  });
});
