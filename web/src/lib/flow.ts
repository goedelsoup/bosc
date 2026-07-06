/**
 * Flow-field geometry helpers (epic #1237 / #1235) — pure, GPU-agnostic path math the
 * `FlowLayer` particle-advection layer builds on. Kept out of the layer (which pulls
 * deck.gl/luma.gl) so it unit-tests in plain Node.
 *
 * The core trick: `resamplePath` re-samples a reach polyline into `k` *evenly arc-length
 * spaced* vertices. Packed into a texture row, that lets the vertex shader map a particle's
 * phase `s ∈ [0,1)` straight to a vertex index (`s·(k-1)`) with a plain lerp — no per-fragment
 * arc-length search. Everything downstream (particle counts, speeds) is normalized here so the
 * island only has to hand over already-scaled magnitudes.
 */

/** A lon/lat vertex. */
export type LngLat = [number, number];

/** One reach ready to advect: its centerline plus the normalized flow encodings. */
export interface FlowReach {
  /** The reach node id (for keying / debugging). */
  id: string;
  /** The centerline, ordered head → downstream (lon, lat). */
  path: LngLat[];
  /** Advection speed, 0–1 (particles/sec along the normalized path); encodes flow magnitude. */
  speed: number;
  /** Particle density, 0–1; encodes flow magnitude (deficit reaches thin toward 0). */
  density: number;
  /** True when consumptive draw exceeds supply — draws oxblood + thins particles. */
  deficit: boolean;
}

/** Planar distance between two lon/lat points (degrees; monotone, fine for even spacing). */
function dist(a: LngLat, b: LngLat): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

/** Cumulative arc length at each vertex (`out[0] === 0`, `out[n-1] === total`). */
export function cumulativeLengths(path: LngLat[]): number[] {
  const out = [0];
  for (let i = 1; i < path.length; i++) out.push(out[i - 1] + dist(path[i - 1], path[i]));
  return out;
}

/** Total arc length of a polyline (0 for a <2-vertex path). */
export function pathLength(path: LngLat[]): number {
  if (path.length < 2) return 0;
  return cumulativeLengths(path).at(-1) ?? 0;
}

/** The lon/lat point at arc-length fraction `f ∈ [0,1]` of a polyline (clamped). */
export function pointAtFraction(path: LngLat[], f: number): LngLat {
  if (path.length === 0) return [0, 0];
  if (path.length === 1) return path[0];
  const cum = cumulativeLengths(path);
  const total = cum.at(-1) ?? 0;
  if (total === 0) return path[0];
  const target = Math.min(Math.max(f, 0), 1) * total;
  // Find the segment containing `target`.
  let i = 1;
  while (i < cum.length && cum[i] < target) i++;
  const seg = Math.min(i, path.length - 1);
  const segLen = cum[seg] - cum[seg - 1] || 1;
  const t = (target - cum[seg - 1]) / segLen;
  const a = path[seg - 1];
  const b = path[seg];
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/**
 * Re-sample a polyline into exactly `k` vertices evenly spaced by arc length (endpoints
 * included). A degenerate path (<2 vertices or zero length) is padded with its single point,
 * so the result is always length `k` — the texture row is never ragged.
 */
export function resamplePath(path: LngLat[], k: number): LngLat[] {
  if (k < 2) return path.slice(0, 1);
  const out: LngLat[] = [];
  for (let j = 0; j < k; j++) out.push(pointAtFraction(path, j / (k - 1)));
  return out;
}

/**
 * How many particles a reach carries, from its normalized `density`. Deficit reaches are
 * thinned to a third (a restrained, drying-up read — never zero, so the reach stays legible).
 * Always ≥ `min` on a live reach so a trickle still shows.
 */
export function particleCount(reach: FlowReach, maxPerReach: number, min = 2): number {
  const base = Math.round(reach.density * maxPerReach);
  const thinned = reach.deficit ? Math.round(base / 3) : base;
  return Math.max(min, thinned);
}

/** Clamp a raw magnitude ratio into the 0–1 encoding range (shared by speed + density). */
export function normalizeMagnitude(value: number, max: number, floor = 0.15): number {
  if (!(max > 0) || !Number.isFinite(value)) return floor;
  return Math.min(1, Math.max(floor, value / max));
}
