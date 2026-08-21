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
 *
 * Each published README **declares whose prose it is** in its front matter (#1905). Before that,
 * there was exactly one README per dataset — Lima's — and every peer rendered it verbatim, so
 * Urbana and Troy-Piqua served byte-identical Allen-County-OH documentation of their own,
 * different datasets and `/network/fort-wayne/site/reference/rsei` described an Ohio county under
 * an Indiana watershed point. The dataset scoping was never the problem (`scopedReference` has
 * resolved the right datasets through the catalog seam since #1260) — the *words* were. So the
 * prose is split: the README carries what is true wherever the connector points, and what a
 * particular site's copy turned out to say lives in `data/reference/<set>/instances/<slug>.md`.
 * {@link referenceForSite} is what a page renders — the scope declaration, the site's OWN catalog
 * rows, and that site's instance note if it has one.
 */
import { hasFeed, loadFeed, repoPath } from "./bundle";
import type { CatalogItem } from "./feeds";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { parse as parseYaml } from "yaml";
import { catalogFreshness, type CatalogFreshness } from "./feeds";

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
    // Blurbs render on EVERY owning site's reference index, so a Lima literal here is the same
    // borrowed context #1905 fixed in the READMEs — one line up. Each site's county is named by
    // its own catalog title and its own data, never by this registry.
    title: "RSEI toxic-release inventory (EPA)",
    blurb: "The EPA RSEI Public Data Set reduced to this site's county toxic-release facilities.",
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
    blurb: "The site county's employment (BLS QCEW) and population (Census ACS) — the localized baseline.",
    catalogIds: ["economics-baseline"],
  },
  {
    // Published for #1885: the study's power chapter reads the serving utility, the balancing
    // authority, and all three load denominators off this dataset and tags them `[verified]`.
    // Until it had a page, that tag was the study's only claim with no destination behind it —
    // every site owns the EIA catalog entries (the backdrop floor is EIA-keyed), so every site's
    // power chapter can now cite the series its figures came from.
    repo: "eia/README.md",
    slug: "eia",
    title: "Grid & consumer energy (US EIA)",
    blurb:
      "The serving utility and balancing authority (EIA-861/930), the state retail market, and the household energy prices the ratepayer read is built on.",
    catalogIds: ["eia-grid-profile", "eia-consumer-energy", "eia-demand-pressure", "eia"],
  },
  {
    // Also published for #1885 — the study's groundwater chapter screens the county well census
    // and the campus dewatering wellfield, and both of those are this one README's datasets. The
    // `catalogIds` list is closed by design (as everywhere in this registry): a peer that pulls
    // its own county census adds that id here rather than inheriting Allen County's.
    repo: "ohio-waterwells/README.md",
    slug: "ohio-waterwells",
    title: "Ohio water-well-log census (Ohio DNR)",
    blurb:
      "The R.C. 1521.05 contractor well logs — the county well census and the campus construction-dewatering wellfield behind the groundwater screens.",
    catalogIds: ["ohio-waterwells-allen", "ohio-waterwells-shelby", "lima-campus-dewatering"],
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

// --- the prose scope declaration (#1905) -------------------------------------------------

/**
 * Whose words a README is, declared in its own front matter:
 *
 *  - `network`      — true wherever the connector is pointed (source, method, caveats). It may
 *                     name no site's county as *the* county; the reading site's own figures come
 *                     from its own copy of the data.
 *  - `basin:<name>` — one artifact pulled per basin and shared by every site draining it. Naming
 *                     the basin's own places is honest here: the file itself is the basin's.
 *  - `site:<slug>`  — documents that site's instance by construction (a county parcel layer, a
 *                     city zoning service). Only that site owns the catalog entry, so only that
 *                     site renders it.
 *
 * The vocabulary deliberately mirrors the catalog's `site_scope`, but it is a SEPARATE decision:
 * `site_scope` says which sites own the *dataset*, this says who the *prose* is about. The whole
 * bug was the two silently disagreeing — a `slug-scoped` dataset (every site gets its own copy)
 * documented by prose about one county.
 */
export type ReferenceScope = "network" | `basin:${string}` | `site:${string}`;

export interface ReferenceProse {
  scope: ReferenceScope;
  /** The declared reason, rendered to the reader as the page's scope banner. */
  scopeNote: string;
}

const SCOPE_RE = /^(network|basin:[a-z0-9-]+|site:[a-z0-9-]+)$/;

/** Parse a leading `---` YAML front-matter block, or null when the file has none. */
function frontMatter(path: string): Record<string, unknown> | null {
  if (!existsSync(path)) return null;
  const text = readFileSync(path, "utf8");
  if (!text.startsWith("---\n")) return null;
  const end = text.indexOf("\n---", 3);
  if (end < 0) return null;
  const parsed: unknown = parseYaml(text.slice(4, end + 1));
  return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
}

const proseCache = new Map<string, ReferenceProse>();

/**
 * A published dataset's declared prose scope, read from its README front matter.
 *
 * **Throws** on a published README with no (or a malformed) declaration, rather than assuming a
 * default. A silent default is exactly how the bug got in: the un-declared README read as
 * network-general to the routing layer while being written about one county. Build-only.
 */
export function referenceProse(datasetSlug: string): ReferenceProse {
  const cached = proseCache.get(datasetSlug);
  if (cached) return cached;
  const dataset = refBySlug.get(datasetSlug);
  if (!dataset) throw new Error(`Unknown reference dataset "${datasetSlug}".`);
  const fm = frontMatter(repoPath("data", "reference", dataset.repo));
  const scope = fm?.scope;
  const note = fm?.scope_note;
  if (typeof scope !== "string" || !SCOPE_RE.test(scope)) {
    throw new Error(
      `data/reference/${dataset.repo} declares no valid \`scope\` front matter. ` +
        `Expected one of: network | basin:<name> | site:<slug> (#1905).`,
    );
  }
  if (typeof note !== "string" || note.trim().length === 0) {
    throw new Error(
      `data/reference/${dataset.repo} declares \`scope: ${scope}\` with no \`scope_note\`. ` +
        `The reason is the point — it is what the page shows the reader (#1905).`,
    );
  }
  const prose: ReferenceProse = { scope: scope as ReferenceScope, scopeNote: note.trim() };
  proseCache.set(datasetSlug, prose);
  return prose;
}

/** The directory holding a dataset's per-site instance notes (sibling of its README). */
function instancesDir(dataset: ReferenceDataset): string {
  return repoPath("data", "reference", dataset.repo.replace(/README\.md$/, "instances"));
}

/**
 * The sites with a committed instance note for a dataset — `data/reference/<set>/instances/
 * <slug>.md`, the file that carries what THIS site's copy of the data turned out to say. Sorted,
 * so the derived content keys are stable. Build-only.
 *
 * A filename here IS a site slug, so a `README.md` explaining the directory would read as a site
 * called "README". Skipped by name, the same way `bosc.catalog.backfill._SKIP_NAMES` skips it one
 * tree over — prose about the notes is not one of the notes.
 */
export function instanceSites(datasetSlug: string): string[] {
  const dataset = refBySlug.get(datasetSlug);
  if (!dataset) return [];
  const dir = instancesDir(dataset);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".md") && f !== "README.md")
    .map((f) => f.slice(0, -3))
    .sort();
}

/**
 * The content-collection id of `site`'s instance note for a dataset, or null when it has none.
 * A site without a note is the normal case and renders the network prose plus its own data —
 * an absent note is never filled from another site's.
 */
export function instanceNoteId(datasetSlug: string, site: string): string | null {
  return instanceSites(datasetSlug).includes(site) ? `${datasetSlug}/${site}` : null;
}

/** One catalog row behind a dataset, resolved for the site reading it. */
export interface DatasetInstance {
  id: string;
  /** The site's own storage paths — `{site}` resolved, so the path names the reading site. */
  files: string[];
  command: string | null;
  cadence: string;
  lastRefreshed: string | null;
  freshness: CatalogFreshness;
}

/**
 * A catalog entry's storage paths as they resolve FOR a site — the TS peer of
 * `bosc.catalog.resolve.resolved_for_site`. A `slug-scoped` entry's `{site}` template is the
 * site's own copy; the reference build is the one site that ALSO keeps the un-slugged peers where
 * the entry carries them (the `lima-legacy` reference convention). Everything else uses the
 * un-templated paths verbatim.
 *
 * The peers are a UNION with the reference build's own template expansions, not an alternative to
 * them (#2066): `hydrology-reaches` gives Lima both an un-slugged `reach-nav.yaml` and a slugged
 * `reaches/lima.geojson`, and an either/or rule silently dropped the second.
 *
 * This is what makes the block genuinely per-site with no new plumbing: Urbana is told it reads
 * `reference/rsei/urbana/inventory.yaml`, Troy-Piqua `reference/rsei/troy-piqua/inventory.yaml`.
 *
 * Filtered to what is actually committed for the site, because some templated paths are optional
 * by construction — `reference/rsei/{site}/enclave.yaml` exists only where the site's facility is
 * a federal installation (#1664). Naming a file a site does not have would be the same borrowed
 * context this whole seam exists to stop, one level down.
 */
function resolvedFiles(row: CatalogItem, slug: string, isReferenceBuild: boolean): string[] {
  const paths = row.storage.map((s) => s.relpath);
  const resolve = (): string[] => {
    if (row.site_scope !== "slug-scoped") return paths.filter((p) => !p.includes("{site}"));
    const templated = paths.filter((p) => p.includes("{site}")).map((p) => p.replaceAll("{site}", slug));
    if (!isReferenceBuild) return templated;
    return [...paths.filter((p) => !p.includes("{site}")), ...templated];
  };
  return resolve().filter((p) => existsSync(repoPath("data", p)));
}

/** What `/site/reference/<slug>` renders for one site: the declaration, its data, its note. */
export interface SiteReferenceEntry {
  dataset: ReferenceDataset;
  prose: ReferenceProse;
  /** The site's OWN catalog rows behind this README (already scoped by the bundle feed). */
  instances: DatasetInstance[];
  /** This site's instance-note collection id, or null when it has none. */
  note: string | null;
}

/**
 * The reference section as one site reads it — {@link scopedReference} joined to each dataset's
 * declared prose scope, that site's own catalog rows, and its instance note.
 *
 * The reference build is identified by owning an un-slugged peer path rather than by a hardcoded
 * slug: `lima-legacy` is a storage convention, and the site axis forbids re-baking the slug here.
 */
export function referenceForSite(slug: string): SiteReferenceEntry[] {
  const rows = hasFeed("catalog", slug)
    ? new Map(loadFeed<CatalogItem[]>("catalog", slug).map((c) => [c.id, c]))
    : new Map<string, CatalogItem>();
  // A site owning a `lima-legacy` entry IS the reference build — the un-slugged files are its own.
  const isReferenceBuild = [...rows.values()].some((c) => c.site_scope === "lima-legacy");
  return scopedReference(slug).map((dataset) => ({
    dataset,
    prose: referenceProse(dataset.slug),
    instances: dataset.catalogIds
      .map((id) => rows.get(id))
      .filter((row): row is CatalogItem => row !== undefined)
      .map((row) => ({
        id: row.id,
        files: resolvedFiles(row, slug, isReferenceBuild),
        command: row.command ?? null,
        cadence: row.cadence,
        lastRefreshed: row.last_refreshed ?? null,
        freshness: catalogFreshness(row.observed, row.site_scope),
      })),
    note: instanceNoteId(dataset.slug, slug),
  }));
}

/**
 * The reference facet's content identity for a site — what the facet guard compares.
 *
 * The old key was the list of dataset SLUGS, which is why the collision it reported could never
 * be fixed by writing better prose: two sites owning the same datasets keyed identically no
 * matter what those pages said. This key is what actually renders — the declared scope, the
 * site's own resolved file paths, and its instance note — so two sites collide only when they
 * genuinely serve the same words about the same bytes.
 */
export function referenceContentKey(slug: string): string {
  return JSON.stringify(
    referenceForSite(slug).map((e) => [
      e.dataset.slug,
      e.prose.scope,
      e.note ?? "",
      e.instances.map((i) => i.files),
    ]),
  );
}
