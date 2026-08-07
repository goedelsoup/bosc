import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import sitemap from "@astrojs/sitemap";
import rehypeDocLinks from "@watermark/core/rehype-doc-links";
import { SITE_BASE } from "@watermark/core/routes";
import { SITES } from "@watermark/core/sites";
import { watermarkBundle } from "./plugins/watermark-bundle";

// Static build (the default). `site`/`base` come from the environment so the
// parity-gated Pages cutover can set them later without a code change.
//
// React powers the interactive deck.gl/MapLibre islands (Epic #55); they mount
// client:only over an SSR fallback, so the rest of the site stays zero-framework.
// MDX must come after React so .mdx still renders.
//
// The rehype plugin rewrites the migrated `docs/` narrative's in-repo links into
// the new IA (issue #69) without editing the source — see rehype-doc-links.ts.
const base = process.env.BASE_PATH || "";
const site = process.env.SITE_URL || undefined;
// The live site is physically re-rooted under /network/<id> (was /bosc, #307 PR 2) so future
// watershed sites are clean siblings; the migrated markdown's doc/reference cross-links resolve
// there. SITE_BASE is the single source of truth (src/lib/routes.ts).
const limaBase = `${base}${SITE_BASE}`;

// The sites the build exports a content bundle for — DERIVED from the identity registry's
// `selectable` flag (data/sites.yaml -> sites-registry.json), never a hand-kept list.
//
// `selectable` already means exactly this: "a site whose full build is deployed". It is the same
// flag `selectableSitePaths` uses to plan `getStaticPaths` for every `network/[site]/…` route, so
// deriving here makes the two structurally incapable of disagreeing. A hardcoded list could — and
// did: troy-piqua was promoted to `selectable` (#1876) without being added, and because the
// committed `web/sites/` fixtures are an explicit `WATERMARK_BUNDLE_DIR` opt-in (set only by
// `mise run //web:check`) and NOT a fallback, the Pages build planned troy-piqua's routes and then
// died in `loadManifest` with "No content bundle found". Promotion is now the only edit needed.
const exportSites = SITES.filter((s) => s.selectable).map((s) => s.slug);

export default defineConfig({
  site,
  base: process.env.BASE_PATH || undefined,
  // The sitemap needs an absolute `site`; only register it in production builds
  // where SITE_URL is set (locally / in CI it'd warn and emit nothing useful).
  // Keep the `noindex` route out of the sitemap too (#593). One entry left: #1894 retired the
  // component galleries and the locked preview from the production artifact — a route that isn't
  // built needs no filter — and `/pre-launch` is the standalone landing the Pages middleware
  // rewrites `/` to when `preLaunch` is on, so it ships and stays out of the sitemap.
  integrations: [
    react(),
    mdx(),
    ...(site ? [sitemap({ filter: (page) => !page.includes("/pre-launch") })] : []),
  ],
  markdown: {
    // Shiki's default theme is github-dark; the site chrome is light (and
    // `.prose pre` styles a light code block), so pin a light theme so fenced
    // code matches inline code and the rest of the page (#106).
    shikiConfig: { theme: "github-light" },
    rehypePlugins: [[rehypeDocLinks, { base: limaBase }]],
  },
  vite: {
    plugins: [
      watermarkBundle({
        sites: exportSites,
        cmd: ["uv", "run", "watermark"],
      }),
    ],
  },
});
