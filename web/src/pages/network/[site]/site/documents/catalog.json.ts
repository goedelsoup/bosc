import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";
import { containerOf, folderPathOf } from "@watermark/core/docBrowse";
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
// Fields are single-character to keep the asset small, and `rel` is NOT stored — it is exactly
// `c/[k/][f/]n`, so the client reconstructs it and the corpus's long as-received paths aren't
// paid for twice.
interface CatalogRow {
  n: string; // file name, as received
  c: string; // collection slug
  k: string; // container slug ("" when the file sits directly in the collection)
  f: string; // folder trail below the container ("" when none)
  t: string; // render_class
  a: string; // docAccess: published | dev-only | absent
  s: number; // size in bytes
  x: string; // non-routable reason ("" when the file gets a page)
}

export function getStaticPaths() {
  return withSitePaths((slug: string) => (facetAvailable(slug, "documents") ? [{ params: {} }] : []));
}

export const GET: APIRoute = () => {
  const rows: CatalogRow[] = [];
  if (hasFeed("documents")) {
    for (const collection of loadFeed<DocumentCollectionItem[]>("documents")) {
      for (const entry of collection.entries) {
        rows.push({
          n: entry.name,
          c: collection.slug,
          k: containerOf(entry.rel) ?? "",
          f: folderPathOf(entry.rel).join("/"),
          t: entry.render_class,
          a: docAccess(entry),
          s: entry.size_bytes,
          x: nonRoutableReason(entry) ?? "",
        });
      }
    }
  }
  return new Response(JSON.stringify({ rows }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
