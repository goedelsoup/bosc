import type { APIRoute } from "astro";
import { buildSiteSearchIndex } from "@watermark/core/search";
import { selectableSitePaths } from "@watermark/core/sites";

// Static per-site endpoint: `/network/<id>/search-index.json` (#1890, epic #1884 phase 6).
//
// One shard per selectable site, holding that site's OWN record — records, timeline, documents
// (every routable file, by its #1887 handle), meetings, places, people, exhibits, legal, and
// reference. The network-global half (root sections, the site directory, the `/docs/` prose, the
// wiki nouns) ships once at `/search-index.json`; the client loads the two together and says which
// scope it is searching.
//
// Before this existed there was one index, assembled with no site argument, so every read fell
// through to Lima: the box in the header of every Fort Wayne page could only find Ohio. A shard
// per site is what makes "searching from a peer searches that peer" true rather than aspirational.
//
// The slug comes from the route props (not `activeSite()`), and `buildSiteSearchIndex` re-enters
// `runWithSite` itself — the site binding is explicit at both ends, which is what keeps a
// getStaticPaths-time read from silently resolving Lima's bundle for every site.
export const getStaticPaths = selectableSitePaths;

export const GET: APIRoute = ({ props }) =>
  new Response(JSON.stringify(buildSiteSearchIndex((props as { slug: string }).slug)), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
