import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import rehypeDocLinks from "./src/lib/rehype-doc-links";

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

export default defineConfig({
  site: process.env.SITE_URL || undefined,
  base: process.env.BASE_PATH || undefined,
  integrations: [react(), mdx()],
  markdown: {
    rehypePlugins: [[rehypeDocLinks, { base }]],
  },
});
