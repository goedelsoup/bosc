import { describe, expect, it } from "vitest";
import { hasFeed, loadFeed } from "./bundle";
import { publishedRels, publishedRelsFrom } from "./docGate";
import type { DocumentCollectionItem, DocumentEntry } from "./feeds";
import { exportedSiteSlugs, SITES } from "./sites";

function entry(rel: string, published: boolean): DocumentEntry {
  return {
    rel,
    name: rel.split("/").pop() ?? rel,
    size_bytes: 1,
    suffix: "pdf",
    media_type: "application/pdf",
    render_class: "pdf",
    published,
    available: true,
  };
}

function feed(...entries: DocumentEntry[]): DocumentCollectionItem[] {
  return [{ slug: "oepa", title: "Ohio EPA", entries }];
}

describe("publishedRelsFrom", () => {
  it("admits only published entries", () => {
    const read = () => feed(entry("oepa/a.pdf", true), entry("oepa/b.pdf", false));
    expect(publishedRelsFrom(["lima"], read)).toEqual(["oepa/a.pdf"]);
  });

  it("unions across sites — the #2149 regression", () => {
    // The bug in one assertion: reading ONE site's feed (Lima) admits only Lima's set, and every
    // other site's published documents 404 at the gate before R2 is ever asked.
    const feeds: Record<string, DocumentCollectionItem[]> = {
      lima: feed(entry("oepa/lima.pdf", true)),
      findlay: feed(entry("findlay/wwtp.pdf", true)),
      "bowling-green": feed(entry("bowling-green/commissioners/10032023.pdf", true)),
    };
    const read = (slug: string) => feeds[slug] ?? null;

    expect(publishedRelsFrom(["lima"], read)).toEqual(["oepa/lima.pdf"]);
    expect(publishedRelsFrom(["lima", "findlay", "bowling-green"], read)).toEqual([
      "bowling-green/commissioners/10032023.pdf",
      "findlay/wwtp.pdf",
      "oepa/lima.pdf",
    ]);
  });

  it("de-duplicates a rel two sites both publish, and sorts for a byte-stable asset", () => {
    const shared = "oepa/OHD000001_Draft.pdf";
    const feeds: Record<string, DocumentCollectionItem[]> = {
      zeta: feed(entry("zeta/z.pdf", true), entry(shared, true)),
      alpha: feed(entry(shared, true), entry("alpha/a.pdf", true)),
    };
    const rels = publishedRelsFrom(["zeta", "alpha"], (s) => feeds[s] ?? null);
    expect(rels).toEqual(["alpha/a.pdf", shared, "zeta/z.pdf"]);
    // Site order must not reshuffle the asset: a promotion would otherwise rewrite the whole file.
    expect(publishedRelsFrom(["alpha", "zeta"], (s) => feeds[s] ?? null)).toEqual(rels);
  });

  it("skips a site with no documents feed rather than throwing", () => {
    const read = (slug: string) => (slug === "lima" ? feed(entry("oepa/a.pdf", true)) : null);
    expect(publishedRelsFrom(["lima", "fort-wayne"], read)).toEqual(["oepa/a.pdf"]);
  });

  it("admits nothing when no site is exported — default-deny, not an open gate", () => {
    expect(publishedRelsFrom([], () => feed(entry("oepa/a.pdf", true)))).toEqual([]);
  });
});

describe("exportedSiteSlugs", () => {
  it("is exactly the selectable sites — the bundles the build actually writes", () => {
    expect([...exportedSiteSlugs()]).toEqual(SITES.filter((s) => s.selectable).map((s) => s.slug));
  });

  it("carries more than one site, so the gate union is not vacuous", () => {
    // If this ever falls to 1 the union above stops being exercised by the real registry.
    expect(exportedSiteSlugs().length).toBeGreaterThan(1);
  });
});

describe("publishedRels, against the committed bundles", () => {
  const rels = new Set(publishedRels());
  const lima = new Set(
    publishedRelsFrom(["lima"], (slug) =>
      hasFeed("documents", slug) ? loadFeed<DocumentCollectionItem[]>("documents", slug) : null,
    ),
  );

  it("reaches past Lima — the gate the deployed build shipped was Lima's set alone", () => {
    // Not an exact count: the allowlist's cleared scope grows, and pinning a number here would
    // make every clearance a test edit. What must hold is that the union is STRICTLY larger.
    expect(rels.size).toBeGreaterThan(lima.size);
    for (const rel of lima) expect(rels.has(rel)).toBe(true);
  });

  it("admits documents from every exported site that publishes any", () => {
    // The regression in the form a reader hits it: a site whose documents render as available
    // downloads while the gate has never heard of them.
    const missing: string[] = [];
    for (const slug of exportedSiteSlugs()) {
      const own = publishedRelsFrom([slug], (s) =>
        hasFeed("documents", s) ? loadFeed<DocumentCollectionItem[]>("documents", s) : null,
      );
      if (own.length > 0 && !own.some((r) => rels.has(r))) missing.push(slug);
    }
    expect(missing).toEqual([]);
  });

  it("still withholds what the allowlist carves out (#2031, #1267)", () => {
    // Two files are cleared by their collection and withheld by name, both for aggregated
    // personal contact details. The union must not launder a withhold into a publish.
    expect(rels.has("van-wert/council/5.11.26.pdf")).toBe(false);
    expect(rels.has("findlay/reference/2026 Directory of Officials_202604131412522342.pdf")).toBe(false);
  });
});
