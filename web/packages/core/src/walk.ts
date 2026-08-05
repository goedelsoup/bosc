/**
 * The story model — the per-site narrative spine (#724/#729), layered over a site's
 * reference library. A `Walk` is one reading path (a codename) over a site's record: an
 * ordered list of teaching `Chapter`s plus the record→chapter backlink anchors. A site can
 * host several stories over time; today the only one is Lima's `project-bosc` (the original
 * guided walk).
 *
 * This module is the single source of truth for chapter order, the wayfinding bar, the story
 * home (the on-ramp), and the table of contents. A story lives under its site at
 * `/network/<id>/stories/<codename>`; chapters are flattened directly beneath. The
 * `walkFor(site, codename)` lookup + the per-story `chapterHref`/`walkChapterByStep`/…
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
import { walkUrl } from "./site";
import { surfacedWalks } from "./sites";
import { buildAllWalks } from "./walkContent";

export interface Chapter {
  /** 1-based position among the teaching chapters. */
  step: number;
  /** Route slug, flattened directly under the story (`walkBase/<slug>`). */
  slug: string;
  title: string;
  /** The record-reading skill the chapter teaches. */
  skill: string;
  /** The anchor record(s) it tears down. */
  anchor: string;
  /** Whether the chapter page exists (vs. still drafting). */
  live: boolean;
  /** The impact-study chapter this walk chapter teaches toward (a `STUDY_CHAPTERS` id) —
   *  the walk↔study cross-link: the walk teaches the record-reading, the study owns the
   *  finding, and each surface links the other exactly once (never inlines it). */
  studySection?: string;
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
 *
 * **Named `ContentOwner`, not `WalkOwner` or `StoryOwner` (#1972).** It is the one type in this
 * split that genuinely spans BOTH systems: a `site` owner owns an editorial walk, a `user` owner
 * owns a reader-composed Story, and the Pages Functions type their user-owned rows with it. Naming
 * it for either half would misdescribe the other.
 */
export interface ContentOwner {
  kind: "site" | "user";
  /** A `site` owner's `id` is the network-site slug; a `user` owner's `id` is the user id. */
  id: string;
}

/** The site-owner for a network-site slug — the owner of that site's editorial stories. */
export function siteOwner(site: string): ContentOwner {
  return { kind: "site", id: site };
}

/**
 * Filter stories to a single owner (#1092): a site page lists its own site-owned stories (and,
 * later, featured user-owned ones); an account page lists a user's own. Matches on the `(kind, id)`
 * pair so a site slug and a user id sharing a string can never collide.
 */
export function walksOwnedBy(stories: readonly Walk[], owner: ContentOwner): Walk[] {
  return stories.filter((s) => s.owner.kind === owner.kind && s.owner.id === owner.id);
}

/** A site's story: a reading path (codename) over its record. */
export interface Walk {
  /**
   * Who owns this story (#1092). For a site-owned (editorial) story `owner` is
   * `{ kind: "site", id: site }`, so `owner.id === site`; the field is the substrate the
   * user-authored path (a DB-sourced `{ kind: "user", id }`) shares without a rename.
   */
  owner: ContentOwner;
  /** Registry slug of the site this story belongs to (the `bosc.sites` / map key). */
  site: string;
  /** Walk codename — the URL segment under the site's `stories/` and the store key. */
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
 * `buildWalk` (title/dek come from the site registry). The collection is now the single source
 * of truth; the hand-maintained Lima spine that used to live here is gone. Adding a chapter (or a
 * whole site's story) is an MDX edit, not a code edit.
 */
export const WALKS: readonly Walk[] = buildAllWalks();

/** The story for a (site, codename) pair, or `undefined` if none is registered. */
export function walkFor(site: string, codename: string): Walk | undefined {
  return WALKS.find((s) => s.site === site && s.codename === codename);
}

/** The story home (on-ramp) href for a story. */
export function walkHomeHref(story: Walk): string {
  return walkUrl(story.site, story.codename, "");
}

/** The table-of-contents href for a story. */
export function walkContentsHref(story: Walk): string {
  return walkUrl(story.site, story.codename, "/contents");
}

/** A chapter href within a story (`walkBase/<slug>`). */
export function chapterHref(story: Walk, slug: string): string {
  return walkUrl(story.site, story.codename, `/${slug}`);
}

/** The chapter at a given step within a story. */
export function walkChapterByStep(story: Walk, step: number): Chapter | undefined {
  return story.chapters.find((c) => c.step === step);
}

/** The record→chapter backlink for a `rel` within a story. */
export function walkAnchorForIn(story: Walk, rel: string): WalkAnchor | undefined {
  return story.anchors[rel];
}

// ── Surfaced-story resolution (#1256) ────────────────────────────────────────
// A story is *surfaced* only when it's registered in the `sites.ts` WALKS overlay AND not
// `hidden` (see `surfacedWalks`). Its MDX content, its `/stories/<codename>` routes, and the
// WALK_* content-presence guard all stay put regardless — so hiding a story unsurfaces it
// everywhere without touching the record. Every site-scoped surface (the hub, catalog/atoms, the
// record→chapter backlinks) resolves through these, NOT through the Lima-pinned WALK_* conveniences,
// so a hidden or absent story emits no links and no non-Lima site can leak into Lima's story.

/** Whether a site *surfaces* a story codename — registered in the `sites.ts` overlay and not hidden. */
export function siteSurfacesWalk(site: string, codename: string): boolean {
  return surfacedWalks(site).some((r) => r.codename === codename);
}

/** The active site's surfaced story (its first *surfaced* — registered and non-hidden — story), or
 *  `undefined` when the site surfaces none. The ambient, hidden-aware peer of `LIMA_WALK`. */
export function activeWalk(): Walk | undefined {
  const ref = surfacedWalks(activeSite())[0];
  return ref ? walkFor(activeSite(), ref.codename) : undefined;
}

/** The record→chapter backlink for a `rel` within the *active site's surfaced story*, or
 *  `undefined` when the site surfaces no story — the current-site, hidden-aware peer of
 *  `walkAnchorFor` (used by the timeline + record-block backlinks). */
export function activeWalkAnchorFor(rel: string): WalkAnchor | undefined {
  const story = activeWalk();
  return story ? walkAnchorForIn(story, rel) : undefined;
}

// ── Lima-pinned conveniences ────────────────────────────────────────────────
// The original `WALK_*` / `walk*` API, now derived from the Lima `project-bosc` story (resolved
// from the collection) so every existing caller (the story pages, nav, the record block) is
// unchanged. Multi-site callers resolve a `Walk` via `walkFor` and use the per-story helpers.

const LIMA_WALK: Walk = (() => {
  const story = walkFor(LIMA_SLUG, DEFAULT_STORY_CODENAME);
  if (!story) {
    throw new Error(
      `The Lima "${DEFAULT_STORY_CODENAME}" story is missing from the stories collection — ` +
        "the WALK_* conveniences derive from it.",
    );
  }
  return story;
})();

export const WALK_CHAPTERS: Chapter[] = LIMA_WALK.chapters;
export const WALK_TOTAL = WALK_CHAPTERS.length;
export const WALK_ANCHORS: Record<string, WalkAnchor> = LIMA_WALK.anchors;

/** The story home (the on-ramp / "where the walk begins"). */
export const WALK_START_HREF = walkHomeHref(LIMA_WALK);
/** The table of contents — all chapters in order. */
export const WALK_INDEX_HREF = walkContentsHref(LIMA_WALK);

export function walkHref(slug: string): string {
  return chapterHref(LIMA_WALK, slug);
}

export function chapterByStep(step: number): Chapter | undefined {
  return walkChapterByStep(LIMA_WALK, step);
}

export function walkAnchorFor(rel: string): WalkAnchor | undefined {
  return walkAnchorForIn(LIMA_WALK, rel);
}
