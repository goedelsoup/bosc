import type { APIRoute } from "astro";
import { buildAskIndex } from "@watermark/core/askIndex";

// Static endpoint: emits `/ask-index.json` at build time (#209). The `/api/ask` Pages
// Function fetches it as a static asset and runs BM25 retrieval over it server-side
// (functions/api/_lib/retrieval.ts) — the same static-asset pattern as the client
// search index (`/search-index.json`). URLs inside are root-absolute (pre-base); the
// citation-resolution UI prefixes them with the site base.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(buildAskIndex()), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
