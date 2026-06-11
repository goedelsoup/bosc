import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";

// The `narrative` collection sources the public prose under the repo-root `docs/`
// AS-IS (issue #69) — docs are not moved/edited (the legacy Python SSG also reads
// them). The route renders only the curated set in `lib/narrative.ts`; in-repo
// links are rewritten at build by the rehype plugin (see astro.config.ts).
//
// `id` is the lowercased path without extension (e.g. "legal/mandamus-analysis"),
// matching `slugForRepoPath` so route slugs and the link rewriter agree.
const narrative = defineCollection({
  loader: glob({
    pattern: ["*.md", "legal/*.md"],
    base: "../docs",
    generateId: ({ entry }) => entry.replace(/\.md$/, "").toLowerCase(),
  }),
});

export const collections = { narrative };
