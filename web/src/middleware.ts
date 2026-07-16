/**
 * Active-site middleware (#724/#739). Resolves the network site a request renders from its
 * URL (`/network/<id>/…` → registry slug), stashes the slug on `Astro.locals.site`, AND runs the
 * page render inside `runWithSite` — so every build-time `loadFeed`/`hasFeed` the render performs
 * (transitively, through the ~12 feed libs) reads that site's bundle, with no slug threaded
 * through each call. Runs during static generation (Astro runs middleware for prerendered pages).
 *
 * A request outside `/network/<id>/` (the network-global pages: about, wiki, ask, search, the
 * `/network` hub) has no active site, so the render falls through to Lima (`activeSite`'s
 * default). `getStaticPaths` runs before middleware, so its enumeration is Lima-default too — a
 * second selectable site's per-site path enumeration is handled at onboarding (#235).
 */
import { runWithSite } from "@watermark/core/bundle";
import { LIMA_SLUG, slugForSiteId } from "@watermark/core/routes";
import { SITES } from "@watermark/core/sites";
import { defineMiddleware } from "astro:middleware";

const SELECTABLE = new Set(SITES.filter((s) => s.selectable).map((s) => s.slug));

export const onRequest = defineMiddleware((context, next) => {
  const match = context.url.pathname.match(/\/network\/([^/]+)(?:\/|$)/);
  const urlSlug = match ? slugForSiteId(match[1]) : null;
  // Only a *selectable* site has its own bundle + page tree; a non-selectable (coming-soon)
  // `/network/<id>/` page has no data, so it renders against the Lima reference. Global pages
  // (no `/network/<id>/`) are Lima too.
  const slug = urlSlug && SELECTABLE.has(urlSlug) ? urlSlug : LIMA_SLUG;
  context.locals.site = slug;
  return runWithSite(slug, () => next());
});
