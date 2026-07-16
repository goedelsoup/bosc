/**
 * USD formatters — client-safe (no `node:` imports), so both the build-time
 * money-flow assembly and the `MoneyFlow` island share one definition. Deterministic,
 * locale-free (the build must be reproducible).
 */

/** Full grouped USD ($14,223,081) — for tables and line items. */
export function fmtUsdFull(n: number): string {
  const grouped = Math.round(n)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `$${grouped}`;
}

/** Compact USD ($14.5M / $3.52M / $500M) — for the flow bars. */
export function fmtUsd(n: number): string {
  if (Math.abs(n) >= 1_000_000) {
    const m = n / 1_000_000;
    // ≥100M: whole millions. Below: 2dp, then strip trailing zeros *after the
    // decimal point only* (so "500" stays 500, "14.50" → 14.5).
    if (m >= 100) return `$${m.toFixed(0)}M`;
    return `$${m.toFixed(2).replace(/\.?0+$/, "")}M`;
  }
  return fmtUsdFull(n);
}

/** USD always in millions, 1dp ($0.9M / $2.1M) — for the abatement-per-job band,
 *  where sub-million figures read cleaner as a consistent fraction of a million. */
export function fmtUsdM(n: number): string {
  return `$${(n / 1_000_000).toFixed(1)}M`;
}
