// The search index (#592, re-shaped by #1890) — the most complex indexing logic in the tree.
// Runs against the committed `sites/` bundles.
//
// #1890 split one Lima-only index into a network-global shard plus one shard per selectable site.
// The assertions below are the properties that split exists to buy, in the shape #1886 established
// for the record facets: a site's shard holds that site's record and nothing else, a locked facet
// contributes nothing, and no two sites serve the same row. Structural contracts the client matcher
// (`scripts/searchEngine.ts`) depends on are asserted; exact counts are not.
import { describe, expect, it } from "vitest";
import { hasFeed, loadFeed, runWithSite } from "./bundle";
import { isRoutableDoc } from "./docRouting";
import { isDocumentId } from "./documentId";
import type { DocumentCollectionItem } from "./feeds";
import { sections } from "./nav";
import { facetAvailable } from "./readiness";
import { siteBase } from "./routes";
import { buildNetworkSearchIndex, buildSiteSearchIndex, searchShardRefs, type SearchDoc } from "./search";
import { SITES } from "./sites";

const SELECTABLE = SITES.filter((s) => s.selectable).map((s) => s.slug);

/** Every row of every shard, as the client sees it under network scope. */
function wholeIndex(): SearchDoc[] {
  return [...buildNetworkSearchIndex(), ...SELECTABLE.flatMap((slug) => buildSiteSearchIndex(slug))];
}

function wellFormed(docs: SearchDoc[]): void {
  for (const d of docs) {
    expect(typeof d.title).toBe("string");
    expect(d.title.length).toBeGreaterThan(0);
    expect(typeof d.url).toBe("string");
    expect(d.url.startsWith("/")).toBe(true); // root-absolute deep links
    expect(typeof d.text).toBe("string");
    expect(typeof d.kind).toBe("string");
    expect(d.kind.length).toBeGreaterThan(0);
  }
}

/** Whether `url` addresses something under `base` — the site landing itself, an anchor on it, or
 *  any page beneath it. (The Home section's TOC rows are `base#anchor`, hence the third case.) */
function underSite(url: string, base: string): boolean {
  return url === base || url.startsWith(`${base}/`) || url.startsWith(`${base}#`);
}

/** Documents the reference build's corpus catalogs, split by whether they get a page. */
function limaEntries(): { routable: number; nonRoutable: number } {
  return runWithSite("lima", () => {
    const entries = loadFeed<DocumentCollectionItem[]>("documents").flatMap((c) => c.entries);
    return {
      routable: entries.filter((e) => isRoutableDoc(e)).length,
      nonRoutable: entries.filter((e) => !isRoutableDoc(e)).length,
    };
  });
}

describe("the network-global shard", () => {
  const docs = buildNetworkSearchIndex();

  it("returns a non-empty, well-formed index", () => {
    expect(docs.length).toBeGreaterThan(0);
    wellFormed(docs);
  });

  it("carries no site attribution — every row of it belongs to the whole network", () => {
    // The inverse of the per-site assertion below. A row with a `site` in this shard would be one
    // site's record served from the file every other site also loads: #1886's bug, relocated.
    expect(docs.filter((d) => d.site !== undefined)).toEqual([]);
  });

  it("indexes the network-global sections, and no site's", () => {
    const globals = new Set(
      sections()
        .filter((s) => !s.href.startsWith("/network/"))
        .map((s) => s.label),
    );
    const indexed = new Set(docs.filter((d) => d.kind === "Section").map((d) => d.section));
    for (const label of globals) expect(indexed.has(label)).toBe(true);
    // A per-site section landing (`/network/<id>/timeline`) must not be here; the only
    // `/network/…` rows are the directory's own, which point at site *homes*.
    const siteRooted = docs.filter((d) => d.url.startsWith("/network/") && d.kind !== "Site");
    expect(siteRooted.map((d) => d.url)).toEqual([]);
  });

  it("indexes every registered network site, and the index page (#1888)", () => {
    // Off the registry, not the bundle: a site is findable the moment it's registered, so a
    // reader searching a place name lands on that site rather than on whichever page mentions it.
    const siteDocs = new Map(docs.filter((d) => d.kind === "Site").map((d) => [d.url, d]));
    expect(siteDocs.size).toBe(SITES.length);
    for (const site of SITES) {
      const doc = siteDocs.get(site.href);
      expect(doc, `no search entry for "${site.slug}"`).toBeDefined();
      expect(doc?.title).toBe(site.place);
    }
    expect(docs.some((d) => d.url === "/network")).toBe(true);
  });

  it("carries the wiki nouns, at their canonical network-global routes (#1892)", () => {
    // Entities and concepts build ONCE, at the root. They belong to this shard precisely because
    // there is one build of them — putting them in each site's shard would ship 77 concepts four
    // times over and imply the per-site curation the taxonomy explicitly retired.
    expect(docs.some((d) => d.kind === "Entity")).toBe(true);
    expect(docs.some((d) => d.kind === "Concept")).toBe(true);
    for (const d of docs.filter((d) => d.kind === "Entity" || d.kind === "Concept")) {
      expect(d.url.startsWith("/wiki/")).toBe(true);
    }
  });

  it("is deterministic across runs", () => {
    expect(buildNetworkSearchIndex()).toEqual(docs);
  });
});

describe("each site's own shard", () => {
  it("ships a non-empty index for every selectable site", () => {
    // The acceptance criterion. Before #1890 there was one index built with no site argument, so
    // three of the four selectable sites shipped nothing of their own at all.
    expect(SELECTABLE.length).toBeGreaterThan(1);
    for (const slug of SELECTABLE) {
      const docs = buildSiteSearchIndex(slug);
      expect(docs.length, `"${slug}" ships an empty search index`).toBeGreaterThan(0);
      wellFormed(docs);
    }
  });

  it("attributes every row to its own site, and roots every URL in that site's base", () => {
    for (const slug of SELECTABLE) {
      const base = siteBase(slug);
      for (const d of buildSiteSearchIndex(slug)) {
        expect(d.site, `${slug}: row "${d.title}" carries no site`).toBe(slug);
        expect(
          underSite(d.url, base),
          `${slug}: "${d.kind}" row "${d.title}" points outside the site base → ${d.url}`,
        ).toBe(true);
      }
    }
  });

  it("never serves another site's row — no URL appears in two shards (#1886)", () => {
    // The property `facets.test.ts` enforces for the rendered pages, carried into the index that
    // points at them. A search result is a claim that this record is this site's.
    const owner = new Map<string, string>();
    const collisions: string[] = [];
    for (const slug of SELECTABLE) {
      for (const d of buildSiteSearchIndex(slug)) {
        const first = owner.get(d.url);
        if (first === undefined) owner.set(d.url, slug);
        else if (first !== slug) collisions.push(`${d.url} — ${first} and ${slug}`);
      }
    }
    expect(collisions).toEqual([]);
  });

  it("indexes nothing behind a locked facet", () => {
    // A locked facet renders the lock + the ask, so a row pointing at it would deep-link a reader
    // into a request for a source. `facetAvailable` is read rather than re-derived.
    const KIND_FACET: Record<string, Parameters<typeof facetAvailable>[1]> = {
      Record: "records",
      Timeline: "timeline",
      Person: "people",
      Place: "places",
      Exhibit: "exhibits",
      Legal: "legal",
      Reference: "reference",
      Document: "documents",
      Collection: "documents",
    };
    for (const slug of SELECTABLE) {
      for (const d of buildSiteSearchIndex(slug)) {
        const facet = KIND_FACET[d.kind];
        if (!facet) continue;
        expect(facetAvailable(slug, facet), `${slug}: "${d.kind}" row behind a locked ${facet}`).toBe(true);
      }
    }
  });

  it("locks with the peers — Fort Wayne indexes its own record and none of Lima's", () => {
    // The concrete case #1886 found, in the search surface. Fort Wayne's corpus carries records,
    // documents and places; it carries no timeline, people or exhibits, and the index says so
    // rather than filling from the reference build.
    const kinds = new Set(buildSiteSearchIndex("fort-wayne").map((d) => d.kind));
    expect(kinds.has("Record")).toBe(true);
    expect(kinds.has("Document")).toBe(true);
    expect(kinds.has("Timeline")).toBe(false);
    expect(kinds.has("Person")).toBe(false);
    expect(kinds.has("Exhibit")).toBe(false);
  });

  it("only attaches an evidence tag where a row genuinely carries one (no fabricated dots)", () => {
    const allowed = new Set<SearchDoc["tag"]>([undefined, "verified", "inference", "open"]);
    const docs = wholeIndex();
    for (const d of docs) expect(allowed.has(d.tag)).toBe(true);
    // a row without a tag is fine; a tagged row must be a real evidence kind (asserted above)
    expect(docs.some((d) => d.tag === undefined)).toBe(true);
  });

  it("is deterministic across runs", () => {
    for (const slug of SELECTABLE) {
      expect(buildSiteSearchIndex(slug)).toEqual(buildSiteSearchIndex(slug));
    }
  });
});

describe("the document layer (#1890 over #1887)", () => {
  const rows = buildSiteSearchIndex("lima").filter((d) => d.kind === "Document");

  it("indexes every routable document in the reference build's corpus", () => {
    // The finding: 3,247 document pages, 21 index entries — one per collection. The corpus was
    // the one thing the search over the corpus could not find.
    const { routable } = limaEntries();
    expect(routable).toBeGreaterThan(1000);
    expect(rows.length).toBe(routable);
  });

  it("addresses each one by its handle, not its as-received path", () => {
    const base = siteBase("lima");
    for (const d of rows) {
      expect(d.url.startsWith(`${base}/doc/`), `not a permalink: ${d.url}`).toBe(true);
      const handle = d.url.slice(`${base}/doc/`.length).replace(/\/$/, "");
      expect(isDocumentId(handle), `not a handle: ${handle}`).toBe(true);
      expect(d.id).toBe(handle);
    }
    // One row per document, so a result set can't double-count the same file.
    expect(new Set(rows.map((d) => d.url)).size).toBe(rows.length);
  });

  it("excludes the entries that have no page", () => {
    // Windows thumbnail caches and the sidecars Office writes beside a save-as-web-page stay in
    // the corpus and stay listed in their production's manifest — they are simply not
    // destinations. A search result is a promise that there is somewhere to land.
    const { routable, nonRoutable } = limaEntries();
    expect(nonRoutable).toBeGreaterThan(0); // the exclusion is exercised, not vacuous
    expect(rows.length).toBe(routable);
    expect(rows.length).toBeLessThan(routable + nonRoutable);
  });

  it("keeps the custodian's folder trail searchable, though the URL no longer carries it", () => {
    // The permalink drops the path; the provenance moves into the text. A reader who knows a file
    // by where it sat ("Shawnee force main") must still find it.
    const deep = runWithSite("lima", () =>
      loadFeed<DocumentCollectionItem[]>("documents")
        .flatMap((c) => c.entries)
        .find((e) => isRoutableDoc(e) && e.rel.split("/").length > 3),
    );
    expect(deep).toBeDefined();
    const row = rows.find((d) => d.title === deep!.name);
    expect(row).toBeDefined();
    // The container segment is the second path element; it must be somewhere in the text.
    expect(row!.text).toContain(deep!.rel.split("/")[1]);
  });

  it("indexes the collection landings too", () => {
    const collections = runWithSite("lima", () => loadFeed<DocumentCollectionItem[]>("documents"));
    const landings = buildSiteSearchIndex("lima").filter((d) => d.kind === "Collection");
    expect(landings.length).toBe(collections.length);
  });
});

describe("the shard manifest the client reads", () => {
  it("names exactly the selectable sites, each at its own base", () => {
    const refs = searchShardRefs();
    expect(refs.map((r) => r.slug).sort()).toEqual([...SELECTABLE].sort());
    for (const r of refs) {
      expect(r.path).toBe(`${siteBase(r.slug)}/search-index.json`);
      expect(r.label.length).toBeGreaterThan(0);
    }
  });

  it("is what a site promoted to selectable gets for free", () => {
    // The list is derived from the registry, so promotion makes a site searchable with no edit
    // here — the failure mode being guarded against is a hand-maintained list that silently omits
    // the newest site.
    expect(searchShardRefs().length).toBe(SITES.filter((s) => s.selectable).length);
  });
});

describe("coverage of the built record", () => {
  it("indexes vastly more than the 531 rows the Lima-only index carried", () => {
    // Not a precise count (the corpus grows); the point is the order of magnitude the issue named.
    // 531 entries against 4,078 routes was 13% coverage, and the missing 87% was the corpus.
    expect(wholeIndex().length).toBeGreaterThan(3000);
  });

  it("covers every selectable site's record, not just the reference build's", () => {
    for (const slug of SELECTABLE) {
      const own = buildSiteSearchIndex(slug);
      // Every site whose bundle carries records puts something searchable behind it.
      if (runWithSite(slug, () => hasFeed("records"))) {
        expect(own.some((d) => d.kind === "Record" || d.kind === "Section")).toBe(true);
      }
    }
  });
});
