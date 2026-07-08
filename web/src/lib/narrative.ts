/**
 * The narrative content collection (issue #69): the public prose under `docs/`
 * surfaced in the Astro site.
 *
 * Single-source decision: `docs/` STAYS at the repo root — it's also the legacy
 * Python SSG's input (`bosc.site.build` mirrors it) and general repo docs, so the
 * frontend reads it *as-is* (a content collection over `../docs`), never moving or
 * editing it. Cross-links are rewritten at build time by the rehype plugin
 * (`rehype-doc-links.ts`) so the source stays valid for both tiers.
 *
 * This module is the single source of truth for which docs are published, their
 * slugs/titles/sections, and the legacy→IA link map — consumed by the route, the
 * search index, AND the rehype plugin (via astro.config).
 */
import type { SectionId } from "./nav";

export interface NarrativeDoc {
  /** Path under `docs/` (the migrated file). */
  repo: string;
  /** Route slug under the network-global `/docs/` (lowercased repo path, no extension). */
  slug: string;
  title: string;
  section: SectionId;
  blurb: string;
}

export const NARRATIVE: NarrativeDoc[] = [
  // Methodology retired from the per-site docs set (#1132): it's now the network-global
  // `/methodology` hub (epic #1126), not a site-scoped narrative. The old route
  // `/network/[site]/docs/methodology` redirects there via a catch page
  // (pages/network/[site]/docs/methodology.astro).
  // The two framing essays are the author's investigation overview, not per-site landing
  // copy — re-homed out of the (site-scoped) `home` section into the network-global About
  // area (#1308, part of the IA reorg #1309). `home` stays the Overview/landing section; only
  // these docs move, so they group under "About" in the docs index/search and back-link to
  // `/about` instead of the site root.
  {
    repo: "COURSE.md",
    slug: "course",
    title: "Research course",
    section: "about",
    blurb: "What Watermark is investigating, and the open threads — a living draft.",
  },
  {
    repo: "bigger-picture.md",
    slug: "bigger-picture",
    title: "The bigger picture",
    section: "about",
    blurb: "Project BOSC placed against the national data-center build-out.",
  },
  {
    repo: "DOSSIER.md",
    slug: "dossier",
    title: "Research dossier",
    section: "site",
    blurb: "A synthesis of everything deconstructed from the record — the actors, the corridor, the case.",
  },
  {
    repo: "legal/mandamus-analysis.md",
    slug: "legal/mandamus-analysis",
    title: "Mandamus analysis",
    section: "site",
    blurb: "Legal analysis of the public-records mandamus action.",
  },
  {
    repo: "legal/proponent-analysis.md",
    slug: "legal/proponent-analysis",
    title: "Proponent analysis",
    section: "site",
    blurb: "A neutral, precise read of the proponent submissions to the Select Committee.",
  },
  {
    repo: "HYDROLOGY.md",
    slug: "hydrology",
    title: "Hydrology — Tier-0 findings",
    section: "environment",
    blurb: "Tier-0 municipal water-flow screening — the prose companion to the water-balance dashboard.",
  },
  {
    repo: "ECONOMICS.md",
    slug: "economics",
    title: "Economics — demand & public benefits",
    section: "environment",
    blurb:
      "The demand-side companion to Hydrology: regional cloud-consumer demand and the benefits extended to it.",
  },
  {
    repo: "end-use-and-workloads.md",
    slug: "end-use-and-workloads",
    title: "End use & workloads — what the facility is for",
    section: "reports",
    blurb:
      "The customer is known (Google); the use is not. What the Select-Committee record establishes about hyperscale vs colocation vs federal enclaves — and the open question of who can use the Lima campus.",
  },
  {
    repo: "defense-nexus.md",
    slug: "defense-nexus",
    title: "The defense nexus — what the corridor shows, and what it can't",
    section: "reports",
    blurb:
      "A defense plant nearby, a developer cleared to SECRET, an industry that hosts the CIA — three true facts that don't, combined, make a finding. The sharpest open question, held open.",
  },
  {
    repo: "toxics-and-the-corridor.md",
    slug: "toxics-and-the-corridor",
    title: "Toxics and the corridor — the river the campus joins",
    section: "reports",
    blurb:
      "The campus discharges into a river that is already 93% treated effluent at low flow, in a corridor carrying the county's heaviest industrial toxic load. What RSEI screening shows, what it can't measure, and the assimilative question the record leaves open.",
  },
  {
    repo: "the-load-and-the-grid.md",
    slug: "the-load-and-the-grid",
    title: "The load and the grid — a city's worth of demand, and who carries it",
    section: "reports",
    blurb:
      "A single campus equal to ~5–6% of its utility's entire retail load, for ~50 jobs — load, not jobs. The headline “313 MW” is backup generation (and redacted in the final permit); “behind-the-meter” is a claim, not a fact. What the record carries, and who pays to carry the load.",
  },
  {
    repo: "the-economic-ledger.md",
    slug: "the-economic-ledger",
    title: "The economic ledger — what the deal costs, modeled where the record is silent",
    section: "reports",
    blurb:
      "A 15-year public ledger of the deal: ~$45M–$90M in forgone tax for ~50 jobs (≈0.1% of a shrinking county). Four figures the record withholds — the building share, the job count, the school terms, the equipment spend — are modeled as a band across scenarios rather than blanked or guessed.",
  },
];

/** Repo paths (under docs/) of the migrated docs, e.g. "docs/DOSSIER.md". */
export const MIGRATED: Set<string> = new Set(NARRATIVE.map((d) => `docs/${d.repo}`));

/** slug for a migrated repo path: "docs/DOSSIER.md" → "dossier". */
export function slugForRepoPath(repoPath: string): string {
  return repoPath
    .replace(/^docs\//, "")
    .replace(/\.md$/, "")
    .toLowerCase();
}

/**
 * Legacy generated-page targets (repo-root-relative, as the docs link to the old
 * `web/` layout) → their new-IA routes. Used by the rehype link rewriter.
 */
// Values are site-relative WITHOUT the /network/american-sugar-creek-allen-co prefix — the rehype-doc-links plugin prepends
// the Lima base (`/network/american-sugar-creek-allen-co`, #307 PR 2) at build time, so prefixing here would double it.
// Exception: network-global routes (`/wiki/…`) live at the site root and are NOT base-prefixed
// (the plugin's GLOBAL_ROUTE guard passes them through), so they stay correct here too.
export const LINK_MAP: Record<string, string> = {
  "entities.md": "/wiki/entities/",
  "timeline.md": "/timeline",
  "meetings.md": "/site/legal",
  "people/index.md": "/site/people/",
  "places/index.md": "/site/people/",
  "documents/index.md": "/site/documents/",
  "exhibits.md": "/site/exhibits",
  "records/index.md": "/site/records/",
  "records/opc.md": "/site/records/opc/",
  "candidates.md": "/wiki/",
  "gis-map.md": "/environment/map",
  "economics-baseline.md": "/docs/economics",
  // The legacy "notebooks" page is superseded by the native OPC scenario explorer (the
  // marimo POC was retired — see docs/marimo-integration-investigation.md). Base-relative.
  "notebooks.md": "/reports/opc-scenario",
};

export const bySlug = new Map(NARRATIVE.map((d) => [d.slug, d]));
