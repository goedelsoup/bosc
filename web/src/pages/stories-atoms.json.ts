import type { APIRoute } from "astro";
import { buildRenderCatalog } from "~/lib/renderCatalog";

// Static endpoint: emits `/stories-atoms.json` at build time (#1097) — the hydrated render catalog
// the reader/editor islands fetch to resolve each SDM `atom` handle into its embedded-scale card.
// The runtime renderer is a client island and can't read the content bundle off disk, so this is the
// same static-asset-at-runtime pattern as `/stories-catalog.json` (the thin resolver catalog) and
// `/ask-index.json`. Immutable per deploy → the browser caches it.
export const GET: APIRoute = () => {
  const catalog = buildRenderCatalog();
  const atoms = Object.values(catalog);
  return new Response(JSON.stringify({ atoms }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
