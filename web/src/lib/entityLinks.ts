/**
 * Entity-link resolution. A profile (place, person, entity) can reference a
 * related entity that has no generated `/wiki/entities/<slug>/` page — e.g. a
 * relationship target that isn't itself in the `entities` feed, or any entity
 * absent from a trimmed bundle (the CI sample bundle). Linking to it
 * unconditionally emits a 404. `entityHref` returns a href only when the page
 * will exist, so callers fall back to plain text instead. The present set
 * mirrors the `getStaticPaths` of `wiki/entities/[key].astro`.
 *
 * The set is resolved **per active site at call time** (memoized per slug), not at
 * module load — computing it once would freeze it to the default (Lima) feed and
 * validate every site's links against Lima's entities (#1217).
 */
import { activeSite, hasFeed, loadFeed } from "./bundle";
import { slugify, type EntityNode } from "./feeds";
import { withBase } from "./site";

const presentBySite = new Map<string, Set<string>>();

/** The slugs of the *active* site's entity pages — computed once per site, then cached. */
function presentEntities(): Set<string> {
  const slug = activeSite();
  let set = presentBySite.get(slug);
  if (!set) {
    set = new Set((hasFeed("entities") ? loadFeed<EntityNode[]>("entities") : []).map((e) => slugify(e.key)));
    presentBySite.set(slug, set);
  }
  return set;
}

/** Href to an entity's page, or `undefined` if no page is generated for it. */
export function entityHref(key: string): string | undefined {
  const slug = slugify(key);
  return presentEntities().has(slug) ? `${withBase("/wiki/entities/")}${slug}/` : undefined;
}
