/**
 * The reference-data collection (Pages cutover Gap C, #104): the authoritative
 * external datasets' READMEs under `data/reference/`, surfaced in-site.
 *
 * Like `lib/narrative.ts`, this is the single source of truth for which reference
 * READMEs are published, their slugs/titles, and (via `PUBLISHED_REFERENCE`) the
 * link-rewrite map the rehype plugin consults so `../<set>/README.md` cross-links
 * between reference pages resolve to their new `/network/american-sugar-creek-allen-co/site/reference/<slug>` routes.
 *
 * The READMEs are read AS-IS — source is never moved or edited.
 */
import { hasFeed, loadFeed } from "./bundle";
import type { CatalogItem } from "./feeds";

export interface ReferenceDataset {
  /** Path under `data/reference/` (the README). */
  repo: string;
  /** Route slug under `/network/american-sugar-creek-allen-co/site/reference/`. */
  slug: string;
  title: string;
  blurb: string;
  /**
   * The data catalog entry id(s) (`data/catalog/reference/<id>.yaml`) this README documents
   * (#1260). This is the per-site scope seam: the dataset surfaces on a site iff the site owns at
   * least one of these entries, resolved from the bundle's already-scoped `catalog` feed
   * (`bosc.site.catalog._in_site_scope`). The scope decision lives entirely in the catalog YAML
   * (`site_scope`), so `web/` re-hardcodes no Lima/Allen-County value — it just names the link.
   */
  catalogIds: string[];
}

export const REFERENCE: ReferenceDataset[] = [
  {
    repo: "echo/README.md",
    slug: "echo",
    title: "Maumee NPDES inventory (EPA ECHO)",
    blurb: "The EPA ECHO wastewater-discharger inventory for the Maumee basin (NPDES permits).",
    catalogIds: ["echo-maumee-npdes"],
  },
  {
    repo: "allen-gis/README.md",
    slug: "allen-gis",
    title: "Allen County parcels (CAMA)",
    blurb: "Parcel ownership / situs / acreage from the Allen County GIS Current Parcels layer.",
    catalogIds: ["allen-gis-parcels"],
  },
  {
    repo: "lima-gis/README.md",
    slug: "lima-gis",
    title: "Lima zoning districts",
    blurb: "City of Lima zoning districts (and the FEMA DFIRM floodzone) from the city GIS.",
    catalogIds: ["lima-gis"],
  },
  {
    repo: "rsei/README.md",
    slug: "rsei",
    title: "RSEI toxic-release inventory (EPA)",
    blurb: "The EPA RSEI Public Data Set reduced to Allen County's toxic-release facilities.",
    catalogIds: ["rsei-inventory"],
  },
  {
    repo: "gleif/README.md",
    slug: "gleif",
    title: "Entity LEIs (GLEIF)",
    blurb: "GLEIF Legal Entity Identifier resolution for corridor entity parents.",
    catalogIds: ["gleif"],
  },
  {
    repo: "economics/README.md",
    slug: "economics",
    title: "Economic baseline (BLS QCEW / Census)",
    blurb: "Allen County employment (BLS QCEW) and population (Census ACS) — the localized baseline.",
    catalogIds: ["economics-baseline"],
  },
  {
    repo: "hydrology/wbd/README.md",
    slug: "wbd",
    title: "USGS watershed boundaries (WBD)",
    blurb: "The USGS Watershed Boundary Dataset HUC boundaries framing the campus AOI.",
    catalogIds: ["hydrology-wbd"],
  },
];

/** Repo paths (under data/reference/) of the published READMEs. */
export const PUBLISHED_REFERENCE: Set<string> = new Set(REFERENCE.map((d) => `data/reference/${d.repo}`));

/** slug for a published reference repo path, or "" if not published. */
export function refSlugForRepoPath(repoPath: string): string {
  const d = REFERENCE.find((r) => `data/reference/${r.repo}` === repoPath);
  return d ? d.slug : "";
}

export const refBySlug = new Map(REFERENCE.map((d) => [d.slug, d]));

/**
 * The catalog entry ids a site owns — read straight from its bundle's `catalog` feed, which
 * Python already filters to the site's own scope (`bosc.site.catalog._in_site_scope`, keyed off
 * each entry's `site_scope`). Empty when a bundle predates/omits the feed, so scoping degrades to
 * "show nothing" rather than leak the reference build's set. Build-only (reads the bundle on disk).
 */
function ownedCatalogIds(slug: string): Set<string> {
  if (!hasFeed("catalog", slug)) return new Set<string>();
  return new Set(loadFeed<CatalogItem[]>("catalog", slug).map((c) => c.id));
}

/**
 * The reference datasets scoped to `slug` (#1260): a README surfaces iff the site owns at least
 * one of the catalog entries it documents. This is what keeps a sibling site's
 * `/site/reference/` from rendering Lima zoning / Allen County parcels / the Lima WBD verbatim —
 * those catalog entries are `lima-legacy`, so only the reference build owns them. The scope lives
 * in the catalog YAML; this is a thin reader of the already-scoped bundle feed.
 */
export function scopedReference(slug: string): ReferenceDataset[] {
  const owned = ownedCatalogIds(slug);
  return REFERENCE.filter((d) => d.catalogIds.some((id) => owned.has(id)));
}
