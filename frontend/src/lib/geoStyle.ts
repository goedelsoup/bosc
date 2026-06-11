/**
 * Client-safe geo styling helpers shared by the corridor-map island and the
 * server-rendered legend. No `node:` imports here (the islands bundle this), so
 * the build-time feed loaders live separately in `geo.ts`.
 *
 * Styling is data-driven: per-feature `color` (hex) and `role` come straight off
 * the typed GeoJSON feeds (`bosc.site.feeds.GeoProperties`). The only presentation
 * chrome below is layer ordering / display names / default visibility — UI, not
 * corpus data.
 */
import type { Feature, Geometry } from "geojson";

export interface GeoProps {
  layer: string;
  label?: string;
  color?: string;
  role?: "area" | "line" | "point";
  radius?: number;
  scored?: boolean;
  water_flag?: "critical" | "elevated";
  [k: string]: unknown;
}
export type GeoFeature = Feature<Geometry, GeoProps>;
export type RGBA = [number, number, number, number];

/** Draw order (areas first, points last) and friendly per-layer names. The
 *  watershed boundary draws first so it sits underneath as context. */
export const LAYER_ORDER = [
  "watershed",
  "floodplain",
  "floodway",
  "corridor",
  "campus",
  "jsmc",
  "roadwork",
  "wwtp",
  "rsei",
] as const;

export const LAYER_LABELS: Record<string, string> = {
  watershed: "Watershed boundary (USGS WBD)",
  floodplain: "FEMA floodplain",
  floodway: "FEMA floodway",
  corridor: "Corridor study area",
  campus: "Campus footprint",
  jsmc: "JSMC (US-owned)",
  roadwork: "Roadwork centerline",
  wwtp: "WWTP NPDES points",
  rsei: "RSEI facilities",
};

/** Layers off by default (the heavy county-wide overlay), matching the legacy map. */
export const DEFAULT_OFF = new Set(["rsei"]);

export function layerLabel(layer: string): string {
  return LAYER_LABELS[layer] ?? layer;
}

/** Parse "#rrggbb" (or "#rgb") to [r,g,b]; falls back to slate grey. */
export function hexToRgb(hex: string | undefined): [number, number, number] {
  if (!hex) return [120, 120, 130];
  let h = hex.replace("#", "").trim();
  if (h.length === 3)
    h = h
      .split("")
      .map((c) => c + c)
      .join("");
  const n = parseInt(h, 16);
  if (Number.isNaN(n) || h.length !== 6) return [120, 120, 130];
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function rgba(hex: string | undefined, alpha: number): RGBA {
  const [r, g, b] = hexToRgb(hex);
  return [r, g, b, alpha];
}

/** Distinct layers present in a feature set, in canonical draw order. */
export function layersPresent(features: GeoFeature[]): string[] {
  const present = new Set(features.map((f) => f.properties.layer));
  const ordered = LAYER_ORDER.filter((l) => present.has(l)) as string[];
  for (const l of present) if (!ordered.includes(l)) ordered.push(l);
  return ordered;
}
