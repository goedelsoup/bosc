/**
 * The story model — the per-site narrative spine (#724/#729), layered over a site's
 * reference library. A `Story` is one reading path (a codename) over a site's record: an
 * ordered list of teaching `Chapter`s plus the record→chapter backlink anchors. A site can
 * host several stories over time; today the only one is Lima's `project-bosc` (the original
 * guided walk).
 *
 * This module is the single source of truth for chapter order, the wayfinding bar, the story
 * home (the on-ramp), and the table of contents. A story lives under its site at
 * `/network/<id>/stories/<codename>`; chapters are flattened directly beneath. The
 * `storyFor(site, codename)` lookup + the per-story `chapterHref`/`storyChapterByStep`/…
 * helpers are the framework API; the `WALK_*`/`walk*` exports are the Lima-pinned
 * conveniences that keep today's callers (the story pages, nav, the record block) unchanged.
 *
 * Chapter ordering is cause → consequence so no figure depends on a number established in a
 * later chapter — Assembly (how the land + deal were put together and kept quiet) follows Who
 * and precedes Scale; Scale (air) precedes Water because the cooling draw derives from the IT
 * load. `live` is the build flag the wayfinding/index gate their go-links on.
 */

import { activeSite } from "./bundle";
import { DEFAULT_STORY_CODENAME, LIMA_SLUG } from "./routes";
import { storyHref } from "./site";
import { surfacedStories } from "./sites";
import { buildAllStories } from "./stories";

export interface Chapter {
  /** 1-based position among the teaching chapters. */
  step: number;
  /** Route slug, flattened directly under the story (`storyBase/<slug>`). */
  slug: string;
  title: string;
  /** The record-reading skill the chapter teaches. */
  skill: string;
  /** The anchor record(s) it tears down. */
  anchor: string;
  /** Whether the chapter page exists (vs. still drafting). */
  live: boolean;
}

/** @deprecated Prefer {@link Chapter}; kept so existing type imports don't break. */
export type WalkChapter = Chapter;

/**
 * The reciprocal of the teardowns' `recordRel`: which chapter tears a library record down,
 * keyed by the record's `rel`. Drives the "↩ seen in the walk" backlink on the record block,
 * so the deep links resolve both directions.
 */
export interface WalkAnchor {
  ch: string;
  slug: string;
  label: string;
}

/**
 * The **owner axis** (#1092) — the discriminator that unifies today's editorial stories and the
 * new user-authored ones as *one resource, two owners*, so they never contend (not in naming,
 * storage, or routing). A `site` owner is the editorial case (owner `id` = the network-site slug);
 * a `user` owner is the reader-authored case (owner `id` = the authoring user's id). This file is
 * the **site-owned** implementation — recognized as one special case of the axis, no rename (#1092).
 */
export interface StoryOwner {
  kind: "site" | "user";
  /** A `site` owner's `id` is the network-site slug; a `user` owner's `id` is the user id. */
  id: string;
}

/** The site-owner for a network-site slug — the owner of that site's editorial stories. */
export function siteOwner(site: string): StoryOwner {
  return { kind: "site", id: site };
}

/**
 * Filter stories to a single owner (#1092): a site page lists its own site-owned stories (and,
 * later, featured user-owned ones); an account page lists a user's own. Matches on the `(kind, id)`
 * pair so a site slug and a user id sharing a string can never collide.
 */
export function storiesOwnedBy(stories: readonly Story[], owner: StoryOwner): Story[] {
  return stories.filter((s) => s.owner.kind === owner.kind && s.owner.id === owner.id);
}

/** A site's story: a reading path (codename) over its record. */
export interface Story {
  /**
   * Who owns this story (#1092). For a site-owned (editorial) story `owner` is
   * `{ kind: "site", id: site }`, so `owner.id === site`; the field is the substrate the
   * user-authored path (a DB-sourced `{ kind: "user", id }`) shares without a rename.
   */
  owner: StoryOwner;
  /** Registry slug of the site this story belongs to (the `bosc.sites` / map key). */
  site: string;
  /** Story codename — the URL segment under the site's `stories/` and the store key. */
  codename: string;
  /** Display title, e.g. "Project BOSC". */
  title: string;
  /** One-line description (the on-ramp dek / nav blurb). */
  dek: string;
  /** The teaching chapters, in reading order. */
  chapters: Chapter[];
  /** record `rel` → the chapter that tears it down. */
  anchors: Record<string, WalkAnchor>;
}

/**
 * Every registered story across the network — built from the `stories` MDX collection (#733):
 * each chapter's frontmatter is its spine, grouped by `<site>/<codename>` and assembled by
 * `buildStory` (title/dek come from the site registry). The collection is now the single source
 * of truth; the hand-maintained Lima spine that used to live here is gone. Adding a chapter (or a
 * whole site's story) is an MDX edit, not a code edit.
 */
export const STORIES: readonly Story[] = buildAllStories();

/** The story for a (site, codename) pair, or `undefined` if none is registered. */
export function storyFor(site: string, codename: string): Story | undefined {
  return STORIES.find((s) => s.site === site && s.codename === codename);
}

/** The story home (on-ramp) href for a story. */
export function storyHomeHref(story: Story): string {
  return storyHref(story.site, story.codename, "");
}

/** The table-of-contents href for a story. */
export function storyContentsHref(story: Story): string {
  return storyHref(story.site, story.codename, "/contents");
}

/** A chapter href within a story (`storyBase/<slug>`). */
export function chapterHref(story: Story, slug: string): string {
  return storyHref(story.site, story.codename, `/${slug}`);
}

/** The chapter at a given step within a story. */
export function storyChapterByStep(story: Story, step: number): Chapter | undefined {
  return story.chapters.find((c) => c.step === step);
}

/** The record→chapter backlink for a `rel` within a story. */
export function storyAnchorFor(story: Story, rel: string): WalkAnchor | undefined {
  return story.anchors[rel];
}

// ── Surfaced-story resolution (#1256) ────────────────────────────────────────
// A story is *surfaced* only when it's registered in the `sites.ts` STORIES overlay AND not
// `hidden` (see `surfacedStories`). Its MDX content, its `/stories/<codename>` routes, and the
// WALK_* content-presence guard all stay put regardless — so hiding a story unsurfaces it
// everywhere without touching the record. Every site-scoped surface (the hub, catalog/atoms, the
// record→chapter backlinks) resolves through these, NOT through the Lima-pinned WALK_* conveniences,
// so a hidden or absent story emits no links and no non-Lima site can leak into Lima's story.

/** Whether a site *surfaces* a story codename — registered in the `sites.ts` overlay and not hidden. */
export function siteSurfacesStory(site: string, codename: string): boolean {
  return surfacedStories(site).some((r) => r.codename === codename);
}

/** The active site's surfaced story (its first *surfaced* — registered and non-hidden — story), or
 *  `undefined` when the site surfaces none. The ambient, hidden-aware peer of `LIMA_STORY`. */
export function activeStory(): Story | undefined {
  const ref = surfacedStories(activeSite())[0];
  return ref ? storyFor(activeSite(), ref.codename) : undefined;
}

/** The record→chapter backlink for a `rel` within the *active site's surfaced story*, or
 *  `undefined` when the site surfaces no story — the current-site, hidden-aware peer of
 *  `walkAnchorFor` (used by the timeline + record-block backlinks). */
export function activeStoryAnchorFor(rel: string): WalkAnchor | undefined {
  const story = activeStory();
  return story ? storyAnchorFor(story, rel) : undefined;
}

// ── Lima-pinned conveniences ────────────────────────────────────────────────
// The original `WALK_*` / `walk*` API, now derived from the Lima `project-bosc` story (resolved
// from the collection) so every existing caller (the story pages, nav, the record block) is
// unchanged. Multi-site callers resolve a `Story` via `storyFor` and use the per-story helpers.

const LIMA_STORY: Story = (() => {
  const story = storyFor(LIMA_SLUG, DEFAULT_STORY_CODENAME);
  if (!story) {
    throw new Error(
      `The Lima "${DEFAULT_STORY_CODENAME}" story is missing from the stories collection — ` +
        "the WALK_* conveniences derive from it.",
    );
  }
  return story;
})();

export const WALK_CHAPTERS: Chapter[] = LIMA_STORY.chapters;
export const WALK_TOTAL = WALK_CHAPTERS.length;
export const WALK_ANCHORS: Record<string, WalkAnchor> = LIMA_STORY.anchors;

/** The story home (the on-ramp / "where the walk begins"). */
export const WALK_START_HREF = storyHomeHref(LIMA_STORY);
/** The table of contents — all chapters in order. */
export const WALK_INDEX_HREF = storyContentsHref(LIMA_STORY);

export function walkHref(slug: string): string {
  return chapterHref(LIMA_STORY, slug);
}

export function chapterByStep(step: number): Chapter | undefined {
  return storyChapterByStep(LIMA_STORY, step);
}

export function walkAnchorFor(rel: string): WalkAnchor | undefined {
  return storyAnchorFor(LIMA_STORY, rel);
}
