import type { APIRoute } from "astro";
import { hasFeed } from "../../../lib/bundle";
import { loadGeo } from "../../../lib/geo";

// Static endpoint: the imagery time-slider's data — the `geo/imagery` feed served
// verbatim (issue #72). Unlike the corridor map's merged endpoint, this keeps the
// feed's `meta` (the dated Esri Wayback ladder the ImagerySlider island reads) and
// the per-AOI footprint. Falls back to an empty collection if the bundle lacks it.
export const GET: APIRoute = () => {
  const fc = hasFeed("geo/imagery")
    ? loadGeo("geo/imagery")
    : { type: "FeatureCollection", features: [] };
  return new Response(JSON.stringify(fc), {
    headers: { "content-type": "application/geo+json; charset=utf-8" },
  });
};
