/**
 * Derive the per-site `Walk` model (`./walk`) from the `stories` MDX content collection
 * (#724/#730). One MDX file per chapter under `src/content/walk/<site>/<codename>/<slug>.mdx`;
 * the frontmatter is the chapter spine, the body is the prose (rendered in #732).
 *
 * `buildWalk` is a pure function (no `astro:content`), so it's unit-testable and the spine
 * derivation is verified against the canonical Lima story. `loadWalks` is the **async**
 * build-time wrapper (lazy `astro:content`) used where a render path already awaits; `buildAllWalks`
 * is the **sync** source the `walk.WALKS` const is built from (#733) — it reads the same chapter
 * frontmatter via `import.meta.glob('?raw')`, which is plugin-free (so it works in the Astro build
 * AND in vitest, which has no MDX transform). The MDX *bodies* are still rendered by `astro:content`;
 * this reads only the frontmatter spine.
 */
import { parse as parseYaml } from "yaml";
import { SITES } from "./sites";
import type { Chapter, Walk, WalkAnchor } from "./walk";

/** A chapter's parsed frontmatter — the TS mirror of `STORY_CHAPTER_SCHEMA` (content.config.ts). */
export interface WalkChapterSpine {
  step: number;
  slug: string;
  title: string;
  skill: string;
  anchor: string;
  anchorRecordRels: string[];
  live: boolean;
  eyebrow?: string;
  /** The impact-study chapter this walk chapter teaches toward (walk↔study cross-link). */
  studySection?: string;
}

/** Walk-level metadata not carried per chapter — supplied by the registry (`WalkRef`). */
export interface WalkMeta {
  title: string;
  dek: string;
}

/**
 * Assemble a `Walk` from its chapter spines: order by step, map to `Chapter`s, and invert
 * each chapter's `anchorRecordRels` into the record→chapter backlink map (`ch` = zero-padded
 * step, `label` = chapter title) — exactly the shape the record block reads.
 */
export function buildWalk(
  site: string,
  codename: string,
  meta: WalkMeta,
  spines: readonly WalkChapterSpine[],
): Walk {
  const ordered = [...spines].sort((a, b) => a.step - b.step);
  const chapters: Chapter[] = ordered.map((c) => ({
    step: c.step,
    slug: c.slug,
    title: c.title,
    skill: c.skill,
    anchor: c.anchor,
    live: c.live,
    ...(c.studySection ? { studySection: c.studySection } : {}),
  }));
  const anchors: Record<string, WalkAnchor> = {};
  for (const c of ordered) {
    for (const rel of c.anchorRecordRels) {
      anchors[rel] = { ch: String(c.step).padStart(2, "0"), slug: c.slug, label: c.title };
    }
  }
  // Site-owned (editorial) story — the `site` special case of the owner axis (#1092). Inlined
  // rather than importing `siteOwner` from `./walk` to keep this module free of a runtime cycle
  // (walk.ts imports `buildAllWalks` from here).
  return {
    owner: { kind: "site", id: site },
    site,
    codename,
    title: meta.title,
    dek: meta.dek,
    chapters,
    anchors,
  };
}

/** The registry metadata for a (site, codename), or a codename-titled fallback. */
function storyMetaFor(site: string, codename: string): WalkMeta {
  const ref = SITES.find((s) => s.slug === site)?.stories?.find((r) => r.codename === codename);
  return { title: ref?.title ?? codename, dek: ref?.dek ?? "" };
}

/**
 * Read every story from the `stories` collection and group its chapters into `Walk`s, keyed by
 * the `<site>/<codename>` prefix of each entry's id. Build-time only (Astro/MDX context).
 */
export async function loadWalks(): Promise<Walk[]> {
  const { getCollection } = await import("astro:content");
  const entries = await getCollection("walk");

  const groups = new Map<string, { site: string; codename: string; spines: WalkChapterSpine[] }>();
  for (const entry of entries) {
    // Skip the story home (`_home.mdx`) and any non-chapter entry — chapters carry a numeric step.
    if (typeof (entry.data as { step?: unknown }).step !== "number") continue;
    const [site, codename] = String(entry.id).split("/");
    if (!site || !codename) continue;
    const key = `${site}/${codename}`;
    let group = groups.get(key);
    if (!group) {
      group = { site, codename, spines: [] };
      groups.set(key, group);
    }
    group.spines.push(entry.data as WalkChapterSpine);
  }

  return [...groups.values()].map((g) =>
    buildWalk(g.site, g.codename, storyMetaFor(g.site, g.codename), g.spines),
  );
}

// ── The sync source of `walk.WALKS` (#733) ─────────────────────────────────
// Read every chapter's frontmatter at build, plugin-free: `?raw` gives the file text (no MDX
// transform needed, so this resolves the same in vitest as in the Astro build), and we parse the
// YAML frontmatter ourselves. Build-only — `walk.ts` has no client consumers (like `bundle.ts`).
const WALK_RAW = import.meta.glob("../../../src/content/walk/**/*.mdx", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

/** The YAML frontmatter block of an MDX file, parsed to an object (empty if none). */
function frontmatterOf(raw: string): Record<string, unknown> {
  const m = raw.match(/^---\n([\s\S]*?)\n---/);
  return m ? ((parseYaml(m[1]) as Record<string, unknown>) ?? {}) : {};
}

/** Recover `[site, codename, slug]` from a `…/stories/<site>/<codename>/<slug>.mdx` path. */
function pathParts(path: string): [string, string] | null {
  const parts = path.split("/");
  const i = parts.lastIndexOf("walk");
  const site = parts[i + 1];
  const codename = parts[i + 2];
  return i >= 0 && site && codename ? [site, codename] : null;
}

/**
 * Every registered `Walk`, built synchronously from the `stories` collection frontmatter — the
 * source of `walk.WALKS` (#733). `_home.mdx` and any non-chapter entry (no numeric `step`) are
 * skipped; chapters group by `<site>/<codename>` and `buildWalk` assembles each, with title/dek
 * from the site registry (`storyMetaFor`).
 */
export function buildAllWalks(): Walk[] {
  const groups = new Map<string, { site: string; codename: string; spines: WalkChapterSpine[] }>();
  for (const [path, raw] of Object.entries(WALK_RAW)) {
    const fm = frontmatterOf(raw);
    if (typeof fm.step !== "number") continue; // skip _home + any non-chapter entry
    const ids = pathParts(path);
    if (!ids) continue;
    const [site, codename] = ids;
    const key = `${site}/${codename}`;
    let group = groups.get(key);
    if (!group) {
      group = { site, codename, spines: [] };
      groups.set(key, group);
    }
    group.spines.push({
      step: fm.step,
      slug: String(fm.slug),
      title: String(fm.title),
      skill: String(fm.skill),
      anchor: String(fm.anchor),
      anchorRecordRels: Array.isArray(fm.anchorRecordRels) ? (fm.anchorRecordRels as string[]) : [],
      live: fm.live !== false, // STORY_CHAPTER_SCHEMA defaults live=true
      eyebrow: fm.eyebrow != null ? String(fm.eyebrow) : undefined,
      studySection: fm.studySection != null ? String(fm.studySection) : undefined,
    });
  }
  return [...groups.values()].map((g) =>
    buildWalk(g.site, g.codename, storyMetaFor(g.site, g.codename), g.spines),
  );
}
