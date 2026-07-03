import type { APIRoute } from "astro";
import { loadCatalog } from "../lib/catalogBuild";

// Static endpoint: emits `/stories-catalog.json` at build time (#1095) — the hydrated catalog the
// /api/stories write path validates handles against server-side (functions/api/_lib/catalogAsset.ts
// fetches it as a static asset, the same pattern as /ask-index.json). The Worker can't read the
// content bundle off disk, so this is how the compiler's `resolveHandle` gets its catalog at runtime.
//
// Emits the active site's catalog (default Lima); handles embed their own site, so one asset can be
// extended to the whole network later. Immutable per deploy → the Function caches it per isolate.
export const GET: APIRoute = () => {
  const catalog = loadCatalog();
  const atoms = [...catalog.byHandle.values()];
  return new Response(JSON.stringify({ site: catalog.site, version: catalog.version, atoms }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
