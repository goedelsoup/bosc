/**
 * Defense-nexus map model (#233 interactive layer for docs/defense-nexus.md).
 *
 * The essay's spine is a single discipline: geographic adjacency, a capability,
 * and a named market segment are an *inferred* connection — raised as a question,
 * never asserted. This build-time model backs the interactive companion that makes
 * that visible: the campus footprint and the JSMC (US-owned) footprint drawn on one
 * map, with the **measured gap between them computed from the cited geometry**.
 *
 * The number matters. The prose first reached for "two miles" / "the next parcels
 * over"; the parcels themselves say otherwise — the nearest campus and JSMC parcels
 * are ~5.5 mi apart, centers ~6.6 mi. Computing it here keeps the page honest and
 * keeps "proximity is not connection" landing on a real distance, not a vibe.
 *
 * Build-time only: imports the node:fs bundle loader (the island gets the result as
 * a prop, never imports this). Guarded on `hasFeed` so an incomplete bundle renders
 * the prose without crashing the build.
 */
import type { Feature, FeatureCollection, Polygon } from "geojson";
import { hasFeed } from "@watermark/core/bundle";
import { round } from "@watermark/core/format";
import { loadGeo } from "./geo";
import type { GeoProps } from "./geoStyle";

export type DnFactKey = "geography" | "capability" | "silence";

/** What the map emphasizes when a fact tab is active. */
export type DnEmphasis = "campus" | "jsmc" | "gap";

/** The register of a map annotation — the visual encoding matching the engine grammar
 *  (#272). `verified` = a labeled fact on the ground; `inference` = a capability whose
 *  bearing on Lima is inferred; `open` = an absence (the "no records" marker). */
export type DnRegister = import("@watermark/core/evidence").TagKind; // the canonical TagKind (#579)

/** A labeled annotation pinned to real geometry — never a connecting line. The capability
 *  pin carries its caveat inline; the silence marker sits exactly where an inferred line
 *  *would* go, so the gap reads as measured and empty (#267). */
export interface DnAnnotation {
  key: DnFactKey;
  position: [number, number];
  label: string;
  register: DnRegister;
}

export interface DnFact {
  key: DnFactKey;
  /** Short tab label. */
  tab: string;
  /** Detail heading. */
  title: string;
  /** The detail prose. */
  body: string;
  /** What the map highlights for this fact. */
  emphasis: DnEmphasis;
  /** Source citation (mono footnote). */
  cite: string;
}

export interface DnMetrics {
  /** Nearest parcel-edge distance, miles (1 dp). */
  nearestMi: number;
  /** Centroid-to-centroid distance, miles (1 dp). */
  centroidMi: number;
  /** The two nearest points [lon,lat] — endpoints of the on-map measurement line. */
  nearestPair: [[number, number], [number, number]];
  campusAcres: number;
  jsmcAcres: number;
  campusParcels: number;
  jsmcParcels: number;
}

export interface DnView {
  longitude: number;
  latitude: number;
  zoom: number;
}

export interface DefenseNexusData {
  /** False when the bundle lacks campus or jsmc (the page drops the map, keeps prose). */
  available: boolean;
  /** campus + jsmc features merged (the island filters by `properties.layer`). */
  geo: FeatureCollection<Polygon, GeoProps>;
  metrics: DnMetrics;
  view: DnView;
  facts: DnFact[];
  /** Map annotations, keyed to the active fact tab — labeled facts, never a line (#267). */
  annotations: DnAnnotation[];
  readout: { verified: string; open: string };
}

type Ring = [number, number][];
const R_MILES = 3958.7613;
const rad = (d: number): number => (d * Math.PI) / 180;

function haversineMi(a: [number, number], b: [number, number]): number {
  const [lon1, lat1] = a;
  const [lon2, lat2] = b;
  const dp = rad(lat2 - lat1);
  const dl = rad(lon2 - lon1);
  const h = Math.sin(dp / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dl / 2) ** 2;
  return 2 * R_MILES * Math.asin(Math.sqrt(h));
}

function outerRings(fc: FeatureCollection<Polygon, GeoProps>): Ring[] {
  return fc.features.map((f) => f.geometry.coordinates[0] as Ring);
}

/** Min vertex-to-vertex distance + the pair, in miles. The parcels are blocky and the
 *  separation is north–south, so vertex-nearest ≈ edge-nearest here (verified offline). */
function nearest(a: Ring[], b: Ring[]): { mi: number; pair: [[number, number], [number, number]] } {
  let mi = Number.POSITIVE_INFINITY;
  let pair: [[number, number], [number, number]] = [
    [0, 0],
    [0, 0],
  ];
  for (const ra of a) {
    for (const pa of ra) {
      for (const rb of b) {
        for (const pb of rb) {
          const d = haversineMi(pa as [number, number], pb as [number, number]);
          if (d < mi) {
            mi = d;
            pair = [pa as [number, number], pb as [number, number]];
          }
        }
      }
    }
  }
  return { mi, pair };
}

function centroid(rings: Ring[]): [number, number] {
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (const r of rings) {
    for (const [x, y] of r) {
      sx += x;
      sy += y;
      n += 1;
    }
  }
  return n ? [sx / n, sy / n] : [0, 0];
}

function bounds(rings: Ring[]): [number, number, number, number] {
  let w = Number.POSITIVE_INFINITY;
  let s = Number.POSITIVE_INFINITY;
  let e = Number.NEGATIVE_INFINITY;
  let n = Number.NEGATIVE_INFINITY;
  for (const r of rings) {
    for (const [x, y] of r) {
      if (x < w) w = x;
      if (x > e) e = x;
      if (y < s) s = y;
      if (y > n) n = y;
    }
  }
  return [w, s, e, n];
}

function fitView(b: [number, number, number, number]): DnView {
  const [w, s, e, n] = b;
  const latSpan = Math.max(0.002, n - s);
  const zoom = Math.min(13, Math.max(10, Math.log2(360 / (latSpan * 1.6))));
  return { longitude: (w + e) / 2, latitude: (s + n) / 2, zoom: round(zoom, 1) };
}

function acres(fc: FeatureCollection<Polygon, GeoProps>): number {
  const sum = fc.features.reduce((t, f) => t + (Number(f.properties.acreage) || 0), 0);
  return round(sum, 1);
}

function facts(m: DnMetrics): DnFact[] {
  return [
    {
      key: "geography",
      tab: "The geography",
      title: "The geography is real",
      body: `The Joint Systems Manufacturing Center — the Lima Army Tank Plant, operated by General Dynamics Land Systems — sits ${m.nearestMi.toFixed(1)} miles south of the campus, ${m.jsmcParcels} contiguous parcels totaling ~${Math.round(m.jsmcAcres)} acres, every one owned in the auditor's field by "UNITED STATES." It is on the parcel map. And it is only on the parcel map: a fact of geography, not a fact about the campus.`,
      emphasis: "jsmc",
      cite: "geo/jsmc.geojson · 5 parcels, owner UNITED STATES",
    },
    {
      key: "capability",
      tab: "The capability",
      title: "The capability is real",
      body: "The developer is Google, which has achieved IL-6 — the DoD impact level for data classified up to SECRET — and runs an air-gapped Distributed Cloud at IL-5. Before the same Ohio committee, AWS named the Department of War and the CIA among its government customers, and the relator tied the timing to Executive Order 14265. Every word of that is a capability Google holds everywhere it operates. None of it is a fact about Lima.",
      emphasis: "campus",
      cite: "relator testimony 2026-06-04 · DoD CC SRG · EO 14265",
    },
    {
      key: "silence",
      tab: "Proximity ≠ connection",
      title: "Nothing in the record draws the line",
      body: `Set the footprints down together and the temptation is to let ${m.nearestMi.toFixed(1)} miles of city collapse into a connection. The method forbids it, and so does the record: there is no contract, no filing, no dated communication naming both. The public-records request for any County ⇄ DoD / GDLS communications came back "No records." Google's own legislative testimony did not name Lima at all. The gap on this map is the finding — measured, and empty.`,
      emphasis: "gap",
      cite: 'response-index.yaml item 2 — "No records"',
    },
  ];
}

const EMPTY: DefenseNexusData = {
  available: false,
  geo: { type: "FeatureCollection", features: [] },
  metrics: {
    nearestMi: 0,
    centroidMi: 0,
    nearestPair: [
      [0, 0],
      [0, 0],
    ],
    campusAcres: 0,
    jsmcAcres: 0,
    campusParcels: 0,
    jsmcParcels: 0,
  },
  view: { longitude: -84.128, latitude: 40.748, zoom: 11 },
  facts: [],
  annotations: [],
  readout: { verified: "", open: "" },
};

/** The per-tab map annotations: a label on the JSMC parcels, a caveated capability pin on
 *  the campus, and a "No records" marker exactly where an inferred line would run. The map
 *  never draws that line — the marker is the absence made visible. */
function annotations(
  campusCentroid: [number, number],
  jsmcCentroid: [number, number],
  gapMid: [number, number],
): DnAnnotation[] {
  return [
    { key: "geography", position: jsmcCentroid, label: "Lima Army Tank Plant · GDLS", register: "verified" },
    {
      key: "capability",
      position: campusCentroid,
      label: "Google capability — held everywhere, not a Lima fact",
      register: "inference",
    },
    { key: "silence", position: gapMid, label: "No records (PRR item 2)", register: "open" },
  ];
}

/**
 * Build the defense-nexus map model from the bundle: campus + JSMC footprints and
 * the geometry-derived gap between them. Returns `available: false` (and the prose
 * facts) when either feed is missing so the page degrades rather than crashing.
 */
export function buildDefenseNexus(): DefenseNexusData {
  if (!hasFeed("geo/campus") || !hasFeed("geo/jsmc")) {
    const fallback = facts(EMPTY.metrics);
    return {
      ...EMPTY,
      facts: fallback,
      readout: {
        verified:
          "A federal plant a few miles from the campus, a developer cleared to SECRET, an industry that hosts the CIA — three true facts.",
        open: "None of them, alone or together, connects the Lima campus to a defense workload. The map data isn't in this bundle; the full report carries every claim to its source.",
      },
    };
  }

  const campus = loadGeo("geo/campus") as FeatureCollection<Polygon, GeoProps>;
  const jsmc = loadGeo("geo/jsmc") as FeatureCollection<Polygon, GeoProps>;
  const cr = outerRings(campus);
  const jr = outerRings(jsmc);
  const near = nearest(cr, jr);
  const metrics: DnMetrics = {
    nearestMi: round(near.mi, 1),
    centroidMi: round(haversineMi(centroid(cr), centroid(jr)), 1),
    nearestPair: near.pair,
    campusAcres: acres(campus),
    jsmcAcres: acres(jsmc),
    campusParcels: campus.features.length,
    jsmcParcels: jsmc.features.length,
  };
  const geo: FeatureCollection<Polygon, GeoProps> = {
    type: "FeatureCollection",
    features: [...campus.features, ...jsmc.features] as Feature<Polygon, GeoProps>[],
  };

  const [pa, pb] = near.pair;
  const gapMid: [number, number] = [(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2];

  return {
    available: true,
    geo,
    metrics,
    view: fitView(bounds([...cr, ...jr])),
    facts: facts(metrics),
    annotations: annotations(centroid(cr), centroid(jr), gapMid),
    readout: {
      verified: `A federal plant ${metrics.nearestMi.toFixed(1)} miles from the campus, a developer cleared to SECRET, an industry that hosts the CIA — three true facts.`,
      open: "None of them, alone or together, connects the Lima campus to a defense workload. What would close it — the facility's FedRAMP / DoD authorization posture — is not in the record.",
    },
  };
}
