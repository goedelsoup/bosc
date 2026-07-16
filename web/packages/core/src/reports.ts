/**
 * The interactive-report registry (#584) — the single source for which narrative
 * essays have an interactive companion page under `/reports/<slug>` and what they're
 * called. Previously the slug→href map was hardcoded twice: the reports index
 * (`reports/index.astro`, deciding the companion link + "interactive" badge) and the
 * public balance sheet (`balanceSheet.ts`, linking each band back to its narrative).
 *
 * The slug is also the docs-essay slug (`docs/<slug>.md`); a report with no companion
 * falls back to that essay. URLs are built with `siteHref(siteSlug, …)` — the client-safe,
 * slug-parameterized peer of `withSite` (`./base`) — so a companion link resolves to the
 * *active* site, not a Lima-pinned root (#1145). Both call sites (the build-time reports
 * index and the client balance-sheet island) thread the active site slug; the result already
 * carries the deploy base, so neither wraps it in `withBase`.
 */
import { siteHref } from "./base";

export interface ReportEntry {
  /** `/reports/<slug>` and `docs/<slug>.md`. */
  slug: string;
  /** Display title — the narrative's name. */
  label: string;
}

/** Reports whose essay has an interactive companion page (the SSOT slug list). */
export const INTERACTIVE_REPORTS: ReportEntry[] = [
  { slug: "end-use-and-workloads", label: "End use & workloads" },
  { slug: "defense-nexus", label: "The defense nexus" },
  { slug: "the-economic-ledger", label: "The economic ledger" },
  { slug: "toxics-and-the-corridor", label: "Toxics and the corridor" },
  { slug: "the-load-and-the-grid", label: "The load and the grid" },
];

const BY_SLUG = new Map(INTERACTIVE_REPORTS.map((r) => [r.slug, r]));

/** The companion page URL for a report slug on a given site (deploy base included). */
export function reportUrl(slug: string, siteSlug: string): string {
  return siteHref(siteSlug, `/reports/${slug}`);
}

/** True when the report has an interactive companion (vs only the docs essay). */
export function hasInteractive(slug: string): boolean {
  return BY_SLUG.has(slug);
}
