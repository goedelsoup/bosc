import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";
import type { DispersionField } from "@watermark/core/feeds";

// Static feed endpoint: exposes the `air-dispersion-field` feed (the gridded AERMOD
// concentration surfaces, one per pollutant) as a root-absolute JSON asset the deck.gl
// FieldLayer island fetches at runtime (epic #1237 / #1232). Empty array when the reference
// site ships no field (a non-reference/peer bundle) — the island then renders the locked state.
export const GET: APIRoute = () =>
  new Response(
    JSON.stringify(
      hasFeed("air-dispersion-field") ? loadFeed<DispersionField[]>("air-dispersion-field") : [],
    ),
    { headers: { "content-type": "application/json; charset=utf-8" } },
  );
