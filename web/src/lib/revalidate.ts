/**
 * Catalog revalidation core (#1099) — the pure, framework-free logic that keeps stored Story
 * references honest as the corpus evolves. Handles are `<kind>:<site>:<localId>` reusing each feed's
 * existing stable key (#1093), but a `localId` (a record `rel`, a slug) *can* change, so a handle a
 * Story cited may stop resolving. This module re-resolves a Story's handles against the current
 * catalog and decides, per handle: still-good, auto-healed (a curated rename maps it to a resolvable
 * handle), or dangling (flag the Story so the author is nudged; the renderer already degrades).
 *
 * Pure (no D1, no fs) — the store/job layer (`functions/api/_lib/revalidateStories.ts`) applies the
 * result; the tests exercise this directly.
 */
import type { SdmBlock, StoryDocument } from "./sdm";

/** A curated `oldHandle → newHandle` map for renamed atoms (the optional auto-heal from #1099). */
export type RenameMap = Record<string, string>;

export interface RevalidationResult {
  /** Dangling handles a rename resolved to a live one (auto-healed). */
  heals: { from: string; to: string }[];
  /** Handles that still don't resolve (no rename, or the rename target is also gone) — the flag. */
  stillDangling: string[];
  /** Whether the Story should be flagged stale (has at least one unhealed dangling handle). */
  stale: boolean;
}

/**
 * Re-resolve a Story's cited handles against the current catalog handle set. A handle in the catalog
 * is fine; one that isn't is dangling — healed when a rename maps it to a resolvable handle, else it
 * stays dangling and the Story is flagged. Deduplicates repeated handles.
 */
export function revalidateHandles(
  handles: readonly string[],
  catalog: ReadonlySet<string>,
  renames: RenameMap = {},
): RevalidationResult {
  const heals: { from: string; to: string }[] = [];
  const stillDangling: string[] = [];
  const seen = new Set<string>();
  for (const h of handles) {
    if (catalog.has(h) || seen.has(h)) continue;
    seen.add(h);
    const to = renames[h];
    if (to && catalog.has(to)) heals.push({ from: h, to });
    else stillDangling.push(h);
  }
  return { heals, stillDangling, stale: stillDangling.length > 0 };
}

/**
 * Rewrite atom handles in an SDM tree via a `{ from → to }` map — the auto-heal applied to the stored
 * render artifact so a renamed citation resolves live again. Pure: returns a new document, and only
 * the `handle` changes (the `kind`/`title` thin snapshot is preserved).
 */
export function remapSdmHandles(doc: StoryDocument, map: Record<string, string>): StoryDocument {
  const remapBlock = (block: SdmBlock): SdmBlock => {
    switch (block.type) {
      case "atom":
        return map[block.handle] ? { ...block, handle: map[block.handle] } : block;
      case "blockquote":
      case "callout":
        return { ...block, children: block.children.map(remapBlock) };
      case "list":
        return { ...block, items: block.items.map((item) => item.map(remapBlock)) };
      default:
        return block;
    }
  };
  return { ...doc, blocks: doc.blocks.map(remapBlock) };
}
