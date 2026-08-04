import type { APIRoute } from "astro";
import { buildSiteSearchIndex, searchShardRefs } from "@watermark/core/search";
import { siteBase } from "@watermark/core/routes";

// Static per-site endpoint: `/network/<id>/search-index.json` (#1890, epic #1884 phase 6).
//
// One shard per site that publishes rows of its own, holding that site's OWN record — records,
// timeline, documents (every routable file, by its #1887 handle), meetings, places, people,
// exhibits, legal, and reference. The network-global half (root sections, the site directory, the
// `/docs/` prose, the wiki nouns) ships once at `/search-index.json`; the client loads the two
// together and says which scope it is searching.
//
// Before this existed there was one index, assembled with no site argument, so every read fell
// through to Lima: the box in the header of every Fort Wayne page could only find Ohio. A shard
// per site is what makes "searching from a peer searches that peer" true rather than aspirational.
//
// The paths come from `searchShardRefs()` rather than `selectableSitePaths` (#1907), so the routes
// this emits and the shard list the chrome hands the client are the SAME list — a site whose shard
// is advertised but not built is a 404 the reader pays for, and one built but not advertised is a
// file nobody fetches. `check-routes.mjs` compares the built shards against that same declaration.
//
// The slug comes from the route props (not `activeSite()`), and `buildSiteSearchIndex` re-enters
// `runWithSite` itself — the site binding is explicit at both ends, which is what keeps a
// getStaticPaths-time read from silently resolving Lima's bundle for every site.
export function getStaticPaths(): Array<{ params: { site: string }; props: { slug: string } }> {
  return searchShardRefs().map((ref) => ({
    params: { site: siteBase(ref.slug).replace("/network/", "") },
    props: { slug: ref.slug },
  }));
}

export const GET: APIRoute = ({ props }) =>
  new Response(JSON.stringify(buildSiteSearchIndex((props as { slug: string }).slug)), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
