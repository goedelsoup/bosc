/**
 * Build-time geo feed access (imports the node:fs bundle loader, so this is NOT
 * client-safe — islands use `geoStyle.ts` instead). Reads the typed GeoJSON feeds
 * and merges them for the corridor map endpoint.
 */
import type { FeatureCollection } from "geojson";
import { loadFeed, loadManifest } from "./bundle";
import type { GeoFeature } from "./geoStyle";

// The imagery feed is the time-slider's data (an AOI footprint + the Wayback
// ladder in its meta), not a corridor-map layer — keep it out of the merge.
const MERGE_EXCLUDE = new Set(["geo/imagery"]);

/** Manifest names of the geo layer feeds (e.g. "geo/campus"). */
export function geoFeedNames(): string[] {
  return loadManifest()
    .feeds.filter((f) => f.kind === "geojson")
    .map((f) => f.name);
}

/** One geo layer feed as a GeoJSON FeatureCollection (meta preserved). */
export function loadGeo(name: string): FeatureCollection {
  return loadFeed<FeatureCollection>(name);
}

/** The corridor + watershed map's source: every geo layer feed merged into one
 *  FeatureCollection (minus the imagery feed, which drives the slider). */
export function mergedGeo(): FeatureCollection {
  const features: GeoFeature[] = [];
  for (const name of geoFeedNames()) {
    if (MERGE_EXCLUDE.has(name)) continue;
    const fc = loadGeo(name);
    features.push(...(fc.features as GeoFeature[]));
  }
  return { type: "FeatureCollection", features };
}
