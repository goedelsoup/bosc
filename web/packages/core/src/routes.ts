/**
 * The URL roots for the network's sites and their stories — the single source of truth.
 *
 * Plain string constants/functions with NO Astro/runtime dependency, so `astro.config.ts`
 * can import them too (it feeds `SITE_BASE` to the base-aware `rehype-doc-links` plugin).
 * The live site was historically rooted at `/bosc`; every site now lives under
 * `/network/<id>` so they're clean siblings, and an investigation is a *story* beneath a
 * site (so a site can host several over time — `/network/<id>/stories/<codename>`).
 *
 * The parameterized core (`siteBase`/`storyBase`) keys off the registry `slug` (the same
 * key the Python `bosc.sites` peer uses for facility maps, grouping, …). Lima is the one
 * site whose URL id differs from its slug (`lima` → `american-sugar-creek-allen-co`, the
 * historical re-root); every other site's URL id IS its slug. This map is the only place
 * that special case lives — it stays here (not in `sites.ts`) so this module keeps its
 * zero-dependency contract and `sites.ts` can import `siteBase` from it without a cycle.
 */

/** The live reference site's registry slug. */
export const LIMA_SLUG = "lima";

/** The default (and, today, only) story codename hosted under the Lima site. */
export const DEFAULT_STORY_CODENAME = "project-bosc";

/**
 * Registry slug → URL segment, for the sites whose URL id differs from their slug.
 * Only Lima differs (the `/network/american-sugar-creek-allen-co` re-root); every other
 * slug maps to itself via the fallback in `siteBase`.
 */
const SITE_URL_IDS: Record<string, string> = {
  [LIMA_SLUG]: "american-sugar-creek-allen-co",
};

/**
 * A site's URL root from its registry slug, with NO deploy-base prefix.
 * `siteBase("lima")` → `/network/american-sugar-creek-allen-co`;
 * `siteBase("fort-wayne")` → `/network/fort-wayne`.
 */
export function siteBase(slug: string): string {
  return `/network/${SITE_URL_IDS[slug] ?? slug}`;
}

/** The inverse of `SITE_URL_IDS`: a site's URL segment → its registry slug. */
const SITE_IDS_TO_SLUG: Record<string, string> = Object.fromEntries(
  Object.entries(SITE_URL_IDS).map(([slug, id]) => [id, slug]),
);

/**
 * Resolve a registry slug from a `/network/<id>/` URL segment — the inverse of `siteBase`.
 * `slugForSiteId("american-sugar-creek-allen-co")` → `"lima"`; any other id maps to itself.
 * Used by the middleware to set the active site from the request path (#724/#739).
 */
export function slugForSiteId(id: string): string {
  return SITE_IDS_TO_SLUG[id] ?? id;
}

/**
 * A story's URL root (`<siteBase>/stories/<codename>`) — a site can host several stories.
 * `storyBase("lima", "project-bosc")` → the Project BOSC story root.
 */
export function storyBase(slug: string, codename: string): string {
  return `${siteBase(slug)}/stories/${codename}`;
}

/** The live reference site's URL root (was `/bosc`). The Lima specialization of `siteBase`. */
export const SITE_BASE = siteBase(LIMA_SLUG);

/** The Project BOSC story under that site — the Lima specialization of `storyBase`. */
export const STORY_BASE = storyBase(LIMA_SLUG, DEFAULT_STORY_CODENAME);

/**
 * Build a Lima-site URL with NO deploy-base prefix — the Astro-free peer of `withSite()`
 * (`src/lib/site.ts`). Use this in `.ts` modules that must stay free of `import.meta.env`
 * (anything `astro.config.ts` / the rehype plugin can reach) or that emit *stored* canonical
 * paths (the search / ask index), where the deploy base is applied at render, not at storage.
 * `siteUrl("/site/")` → `/network/american-sugar-creek-allen-co/site/`.
 *
 * This is the Lima-pinned convenience; the slug-parameterized peer is `siteBase(slug) + path`.
 */
export function siteUrl(path = ""): string {
  return `${SITE_BASE}${path}`;
}

/** The story-root peer of `siteUrl()` — `storyUrl("/water")` → the flattened chapter path. */
export function storyUrl(path = ""): string {
  return `${STORY_BASE}${path}`;
}
