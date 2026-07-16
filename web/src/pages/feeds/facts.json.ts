import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";

export const GET: APIRoute = () =>
  new Response(JSON.stringify(hasFeed("facts") ? loadFeed("facts") : []), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
