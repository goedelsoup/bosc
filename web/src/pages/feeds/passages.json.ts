import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";

// Static endpoint: emits `/feeds/passages.json` at build time (#1589) — the page-level
// excerpt index over the published source PDFs the search_passages MCP tool reads. `loadFeed`
// transparently reads the NDJSON on-disk form and re-serialises it as a JSON array here.
// Empty when the feed is absent (a site with no published PDFs / offline build).
export const GET: APIRoute = () =>
  new Response(JSON.stringify(hasFeed("passages") ? loadFeed("passages") : []), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
