import { describe, expect, it } from "vitest";
import { compareDocs, matchesDoc, type DocData } from "./docCatalog";

const row = (over: Partial<DocData> = {}): DocData => ({
  collection: "Recorder",
  name: "amazon deed 2025.pdf", // glue stores data-name lowercased
  type: "pdf",
  access: "published",
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
