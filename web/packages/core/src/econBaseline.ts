/**
 * Absence-preserving derivations for the localized labor baseline (#1918) — the model behind
 * `/network/<site>/economy/economics-baseline` and the study's Labor chapter.
 *
 * The gap this closes: the page's formatters were careful (`—` for a `ProvenancedValue` with no
 * `value`), but every arithmetic call site undid that with `?? 0`. A QCEW-suppressed sector became
 * a real-looking zero — a sector ranked last as though nobody worked there, a zero point dropping
 * out of the employment line, a residual reconciled against a sum nobody reported. That is the
 * invention `data discipline` exists to prevent: **prefer omission over invention**.
 *
 * So absence travels through the arithmetic here rather than being flattened at the door. A sum
 * over rows that are not all reported is `complete: false` and its dependent output is withheld;
 * a chart series carries only the years actually measured; an employment change over fewer than
 * two reported years is `null`. Nothing in this module substitutes a number for a gap.
 *
 * These are decisions, not prose — the presentation tier renders the gap it is handed.
 */
import type { EconOwnership, EconSector, EconTrendPoint, ProvenancedValue } from "./feeds";

/** An employment-carrying row — the shape a private sector and a government slice share. */
export type EmploymentRow = Pick<EconSector | EconOwnership, "annual_avg_employment">;

/**
 * Rank rows by employment, largest first. Rows whose employment is **absent** sort last, in their
 * original order — an unreported sector is unranked, not a sector with nobody in it. (The old
 * `?? 0` comparator produced the same tail position by asserting a zero, which is the assertion
 * this module exists to refuse; a genuine reported `0` still ranks ahead of an absent one.)
 */
export function rankByEmployment<T extends EmploymentRow>(rows: readonly T[]): T[] {
  return [...rows].sort((a, b) => {
    const av = a.annual_avg_employment?.value ?? null;
    const bv = b.annual_avg_employment?.value ?? null;
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return bv - av;
  });
}

/** A sum over rows that may not all be reported. `total` covers `reported` rows only. */
export interface EmploymentSum {
  /** The sum of the rows that carry a value — meaningful only when `complete`. */
  total: number;
  reported: number;
  missing: number;
  /** True when every row carried a value, i.e. `total` is the whole sum and not a floor. */
  complete: boolean;
}

/** Sum the employment of `rows`, counting rather than zero-filling the ones with no measurement. */
export function sumEmployment(rows: readonly EmploymentRow[]): EmploymentSum {
  let total = 0;
  let reported = 0;
  for (const row of rows) {
    const v = row.annual_avg_employment?.value ?? null;
    if (v == null) continue;
    total += v;
    reported += 1;
  }
  return { total, reported, missing: rows.length - reported, complete: reported === rows.length };
}

/**
 * The private + government ↔ all-ownership reconciliation. `reconciled` only when the county
 * total and **every** row behind both sums is reported; otherwise the residual would be the
 * arithmetic of a number nobody published, so it is withheld and the gap is described instead.
 */
export type EmploymentReconciliation =
  | { kind: "reconciled"; sectorJobs: number; govJobs: number; totalJobs: number; residual: number }
  | { kind: "incomplete"; totalJobs: number | null; missing: number };

export function reconcileEmployment(
  totalEmployment: ProvenancedValue | null | undefined,
  sectors: readonly EmploymentRow[],
  government: readonly EmploymentRow[],
): EmploymentReconciliation {
  const totalJobs = totalEmployment?.value ?? null;
  const sec = sumEmployment(sectors);
  const gov = sumEmployment(government);
  const missing = sec.missing + gov.missing;
  if (totalJobs == null || missing > 0) return { kind: "incomplete", totalJobs, missing };
  return {
    kind: "reconciled",
    sectorJobs: sec.total,
    govJobs: gov.total,
    totalJobs,
    residual: Math.round(totalJobs - sec.total - gov.total),
  };
}

/** One measured year of a series — an absent year is not represented at all. */
export interface ReportedPoint {
  year: number;
  value: number;
}

/**
 * The years of `rows` that actually carry a measurement for `pick`. A suppressed year is dropped
 * rather than plotted at zero: the chart then spans the reported years, and the table beside it
 * (which lists every row) is where the `—` is read.
 */
export function reportedSeries<T extends { year: number }>(
  rows: readonly T[],
  pick: (row: T) => ProvenancedValue | null | undefined,
): ReportedPoint[] {
  const out: ReportedPoint[] = [];
  for (const row of rows) {
    const v = pick(row)?.value ?? null;
    if (v != null) out.push({ year: row.year, value: v });
  }
  return out;
}

/** A series that ends where it started has not shrunk — the third case the prose needs. */
export type EmploymentDirection = "grew" | "shrank" | "unchanged";

export interface EmploymentChange {
  /** First and last **reported** year — what the prose must name, since gaps are skipped. */
  first: ReportedPoint;
  last: ReportedPoint;
  direction: EmploymentDirection;
  delta: number;
  /** Percent change on the first reported year; `null` when that year is zero (undefined change). */
  pct: number | null;
}

/**
 * The covered-employment change across the trend, or `null` when fewer than two years are
 * reported (one point is a level, not a change).
 */
export function employmentChange(trend: readonly EconTrendPoint[]): EmploymentChange | null {
  const points = reportedSeries(trend, (t) => t.total_employment);
  if (points.length < 2) return null;
  const first = points[0];
  const last = points[points.length - 1];
  const delta = last.value - first.value;
  return {
    first,
    last,
    delta,
    direction: delta > 0 ? "grew" : delta < 0 ? "shrank" : "unchanged",
    pct: first.value === 0 ? null : (delta / first.value) * 100,
  };
}
