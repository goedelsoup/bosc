/**
 * Pure geometry + colormap helpers for the scalar-field visualization (#1233,
 * epic #1237). No deck.gl / luma.gl / DOM imports — this module is the tested
 * core that both the GPU `FieldLayer` (fragment shader mirrors `rampAt`) and any
 * SSR/legend fallback share. The WebGL shader can't run in CI, so the load-bearing
 * math lives here and is exercised by `field.test.ts`.
 *
 * Grid convention (used identically by the raster shader and the isopleths):
 *   - `values` is row-major, length `width * height`; `values[row * width + col]`.
 *   - Row 0 is the NORTH (top) edge; column 0 is the WEST (left) edge.
 *   - `NaN` marks a no-data cell — it is never interpolated across and never contoured.
 *   - `bounds` is `[west, south, east, north]` (deck's `[left, bottom, right, top]`)
 *     when geo-referenced; absent for a bare cartesian (OrthographicView) field.
 */

export type RGB = [number, number, number];

/** A regular grid of scalar samples. */
export interface FieldGrid {
  /** Columns (nx). */
  width: number;
  /** Rows (ny). */
  height: number;
  /** Row-major samples, length `width * height`; `NaN` = no data. */
  values: number[] | Float32Array;
  /** `[west, south, east, north]` when geo-referenced; omit for cartesian. */
  bounds?: [number, number, number, number];
}

/** A contour edge as two fractional grid coordinates `[[col, row], [col, row]]`. */
export type Segment = [[number, number], [number, number]];

/** One irregular scalar sample, as accepted by {@link gridFromSamples}. */
export interface FieldSample {
  x: number;
  y: number;
  value: number;
}

/** Value at integer cell indices, clamped to the grid edges. */
export function cellValue(grid: FieldGrid, col: number, row: number): number {
  const c = Math.min(grid.width - 1, Math.max(0, col));
  const r = Math.min(grid.height - 1, Math.max(0, row));
  return grid.values[r * grid.width + c];
}

/**
 * Bilinear interpolation at fractional grid coordinates `(col, row)`. Coordinates
 * are clamped to the grid, so edge queries return the edge value. Returns `NaN`
 * if any contributing corner is no-data — the shader discards those texels too.
 */
export function bilinear(grid: FieldGrid, col: number, row: number): number {
  const cc = Math.min(grid.width - 1, Math.max(0, col));
  const rr = Math.min(grid.height - 1, Math.max(0, row));
  const c0 = Math.floor(cc);
  const r0 = Math.floor(rr);
  const c1 = Math.min(grid.width - 1, c0 + 1);
  const r1 = Math.min(grid.height - 1, r0 + 1);
  const fc = cc - c0;
  const fr = rr - r0;

  const v00 = grid.values[r0 * grid.width + c0];
  const v10 = grid.values[r0 * grid.width + c1];
  const v01 = grid.values[r1 * grid.width + c0];
  const v11 = grid.values[r1 * grid.width + c1];
  if (Number.isNaN(v00) || Number.isNaN(v10) || Number.isNaN(v01) || Number.isNaN(v11)) {
    return Number.NaN;
  }

  const top = v00 + (v10 - v00) * fc;
  const bottom = v01 + (v11 - v01) * fc;
  return top + (bottom - top) * fr;
}

/** Min/max over the finite (non-`NaN`) samples; `[0, 0]` for an all-empty grid. */
export function valueExtent(grid: FieldGrid): [number, number] {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const v of grid.values) {
    if (Number.isNaN(v)) continue;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  if (min > max) return [0, 0];
  return [min, max];
}

/** Normalize `v` into `[0, 1]` against `[min, max]`; a zero-width range maps to 0. */
export function normalize(v: number, min: number, max: number): number {
  if (max <= min) return 0;
  const t = (v - min) / (max - min);
  return t < 0 ? 0 : t > 1 ? 1 : t;
}

/** Component-wise linear blend of two colors. `t` is not clamped. */
export function mix(a: RGB, b: RGB, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

/**
 * The one-hue luminance ramp: `t` in `[0, 1]` maps low → mid → high (bone → forest
 * → ink). This is the exact function the fragment shader reproduces in GLSL, so the
 * SSR legend and the GPU raster agree.
 */
export function rampAt(t: number, low: RGB, mid: RGB, high: RGB): RGB {
  const c = t < 0 ? 0 : t > 1 ? 1 : t;
  return c < 0.5 ? mix(low, mid, c * 2) : mix(mid, high, (c - 0.5) * 2);
}

/** Linear crossing fraction of `level` between `a` and `b` (0 when `a === b`). */
function crossing(a: number, b: number, level: number): number {
  const d = b - a;
  return d === 0 ? 0 : (level - a) / d;
}

/**
 * Marching-squares isoline for a single `level`, returned as edge segments in
 * fractional grid coordinates. Cells touching a no-data corner are skipped. Saddle
 * cases (5, 10) are disambiguated by the cell-center average — the standard resolution.
 */
export function marchingSquares(grid: FieldGrid, level: number): Segment[] {
  const { width, height, values } = grid;
  const segments: Segment[] = [];

  for (let r = 0; r < height - 1; r++) {
    for (let c = 0; c < width - 1; c++) {
      const a = values[r * width + c]; // top-left
      const b = values[r * width + c + 1]; // top-right
      const e = values[(r + 1) * width + c + 1]; // bottom-right
      const d = values[(r + 1) * width + c]; // bottom-left
      if (Number.isNaN(a) || Number.isNaN(b) || Number.isNaN(d) || Number.isNaN(e)) continue;

      let idx = 0;
      if (a > level) idx |= 8;
      if (b > level) idx |= 4;
      if (e > level) idx |= 2;
      if (d > level) idx |= 1;
      if (idx === 0 || idx === 15) continue;

      // Crossing points on each of the four cell edges (only the referenced ones are used).
      const top: [number, number] = [c + crossing(a, b, level), r];
      const right: [number, number] = [c + 1, r + crossing(b, e, level)];
      const bottom: [number, number] = [c + crossing(d, e, level), r + 1];
      const left: [number, number] = [c, r + crossing(a, d, level)];

      const push = (p: [number, number], q: [number, number]): void => {
        segments.push([p, q]);
      };

      switch (idx) {
        case 1:
          push(left, bottom);
          break;
        case 2:
          push(bottom, right);
          break;
        case 3:
          push(left, right);
          break;
        case 4:
          push(top, right);
          break;
        case 5: {
          // Saddle: resolve with the center average.
          const center = (a + b + d + e) / 4;
          if (center > level) {
            push(left, top);
            push(bottom, right);
          } else {
            push(left, bottom);
            push(top, right);
          }
          break;
        }
        case 6:
          push(top, bottom);
          break;
        case 7:
          push(left, top);
          break;
        case 8:
          push(top, left);
          break;
        case 9:
          push(top, bottom);
          break;
        case 10: {
          const center = (a + b + d + e) / 4;
          if (center > level) {
            push(top, right);
            push(left, bottom);
          } else {
            push(top, left);
            push(bottom, right);
          }
          break;
        }
        case 11:
          push(top, right);
          break;
        case 12:
          push(left, right);
          break;
        case 13:
          push(bottom, right);
          break;
        case 14:
          push(left, bottom);
          break;
        default:
          break;
      }
    }
  }
  return segments;
}

/** `n` evenly spaced interior contour levels across `[min, max]` (endpoints excluded). */
export function contourLevels(min: number, max: number, n: number): number[] {
  if (n < 1 || max <= min) return [];
  const levels: number[] = [];
  for (let i = 1; i <= n; i++) levels.push(min + ((max - min) * i) / (n + 1));
  return levels;
}

/**
 * Map a fractional grid coordinate to a world position. Geo-referenced grids
 * (with `bounds`) return `[lng, lat]` — row 0 is north, so `lat` decreases with
 * `row`; bare grids return `[col, row]` for a cartesian view.
 */
export function gridToWorld(grid: FieldGrid, col: number, row: number): [number, number] {
  if (!grid.bounds) return [col, row];
  const [west, south, east, north] = grid.bounds;
  const u = grid.width > 1 ? col / (grid.width - 1) : 0;
  const v = grid.height > 1 ? row / (grid.height - 1) : 0;
  return [west + (east - west) * u, north - (north - south) * v];
}

/** Project a whole isoline segment to world coordinates via {@link gridToWorld}. */
export function segmentToWorld(grid: FieldGrid, seg: Segment): [[number, number], [number, number]] {
  return [gridToWorld(grid, seg[0][0], seg[0][1]), gridToWorld(grid, seg[1][0], seg[1][1])];
}

/**
 * Build a {@link FieldGrid} from irregular `{x, y, value}` samples laid out on a
 * regular lattice. Unique `x`s become columns (west→east) and unique `y`s become
 * rows (north→south). Missing cells are filled with `NaN`. Throws if the distinct
 * x/y counts don't multiply to the sample count (i.e. the lattice isn't regular).
 */
export function gridFromSamples(samples: FieldSample[]): FieldGrid {
  if (samples.length === 0) return { width: 0, height: 0, values: [] };

  const xs = [...new Set(samples.map((s) => s.x))].sort((p, q) => p - q);
  const ys = [...new Set(samples.map((s) => s.y))].sort((p, q) => q - p); // north (max y) first
  const width = xs.length;
  const height = ys.length;
  if (width * height !== samples.length) {
    throw new Error(
      `gridFromSamples: ${samples.length} samples do not form a regular ${width}×${height} lattice`,
    );
  }

  const colOf = new Map(xs.map((x, i) => [x, i]));
  const rowOf = new Map(ys.map((y, i) => [y, i]));
  const values = new Float32Array(width * height).fill(Number.NaN);
  for (const s of samples) {
    const col = colOf.get(s.x);
    const row = rowOf.get(s.y);
    if (col === undefined || row === undefined) continue;
    values[row * width + col] = s.value;
  }

  return {
    width,
    height,
    values,
    bounds: [xs[0], ys[ys.length - 1], xs[width - 1], ys[0]],
  };
}
