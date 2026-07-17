// Fetch the build-time passages index (`/feeds/passages.json`, #1589) as a static asset from
// the same origin and cache the parsed rows in module scope. Parallel to askIndexLoad.ts: the
// asset is immutable per deploy, so caching across requests in one Workers isolate is safe.
// The endpoint always exists (it emits `[]` when the feed is absent), so an empty result just
// means the active site has no published-PDF passages — search_passages then returns nothing.

import { fetchWithTimeout } from "./http";

/** One page-level passage from the `passages` bundle feed (#1589) — the row contract. */
export interface PassageRow {
  /** Stable id, `${document_id}#p${page}` — what search_passages cites by. */
  id: string;
  /** DocumentItem.rel — path relative to data/documents; the join key to get_document. */
  document_id: string;
  /** First path segment of document_id (e.g. "oepa") — the collection axis. */
  collection: string;
  /** The source document's catalog name, for display. */
  title: string;
  /** 1-indexed printed page number. */
  page: number;
  /** Sub-page heading when known; null for plain page chunks. */
  section: string | null;
  /** The page's text-layer extraction (verbatim; garbled OCR for scans). */
  text: string;
}

// Keyed by resolved URL so a different indexUrl (e.g. a per-site override) doesn't return
// another feed's cached rows. Mirrors askEmbeddingsLoad.
const cache = new Map<string, PassageRow[]>();

/** Test seam: drop the isolate cache. */
export function _resetPassagesCache(): void {
  cache.clear();
}

/**
 * Load the passages index. `indexUrl` overrides the default same-origin asset URL. Returns an
 * empty array when the asset is absent (404) — a site with no published PDFs — so the caller
 * degrades to "no passages" rather than a failure. Throws on other fetch/parse failures.
 */
export async function loadPassages(requestUrl: string, indexUrl?: string): Promise<PassageRow[]> {
  const url = indexUrl ?? new URL("/feeds/passages.json", requestUrl).toString();
  const hit = cache.get(url);
  if (hit) return hit;
  const res = await fetchWithTimeout(url);
  if (res.status === 404) {
    const empty: PassageRow[] = []; // feed absent (no published PDFs) → treat as empty, not a failure
    cache.set(url, empty);
    return empty;
  }
  if (!res.ok) throw new Error(`passages fetch failed: ${res.status}`);
  const rows = (await res.json()) as PassageRow[];
  if (!Array.isArray(rows)) throw new Error("passages is not an array");
  cache.set(url, rows);
  return rows;
}
