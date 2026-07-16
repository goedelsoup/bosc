// View-model helpers for the source-document viewer (epic #274 / D1, D2). Pure and
// dependency-free so they're unit-tested and shared by DocViewer.astro + the doc route.

import type { DocumentEntry, RenderClass } from "./feeds";

/**
 * The `/api/doc/<rel>` byte URL for a document. The rel is path-segment-encoded (each
 * segment via encodeURIComponent, slashes preserved) so spaces/specials survive — the
 * Pages Function decodes it back with decodeURIComponent. Root-absolute: the Function
 * lives at the origin root, never under the Astro base.
 */
export function docApiUrl(rel: string): string {
  const encoded = rel
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `/api/doc/${encoded}`;
}

/** How a reader can reach a document's bytes, given the gate + local availability. */
export type DocAccess = "published" | "dev-only" | "absent";

/**
 * Classify access: `published` (public + viewable everywhere), `dev-only` (bytes exist
 * but aren't on the public allowlist — viewable in dev/preview, gated in prod), or
 * `absent` (no servable bytes — an unreadable/missing source file; an LFS pointer still
 * counts as available since its bytes are served from the object store, #1347).
 */
export function docAccess(entry: Pick<DocumentEntry, "available" | "published">): DocAccess {
  if (!entry.available) return "absent";
  return entry.published ? "published" : "dev-only";
}

/** The viewer tier to render. An unavailable file is always download-only (`other`). */
export function viewerTier(entry: Pick<DocumentEntry, "available" | "render_class">): RenderClass {
  return entry.available ? entry.render_class : "other";
}
