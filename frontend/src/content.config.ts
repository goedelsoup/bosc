import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { LEGAL } from "./lib/legal";
import { REFERENCE } from "./lib/reference";

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

// The `reference` collection (Pages cutover Gap C, #104): the authoritative
// external datasets' READMEs under `data/reference/`, read AS-IS. `id` is each
// dataset's slug (from `lib/reference.ts`), so the route + the rehype rewriter agree.
const reference = defineCollection({
  loader: glob({
    pattern: ["{echo,allen-gis,lima-gis,rsei,gleif,economics}/README.md", "hydrology/wbd/README.md"],
    base: "../data/reference",
    generateId: ({ entry }) => REFERENCE.find((r) => r.repo === entry)?.slug ?? entry,
  }),
});

// The `legal` collection (Pages cutover Gap B, #105): the curated legal-history
// records under `data/extracted/`, read AS-IS. `id` is each doc's slug (from
// `lib/legal.ts`), so the route + the rehype rewriter agree.
const legal = defineCollection({
  loader: glob({
    pattern: [
      "legal/select-committee-2026/relator-testimony/*.md",
      "legal/select-committee-2026/hearings-audio/*.transcript.md",
      "legal/prr-mandamus/bosc-prr-production-*.analysis.md",
      "legal/prr-mandamus/README.md",
      "legal/corpus-completeness-audit.md",
      "legal/web-vendor-audit/*.md",
      "commissioners/README.md",
    ],
    base: "../data/extracted",
    generateId: ({ entry }) => LEGAL.find((r) => r.repo === entry)?.slug ?? entry,
  }),
});

export const collections = { narrative, reference, legal };
