/**
 * Network locator-map geometry (#2034, epic #2033) — the projection behind the homepage map.
 *
 * Pure + SSR, in the idiom of its neighbour `charts.ts`: this module owns the *geometry*, the
 * `NetworkMap.astro` component is a thin SVG template over it, and there is **no client JS**.
 * `@watermark/viz` quarantines deck.gl/MapLibre so the otherwise zero-framework site never loads
 * it, and the map's first mount is `/` — a network-global page. A locator does not need pan/zoom,
 * and buying it with several hundred KB of JS on the front door is the wrong trade.
 *
 * ## The projection
 *
 * Equirectangular with a cos(φ) correction at a standard parallel. The network spans ~3.6° of
 * latitude by ~5.0° of longitude; over a box that small the distortion of anything fancier is
 * below the width of a marker, so a projection library would be false precision. The scale is
 * **uniform** in x and y (one `scale`, not two) — an anisotropic fit would stretch the state to
 * whatever aspect the layout wanted and quietly lie about distance.
 *
 * Latitude increases north and SVG `y` increases down, so y inverts. That is the single easiest
 * thing here to get backwards, and it has its own test.
 *
 * ## Why the outline is projected rather than drawn
 *
 * The state border and the continental divide ship below as coarse lat/lon vertex lists and go
 * through the **same** {@link project} as the markers.
 *
 * This is the point of the module. A hand-drawn SVG path and a projected dot can disagree, and
 * the failure mode is a site rendering visually outside its own state — a map wrong in exactly
 * the way a map must not be. `basin.astro`'s schematic avoids this only by hand-placing its
 * markers too (a `MAP_XY` table keyed by slug), which does not survive 38 sites and does not
 * move when a site is registered. Projecting both through one function makes the whole class of
 * error impossible by construction.
 *
 * The geometry is still **simplified** — ~40 vertices for a border with thousands, a divide
 * traced to the county rather than the ridge — and every surface that renders it is required to
 * caption it as such. Simplified is not the same as misregistered, and only the second one is a
 * defect.
 *
 * ## What it refuses to do
 *
 * A site with no coordinates comes back in {@link NetworkMapModel.unplaced}, named. It is never
 * dropped and never guessed onto the map. 12 of the 38 registry entries carry `map_lat: null`
 * (all `tracking`, pending #2037), and a map that silently showed the other 26 under the caption
 * "the network" would claim a completeness it does not have — the same discipline as `/network`'s
 * "a dash is unmeasured, 0 is a measured none".
 */
import type { DivideKey } from "@watermark/core/placement";

/**
 * The build-phase vocabulary, restated rather than imported.
 *
 * It is `SiteStatus` in `@watermark/core/sites` — but that module reaches `./bundle`, which reads
 * `node:fs`, and this package's tsconfig sets `"types": []` precisely to keep the chart library
 * DOM-free and node-free. Importing the type would drag the bundle reader into the geometry
 * package's type graph to borrow a four-member union.
 *
 * The duplication is guarded, not trusted: `src/lib/networkMap.test.ts` asserts this union and
 * `SiteStatus` still name the same four phases, so adding a fifth to the registry fails there
 * rather than silently widening what the map will accept.
 */
export type MapPhase = "live" | "building" | "queued" | "tracking";

/**
 * A site this module can place — the slice of the registry the map reads, structural rather than
 * a `NetworkSite` import, in the idiom of `placement.ts`'s `Placeable`. The caller resolves
 * `divide` (via `basinForSlug`) and `open` (registry `selectable`) so this module needs no
 * registry lookups of its own and stays trivially testable.
 */
export interface MappableSite {
  slug: string;
  /** Display name of the place, e.g. "Lima". */
  place: string;
  /** Switcher badge — the site's codename, or its three-letter mono. */
  badge: string;
  /** Receiving-water / sub-basin subline, e.g. "Ottawa River · Lima, OH". */
  basin: string;
  /** Major-basin slug (`maumee`, `scioto`, …) — a filter axis for #2038. */
  basinMajor: string;
  /** Which side of the continental divide the site's basin drains to. */
  divide: DivideKey;
  /** Build phase — drives the marker fill. */
  status: MapPhase;
  /** Where the marker links: the registry href, the same one the switcher and scorecard use. */
  href: string;
  /** Can a reader actually enter this site today? Drives the map's one forest signal. */
  open: boolean;
  /**
   * The site's coordinate, or `null` when the registry has none.
   *
   * ⚠️ This is `map_lat`/`map_lon` from `data/sites.yaml` — a **default DeckGL viewport centre**,
   * i.e. the town. It is NOT a facility location, and for most of these sites the record makes no
   * siting claim at all. Every surface rendering a marker is required to label it as the place.
   */
  point: { lat: number; lon: number } | null;
}

/** A placed site: its input row, plus where it lands in the SVG. */
export interface NetworkMapMarker extends MappableSite {
  point: { lat: number; lon: number };
  x: number;
  y: number;
  /**
   * Where this marker's always-on badge goes — or that it cannot be drawn at all (#2044).
   *
   * Only `open` markers carry a badge at rest; the others reveal one on hover, transiently, and
   * are never placed. Where the network clusters, a default-above badge collides: Sidney's square
   * sits in Troy-Piqua's label, and at the compact instance's scale that renders as a codename
   * with a box through it.
   *
   * A single "flip it below" pass does NOT converge — it moved Bowling Green's badge straight into
   * Findlay's. So placement is greedy over a stable order: try above, then below, and if neither
   * is clear of every marker square and every already-placed label, emit `"none"`.
   *
   * `"none"` is the honest terminal state, not a failure. The site keeps its marker, its link, its
   * tooltip and its accessible name — only the painted codename is withheld, because two codenames
   * drawn through each other name neither site. Resolved here rather than nudged in CSS because it
   * depends on where sites actually are, which changes whenever one is registered.
   */
  badgePlacement: "above" | "below" | "none";
}

/** A projected polyline, carried as both points and a ready `d` attribute. */
export interface MapPath {
  points: readonly { x: number; y: number }[];
  d: string;
}

export interface NetworkMapModel {
  width: number;
  height: number;
  viewBox: string;
  /** Every site with a coordinate, in input order. */
  markers: readonly NetworkMapMarker[];
  /** Every site without one, in input order — rendered as an off-map list, never dropped. */
  unplaced: readonly MappableSite[];
  /** The Ohio border, closed. */
  outline: MapPath;
  /** The Michigan/Indiana border west of Ohio — open, because Indiana continues off-frame. */
  frame: MapPath;
  /**
   * The Lake Erie / Ohio River continental divide, open at both ends.
   *
   * The line only. It carried two on-map drainage labels through three iterations and they were
   * cut: every anchor that cleared the line and the markers at one moment was overrun the moment
   * #2037 backfilled twelve more sites, and "Lake Erie drainage" ended up struck through Akron's
   * badge. A label that must be re-tuned whenever a site is registered is a maintenance trap on a
   * component whose whole point is that new sites place themselves. The drainage is explained in
   * the key instead, in a sentence, which is both collision-proof and clearer than two floating
   * labels — see `NetworkMap.astro`.
   */
  divide: MapPath;
  /**
   * Faint state labels, so the frame reads as geography rather than a floating shape. Indiana
   * only — see the note at its construction below.
   */
  stateLabels: readonly { code: string; label: string; x: number; y: number }[];
  bounds: MapBounds;
  /** Degrees of latitude per SVG unit — lets a caller size a marker in real terms if it wants. */
  scale: number;
}

export interface MapBounds {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

/**
 * The map frame. Wider than the sites alone: it has to contain the whole Ohio border (down to the
 * southern tip at 38.40°N, east to the Pennsylvania line at −80.52°) plus enough Indiana west of
 * the state line to seat Fort Wayne (−85.14°) without it touching the edge.
 */
export const MAP_BOUNDS: MapBounds = {
  minLat: 38.34,
  maxLat: 42.04,
  minLon: -85.45,
  maxLon: -80.36,
};

/** Standard parallel for the cos(φ) x-correction — mid-frame, ≈ 40.2°N. */
export const STANDARD_PARALLEL = 40.2;

/** Padding inside the viewBox, in SVG units, so edge markers have room for their labels. */
const PAD = 16;

/*
 * Label-placement geometry, in viewBox units, derived from the glyph rather than guessed.
 *
 * All of it is sized to the COMPACT instance, which is the larger of the two renderings: it hangs
 * a 10px badge at `y − RING − 3` with `RING` = 8, over a marker of half-width 5. Reserving a
 * little more room than the full-size instance needs costs at most a label placed below where it
 * would also have fit above; reserving less would let a codename be drawn through a square.
 */
const MARKER_HALF = 5.5;
const BADGE_TEXT_H = 10;
const BADGE_CHAR_W = 6.2;
/** Baseline offset from the marker centre, above and below. */
const BADGE_UP = 11;
const BADGE_DOWN = 18;

interface Box {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

const hits = (a: Box, b: Box): boolean => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0;

const badgeBox = (m: { x: number; badge: string }, baselineY: number): Box => {
  const halfW = Math.max(12, (m.badge.length * BADGE_CHAR_W) / 2);
  return { x0: m.x - halfW, x1: m.x + halfW, y0: baselineY - BADGE_TEXT_H, y1: baselineY + 2 };
};

/**
 * Greedy label placement over the markers that carry an always-on badge.
 *
 * Every marker square is an obstacle from the start — including the ones whose own badges only
 * appear on hover — and each label that lands becomes one too, so no two placed labels can
 * overlap. Order is by `y` then `x`: stable, independent of registry order, and it resolves a
 * vertical cluster top-down the way a reader scans it.
 */
function placeBadges(markers: NetworkMapMarker[]): void {
  const occupied: Box[] = markers.map((m) => ({
    x0: m.x - MARKER_HALF,
    x1: m.x + MARKER_HALF,
    y0: m.y - MARKER_HALF,
    y1: m.y + MARKER_HALF,
  }));

  for (const m of [...markers].sort((a, b) => a.y - b.y || a.x - b.x)) {
    // Only `open` markers are labelled at rest; the rest reveal a badge on hover, transiently,
    // and a transient label is allowed to overlap whatever it lands on.
    if (!m.open) continue;
    const above = badgeBox(m, m.y - BADGE_UP);
    const below = badgeBox(m, m.y + BADGE_DOWN);
    if (!occupied.some((b) => hits(above, b))) {
      m.badgePlacement = "above";
      occupied.push(above);
    } else if (!occupied.some((b) => hits(below, b))) {
      m.badgePlacement = "below";
      occupied.push(below);
    } else {
      m.badgePlacement = "none";
    }
  }
}

const K = Math.cos((STANDARD_PARALLEL * Math.PI) / 180);

/**
 * The Ohio border, clockwise from the northwest corner — ~40 vertices for a boundary with many
 * thousands. Lake Erie's shore, the Pennsylvania meridian, the Ohio River, and the Indiana line.
 *
 * Coarse on purpose: this is presentational geography at ~1px per 0.01°, and its job is to let a
 * reader place a marker in a state, not to survey one. It is captioned as simplified wherever it
 * renders. See the module note on why it is projected rather than drawn.
 */
const OHIO: readonly (readonly [number, number])[] = [
  [41.7, -84.8], // NW corner — the Ohio/Indiana/Michigan tripoint
  [41.72, -84.35],
  [41.73, -83.85],
  [41.73, -83.45], // the Michigan line meets Maumee Bay
  [41.62, -83.32], // Toledo / the bay shore
  [41.68, -83.1],
  [41.6, -82.95], // Port Clinton
  [41.53, -82.73], // Marblehead
  [41.44, -82.68], // Sandusky Bay
  [41.4, -82.5], // Huron
  [41.42, -82.2], // Lorain
  [41.49, -81.94],
  [41.51, -81.7], // Cleveland
  [41.58, -81.45],
  [41.75, -81.28], // Fairport Harbor
  [41.86, -80.95],
  [41.92, -80.75], // Ashtabula
  [41.98, -80.52], // Conneaut — the Pennsylvania line meets the lake
  [41.35, -80.52], // south along the Pennsylvania meridian
  [40.64, -80.52], // the meridian meets the Ohio River at East Liverpool
  [40.52, -80.63],
  [40.16, -80.7], // Steubenville
  [39.92, -80.75],
  [39.72, -80.87],
  [39.55, -81.03],
  [39.42, -81.45], // Marietta
  [39.22, -81.72],
  [39.03, -81.92],
  [38.85, -82.15], // Gallipolis
  [38.68, -82.3],
  [38.42, -82.6], // the southern tip, at the Kentucky/West Virginia meeting
  [38.6, -82.85],
  [38.73, -83.0], // Portsmouth
  [38.63, -83.3],
  [38.61, -83.65], // the Ohio Brush Creek mouth
  [38.79, -84.05],
  [38.92, -84.28],
  [39.1, -84.51], // Cincinnati
  [39.1, -84.82], // the Indiana line meets the Ohio River
  [39.5, -84.81], // north along the Indiana line
  [40.2, -84.8],
  [41.0, -84.8],
];

/**
 * The Michigan/Indiana border, running west from Ohio's northwest corner to the frame edge.
 *
 * Deliberately open-ended rather than a closed Indiana: Fort Wayne is the network's one
 * non-Ohio site, and drawing the whole state to seat a single marker would give three-quarters
 * of the frame to geography the network has nothing in. An edge that runs off-frame says
 * "the map continues here", which is true.
 */
const INDIANA_EDGE: readonly (readonly [number, number])[] = [
  [41.7, -84.8],
  [41.76, -84.8],
  [41.76, -85.45],
];

/**
 * The Lake Erie / Ohio River continental divide — the network's real organizing geography, and
 * the axis `placement.ts` already sorts every basin along.
 *
 * Traced to the county, not the ridge. Its accountability is the test rather than the vertex
 * list: `networkMap.test.ts` asserts every `erie`-draining site lands north of this line and
 * every `ohio`-draining one south, using each site's own registry basin. A schematic that
 * contradicted the registry it is drawn beside would be worse than no line at all.
 */
const DIVIDE: readonly (readonly [number, number])[] = [
  [40.45, -84.8],
  [40.38, -84.4],
  [40.3, -84.0],
  [40.36, -83.7],
  [40.5, -83.4],
  [40.68, -83.05],
  [40.78, -82.7],
  [40.88, -82.35],
  [40.97, -82.0],
  [41.02, -81.75],
  [41.0, -81.52], // Akron sits astride the divide at the Portage Path; the line passes just south
  [41.1, -81.15],
  [41.22, -80.8],
  [41.32, -80.52],
];

/**
 * The projector for a frame: `(lat, lon) → {x, y}` in SVG units, plus the height that frame
 * implies at the given width. Exported so a caller can place its own annotation in map space
 * rather than guessing pixels.
 */
export function projector(
  bounds: MapBounds,
  width: number,
  pad = PAD,
): { project: (lat: number, lon: number) => { x: number; y: number }; height: number; scale: number } {
  const xSpan = (bounds.maxLon - bounds.minLon) * K;
  const ySpan = bounds.maxLat - bounds.minLat;
  // One scale for both axes. Two would fit the frame exactly and distort every distance on it.
  const scale = (width - 2 * pad) / xSpan;
  const height = ySpan * scale + 2 * pad;
  const project = (lat: number, lon: number): { x: number; y: number } => ({
    x: pad + (lon - bounds.minLon) * K * scale,
    // y inverts: latitude climbs north, SVG y climbs south.
    y: pad + (bounds.maxLat - lat) * scale,
  });
  return { project, height, scale };
}

const round = (n: number): number => Math.round(n * 100) / 100;

function toPath(
  vertices: readonly (readonly [number, number])[],
  project: (lat: number, lon: number) => { x: number; y: number },
  close: boolean,
): MapPath {
  const points = vertices.map(([lat, lon]) => project(lat, lon));
  const d =
    points.map((p, i) => `${i === 0 ? "M" : "L"}${round(p.x)},${round(p.y)}`).join(" ") + (close ? " Z" : "");
  return { points, d };
}

/**
 * Build the locator map: project every placeable site, the border, the frame edge, and the
 * divide into one SVG coordinate system.
 *
 * `width` sets the viewBox width; the height follows from the frame's aspect so the projection
 * stays uniform. Sites arrive in whatever order the caller supplies and leave in that order —
 * ranking is a presentation decision, not a geometric one.
 */
export function buildNetworkMap(
  sites: readonly MappableSite[],
  opts: { width?: number; bounds?: MapBounds; pad?: number } = {},
): NetworkMapModel {
  const width = opts.width ?? 640;
  const bounds = opts.bounds ?? MAP_BOUNDS;
  const { project, height, scale } = projector(bounds, width, opts.pad);

  const markers: NetworkMapMarker[] = [];
  const unplaced: MappableSite[] = [];
  for (const s of sites) {
    // No coordinate, no marker — and no guess. The site goes to `unplaced` by name.
    if (!s.point) {
      unplaced.push(s);
      continue;
    }
    const { x, y } = project(s.point.lat, s.point.lon);
    markers.push({ ...s, point: s.point, x, y, badgePlacement: "above" });
  }

  placeBadges(markers);

  const divide = toPath(DIVIDE, project, false);

  /**
   * Indiana only.
   *
   * Ohio's own label was tried and cut: every interior spot quiet enough to hold it is a spot a
   * site will eventually occupy, and near the border it collides with the outline. The shape is
   * unmistakable and the surrounding page names the network anyway. Indiana earns its place for
   * the opposite reason — it is the only thing telling a reader what the one marker outside the
   * state outline is sitting in.
   */
  const stateLabels = [{ code: "IN", label: "INDIANA", ...project(41.45, -85.3) }];

  return {
    width,
    height: round(height),
    viewBox: `0 0 ${width} ${round(height)}`,
    markers,
    unplaced,
    outline: toPath(OHIO, project, true),
    frame: toPath(INDIANA_EDGE, project, false),
    divide,
    stateLabels,
    bounds,
    scale,
  };
}

/**
 * The latitude of the divide at a given longitude, by linear interpolation between its vertices —
 * the predicate behind the drainage test, and the honest way to ask "is this site north or south
 * of the line as drawn" without eyeballing a rendered SVG.
 *
 * Returns `null` outside the divide's longitude span, where the question has no answer.
 */
export function divideLatAt(lon: number): number | null {
  for (let i = 0; i < DIVIDE.length - 1; i++) {
    const [latA, lonA] = DIVIDE[i];
    const [latB, lonB] = DIVIDE[i + 1];
    const [lo, hi] = lonA <= lonB ? [lonA, lonB] : [lonB, lonA];
    if (lon < lo || lon > hi) continue;
    if (lonB === lonA) return latA;
    return latA + ((lon - lonA) / (lonB - lonA)) * (latB - latA);
  }
  return null;
}
