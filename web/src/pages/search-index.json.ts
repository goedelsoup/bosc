import type { APIRoute } from "astro";
import { buildNetworkSearchIndex } from "@watermark/core/search";

// Static endpoint: emits `/search-index.json` at build time — the NETWORK-GLOBAL shard (#1890).
// Sections at the root, the site directory, the `/docs/` prose, and the wiki nouns: everything
// that exists once for the whole network. Each site's own record ships separately at
// `/network/<id>/search-index.json`, and the client loads the two together (see searchEngine.ts).
//
// The dependency-free client matcher fetches this. URLs inside are root-absolute (pre-base); the
// client prefixes them with the data-base it reads off the DOM.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(buildNetworkSearchIndex()), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
