/**
 * The set of `data/documents` rels the PUBLIC `/api/doc` gate admits (#280, fixed in #2149).
 *
 * `/published-documents.json` is a **network-global** static endpoint — one asset, at the domain
 * root, for one origin — while `documents` is a **per-site** feed. That mismatch is the whole
 * reason this module exists.
 *
 * `getStaticPaths` and a global route both run **outside** the request-time active-site ALS, so a
 * bare `loadFeed("documents")` there resolves *Lima's* bundle whatever site is being built (see
 * `withSitePaths` in `sites.ts`, which documents the same hazard for dynamic routes). The gate
 * asset was written that way, so it carried Lima's published set and nobody else's — and the
 * Function 404s anything the set does not name, **before** it ever asks R2. Measured on production
 * 2026-09-04: of 392 published documents the build offered, the gate admitted 140 and served 26.
 * 252 were unreachable by construction, at any deploy freshness, with the bytes present in R2 for
 * 24 of them.
 *
 * So the gate set is the **union across every site the build exports**. Two properties of that
 * choice are deliberate:
 *
 * - **Union, not intersection, and not "all committed bundles".** A rel is admitted if any
 *   exported site publishes it. The scope stops at the exported sites because that is exactly
 *   what the build offers a reader: a non-selectable site mints no pages, so admitting its
 *   documents would open bytes no page links, which is the opposite of default-deny.
 * - **`published` is per-rel, not per-site.** `data/site/published-documents.yaml` is one global
 *   allowlist, so a rel that two sites both carry gets the same flag from both. The union adds
 *   *reach*, never a second opinion about clearance.
 */

import { hasFeed, loadFeed, manifestOrNull } from "./bundle";
import type { DocumentCollectionItem } from "./feeds";
import { exportedSiteSlugs } from "./sites";

/** Reads one site's `documents` feed, or returns `null` when that site has no such feed. */
export type DocumentFeedReader = (slug: string) => DocumentCollectionItem[] | null;

/**
 * The published rels across `slugs`, sorted and de-duplicated — the testable core (#2149).
 *
 * Sorted so the emitted asset is byte-stable across builds: the union's iteration order follows
 * the site list, which would otherwise reshuffle the whole file when a site is promoted.
 */
export function publishedRelsFrom(slugs: readonly string[], read: DocumentFeedReader): string[] {
  const rels = new Set<string>();
  for (const slug of slugs) {
    const collections = read(slug);
    if (collections === null) continue; // no bundle / no documents feed for that site
    for (const coll of collections) {
      for (const entry of coll.entries) {
        if (entry.published) rels.add(entry.rel);
      }
    }
  }
  return [...rels].sort();
}

/**
 * The gate set for this build — {@link publishedRelsFrom} bound to the real bundles.
 *
 * Build-time only (it reads the bundle from disk); `/published-documents.json` is its one caller,
 * and a test pins its shape against the committed `web/sites/` fixtures.
 */
export function publishedRels(): string[] {
  return publishedRelsFrom(exportedSiteSlugs(), (slug) =>
    // `manifestOrNull` first: `hasFeed` THROWS on a site with no bundle. A selectable site
    // without one already fails the build in `loadManifest`, so this guards against the gate
    // silently emptying rather than describing a supported state.
    manifestOrNull(slug) && hasFeed("documents", slug)
      ? loadFeed<DocumentCollectionItem[]>("documents", slug)
      : null,
  );
}
