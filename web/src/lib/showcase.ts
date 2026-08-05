/**
 * The component galleries — **a development surface, not part of the deployed site** (#1894).
 *
 * The three boards ported from the Claude Design handoff (chart set #306, icon set #309, record
 * teardown) are how a change to a shared primitive gets looked at: every variant of every chart,
 * every icon in the family, the teardown in all three layouts, on one screen. That is worth keeping
 * and worth running — it is not worth shipping. They were three unlinked, `noindex` routes in the
 * production artifact, reachable only by someone who already knew the URL.
 *
 * So they build in `astro dev` and nowhere else. A static `.astro` page always emits, which is why
 * they are one dynamic route: `getStaticPaths` is the only place a page can decline to exist.
 *
 * **Why this is a module and not a `const` in the page's frontmatter.** Astro HOISTS
 * `getStaticPaths` out of the component and runs it in its own scope, so a frontmatter binding it
 * closes over is not defined when it runs. That fails loudly in `astro dev` — and silently in a
 * production build, where the `DEV` branch short-circuits before the registry is ever touched. The
 * build would emit zero showcase routes and look exactly like a working gate while the dev server
 * 500'd on all three. Imports are hoisted; frontmatter consts are not.
 */

export interface Gallery {
  /** The `[gallery]` param — the URL segment, and the key `trail.ts` labels. */
  gallery: "charts" | "icons" | "teardown";
  /** Names the board, and forms the page title. */
  title: string;
  kicker: string;
  h1: string;
}

export const GALLERIES: Gallery[] = [
  { gallery: "charts", title: "Chart set", kicker: "Watermark · component family", h1: "The chart set" },
  { gallery: "icons", title: "Icon set", kicker: "Watermark · design system", h1: "The icon set" },
  {
    gallery: "teardown",
    title: "Record Teardown",
    kicker: "Watermark · component family",
    h1: "The Record Teardown",
  },
];

/**
 * `getStaticPaths` for the galleries: all three in `astro dev`, none in a production build.
 *
 * Asserted from the outside as well — `check-routes.mjs` guard 9 fails on any built route nothing
 * links to, and these are linked by nothing, so a regression that put them back in the artifact is
 * a red build rather than a slow accumulation of dev surface.
 */
export function showcaseGalleryPaths(): Array<{ params: { gallery: string }; props: Gallery }> {
  if (!import.meta.env.DEV) return [];
  return GALLERIES.map((g) => ({ params: { gallery: g.gallery }, props: g }));
}
