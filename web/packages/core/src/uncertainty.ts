/**
 * The shared uncertainty engine (epic #271 / #272) — client-safe, dependency-free.
 *
 * The #233 narratives all end `[open]` for the same reason: a withheld figure, a
 * non-binding estimate, or a modeled screen. This engine makes the *unknown* the thing
 * the reader manipulates, and prices the opacity. Three signature moves every consumer
 * composes from these primitives:
 *   1. simulate the unknowns — Monte-Carlo over the priors → a band, never a point;
 *   2. disclosure collapses the band — pin a prior to a disclosed value, watch it tighten;
 *   3. tornado — rank the unknowns by how much each one alone moves the outcome.
 *
 * Reproducibility is load-bearing: a seeded mulberry32 PRNG means the build precomputes a
 * representative result for the SSR / no-JS fallback and the island reproduces it exactly
 * — no `Math.random`, no fork between server and client. Everything here is pure.
 */

/** Evidence register for the uncertainty engine. A deliberate dialect of the canonical
 *  `TagKind` (`./evidence`, #579): `assumption` stands in for `inference` because the engine's
 *  inputs are cited *bounds*, not a single labelled reading. Kept distinct on purpose. */
export type Register = "verified" | "assumption" | "open";

/** A prior's shape: a disclosed point, a bounded (cited) band, or a wide-open range. */
export type Dist =
  | { kind: "fixed"; value: number } // [verified] — a disclosed/known value
  | { kind: "triangular"; low: number; central: number; high: number } // [assumption] — cited bounds
  | { kind: "uniform"; low: number; high: number }; // [open] — wide until disclosed

/** One uncertain input. `register` drives the visual encoding; `source` cites the bound;
 *  `resolvingRecord` names the record whose disclosure would collapse it. */
export interface Prior {
  key: string;
  label: string;
  register: Register;
  dist: Dist;
  unit?: string;
  source?: string;
  resolvingRecord?: string;
}

/** A model maps one sampled draw (`{key: value}`) to an outcome number. */
export type Model = (draw: Record<string, number>) => number;

// --- distribution helpers ----------------------------------------------------
/** The reference (central) value of a distribution. */
export function central(dist: Dist): number {
  switch (dist.kind) {
    case "fixed":
      return dist.value;
    case "triangular":
      return dist.central;
    case "uniform":
      return (dist.low + dist.high) / 2;
  }
}

/** The band edges [low, high] of a distribution (a fixed value has zero width). */
export function bounds(dist: Dist): [number, number] {
  switch (dist.kind) {
    case "fixed":
      return [dist.value, dist.value];
    case "triangular":
      return [dist.low, dist.high];
    case "uniform":
      return [dist.low, dist.high];
  }
}

/** Inverse-CDF sample of a distribution given a uniform `u` in [0, 1). */
export function quantile(dist: Dist, u: number): number {
  switch (dist.kind) {
    case "fixed":
      return dist.value;
    case "uniform":
      return dist.low + u * (dist.high - dist.low);
    case "triangular": {
      const { low, central: c, high } = dist;
      if (high === low) return low;
      const f = (c - low) / (high - low);
      return u < f
        ? low + Math.sqrt(u * (high - low) * (c - low))
        : high - Math.sqrt((1 - u) * (high - low) * (high - c));
    }
  }
}

// --- seeded PRNG (mulberry32) -------------------------------------------------
/** Deterministic PRNG: same seed ⇒ same stream ⇒ same percentiles (SSR == island). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** The default seed (the golden ratio constant), so every consumer reproduces the same run. */
export const DEFAULT_SEED = 0x9e3779b9;

// --- Monte-Carlo --------------------------------------------------------------
/** Draw `n` outcomes by sampling every prior independently and applying `model`. */
export function sample(priors: Prior[], model: Model, n = 8000, seed = DEFAULT_SEED): number[] {
  const rng = mulberry32(seed);
  const out = new Array<number>(n);
  for (let i = 0; i < n; i++) {
    const draw: Record<string, number> = {};
    for (const p of priors) draw[p.key] = quantile(p.dist, rng());
    out[i] = model(draw);
  }
  return out;
}

export interface HistogramBin {
  x0: number;
  x1: number;
  n: number;
}

export interface Summary {
  p10: number;
  p50: number;
  p90: number;
  mean: number;
  min: number;
  max: number;
  bins: HistogramBin[];
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return Number.NaN;
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.round(p * (sorted.length - 1))));
  return sorted[idx];
}

/** Percentiles + an equal-width histogram over the sampled outcomes. */
export function summarize(outcomes: number[], binCount = 24): Summary {
  const sorted = [...outcomes].sort((a, b) => a - b);
  const min = sorted[0] ?? Number.NaN;
  const max = sorted[sorted.length - 1] ?? Number.NaN;
  const mean = outcomes.reduce((a, b) => a + b, 0) / (outcomes.length || 1);
  const bins: HistogramBin[] = [];
  const width = max > min ? (max - min) / binCount : 1;
  for (let i = 0; i < binCount; i++) {
    bins.push({ x0: min + i * width, x1: min + (i + 1) * width, n: 0 });
  }
  for (const v of outcomes) {
    const i = max > min ? Math.min(binCount - 1, Math.floor((v - min) / width)) : 0;
    bins[i].n++;
  }
  return {
    p10: percentile(sorted, 0.1),
    p50: percentile(sorted, 0.5),
    p90: percentile(sorted, 0.9),
    mean,
    min,
    max,
    bins,
  };
}

// --- tornado (sensitivity) ----------------------------------------------------
export interface TornadoBar {
  key: string;
  label: string;
  register: Register;
  low: number; // outcome with this prior at its low bound (others central)
  high: number; // ...at its high bound
  swing: number; // |high - low| — the leverage
}

/** Rank the uncertain priors by how much each one alone swings the outcome (others held
 *  central). Fixed/`[verified]` priors don't move — they're excluded. */
export function tornado(priors: Prior[], model: Model): TornadoBar[] {
  const base: Record<string, number> = {};
  for (const p of priors) base[p.key] = central(p.dist);
  const bars: TornadoBar[] = [];
  for (const p of priors) {
    if (p.dist.kind === "fixed") continue;
    const [lo, hi] = bounds(p.dist);
    const a = model({ ...base, [p.key]: lo });
    const b = model({ ...base, [p.key]: hi });
    const low = Math.min(a, b);
    const high = Math.max(a, b);
    bars.push({ key: p.key, label: p.label, register: p.register, low, high, swing: high - low });
  }
  return bars.sort((x, y) => y.swing - x.swing);
}

// --- disclosure ---------------------------------------------------------------
/** Collapse a prior to a disclosed point value (`[verified]`) — the "produce this record"
 *  move. Returns a new priors array (pure); recompute the band from it to show the tighten. */
export function disclose(priors: Prior[], key: string, value: number): Prior[] {
  return priors.map((p) =>
    p.key === key ? { ...p, register: "verified", dist: { kind: "fixed", value } } : p,
  );
}

/** A prior's central value, by key (0 if absent). The shared lookup the simulators used to
 *  re-implement as a local `priorCentral`/`PRIOR_BY_KEY` (#580). */
export function priorCentral(priors: Prior[], key: string): number {
  const p = priors.find((x) => x.key === key);
  return p ? central(p.dist) : 0;
}

/** Fold every disclosed knob to its (undisclosed) central value — the "produce a record →
 *  pin it to reference" step every uncertainty simulator runs over its disclose toggles.
 *  Centrals are read from the original priors, so the result is independent of toggle order. */
export function applyDisclosures(priors: Prior[], disclosed: Record<string, boolean>): Prior[] {
  let out = priors;
  for (const p of priors) {
    if (disclosed[p.key]) out = disclose(out, p.key, central(p.dist));
  }
  return out;
}

// --- the shared band contract -------------------------------------------------
/** What every consumer emits so the public balance sheet (#273) can aggregate them. */
export interface UncertainOutcome {
  key: string;
  label: string;
  unit: string;
  central: number;
  low: number;
  high: number;
  register: Register;
  drivers: Prior[];
  resolvingRecord?: string;
}

/** The exact band of a model over the prior grid (every {low, central, high} corner). The
 *  deterministic companion to `sample` — captures interaction between knobs (e.g. one lever
 *  that moves two line items inversely) without sampling noise. Use for a line's band. */
export function outcomeBand(priors: Prior[], model: Model): { central: number; low: number; high: number } {
  const base: Record<string, number> = {};
  for (const p of priors) base[p.key] = central(p.dist);
  const movable = priors.filter((p) => p.dist.kind !== "fixed");
  let lo = Number.POSITIVE_INFINITY;
  let hi = Number.NEGATIVE_INFINITY;
  // Walk the 3^k grid of {low, central, high} per movable prior.
  const levels = movable.map((p) => {
    const [l, h] = bounds(p.dist);
    return [l, central(p.dist), h];
  });
  const total = 3 ** movable.length;
  for (let i = 0; i < total; i++) {
    const draw = { ...base };
    let rem = i;
    for (let j = 0; j < movable.length; j++) {
      draw[movable[j].key] = levels[j][rem % 3];
      rem = Math.floor(rem / 3);
    }
    const v = model(draw);
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return { central: model(base), low: lo, high: hi };
}
