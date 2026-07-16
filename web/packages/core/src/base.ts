/**
 * Client-safe URL helpers (#724/#740). The deploy-base primitive (`withBase`) and the
 * slug-parameterized site/story href builders (`siteHref`/`storyHref`) — all pure, with NO
 * ambient/`AsyncLocalStorage` dependency, so they're safe to import from client islands.
 *
 * The *ambient* `withSite`/`withStory` (which read the active site) live in `./site`, which is
 * build-only. An island that needs a site-scoped URL takes the active slug as a prop and calls
 * `siteHref(slug, …)` from here — it can't read the build-time active-site context client-side.
 */
import { siteBase, storyBase } from "./routes";

export { SITE_BASE, STORY_BASE, siteBase, siteUrl, storyBase, storyUrl } from "./routes";

/**
 * Prefix an absolute in-site path with Astro's configured `base` so links work
 * whether the site is served from `/` or a subpath (the parity-gated Pages
 * cutover may set BASE_PATH). Pass a root-absolute path like `/bosc/site/`.
 */
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const left = base.endsWith("/") ? base.slice(0, -1) : base;
  const right = path.startsWith("/") ? path : `/${path}`;
  return `${left}${right}` || "/";
}

/**
 * Prefix a path with a site's root (by registry slug) and the deploy base.
 * `siteHref("lima", "/site/")` → `/network/american-sugar-creek-allen-co/site/`;
 * `siteHref("fort-wayne")` → that site's home.
 */
export function siteHref(slug: string, path = ""): string {
  return withBase(`${siteBase(slug)}${path}`);
}

/**
 * Prefix a path with a story's root (by site slug + codename) and the deploy base.
 * `storyHref("lima", "project-bosc", "/water")` → that chapter.
 */
export function storyHref(slug: string, codename: string, path = ""): string {
  return withBase(`${storyBase(slug, codename)}${path}`);
}
