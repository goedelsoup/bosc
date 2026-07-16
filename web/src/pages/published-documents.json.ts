import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";
import type { DocumentCollectionItem } from "@watermark/core/feeds";

// Static endpoint: emits `/published-documents.json` at build time (#280) — the set of
// data/documents rels cleared for PUBLIC serving (`DocumentItem.published`, set by the
// default-deny allowlist). The `/api/doc` Pages Function fetches it as a static asset and
// enforces the gate server-side, the same static-asset pattern as `/ask-index.json`
// (#209). Both the catalog UI and the server gate derive from the same flag, so they
// never disagree. In dev/preview the Function serves the whole corpus regardless.
export const GET: APIRoute = () => {
  const rels: string[] = [];
  if (hasFeed("documents")) {
    for (const coll of loadFeed<DocumentCollectionItem[]>("documents")) {
      for (const entry of coll.entries) {
        if (entry.published) rels.push(entry.rel);
      }
    }
  }
  return new Response(JSON.stringify({ rels }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
