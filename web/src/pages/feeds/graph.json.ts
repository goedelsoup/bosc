import type { APIRoute } from "astro";
import { buildGraph } from "@watermark/viz/graph";

// Static endpoint: the entity graph with build-time d3-force coordinates. The
// EntityGraph island fetches it (client:only) and renders nodes/edges directly.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(buildGraph()), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
