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

/**
 * The site-relative **viewer-page** path for a document (`/site/documents/<rel>`). Callers wrap it
 * in `withSite` / `withBasePath`; it carries no base of its own.
 *
 * Deliberately NOT `encodeURIComponent` per segment like `docApiUrl` above — the two have
 * different contracts. The byte URL is read by a Pages Function that calls `decodeURIComponent`,
 * so it wants everything encoded. This one has to address a **static file Astro already wrote to
 * disk**, and Astro encodes only the characters that would break path parsing when it materializes
 * a route param: `#` becomes `%23` in the emitted directory name, while spaces and `&` stay
 * literal. Encoding more than Astro does produces a path that exists nowhere.
 *
 * This matters because source filenames are as-received public records and are never renamed
 * (chain of custody): the sanitary PRR production has 141 files with `#` in the name, 1,571 with
 * `&`, and 1,739 with spaces. Interpolated raw, a `#` reads as a fragment delimiter and the
 * browser requests a truncated path — the link 404s while the file sits on disk.
 */
export function docPagePath(rel: string): string {
  // `%` first so an existing escape can't be re-read as one; then the path-structural characters.
  const encoded = rel.replace(/%/g, "%25").replace(/#/g, "%23").replace(/\?/g, "%3F");
  return `/site/documents/${encoded}`;
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
