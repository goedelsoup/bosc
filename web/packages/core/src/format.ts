// Shared formatters + small numeric/string utils (#581) — the peer of `money.ts` / `charts.ts`.
// These were each duplicated (and quietly diverging) across `lib/` and `components/islands/`;
// this is the one home for them.

/** Round `n` to `decimals` places (half-up via `Math.round`). */
export function round(n: number, decimals = 0): number {
  const f = 10 ** decimals;
  return Math.round(n * f) / f;
}

/** A dilution / ratio multiple: `"∞×"` when non-finite, an integer at ≥10×, else one decimal. */
export function fmtMult(m: number): string {
  if (!Number.isFinite(m)) return "∞×";
  return `${m >= 10 ? Math.round(m) : m.toFixed(1)}×`;
}

/** Megawatts, rounded to whole MW. */
export function fmtMw(n: number): string {
  return `${Math.round(n)} MW`;
}

/** The subset of a `ProvenancedValue` the range formatter needs (#760). */
export interface Ranged {
  value: number | null;
  low?: number | null;
  high?: number | null;
  unit?: string | null;
}

/** True when a quantitative uncertainty band is attached (either bound present). */
export function hasRange(pv: Pick<Ranged, "low" | "high">): boolean {
  return pv.low != null || pv.high != null;
}

/**
 * Render a provenanced value with its uncertainty band (#760): the symmetric case reads
 * `"226 ± ~45 ac"`, an asymmetric or one-sided band reads `"226 (181–271 ac)"`, and a
 * value with no band falls back to `"226 ac"`. `decimals` controls rounding of every part.
 * This is the presentation of the quantitative spread — the qualitative `confidence` badge
 * is rendered separately, alongside it.
 */
export function fmtRanged(pv: Ranged, decimals = 0): string {
  if (pv.value == null) return "—";
  const unit = pv.unit ? ` ${pv.unit}` : "";
  const v = round(pv.value, decimals);
  if (!hasRange(pv)) return `${v}${unit}`;
  const dLo = pv.low != null ? pv.value - pv.low : null;
  const dHi = pv.high != null ? pv.high - pv.value : null;
  // Symmetric two-sided band (bounds equidistant within 5% of the spread) → the ± form.
  if (dLo != null && dHi != null) {
    const spread = Math.max(dLo, dHi);
    if (Math.abs(dLo - dHi) <= 0.05 * Math.max(spread, 1e-9)) {
      return `${v} ± ~${round((dLo + dHi) / 2, decimals)}${unit}`;
    }
  }
  const lo = round(pv.low ?? pv.value, decimals);
  const hi = round(pv.high ?? pv.value, decimals);
  return `${v} (${lo}–${hi}${unit})`;
}

/** The one field these formatters read — anything `ProvenancedValue`-shaped satisfies it. */
export interface Measured {
  value: number | null;
}

/** A whole-number count (`"9,452"`), or `"—"` when the measurement is absent (#1918). */
export function fmtCount(v?: Measured | null): string {
  return v?.value == null ? "—" : Math.round(v.value).toLocaleString("en-US");
}

/** Whole dollars (`"$60,348"`), or `"—"` when the measurement is absent (#1918). */
export function fmtUsd(v?: Measured | null): string {
  return v?.value == null ? "—" : `$${Math.round(v.value).toLocaleString("en-US")}`;
}

/** A percentage (`"3.41%"`), or `"—"` when the measurement is absent (#1918). */
export function fmtPct(v?: Measured | null, decimals = 2): string {
  return v?.value == null ? "—" : `${v.value.toFixed(decimals)}%`;
}

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
};

/** Escape the HTML metacharacters in `s` before interpolating it into an HTML string. */
export function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => HTML_ESCAPES[c]);
}

/** Join the defined, non-empty string parts into one searchable blob (` · `-separated). */
export function blob(...parts: (string | null | undefined)[]): string {
  return parts.filter((p): p is string => typeof p === "string" && p.trim().length > 0).join(" · ");
}
