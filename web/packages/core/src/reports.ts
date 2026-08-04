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

/**
 * Companion pages that stand on their own — a `/reports/<slug>` route with **no docs essay behind
 * it**, so they can't live in {@link INTERACTIVE_REPORTS} without breaking what that list means
 * (`hasInteractive` answers "does this ESSAY have a companion", and is what decides whether the
 * reports index renders the companion link beside an essay).
 *
 * Split out for #1890: the search index needs every report ROUTE, and asking the essay registry
 * for it silently missed these two — the capstone and the cost scenario, which are among the most
 * substantial pages a site builds.
 */
export const STANDALONE_REPORTS: ReportEntry[] = [
  { slug: "public-balance-sheet", label: "The public balance sheet" },
  { slug: "opc-scenario", label: "Opinion-of-probable-cost scenario" },
];

/** Every `/reports/<slug>` companion route a selectable site builds, essay-backed or not. */
export const REPORT_PAGES: ReportEntry[] = [...INTERACTIVE_REPORTS, ...STANDALONE_REPORTS];

const BY_SLUG = new Map(INTERACTIVE_REPORTS.map((r) => [r.slug, r]));

/** The companion page URL for a report slug on a given site (deploy base included). */
export function reportUrl(slug: string, siteSlug: string): string {
  return siteHref(siteSlug, `/reports/${slug}`);
}

/** True when the report has an interactive companion (vs only the docs essay). */
export function hasInteractive(slug: string): boolean {
  return BY_SLUG.has(slug);
}
