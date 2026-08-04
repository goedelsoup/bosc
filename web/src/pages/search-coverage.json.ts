import type { APIRoute } from "astro";
import { searchCoverage } from "@watermark/core/searchCoverage";

// Static endpoint: emits `/search-coverage.json` at build time (#1890).
//
// The declaration of what search covers, and which route families deliberately carry no index row.
// `scripts/check-routes.mjs` reads it out of `dist/` and asserts the measured fraction against it,
// which is how "coverage is a stated, tested fraction of content routes" gets to be true of the
// BUILD rather than of a comment: the guard can't drift from the declaration because it has no
// copy of its own, and the guard is post-build Node that can't import the TypeScript.
//
// That it is also a public asset is deliberate — a reader who wants to know whether search reaches
// everything can read the answer, with reasons, rather than inferring it from a miss.
export const GET: APIRoute = () =>
  new Response(JSON.stringify(searchCoverage(), null, 2), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
