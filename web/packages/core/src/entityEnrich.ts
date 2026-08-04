/**
 * Entity-page enrichment (#1572, epic #1560 workstream C): the corpus-grounded joins that
 * turn a bare entity node into a richer wiki page — its graph degree, its GLEIF/LEI registry
 * record, and that record's resolved parent chain. Every value is pulled from a committed
 * feed; nothing is fabricated (the epic's standing rule).
 */
import { hasFeed, loadFeed, manifestOrNull, runWithSite } from "./bundle";
import type { EntityNode, LeiInventory, LeiRecord, LeiRef, RelationshipEdge } from "./feeds";
import { entityHref } from "./entityLinks";
import { networkEntities, WIKI_CANONICAL } from "./networkEntities";

/**
 * The graph degree of an entity — the same count a yidam `corpus-index` reports for a node,
 * computed here directly from the `relationships` feed (the edge set the mirror projects, so
 * the two agree). `out`/`in` are directed edge counts; `total` is their sum; `neighbors` is the
 * number of *distinct* parties on the other end (two edges to one party count as degree 2 but a
 * single neighbor). A self-edge doesn't add a neighbor.
 */
export interface EntityDegree {
  out: number;
  in: number;
  total: number;
  neighbors: number;
}

/**
 * Degree from an entity's already-partitioned edges — pass the `outgoing` (src === key) and
 * `incoming` (dst === key) slices the entity page has computed, so the count isn't re-derived.
 */
export function entityDegree(
  key: string,
  outgoing: RelationshipEdge[],
  incoming: RelationshipEdge[],
): EntityDegree {
  const neighbors = new Set<string>();
  for (const r of outgoing) neighbors.add(r.dst);
  for (const r of incoming) neighbors.add(r.src);
  neighbors.delete(key); // a self-edge is not a neighbor
  return {
    out: outgoing.length,
    in: incoming.length,
    total: outgoing.length + incoming.length,
    neighbors: neighbors.size,
  };
}

/**
 * The GLEIF registry record for an entity, joined by **exact LEI code** against the `lei`
 * feed (the feed itself is pinned by ID — no fuzzy name match — so the join is 1:1 and
 * authoritative). Returns null when the entity carries no LEI, the inventory isn't shipped,
 * or the code isn't in it.
 *
 * Read from the **canonical wiki build** (#1906): a corporate register is one register, not a
 * per-site reading, and only that bundle ships the `lei` feed. Before the wiki widened past one
 * bundle this happened to be the ambient site; now that the page can render a party carried only
 * by a peer, the coupling has to be stated or a peer-only entity's LEI would silently stop
 * resolving.
 */
export function entityLei(entity: Pick<EntityNode, "lei">): LeiRecord | null {
  if (!entity.lei) return null;
  return runWithSite(WIKI_CANONICAL, () => {
    // `manifestOrNull` before `hasFeed`: naming the canonical build must not make a build that
    // doesn't ship it (a thin fixture, a peer-only export) throw where it used to degrade.
    if (!manifestOrNull() || !hasFeed("lei")) return null;
    const inv = loadFeed<LeiInventory>("lei");
    return inv.records.find((r) => r.lei === entity.lei) ?? null;
  });
}

/** A resolved GLEIF parent — its `{lei, name}` plus an entity-page href when the parent's LEI
 *  is itself a node in the graph (so the ownership chain stays clickable inside the wiki). */
export interface LeiParent {
  lei: string;
  name: string;
  /** Set only when the parent LEI belongs to an entity that has its own generated page. */
  href?: string;
}

/**
 * Resolve a GLEIF parent reference to a linkable target: its name is authoritative from the
 * registry, and if the parent's LEI matches an entity node's `lei` (and that entity has a
 * page), we attach the href so the corporate chain is navigable. Returns null for a missing ref.
 *
 * The lookup runs over the **network** graph (#1906), not one site's feed: a parent whose only
 * appearance is at a peer watershed point now has a page, and matching it against the reference
 * bundle alone would drop the link precisely where the corporate chain crosses sites — which is
 * the cross-site view the entity graph exists for.
 */
export function leiParent(ref: LeiRef | null | undefined): LeiParent | null {
  if (!ref) return null;
  const owner = networkEntities().find((e) => e.node.lei && e.node.lei === ref.lei);
  const href = owner ? entityHref(owner.key) : undefined;
  return { lei: ref.lei, name: ref.name, href };
}

/** A one-line label for a GLEIF legal address (`City, REGION, COUNTRY`), or null when empty. */
export function leiAddress(
  a: { city?: string; region?: string; country?: string } | null | undefined,
): string | null {
  if (!a) return null;
  const parts = [a.city, a.region, a.country].filter((s): s is string => Boolean(s));
  return parts.length ? parts.join(", ") : null;
}
