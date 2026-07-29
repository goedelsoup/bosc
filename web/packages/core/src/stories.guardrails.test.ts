import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { storyFor } from "./walk";

// Framework guardrails for the `stories` MDX collection (#742). These lock the invariants the
// #733 source-flip relies on: the collection is the single source of the story spine, every
// live chapter is backed by a real anchor record, and chapters stay portable (curated-vocabulary
// imports only). CI fails on a broken/incomplete story or an off-vocabulary chapter import.

/** Raw text of every chapter + on-ramp MDX, keyed by collection-relative path. */
const RAW = import.meta.glob("../../../src/content/stories/**/*.mdx", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

/** The repo-root `data/extracted` dir (this test lives at web/packages/core/src/). */
const EXTRACTED = fileURLToPath(new URL("../../../../data/extracted/", import.meta.url));

interface Parsed {
  path: string; // collection-relative mdx path
  site: string;
  codename: string;
  fileSlug: string; // the filename stem (`_home` for the on-ramp)
  frontmatter: string;
  body: string;
  imports: string[]; // module specifiers imported in the body
}

function parse(path: string, raw: string): Parsed {
  const fm = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  const parts = path.split("/");
  const i = parts.lastIndexOf("stories");
  const fileSlug = parts[parts.length - 1].replace(/\.mdx$/, "");
  const body = fm ? fm[2] : raw;
  const imports = [...body.matchAll(/^\s*import\s+[^;]*?from\s+["']([^"']+)["']/gm)].map((m) => m[1]);
  return {
    path,
    site: parts[i + 1],
    codename: parts[i + 2],
    fileSlug,
    frontmatter: fm ? fm[1] : "",
    body,
    imports,
  };
}

const FILES: Parsed[] = Object.entries(RAW).map(([p, raw]) => parse(p, raw));
const CHAPTER_FILES = FILES.filter((f) => f.fileSlug !== "_home");
const STORY_KEYS = [...new Set(FILES.map((f) => `${f.site}/${f.codename}`))];

// The curated story-component vocabulary (#742): a chapter may import only these — the story libs
// and the island components. New vocabulary is added here deliberately (a reviewed change), which
// is the point: it keeps chapter authoring portable and free of ad-hoc one-off imports. The libs
// now live in @watermark/core (Epic #1549, Phase 1 #1551); `~/lib/*` is still accepted for any
// as-yet-unmigrated chapter.
const ALLOWED_LIB = new Set([
  "site",
  "walk",
  "teardowns",
  "bundle",
  "dilution",
  "moneyFlow",
  // The heat side of the water chapter (#1719) — `dilution`'s peer: the same cooling load read
  // against the receiving water's temperature criterion instead of its low flow.
  "thermal",
]);
function isAllowedImport(spec: string): boolean {
  const lib = spec.match(/^(?:~\/lib|@watermark\/core)\/([A-Za-z0-9_]+)$/);
  if (lib) return ALLOWED_LIB.has(lib[1]);
  // The React islands moved to @watermark/viz (Epic #1549, Phase 4 #1554); `~/components/islands/*`
  // is still accepted for any as-yet-unmigrated chapter.
  return /^(?:~\/components\/islands|@watermark\/viz\/islands)\/[A-Za-z0-9_]+\.tsx$/.test(spec);
}

describe("story completeness (#742)", () => {
  it("every story has at least one chapter and an `_home` on-ramp", () => {
    for (const key of STORY_KEYS) {
      const [site, codename] = key.split("/");
      const group = FILES.filter((f) => f.site === site && f.codename === codename);
      expect(
        group.some((f) => f.fileSlug === "_home"),
        `${key} needs _home.mdx`,
      ).toBe(true);
      expect(
        group.some((f) => f.fileSlug !== "_home"),
        `${key} needs at least one chapter`,
      ).toBe(true);
    }
  });

  it("chapter steps are contiguous 1..N and each slug matches its filename", () => {
    for (const key of STORY_KEYS) {
      const [site, codename] = key.split("/");
      const story = storyFor(site, codename);
      expect(story, `${key} must resolve via storyFor`).toBeDefined();
      if (!story) continue;
      expect(story.chapters.map((c) => c.step)).toEqual(story.chapters.map((_, idx) => idx + 1));
      for (const ch of story.chapters) {
        const file = CHAPTER_FILES.find(
          (f) => f.site === site && f.codename === codename && f.fileSlug === ch.slug,
        );
        expect(file, `${key}: chapter slug "${ch.slug}" must have <slug>.mdx`).toBeDefined();
      }
    }
  });

  it("every live chapter's anchor records resolve to a committed extraction", () => {
    for (const key of STORY_KEYS) {
      const [site, codename] = key.split("/");
      const story = storyFor(site, codename);
      if (!story) continue;
      for (const [rel, anchor] of Object.entries(story.anchors)) {
        // An anchor is only reachable for a *live* chapter; skip drafts.
        const ch = story.chapters.find((c) => c.slug === anchor.slug);
        if (!ch?.live) continue;
        expect(existsSync(EXTRACTED + rel), `${key}: anchor record missing: ${rel}`).toBe(true);
      }
    }
  });
});

describe("story spine parity snapshot (#742)", () => {
  it("the Lima project-bosc spine is stable (catches shell/spine regressions)", () => {
    expect(storyFor("lima", "project-bosc")).toMatchSnapshot();
  });
});

describe("provided-component lint (#742)", () => {
  it("chapters import only the curated story-component vocabulary", () => {
    const violations: string[] = [];
    for (const f of FILES) {
      for (const spec of f.imports) {
        if (!isAllowedImport(spec)) violations.push(`${f.path}: ${spec}`);
      }
    }
    expect(violations, `off-vocabulary chapter imports:\n${violations.join("\n")}`).toEqual([]);
  });
});
