import { describe, expect, it } from "vitest";
import { hasFeed, loadFeed } from "./bundle";
import { LEGAL, scopedLegal } from "./legal";
import { RECORD_FACETS, type RecordFacet, facetAvailable, facetStatus, sectionStatus } from "./readiness";
import { scopedReference } from "./reference";
import { SITES } from "./sites";

// The standing guard for #1886, run against the committed `sites/` bundles.
//
// "Never borrow another site's record" was true of records / people / exhibits / timeline only by
// ACCIDENT — they happened to read a feed the exporter had already scoped, and the legal facet,
// which reads the network-global content collection instead, leaked all fifteen of Lima's pages
// onto every peer. The property below is the one that was missing: identical content at the same
// facet route is a bug unless the facet DECLARES itself network-global and says why.

const SELECTABLE = SITES.filter((s) => s.selectable).map((s) => s.slug);
const FACETS = Object.keys(RECORD_FACETS) as RecordFacet[];

/** A facet's content for a site, as a comparable key. Empty string = the site has nothing here
 *  (two empty facets are not a leak — an absence can't be borrowed). */
function contentKey(slug: string, facet: RecordFacet): string {
  const feed = (name: string): string =>
    hasFeed(name, slug) ? JSON.stringify(loadFeed<unknown[]>(name, slug)) : "";
  switch (facet) {
    case "documents":
      return feed("documents");
    case "records":
      return feed("records");
    case "timeline":
      return feed("timeline");
    case "exhibits":
      return feed("exhibits");
    case "people":
      return feed("people");
    case "places":
      return feed("places");
    case "concepts":
      return feed("concepts");
    case "legal":
      return JSON.stringify(scopedLegal(slug).map((d) => d.slug));
    case "reference":
      return JSON.stringify(scopedReference(slug).map((d) => d.slug));
  }
}

const EMPTY = new Set(["", "[]", "{}"]);
const isEmpty = (key: string): boolean => EMPTY.has(key);

/**
 * Sites that serve byte-identical, non-empty content at `route`, reported as collisions. An empty
 * facet collides with nothing — an absence can't be borrowed — and a `network-global` facet is
 * exempt by declaration, which is the whole point of making the scope explicit.
 */
function collisionsAt(route: string, keyFor: (slug: string) => string, global = false): string[] {
  if (global) return [];
  const seen = new Map<string, string>();
  const out: string[] = [];
  for (const slug of SELECTABLE) {
    const key = keyFor(slug);
    if (isEmpty(key)) continue;
    const first = seen.get(key);
    if (first === undefined) seen.set(key, slug);
    else out.push(`${route} — ${first} and ${slug} serve identical content`);
  }
  return out;
}

describe("the record-facet declaration", () => {
  it("covers every facet with a route, a gating section, and a scope", () => {
    for (const facet of FACETS) {
      const d = RECORD_FACETS[facet];
      expect(d.route.startsWith("/")).toBe(true);
      expect(d.label.length).toBeGreaterThan(0);
      expect(d.note.length).toBeGreaterThan(0);
      expect(["per-site", "network-global"]).toContain(d.scope);
    }
  });

  it("declares exactly one network-global facet — the glossary (the #1886 concepts decision)", () => {
    const global = FACETS.filter((f) => RECORD_FACETS[f].scope === "network-global");
    expect(global).toEqual(["concepts"]);
    // The decision lives in the module, not a commit message: the shared method vocabulary is the
    // same at every watershed point, and it renders inside each site build so the record's
    // `[[wiki links]]` resolve without leaving the site (#1567).
    expect(RECORD_FACETS.concepts.note).toContain("#1567");
    expect(RECORD_FACETS.concepts.note).toContain("#1892");
  });
});

/**
 * The one collision this guard admits today, named rather than exempted — the same disease as the
 * legal facet, found by this test in a facet #1886 does not scope.
 *
 * `/site/reference/` renders each dataset's committed README from `data/reference/`, and there is
 * exactly ONE README per dataset: Lima's. Two of the three a Great-Miami peer owns are catalog
 * entries marked `slug-scoped` — `rsei-inventory` and `economics-baseline` — meaning the DATASET is
 * genuinely per-site (Python materializes each site's own title off `title_template`, and each
 * site's `rsei`/`economics-baseline` feed carries its own county). The README is not: it is written
 * about **Allen County, OH (FIPS 39003)**, so Urbana and Troy-Piqua serve identical, Lima-worded
 * documentation of their own datasets, and by the same token Fort Wayne's `/site/reference/rsei`
 * describes an Ohio county under an Indiana watershed point.
 *
 * It is deliberately NOT fixed here. The fix is a data-tier and editorial call — per-site READMEs,
 * or a judgment per dataset about which prose is genuinely basin/network-scoped (`echo`'s
 * Maumee-basin inventory) versus which documents Lima's instance (`rsei`, `economics`, and
 * `gleif`'s corridor watchlist) — not a gating change, and #1886 scopes the gates. Listed here so
 * the property stays enforced for everything else and any NEW collision still fails the build.
 */
const KNOWN_DEVIATIONS = ["/site/reference/ — urbana and troy-piqua serve identical content"];

describe("no two sites serve the same content at the same facet route", () => {
  it("holds across every selectable site, unless the facet is declared network-global", () => {
    // More than one selectable site is what makes this test mean anything at all.
    expect(SELECTABLE.length).toBeGreaterThan(1);
    const collisions = FACETS.flatMap((facet) =>
      collisionsAt(
        RECORD_FACETS[facet].route,
        (slug) => contentKey(slug, facet),
        RECORD_FACETS[facet].scope === "network-global",
      ),
    );
    expect(collisions).toEqual(KNOWN_DEVIATIONS);
  });

  it("catches the reported bug — the guard fails against the pre-fix, unscoped legal read", () => {
    // Re-run the check with the read the page used to do (the whole curated set for every site,
    // regardless of whose corpus it came from). Every peer pair collides, which is the failure the
    // assertion above is now standing guard over — not a property that happens to hold today.
    const preFix = collisionsAt("/site/legal/", () => JSON.stringify(LEGAL.map((d) => d.slug)));
    expect(preFix.length).toBe(SELECTABLE.length - 1);
    expect(preFix[0]).toContain("/site/legal/");
  });
});

describe("facet gating on the committed bundles", () => {
  it("opens every facet on the reference build", () => {
    for (const facet of FACETS) expect(facetStatus("lima", facet)).toBe("available");
  });

  it("locks legal on the peers that were serving Lima's filings", () => {
    for (const peer of ["fort-wayne", "urbana", "troy-piqua"]) {
      expect(facetStatus(peer, "legal")).toBe("locked");
      expect(sectionStatus(peer, "legal")).toBe("locked");
    }
  });

  it("opens a peer's own record facets — the lock is scope, not a peer-wide shutdown", () => {
    // Fort Wayne has its own records, documents, campus geometry and catalog: those stay open.
    expect(facetAvailable("fort-wayne", "records")).toBe(true);
    expect(facetAvailable("fort-wayne", "documents")).toBe(true);
    expect(facetAvailable("fort-wayne", "places")).toBe(true);
    expect(facetAvailable("fort-wayne", "reference")).toBe(true);
    // …and the ones its corpus genuinely doesn't carry lock rather than fill from Lima.
    expect(facetAvailable("fort-wayne", "timeline")).toBe(false);
    expect(facetAvailable("fort-wayne", "people")).toBe(false);
    expect(facetAvailable("fort-wayne", "exhibits")).toBe(false);
  });

  it("keeps the glossary open on a peer — declared network-global, so it is not a leak", () => {
    for (const peer of ["fort-wayne", "urbana", "troy-piqua"]) {
      expect(facetAvailable(peer, "concepts")).toBe(true);
    }
  });

  it("locks the places FACET without closing the places SECTION (Urbana)", () => {
    // Urbana's `places` domain is live off a committed parcel assemblage — geometry the map draws
    // — but it publishes no per-place profile. The leaf locks; claiming the site has no places
    // would be the mirror image of the bug this issue fixes.
    expect(facetStatus("urbana", "places")).toBe("locked");
    expect(sectionStatus("urbana", "places")).toBe("available");
  });
});
