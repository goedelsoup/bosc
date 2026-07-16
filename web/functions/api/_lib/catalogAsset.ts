// Load the build-time hydrated catalog (`/stories-catalog.json`, emitted by
// src/pages/stories-catalog.json.ts) as a static asset from the same origin, and build the pure
// `Catalog` the Story write path resolves handles against (#1093/#1095). Mirrors askIndexLoad: the
// asset is immutable per deploy, so the parsed catalog is cached in module scope (one fetch + parse
// per isolate). The Worker can't read the bundle off disk, so this is how server-side handle
// validation gets its catalog at runtime.

import { type Catalog, type CatalogAtom, catalogFromAtoms } from "@watermark/core/catalog";
import { fetchWithTimeout } from "./http";

interface CatalogAsset {
  site: string;
  version: string;
  atoms: CatalogAtom[];
}

let cached: Catalog | null = null;

/** Test seam: drop the isolate cache. */
export function _resetCatalogCache(): void {
  cached = null;
}

/**
 * Load the catalog. `assetUrl` overrides the default same-origin asset URL (e.g. `STORIES_CATALOG_URL`).
 * Throws if the asset is missing or malformed — the route turns that into a 500 (misconfigured deploy).
 */
export async function loadCatalogAsset(requestUrl: string, assetUrl?: string): Promise<Catalog> {
  if (cached) return cached;
  const url = assetUrl ?? new URL("/stories-catalog.json", requestUrl).toString();
  const res = await fetchWithTimeout(url);
  if (!res.ok) throw new Error(`stories-catalog fetch failed: ${res.status}`);
  const data = (await res.json()) as CatalogAsset;
  if (!data || !Array.isArray(data.atoms)) throw new Error("stories-catalog is malformed");
  cached = catalogFromAtoms(data.site, data.version, data.atoms);
  return cached;
}
