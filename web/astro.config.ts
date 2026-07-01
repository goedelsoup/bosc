import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import sitemap from "@astrojs/sitemap";
import rehypeDocLinks from "./src/lib/rehype-doc-links";
import { SITE_BASE } from "./src/lib/routes";
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

export default defineConfig({
  site,
  base: process.env.BASE_PATH || undefined,
  // The sitemap needs an absolute `site`; only register it in production builds
  // where SITE_URL is set (locally / in CI it'd warn and emit nothing useful).
  // Keep the `noindex` routes out of the sitemap too: the internal component galleries
  // and the unlinked launch/locked previews aren't content (#593).
  integrations: [
    react(),
    mdx(),
    ...(site
      ? [
          sitemap({
            filter: (page) =>
              ![
                "/site/icon-showcase",
                "/site/chart-showcase",
                "/site/teardown-showcase",
                "/pre-launch",
                "/locked-preview",
              ].some((p) => page.includes(p)),
          }),
        ]
      : []),
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
        sites: ["lima", "urbana", "fort-wayne"],
        cmd: ["uv", "run", "watermark"],
      }),
    ],
  },
});
