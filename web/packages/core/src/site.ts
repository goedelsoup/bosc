/**
 * Site-wide constants + the **ambient** site/story URL helpers (#724/#740).
 *
 * `withSite`/`withStory` resolve the *active* network site (set by the middleware from the
 * request URL, read via `activeSite()`), so a page calls `withSite("/leads")` and gets the
 * current site's URL with no slug threaded through it — the URL peer of the per-site bundle
 * (#739). This module is **build-only** (it reads the `AsyncLocalStorage` active-site through
 * `bundle.ts`); client islands import the pure, slug-parameterized helpers from `./base`
 * instead (`withBase`/`siteHref`/`storyHref`).
 *
 * The client-safe primitives are re-exported here so the ~70 build-only importers are unchanged.
 */
import { activeSite } from "./bundle";
import { siteHref, storyHref } from "./base";
import { DEFAULT_STORY_CODENAME } from "./routes";
import { SITES } from "./sites";

export { withBase, siteHref, storyHref } from "./base";
export { SITE_BASE, STORY_BASE, siteBase, siteUrl, storyBase, storyUrl } from "./routes";

export const SITE_NAME = "Watermark";
export const SITE_TAGLINE = "the public record, by watershed";
export const SITE_DESCRIPTION =
  "Watermark — a browsable, citable view of the public record, by watershed: primary " +
  "documents read from scans into structured data, the cross-document analysis, and the " +
  "Maumee-watershed hydrology.";

/** The active site's default story codename (its first registered story), for `withStory`. */
function activeStoryCodename(): string {
  const site = SITES.find((s) => s.slug === activeSite());
  return site?.stories?.[0]?.codename ?? DEFAULT_STORY_CODENAME;
}

/**
 * Prefix a path with the **active** site's root and the deploy base.
 * `withSite("/site/")` → e.g. `/network/american-sugar-creek-allen-co/site/` on a Lima page.
 * Pass "" for the site home. The ambient peer of `siteHref(slug, …)` (`./base`).
 */
export function withSite(path = ""): string {
  return siteHref(activeSite(), path);
}

/**
 * Prefix a path with the active site's **default story** root and the deploy base.
 * `withStory("")` → the story home; `withStory("/water")` → a flattened chapter.
 */
export function withStory(path = ""): string {
  return storyHref(activeSite(), activeStoryCodename(), path);
}
