import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";
import type { CatalogRow } from "@watermark/core/docCatalog";
import { containerOf, folderPathOf } from "@watermark/core/docBrowse";
import { RECORD_ROUTE_BASE, siteExtractions } from "@watermark/core/docExtraction";
import { nonRoutableReason } from "@watermark/core/docRouting";
import { docAccess } from "@watermark/core/docView";
import type { DocumentCollectionItem } from "@watermark/core/feeds";
import { facetAvailable } from "@watermark/core/readiness";
import { withSitePaths } from "@watermark/core/sites";

// Static per-site endpoint: `/network/<site>/site/documents/catalog.json` (#1887).
//
// The filter toolbar on every documents landing needs to search the WHOLE listing, not just the
// 250 rows the current page happens to carry — otherwise "type: pdf" on a 7-page production is a
// lie. This is that index: one compact, cacheable JSON asset per site, fetched once by
// `scripts/doc-catalog.ts` and reused across landings.
//
// It is deliberately not inlined into the pages. Inlining is what the old 2.0 MB index did; the
// whole point of the phase is to get that payload off the HTML critical path. Without JS the
// landings still render their SSR page and pager, so this is pure progressive enhancement.
//
// The row's compact field encoding — and the predicates that read it back — are declared once in
// `@watermark/core/docCatalog`, so this writer and `scripts/doc-catalog.ts` cannot come to
// disagree about what a field means.

export function getStaticPaths() {
  return withSitePaths((slug: string) => (facetAvailable(slug, "documents") ? [{ params: {} }] : []));
}

export const GET: APIRoute = () => {
  const rows: CatalogRow[] = [];
  const extractions = siteExtractions();
  if (hasFeed("documents")) {
    for (const collection of loadFeed<DocumentCollectionItem[]>("documents")) {
      for (const entry of collection.entries) {
        const refs = extractions.get(entry.rel);
        rows.push({
          n: entry.name,
          c: collection.slug,
          k: containerOf(entry.rel) ?? "",
          f: folderPathOf(entry.rel).join("/"),
          t: entry.render_class,
          a: docAccess(entry),
          s: entry.size_bytes,
          x: nonRoutableReason(entry) ?? "",
          // The record screen minus the `RECORD_ROUTE_BASE` the client re-applies from the table's
          // `data-rec-base` — sliced off the ref's own href so the two can't mint different routes.
          ...(refs?.length ? { e: refs.length } : {}),
          ...(refs?.length === 1 ? { r: refs[0].href.slice(RECORD_ROUTE_BASE.length) } : {}),
        });
      }
    }
  }
  return new Response(JSON.stringify({ rows }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
