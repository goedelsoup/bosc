// Fetch the build-time documents feed (`/feeds/documents.json`) and project its version /
// duplicate-cluster metadata (#1590) into a compact `rel -> VersionInfo` map for retrieval dedup.
// Parallel to passagesLoad.ts / askIndexLoad.ts: the asset is immutable per deploy, so caching the
// derived map across requests in one Workers isolate is safe. The documents feed always exists, but
// carries the version fields only for clustered documents (from the curated custody manifest); a
// feed with no clustered documents yields an empty map, so dedup is a no-op there.

import { fetchWithTimeout } from "./http";

/** The version/cluster facts a dedup pass needs about one catalogued document. */
export interface VersionInfo {
  /** Stable duplicate-cluster id (e.g. "oepa:2PH00006"). */
  cluster: string;
  /** Rel of the cluster's canonical (authoritative) member. */
  canonical: string;
  /** This member's version label ("final" | "draft" | "fact_sheet" | "duplicate" | …), or null. */
  version: string | null;
  /** Whether this rel is the cluster's canonical member. */
  isCanonical: boolean;
}

/** The shape we read off each documents-feed entry (a subset of DocumentItem). */
interface DocEntry {
  rel: string;
  duplicate_cluster?: string | null;
  canonical_document_id?: string | null;
  version?: string | null;
}
interface DocCollection {
  entries?: DocEntry[];
}

// Keyed by resolved URL so a per-site override never returns another site's cached map.
const cache = new Map<string, Map<string, VersionInfo>>();

/** Test seam: drop the isolate cache. */
export function _resetDocVersionsCache(): void {
  cache.clear();
}

/** Build the `rel -> VersionInfo` map from a parsed documents feed (clustered entries only). */
function buildMap(collections: DocCollection[]): Map<string, VersionInfo> {
  const map = new Map<string, VersionInfo>();
  for (const coll of collections) {
    for (const e of coll.entries ?? []) {
      if (!e.duplicate_cluster || !e.canonical_document_id) continue;
      map.set(e.rel, {
        cluster: e.duplicate_cluster,
        canonical: e.canonical_document_id,
        version: e.version ?? null,
        isCanonical: e.rel === e.canonical_document_id,
      });
    }
  }
  return map;
}

/**
 * Load the documents feed and return its version/cluster map. `indexUrl` overrides the default
 * same-origin asset URL. An absent feed (404) yields an empty map (dedup no-op); other fetch/parse
 * failures throw (a misconfigured deploy), matching passagesLoad's posture.
 */
export async function loadDocVersions(
  requestUrl: string,
  indexUrl?: string,
): Promise<Map<string, VersionInfo>> {
  const url = indexUrl ?? new URL("/feeds/documents.json", requestUrl).toString();
  const hit = cache.get(url);
  if (hit) return hit;
  const res = await fetchWithTimeout(url);
  if (res.status === 404) {
    const empty = new Map<string, VersionInfo>();
    cache.set(url, empty);
    return empty;
  }
  if (!res.ok) throw new Error(`documents feed fetch failed: ${res.status}`);
  const collections = (await res.json()) as DocCollection[];
  if (!Array.isArray(collections)) throw new Error("documents feed is not an array");
  const map = buildMap(collections);
  cache.set(url, map);
  return map;
}

/**
 * Fail-open variant: any fetch/parse failure degrades to an empty map. Dedup is a retrieval
 * refinement, not an essential like the ask-index, so a search must never hard-fail on it.
 */
export async function loadDocVersionsSafe(
  requestUrl: string,
  indexUrl?: string,
): Promise<Map<string, VersionInfo>> {
  try {
    return await loadDocVersions(requestUrl, indexUrl);
  } catch {
    return new Map<string, VersionInfo>();
  }
}
