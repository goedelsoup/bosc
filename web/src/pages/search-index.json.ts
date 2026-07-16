import type { APIRoute } from "astro";
import { buildSearchIndex } from "@watermark/core/search";

// Static endpoint: emits `/search-index.json` at build time. The dependency-free
// client matcher (scripts/search.ts) fetches it. URLs inside are root-absolute
// (pre-base); the client prefixes them with the data-base it reads off the DOM.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(buildSearchIndex()), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
