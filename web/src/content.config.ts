import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";
import { LEGAL } from "@watermark/core/legal";
import { REFERENCE } from "@watermark/core/reference";

// The `stories` collection (#724/#730): a site's *story* as data — one MDX file per chapter
// under `src/content/stories/<site>/<codename>/<slug>.mdx`. The frontmatter is the chapter
// SPINE (validated below); the MDX body is the prose, which imports the provided story
// components (#731). `id` is `<site>/<codename>/<slug>`, so `loadStories` (src/lib/stories.ts)
// recovers the site + codename from the path and groups chapters into a `Story` (src/lib/walk.ts).
export const STORY_CHAPTER_SCHEMA = z.object({
  /** 1-based reading position within the story. */
  step: z.number().int().positive(),
  /** Route slug, flattened under the story; must match the filename. */
  slug: z.string().min(1),
  title: z.string().min(1),
  /** The record-reading skill this chapter teaches. */
  skill: z.string().min(1),
  /** Human description of the anchor record(s) it tears down. */
  anchor: z.string().min(1),
  /** Library record `rel`s this chapter tears down — drives the "↩ seen in the walk" backlinks. */
  anchorRecordRels: z.array(z.string()).default([]),
  /** Whether the chapter is published (vs. still drafting); gates its wayfinding go-links. */
  live: z.boolean().default(true),
  /** Optional eyebrow override; defaults to "Chapter <step>" at render. */
  eyebrow: z.string().optional(),
  /** Optional `<title>` override; defaults to `<title> — Chapter <step>` at render. */
  pageTitle: z.string().optional(),
  /** Meta description for the chapter page. */
  description: z.string().optional(),
  /** The impact-study chapter this walk chapter teaches toward (a `STUDY_CHAPTERS` id) —
   *  the one-hop-each-way walk↔study cross-link (the missing-impact-study epic). The walk
   *  teaches the record-reading; the study owns the finding. Validated at render by
   *  `studyChapter` (an unknown id fails the build, like `getSection`). */
  studySection: z.string().optional(),
});

// A story's on-ramp / home (`_home.mdx`): the prose-heavy intro the index route renders. Data
// bits (the chapter list, corpus counts, CTAs) come from the model/bundle; the body is the prose.
export const STORY_HOME_SCHEMA = z.object({
  kind: z.literal("home"),
  /** The on-ramp H1 (e.g. "A data center is coming to Lima"). */
  h1: z.string().min(1),
  /** Kicker eyebrow (e.g. "The story · Project BOSC"). */
  kicker: z.string().optional(),
  pageTitle: z.string().optional(),
  description: z.string().optional(),
});

const stories = defineCollection({
  loader: glob({
    pattern: "**/*.{md,mdx}",
    base: "./src/content/stories",
    generateId: ({ entry }) => entry.replace(/\.(md|mdx)$/, ""),
  }),
  // A chapter, or the story home (`_home.mdx`). Chapters carry a numeric `step`; the home a
  // `kind: home`. `loadStories` / the chapter route key off `step` to tell them apart.
  schema: z.union([STORY_CHAPTER_SCHEMA, STORY_HOME_SCHEMA]),
});

// The `study` collection (the missing-impact-study epic, PR6): OPTIONAL per-site narrative
// slotted into an impact-study chapter. Unlike `stories`, the study's spine is the registry
// (`@watermark/core/study`), NOT the MDX — a note enriches a chapter; it never creates one.
// Files live at `src/content/study/<site>/<chapter>.mdx`; a facility-scoped note at
// `<site>/<facility-key>/<chapter>.mdx` wins when that facility's study is being read (the
// multi-project seam, baked into the lookup from day one). Bodies compose STUDY_COMPONENTS
// with no imports, exactly like walk chapters.
export const STUDY_NOTE_SCHEMA = z.object({
  /** The chapter this note belongs to: a `STUDY_CHAPTERS` id, or the reserved `_cover` (the
   *  cover's abstract, read by `study/index.astro` — safe because `[chapter].astro` emits
   *  only `STUDY_CHAPTERS` ids, so `_cover` can never route as a chapter).
   *
   *  ⚠️ The RUNTIME shells never read this field. Both resolve a note by its file-path id,
   *  facility-scoped first and site-level second:
   *
   *    1. `study/<slug>/<facility-key>/<chapter>`   ← wins when that facility is being read
   *    2. `study/<slug>/<chapter>`                  ← the site-level fallback
   *
   *  (`[chapter].astro` for a chapter, `study/index.astro` for `_cover`.) So a `chapter:`
   *  value that disagrees with the filename renders no error, and a typo'd FILENAME becomes
   *  silently dead content. Zod can't close that gap either: this config can't import
   *  `@watermark/core/study` without dragging the bundle reader into the content-config
   *  graph.
   *
   *  The ONE consumer of this field is therefore a test — `src/content/study.notes.test.ts`,
   *  which walks the collection and asserts each note's id AND its `chapter` against the
   *  registry. Keep the field accurate: it is how that guard catches the misnamed file. */
  chapter: z.string().min(1),
  /** Facility key this note is scoped to; absent = the site's primary-facility study. */
  facility: z.string().optional(),
  /** Unpublish a drafted note without deleting it. */
  live: z.boolean().default(true),
  /** Dateline shown with the note (ISO date). */
  updated: z.string().optional(),
});

const study = defineCollection({
  loader: glob({
    pattern: "**/*.{md,mdx}",
    base: "./src/content/study",
    generateId: ({ entry }) => entry.replace(/\.(md|mdx)$/, ""),
  }),
  schema: STUDY_NOTE_SCHEMA,
});

// The `narrative` collection sources the public prose under the repo-root `docs/`
// AS-IS (issue #69) — docs are never moved/edited; the docs source stays canonical.
// The route renders only the curated set in `lib/narrative.ts`; in-repo
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
    pattern: [
      "{echo,allen-gis,lima-gis,rsei,gleif,economics,eia,ohio-waterwells}/README.md",
      "hydrology/wbd/README.md",
    ],
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
      "commissioners/bosc-water-balance.analysis.md",
    ],
    base: "../data/extracted",
    generateId: ({ entry }) => LEGAL.find((r) => r.repo === entry)?.slug ?? entry,
  }),
});

export const collections = { narrative, reference, legal, stories, study };
