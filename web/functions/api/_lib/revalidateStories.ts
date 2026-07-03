// The catalog revalidation job (#1099) — "a scheduled job over one table". Ties the pure core
// (`src/lib/revalidate`) to the Lakebase (Postgres) store: walk every Story not yet validated against the current
// catalog_version, re-resolve its cited handles, auto-heal renamed ones (rewrite refs + SDM), and
// flag the rest `stale` so the author is nudged. Idempotent: a second pass over the same catalog is a
// no-op (healed handles now resolve; still-dangling stay flagged; up-to-date stories are skipped).

import type { StoryDocument } from "../../../src/lib/sdm";
import { type RenameMap, remapSdmHandles, revalidateHandles } from "../../../src/lib/revalidate";
import { type PgLike, type StoryRef, applyStoryRevalidation, storiesToRevalidate } from "./storiesStore";

export interface RevalidationSummary {
  /** Stories inspected (those behind the current catalog_version). */
  checked: number;
  /** Dangling handles auto-healed via the rename map. */
  healed: number;
  /** Stories flagged stale (≥1 unhealed dangling handle). */
  flagged: number;
  /** The flagged Story ids (for an admin follow-up / author notification). */
  flaggedIds: string[];
}

/** The current catalog the job resolves against — the live handle set + its version stamp. */
export interface CurrentCatalog {
  handles: ReadonlySet<string>;
  version: string;
}

export async function revalidateAll(
  db: PgLike,
  catalog: CurrentCatalog,
  renames: RenameMap,
  now: string,
): Promise<RevalidationSummary> {
  const targets = await storiesToRevalidate(db, catalog.version);
  let healed = 0;
  const flaggedIds: string[] = [];

  for (const target of targets) {
    const result = revalidateHandles(
      target.refs.map((r) => r.handle),
      catalog.handles,
      renames,
    );
    const healMap: Record<string, string> = Object.fromEntries(result.heals.map((h) => [h.from, h.to]));

    // Rewrite refs (thin snapshot preserved, only the handle moves) + the stored SDM for healed handles.
    const newRefs: StoryRef[] = target.refs.map((r) =>
      healMap[r.handle] ? { ...r, handle: healMap[r.handle] } : r,
    );
    let sdmJson = target.sdm_json;
    if (result.heals.length > 0) {
      healed += result.heals.length;
      const doc = JSON.parse(target.sdm_json) as StoryDocument;
      sdmJson = JSON.stringify(remapSdmHandles(doc, healMap));
    }
    if (result.stale) flaggedIds.push(target.id);

    await applyStoryRevalidation(db, target.id, {
      sdmJson,
      refs: newRefs,
      catalogVersion: catalog.version,
      stale: result.stale,
      now,
    });
  }

  return { checked: targets.length, healed, flagged: flaggedIds.length, flaggedIds };
}
