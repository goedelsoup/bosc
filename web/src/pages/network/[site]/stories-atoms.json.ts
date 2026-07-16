import type { APIRoute } from "astro";
import { buildRenderCatalog } from "@watermark/core/renderCatalog";
import { selectableSitePaths } from "@watermark/core/sites";

// Per-site render-catalog asset: emits `/network/<site>/stories-atoms.json` at build time (#1097) —
// the hydrated atoms the reader/editor islands resolve each SDM `atom` handle against. One asset per
// selectable site (not a single root asset that would serve Lima's atoms to every site), built from
// that site's registry `slug`. Same static-asset-at-runtime pattern as `/stories-catalog.json`.
export const getStaticPaths = selectableSitePaths;

export const GET: APIRoute = ({ props }) => {
  const { slug } = props as { slug: string };
  const atoms = Object.values(buildRenderCatalog(slug));
  return new Response(JSON.stringify({ site: slug, atoms }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
