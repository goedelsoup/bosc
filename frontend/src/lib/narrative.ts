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
  /** Route slug under `/docs/` (lowercased repo path, no extension). */
  slug: string;
  title: string;
  section: SectionId;
  blurb: string;
}

export const NARRATIVE: NarrativeDoc[] = [
  {
    repo: "methodology.md",
    slug: "methodology",
    title: "Methodology — how we read the record",
    section: "home",
    blurb: "How a deliberately thin public record is read from primary documents into cited, structured data.",
  },
  {
    repo: "COURSE.md",
    slug: "course",
    title: "Research course",
    section: "home",
    blurb: "What Project BOSC is investigating, and the open threads — a living draft.",
  },
  {
    repo: "bigger-picture.md",
    slug: "bigger-picture",
    title: "The bigger picture",
    section: "home",
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
    section: "watershed",
    blurb: "Tier-0 municipal water-flow screening — the prose companion to the water-balance dashboard.",
  },
  {
    repo: "ECONOMICS.md",
    slug: "economics",
    title: "Economics — demand & public benefits",
    section: "watershed",
    blurb: "The demand-side companion to Hydrology: regional cloud-consumer demand and the benefits extended to it.",
  },
];

/** Repo paths (under docs/) of the migrated docs, e.g. "docs/DOSSIER.md". */
export const MIGRATED: Set<string> = new Set(NARRATIVE.map((d) => `docs/${d.repo}`));

/** slug for a migrated repo path: "docs/DOSSIER.md" → "dossier". */
export function slugForRepoPath(repoPath: string): string {
  return repoPath.replace(/^docs\//, "").replace(/\.md$/, "").toLowerCase();
}

/**
 * Legacy generated-page targets (repo-root-relative, as the docs link to the old
 * `web/` layout) → their new-IA routes. Used by the rehype link rewriter.
 */
export const LINK_MAP: Record<string, string> = {
  "entities.md": "/wiki/entities/",
  "timeline.md": "/site/timeline",
  "meetings.md": "/site/legal",
  "people/index.md": "/site/people/",
  "places/index.md": "/site/people/",
  "documents/index.md": "/site/documents/",
  "exhibits.md": "/site/exhibits",
  "records/index.md": "/site/records/",
  "records/opc.md": "/site/records/opc/",
  "candidates.md": "/wiki/",
  "gis-map.md": "/watershed/map",
  "economics-baseline.md": "/docs/economics",
  // The interactive marimo notebooks aren't migrated to the new site; point at
  // their repo source (absolute values are passed through, not base-prefixed).
  "notebooks.md": "https://github.com/goedelsoup/bosc/tree/main/notebooks",
};

export const bySlug = new Map(NARRATIVE.map((d) => [d.slug, d]));
