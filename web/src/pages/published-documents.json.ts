import type { APIRoute } from "astro";
import { publishedRels } from "@watermark/core/docGate";

// Static endpoint: emits `/published-documents.json` at build time (#280) — the set of
// data/documents rels cleared for PUBLIC serving (`DocumentItem.published`, set by the
// default-deny allowlist). The `/api/doc` Pages Function fetches it as a static asset and
// enforces the gate server-side, the same static-asset pattern as `/ask-index.json`
// (#209). In dev/preview the Function serves the whole corpus regardless.
//
// ⚠️ This asset is network-GLOBAL and the `documents` feed is PER-SITE, so every exported site's
// set has to be read explicitly by slug — which is what `publishedRels()` does. Until #2149 this
// route called `loadFeed("documents")` bare; a global route runs outside the active-site ALS, so
// that resolved LIMA's bundle and the gate 404'd every other site's published documents, before R2
// was ever asked. The comment here used to claim the catalog UI and the server gate "derive from
// the same flag, so they never disagree": same flag, different scope, and they disagreed for 252
// of 392 documents. See `docGate.ts` for the measurement and why the union stops at the exported
// sites.
export const GET: APIRoute = () => {
  return new Response(JSON.stringify({ rels: publishedRels() }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
