/**
 * Entity-link resolution. A profile (place, person, entity) can reference a
 * related entity that has no generated `/wiki/entities/<slug>/` page — e.g. a
 * relationship target that isn't itself in the `entities` feed, or any entity
 * absent from a trimmed bundle (the CI sample bundle). Linking to it
 * unconditionally emits a 404. `entityHref` returns a href only when the page
 * will exist, so callers fall back to plain text instead.
 *
 * The present set is the **network union** (`networkEntities`, #1906) — the same set
 * `wiki/entities/[key].astro` mints its paths from, so the guard and the routes cannot
 * disagree. It was previously resolved per active site, which was wrong in both directions
 * once the two sets stopped matching: a peer's page linked entities that had no page (the
 * wiki built from one bundle), and the reference site's pages refused to link a party that
 * only a peer carries. Now that the wiki builds from every selectable site, one set answers
 * for every build, so it is memoized once rather than per slug (#1217's per-site cache was a
 * fix for the per-site *feed* read this no longer does).
 */
import { networkEntitySlugs } from "./networkEntities";
import { slugify } from "./feeds";
import { withBase } from "./site";

/** Href to an entity's page, or `undefined` if no page is generated for it. */
export function entityHref(key: string): string | undefined {
  const slug = slugify(key);
  return networkEntitySlugs().has(slug) ? `${withBase("/wiki/entities/")}${slug}/` : undefined;
}
