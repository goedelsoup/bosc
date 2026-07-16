import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";

// Static feed endpoint: exposes the timeline feed as a root-absolute JSON asset
// so MCP tool handlers can fetch it at runtime via `fetch(new URL("/feeds/timeline.json", requestUrl))`.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(hasFeed("timeline") ? loadFeed("timeline") : []), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
