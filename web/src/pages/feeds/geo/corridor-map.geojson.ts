import type { APIRoute } from "astro";
import { mergedGeo } from "@watermark/viz/geo";

// Static endpoint: the corridor map's data — every geo layer feed merged into one
// FeatureCollection, emitted at build time. The CorridorMap island fetches it
// (client:only), mirroring how the app already ships /search-index.json. Each
// feature keeps its typed `layer`/`color`/`role`/`label` properties, so the
// island styles entirely from the data.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(mergedGeo()), {
    headers: { "content-type": "application/geo+json; charset=utf-8" },
  });
