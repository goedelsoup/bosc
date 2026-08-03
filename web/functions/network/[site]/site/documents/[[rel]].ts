// Legacy document-path redirects (#1887, epic #1884 phase 3).
//
// Until this phase, a source document lived at `…/site/documents/<rel>/` — the corpus directory
// tree used verbatim as the URL tree, reaching sixteen segments. Those URLs are cited, so they
// have to keep resolving; they now 301 to the document's stable handle at `/network/<site>/doc/<id>/`.
//
// WHY A FUNCTION AND NOT `_redirects`: Cloudflare Pages caps `_redirects` at 2,000 static + 100
// dynamic rules. Lima alone has 3,247 documents. A line per document is not merely ugly, it is
// over the platform limit and the deploy fails. Because the handle is a pure function of the rel
// (`documentId`), this computes the target at the edge and needs no map at all — one file instead
// of 3,247 impossible rules.
//
// A document that later MOVES to a different rel keeps its handle via `DOCUMENT_ID_PINS`, and the
// old URL still resolves here: the legacy path hashes to the handle it was minted under, which is
// the handle the pin preserves. So neither side of a move goes dead.
//
// ASSET-FIRST: this catch-all also covers the paths that are still real pages — the documents
// index, the collection and container landings, `page-N`, and `catalog.json`. Rather than trying
// to tell those apart by shape (91 documents genuinely sit at the same depth as a container
// landing), it asks the asset server first and only redirects what actually 404s. No heuristics,
// and a new landing route can be added later without touching this file.
import { documentId } from "@watermark/core/documentId";

interface RequestContext {
  request: Request;
  params: { site?: string | string[]; rel?: string | string[] };
  next: () => Promise<Response>;
}

/** Join a Pages catch-all param (string or string[]) back into a path, or "" when absent. */
function joinParam(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value.join("/");
  return value ?? "";
}

/**
 * Recover the `data/documents` rel from the legacy URL path.
 *
 * `docPagePath` escaped only what would break path parsing when Astro materialized the route
 * (`%`, `#`, `?`); spaces and `&` were left literal and the browser percent-encodes them on the
 * wire. `decodeURIComponent` per segment reverses both, and rejecting traversal keeps a crafted
 * path from addressing anything outside the corpus.
 */
export function relFromLegacyPath(raw: string): string | null {
  if (!raw) return null;
  let rel: string;
  try {
    rel = raw
      .split("/")
      .map((segment) => decodeURIComponent(segment))
      .join("/");
  } catch {
    return null; // malformed percent-encoding
  }
  rel = rel.replace(/^\/+/, "").replace(/\/+$/, "");
  if (!rel || rel.includes("..") || rel.includes("\0")) return null;
  // A rel always has a collection and a file: the catalog skips anything directly under
  // data/documents (`watermark.site.documents.build_documents`), so a single segment is a
  // collection landing, never a document.
  if (!rel.includes("/")) return null;
  return rel;
}

/** The permalink a legacy rel redirects to, site-scoped. */
export function legacyRedirectTarget(site: string, rel: string): string {
  return `/network/${site}/doc/${documentId(rel)}/`;
}

export const onRequest = async (ctx: RequestContext): Promise<Response> => {
  // Ask for the real asset first: if this path is a landing, a page-N, or catalog.json, serve it.
  const asset = await ctx.next();
  if (asset.status !== 404) return asset;

  const site = joinParam(ctx.params.site);
  const rel = relFromLegacyPath(joinParam(ctx.params.rel));
  if (!site || !rel) return asset;

  return new Response(null, {
    status: 301,
    headers: {
      location: legacyRedirectTarget(site, rel),
      // The mapping is derived from the path and never changes for a given rel.
      "cache-control": "public, max-age=86400",
    },
  });
};
