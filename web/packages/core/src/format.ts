// Shared formatters + small numeric/string utils (#581) — the peer of `money.ts` / `charts.ts`.
// These were each duplicated (and quietly diverging) across `lib/` and `components/islands/`;
// this is the one home for them.

/** Round `n` to `decimals` places (half-up via `Math.round`). */
export function round(n: number, decimals = 0): number {
  const f = 10 ** decimals;
  return Math.round(n * f) / f;
}

/**
 * Headline-stat decimals: one at or above 1, two significant figures below it.
 *
 * The peer of `_stat_decimals` in `watermark/site/impact_study.py`, and it must stay identical to
 * it — `study.parity.test.ts` pins the two derivations equal, so a one-sided edit turns the gate
 * red. Two findings drove the rule, both about the same thing: a design low flow is a sub-1
 * number and one decimal cannot carry it.
 *
 * A value that VANISHED (#1995): Sidney's contracted cooling draw, 0.0146 cfs and `[verified]` in
 * an executed service agreement, rendered as "0 cfs" — which reads as *no draw*.
 *
 * A value that merely SHIFTED (#1267), live in three committed bundles: Van Wert's Town Creek
 * 7Q10 is 0.16 cfs and published as "0.2", off by 25% on the denominator its whole
 * effluent-dominance finding rests on. It never vanished, so the first guard never fired.
 *
 * Hence one rule for the whole sub-1 range instead of a patch per symptom. It subsumes the
 * vanish guard exactly — same `1 - floor(log10)`, no longer gated on rounding to zero.
 */
export function statDecimals(value: number | null | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 1;
  if (value === 0 || Math.abs(value) >= 1) return 1;
  return 1 - Math.floor(Math.log10(Math.abs(value)));
}

/**
 * A ratio multiple: integer at ≥10, else significant decimals.
 *
 * Shares `statDecimals`'s sub-1 rule, for the same reason and one the ratio case needs even
 * more (#1265). A fixed single decimal renders every dilution below 0.05 as **"0.0×"** — and a
 * dilution ratio is precisely where the significant digits all sit to the right of the point.
 * Lima's tightest chronic dilution is 0.006987 and Findlay's is 0.009048; both published as
 * "0.0×", which reads as *nothing* rather than as the two most effluent-dominated reaches on
 * the network. `watermark.hydrology.basin._ratio_text` had already learned this on the artifact
 * side ("two decimals silently flattens the whole violation band"); this is the display side.
 *
 * That shared helper widened from a vanish-guard to the whole sub-1 range in #1267, so a ratio in
 * `[0.05, 1)` now keeps two significant figures too (`0.37×` where it used to read `0.4×`). The
 * ratio case wanted that already by the argument above; it simply had no symptom loud enough to
 * force it, because the dilutions that embarrassed the old rule were the ones that vanished.
 */
export function fmtMult(m: number): string {
  if (!Number.isFinite(m)) return "∞×";
  if (m >= 10) return `${Math.round(m)}×`;
  return `${m.toFixed(statDecimals(m))}×`;
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
