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
import { slugify, type DocumentCollectionItem, type EntityNode } from "./feeds";
import { CONNECT_LINK, sections } from "./nav";
import { facetAvailable } from "./readiness";
import { networkEntities } from "./networkEntities";
import { LIMA_SLUG, siteBase } from "./routes";
import { buildNetworkSearchIndex, buildSiteSearchIndex, searchShardRefs, type SearchDoc } from "./search";
import { comingSoonStories, SITES } from "./sites";
import { storyFor } from "./walk";

const SELECTABLE = SITES.filter((s) => s.selectable).map((s) => s.slug);
/** Every site that ships a shard — the selectable ones plus any peer publishing a walk (#1907). */
const SHARDED = searchShardRefs().map((r) => r.slug);

/** Every row of every shard, as the client sees it under network scope. */
function wholeIndex(): SearchDoc[] {
  return [...buildNetworkSearchIndex(), ...SHARDED.flatMap((slug) => buildSiteSearchIndex(slug))];
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
    // A per-site section landing (`/network/<id>/timeline`) must not be here. Asked of the REGISTRY
    // rather than of the `/network/` prefix (#1908): `/network/connect` is a network-global page
    // that happens to live under it, and a prefix test excluded the one page it was never about —
    // the chrome carried Connect from two surfaces while search reached it from none.
    const siteRooted = docs.filter(
      (d) => d.kind !== "Site" && SITES.some((s) => d.url.startsWith(`${siteBase(s.slug)}/`)),
    );
    expect(siteRooted.map((d) => d.url)).toEqual([]);
    expect(docs.map((d) => d.url)).toContain(CONNECT_LINK.href);
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

  it("indexes every party the network publishes a page for, including a peer-only one (#1906)", () => {
    // The gap `searchCoverage.ts` used to declare, closed and now guarded: a party carried only by
    // a peer's `entities` feed has a page since the wiki widened past one bundle, so it must be
    // findable — and nothing may be indexed that has no page, which was the reason it was left out
    // rather than given a URL that would 404 with a good snippet.
    const indexed = new Set(docs.filter((d) => d.kind === "Entity").map((d) => d.url));
    const published = new Set(networkEntities().map((e) => `/wiki/entities/${e.slug}/`));
    expect(indexed).toEqual(published);
    // …and the union really does reach past the canonical build, or this asserts nothing.
    const canonical = new Set(
      runWithSite(LIMA_SLUG, () => loadFeed<EntityNode[]>("entities")).map((e) => slugify(e.key)),
    );
    expect(networkEntities().some((e) => !canonical.has(e.slug))).toBe(true);
  });

  it("is deterministic across runs", () => {
    expect(buildNetworkSearchIndex()).toEqual(docs);
  });
});

describe("each site's own shard", () => {
  it("ships a non-empty index for every site that ships a shard", () => {
    // The acceptance criterion. Before #1890 there was one index built with no site argument, so
    // three of the four selectable sites shipped nothing of their own at all.
    expect(SHARDED.length).toBeGreaterThan(1);
    for (const slug of SHARDED) {
      const docs = buildSiteSearchIndex(slug);
      expect(docs.length, `"${slug}" ships an empty search index`).toBeGreaterThan(0);
      wellFormed(docs);
    }
  });

  it("attributes every row to its own site, and roots every URL in that site's base", () => {
    for (const slug of SHARDED) {
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

  it("lists each destination once within a shard", () => {
    // Two rows for one page is a duplicate in the reader's result list, not two results. It caught
    // a real one: the `timeline` record facet's route IS the timeline section's landing, so every
    // site with both open listed `/timeline` twice.
    //
    // Exempt by design: a Timeline event and a Meeting summary are individually searchable rows
    // that all land on the one page carrying them (`/timeline`, `/site/legal#meetings`). Asserting
    // on everything EXCEPT those — rather than on a list of "landing" kinds — means a NEW kind that
    // accidentally duplicates a destination fails here instead of being quietly exempt.
    const SHARED_DESTINATION = new Set(["Timeline", "Meeting"]);
    for (const slug of SHARDED) {
      const seen = new Map<string, string>();
      const dupes: string[] = [];
      for (const d of buildSiteSearchIndex(slug)) {
        if (SHARED_DESTINATION.has(d.kind)) continue;
        const first = seen.get(d.url);
        if (first === undefined) seen.set(d.url, `${d.kind}:${d.title}`);
        else dupes.push(`${slug} ${d.url} — "${first}" and "${d.kind}:${d.title}"`);
      }
      expect(dupes).toEqual([]);
    }
  });

  it("never serves another site's row — no URL appears in two shards (#1886)", () => {
    // The property `facets.test.ts` enforces for the rendered pages, carried into the index that
    // points at them. A search result is a claim that this record is this site's.
    const owner = new Map<string, string>();
    const collisions: string[] = [];
    for (const slug of SHARDED) {
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
    for (const slug of SHARDED) {
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
    for (const slug of SHARDED) {
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
  it("names exactly the sites with rows of their own, each at its own base", () => {
    // The invariant #1907 turns on: the advertised list and the sites that actually have something
    // to say are the SAME set. A site advertised without rows is a fetch of an empty file (and a
    // `check-routes` failure); a site with rows and no ref is content nothing can reach — which is
    // exactly what sharding on `selectable` did to Findlay.
    const refs = searchShardRefs();
    const withRows = SITES.filter((s) => buildSiteSearchIndex(s.slug).length > 0).map((s) => s.slug);
    expect(refs.map((r) => r.slug).sort()).toEqual([...withRows].sort());
    for (const r of refs) {
      expect(r.path).toBe(`${siteBase(r.slug)}/search-index.json`);
      expect(r.label.length).toBeGreaterThan(0);
    }
  });

  it("is what a site promoted to selectable gets for free", () => {
    // The list is derived from the registry, so promotion makes a site searchable with no edit
    // here — the failure mode being guarded against is a hand-maintained list that silently omits
    // the newest site. Every selectable site is in it; the peers publishing a walk are the extras.
    for (const slug of SELECTABLE) expect(SHARDED).toContain(slug);
    expect(SHARDED.length).toBeGreaterThanOrEqual(SELECTABLE.length);
  });

  it("still reaches past `selectable` for any peer that publishes a walk (#1907/#1971)", () => {
    // The #1907 finding was Findlay: walk routes emit on REGISTRATION, not switchability (#1466),
    // so a non-selectable peer published eight pages nothing could search. Epic #1968 removed the
    // INSTANCE — the three peer walks were absorbed into their studies (#1970) and only Lima, a
    // selectable site, registers one — but not the MECHANISM, which is still registration-gated.
    //
    // So this asserts the invariant rather than the old instance: any peer that registers a walk
    // must be sharded. It is vacuously true today and would bind the moment a peer registers one
    // again, which is exactly when the hazard returns.
    const peers = SITES.filter((s) => !s.selectable && (s.stories ?? []).length > 0);
    for (const p of peers) expect(SHARDED).toContain(p.slug);
    // …and today the shard set really is the selectable set plus nothing, which is the state the
    // line above is guarding. Asserted so "no peers" can't silently become "peers, unsharded".
    expect(peers).toEqual([]);
    expect([...SHARDED].sort()).toEqual([...SELECTABLE].sort());
  });
});

describe("a peer's shard (#1907/#1971)", () => {
  const peers = SITES.filter((s) => !s.selectable && SHARDED.includes(s.slug));

  it("indexes only routes the peer actually builds — a bundle is not a page", () => {
    // The original assertion ("holds its stories and nothing else") named the only thing a peer
    // could publish while non-selectable: its walk. No peer registers one now, so the shard set is
    // the selectable set and this loop is empty — but the property it protects is unchanged and
    // still the right one, so it stays: whatever a peer ships rows for must be a route it builds.
    //
    // The distinction that made #1907 worth a test survives even with no peers: a peer's BUNDLE
    // carries records, timeline, documents and a study — it is exported like any other site — and
    // none of those becomes a page until the site is selectable.
    for (const site of peers) {
      const rows = buildSiteSearchIndex(site.slug);
      expect(rows.length).toBeGreaterThan(0);
      for (const d of rows) {
        expect(
          d.url.startsWith(`${siteBase(site.slug)}/stories/`),
          `${site.slug}: "${d.kind}" row "${d.title}" points at an unbuilt route → ${d.url}`,
        ).toBe(true);
      }
      expect(runWithSite(site.slug, () => hasFeed("records"))).toBe(true);
    }
    expect(peers).toEqual([]);
  });
});

describe("a held story (#1907/#1971)", () => {
  it("is indexed exactly once, at its own root, wherever one is held", () => {
    // A `comingSoon` walk serves the SAME interstitial at every route it emits — the on-ramp, the
    // contents, each chapter — so eight rows would be eight near-identical results promising prose
    // that is deliberately held. One row, at the root; `searchCoverage.ts` declares the rest
    // `represented` by it.
    //
    // NOTHING IS HELD TODAY (#1971): the three `comingSoon` walks were absorbed into their impact
    // studies rather than eventually published, so this loop is empty. The `comingSoon` mechanism
    // survives in `sites.ts` for the next walk that needs holding, and this binds again the moment
    // one does — so it is kept rather than deleted, with the emptiness asserted below so it cannot
    // rot into a test that silently checks nothing.
    const held = SITES.flatMap((s) => comingSoonStories(s.slug).map((ref) => ({ site: s, ref })));
    expect(held).toEqual([]);
    for (const { site, ref } of held) {
      const root = `${siteBase(site.slug)}/stories/${ref.codename}/`;
      const rows = buildSiteSearchIndex(site.slug).filter((d) => d.url.startsWith(root));
      expect(
        rows.map((d) => d.url),
        `${site.slug}/${ref.codename}`,
      ).toEqual([root]);
      // Titled the way the page titles itself, so the row promises the notice, not the narrative.
      expect(rows[0].title).toBe(`${ref.title} — coming soon`);
      expect(rows[0].site).toBe(site.slug);
    }
  });

  it("leaks no chapter prose into the index", () => {
    // #1529's guarantee, carried into search: the content is held, so the only thing a row may
    // carry is the title and dek the teaser already advertises.
    for (const site of SITES) {
      for (const ref of comingSoonStories(site.slug)) {
        const story = storyFor(site.slug, ref.codename);
        expect(story, `${site.slug}/${ref.codename} has no chapters to guard against`).toBeDefined();
        const root = `${siteBase(site.slug)}/stories/${ref.codename}/`;
        const urls = new Set(buildSiteSearchIndex(site.slug).map((d) => d.url));
        for (const c of story!.chapters) expect(urls.has(`${root}${c.slug}/`)).toBe(false);
        expect(urls.has(`${root}contents/`)).toBe(false);
      }
    }
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
