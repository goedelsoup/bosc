/**
 * The legal-history collection (Pages cutover Gap B, #105): substantive primary
 * records under `data/extracted/` that the legacy "Legal history" nav exposed —
 * Select Committee testimony + hearing transcripts, the PRR/mandamus analyses, the
 * corpus-completeness audit, the web-vendor audit, and the commissioners record.
 *
 * Like `lib/narrative.ts` / `lib/reference.ts`, this is the single source of truth
 * for which extracted docs are published, their slugs/titles/groups, and (via
 * `PUBLISHED_LEGAL`) the link-rewrite map the rehype plugin consults so intra-set
 * cross-links resolve to their `/network/american-sugar-creek-allen-co/site/legal/<slug>` routes. The source is read
 * AS-IS — never moved or edited.
 *
 * Unlike every other record facet, this set has no bundle feed between it and the corpus — it is
 * read straight off `data/extracted/` — so nothing was scoping it to a site, and every selectable
 * peer served all fifteen of these Allen-County-OH pages verbatim (#1886). `scopedLegal` supplies
 * the missing seam, off the same slug-derived corpus-scope rule Python resolves at export.
 */
import { corpusOwner } from "./corpusScope";

export interface LegalDoc {
  /** Path under `data/extracted/` (the source markdown). */
  repo: string;
  /** Route slug under `/network/american-sugar-creek-allen-co/site/legal/`. */
  slug: string;
  title: string;
  /** Display group on the legal-history index. */
  group: string;
  blurb: string;
  /**
   * The owning site, declared — for a document the corpus files by PROJECT or CASE name
   * (`legal/thor-v-urbana/…`, `permits/highland55/…`) rather than under the site-attribution
   * path `corpusOwner` derives from the slug. This is the call-site peer of the Python profile's
   * `corpus_relpaths` exceptions (`watermark.sites.SiteProfile`), which the frontend does not
   * carry. **Omit it whenever `repo` is rule-derivable** — an unnecessary literal here is exactly
   * the re-hardcoding the site axis forbids. Every doc below is rule-derivable, so none sets it.
   */
  site?: string;
}

const SELECT = "Select Committee on Data Centers (2026)";
const PRR = "PRR & mandamus";
const AUDITS = "Audits";
const GOV = "County governance";
const ANALYSIS = "Analysis";

export const LEGAL: LegalDoc[] = [
  {
    repo: "legal/select-committee-2026/relator-testimony/bosc-written-testimony-2026-06-01.md",
    slug: "written-testimony",
    title: "Written testimony (2026-06-01)",
    group: SELECT,
    blurb: "BOSC's written testimony to the Ohio Select Committee on Data Centers.",
  },
  {
    repo: "legal/select-committee-2026/relator-testimony/bosc-testimony-deck-2026-06-01.md",
    slug: "testimony-deck",
    title: 'Testimony deck — "Who Is the Customer?"',
    group: SELECT,
    blurb: "The slide outline accompanying the written testimony.",
  },
  {
    repo: "legal/select-committee-2026/relator-testimony/bosc-data-appendix-2026-06-01.md",
    slug: "data-appendix",
    title: "Data appendix — cloud pricing, AI hardware, resource economics",
    group: SELECT,
    blurb: "The cited figures behind the testimony: cloud/hardware/resource economics.",
  },
  {
    repo: "legal/select-committee-2026/hearings-audio/bosc-committee-testimony-2026-06-04.transcript.md",
    slug: "committee-testimony",
    title: "Committee testimony (2026-06-04)",
    group: SELECT,
    blurb: "Transcript of BOSC's spoken testimony before the committee.",
  },
  {
    repo: "legal/select-committee-2026/hearings-audio/bosc-committee-hearing-2026-06-04-am.transcript.md",
    slug: "hearing-am",
    title: "Hearing transcript — morning (2026-06-04)",
    group: SELECT,
    blurb: "Full transcript of the morning hearing session.",
  },
  {
    repo: "legal/select-committee-2026/hearings-audio/bosc-committee-hearing-2026-06-04-pm.transcript.md",
    slug: "hearing-pm",
    title: "Hearing transcript — afternoon (2026-06-04)",
    group: SELECT,
    blurb: "Full transcript of the afternoon hearing session.",
  },
  {
    repo: "legal/select-committee-2026/hearings-audio/bosc-committee-hearing-2026-06-04-pm2.transcript.md",
    slug: "hearing-pm2",
    title: "Hearing transcript — afternoon, cont. (2026-06-04)",
    group: SELECT,
    blurb: "Transcript of the closing afternoon session.",
  },
  {
    repo: "legal/prr-mandamus/bosc-prr-production-2026-06-05.analysis.md",
    slug: "prr-production",
    title: "PRR production analysis (2026-06-05)",
    group: PRR,
    blurb: "Analysis of the Allen County public-records production batch 1.",
  },
  {
    repo: "legal/prr-mandamus/README.md",
    slug: "withholding-map",
    title: "Withholding map & source instruments",
    group: PRR,
    blurb: "The source instruments behind the PRR and the records-withholding map.",
  },
  {
    repo: "legal/corpus-completeness-audit.md",
    slug: "corpus-completeness-audit",
    title: "Corpus completeness audit",
    group: AUDITS,
    blurb: "What source documents the corpus has, is missing, and still seeks.",
  },
  {
    repo: "legal/web-vendor-audit/allen-county-web-vendor-audit.md",
    slug: "web-vendor-audit",
    title: "Who runs the county's websites",
    group: AUDITS,
    blurb: "Who manages the websites of Allen County government bodies.",
  },
  {
    repo: "legal/web-vendor-audit/allen-county-level-sites.md",
    slug: "county-level-sites",
    title: "County-level government websites",
    group: AUDITS,
    blurb: "The county-level government website inventory behind the vendor audit.",
  },
  {
    repo: "commissioners/README.md",
    slug: "commissioners-minutes",
    title: "Commissioners minutes & resolutions",
    group: GOV,
    blurb: "The Allen County Commissioners legislative record — minutes and resolutions.",
  },
  {
    repo: "commissioners/bosc-water-balance.analysis.md",
    slug: "water-balance-screen",
    title: "Water balance — assimilative screen",
    group: ANALYSIS,
    blurb:
      "The Tier-0 water balance + 7Q10 low-flow assimilative screen: all three County receiving streams already fail the dilution screen at design flow, before any data-center load.",
  },
];

/** Repo paths (under data/extracted/) of the published legal docs. */
export const PUBLISHED_LEGAL: Set<string> = new Set(LEGAL.map((d) => `data/extracted/${d.repo}`));

/** slug for a published legal repo path, or "" if not published. */
export function legalSlugForRepoPath(repoPath: string): string {
  const d = LEGAL.find((r) => `data/extracted/${r.repo}` === repoPath);
  return d ? d.slug : "";
}

export const legalBySlug = new Map(LEGAL.map((d) => [d.slug, d]));

/** Distinct groups, in first-seen order (for the index). */
export const LEGAL_GROUPS: string[] = [...new Set(LEGAL.map((d) => d.group))];

/** The site whose corpus a published legal doc belongs to — its declared `site`, else the
 *  slug-derived corpus-scope rule over its `repo` path (#1886). */
export function legalOwner(doc: LegalDoc): string {
  return doc.site ?? corpusOwner(doc.repo);
}

/**
 * The legal-history docs scoped to `slug` (#1886) — the peer of `scopedReference`.
 *
 * A doc surfaces on a site iff that site's corpus is the one it was extracted from. This is what
 * stops `/network/fort-wayne/site/legal/hearing-am` from rendering an **Ohio** Select-Committee
 * hearing under an **Indiana** watershed point, and `withholding-map` /
 * `corpus-completeness-audit` — Allen-County-OH public-records artifacts — from reading as a
 * peer's own filings. A site with none of its own gets the section lock and the ask instead.
 */
export function scopedLegal(slug: string): LegalDoc[] {
  return LEGAL.filter((d) => legalOwner(d) === slug);
}

/** Whether `slug`'s own corpus carries the published legal doc `docSlug` — the guard a page uses
 *  before deep-linking one (a peer's page must not link into the reference build's filings). */
export function hasLegalDoc(slug: string, docSlug: string): boolean {
  const doc = legalBySlug.get(docSlug);
  return doc !== undefined && legalOwner(doc) === slug;
}
