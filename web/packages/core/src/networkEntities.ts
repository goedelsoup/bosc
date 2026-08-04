/**
 * The entity graph, unioned across the network (#1906, epic #1884 follow-on).
 *
 * ## The finding
 *
 * `taxonomy.ts` declares entities **network-global** — "the same operator, counsel, or shell
 * surfaces at more than one watershed point" — so the graph is the network's spine and there is
 * deliberately no per-site entity route. The build did not honour that. `getStaticPaths` in
 * `src/pages/wiki/**` runs *outside* `runWithSite`, so `activeSite()` fell through to the
 * reference site and the whole wiki was minted from one bundle. An entity carried only by a peer —
 * Fort Wayne's `DANA LIGHT AXLE PRODUCTS`, and `project-zodiac-campus`, the campus node for its
 * own facility — was in the bundle, in the graph, and unreachable: no page here, and none anywhere
 * else, because the per-site fallback route does not exist by design.
 *
 * This module is the widened read: one merged node per party, over every site that publishes an
 * `entities` feed. It is the single owner of that union — the page, the index, the link guard
 * (`entityLinks.ts`), the search rows, and the graph layout all read it, so they cannot disagree
 * about which entities have a page.
 *
 * ## Which sites
 *
 * The **selectable** registry sites, in registry order, that have a committed bundle. Selectable is
 * the same boundary `withSitePaths` uses for per-site routes, so the union is exactly the set of
 * builds whose pages can link an entity; nothing links into a site that emits no page tree. A
 * registered-but-unbuilt slug degrades through `manifestOrNull` rather than throwing — a site
 * promoted in the registry before its bundle is exported must not take the whole wiki down.
 *
 * ## The merge rule
 *
 * Stated here, in the module, rather than implied by iteration order. An entity page that silently
 * dropped one site's reading of a party would be the same class of bug as #1886.
 *
 * 1. **Identity is the canonical `key`.** Rows merge when their `key` matches exactly — the
 *    cross-feed reference id that `relationships`, `people.entity_key`, and the corpus mirror all
 *    resolve against. Names are never matched fuzzily here: entity resolution happens once, in the
 *    pipeline (`watermark.pipeline.entities`), and re-resolving at render would invent a party the
 *    record does not assert. Two *different* keys that slugify to one route are a genuine
 *    collision, and {@link networkEntities} throws rather than merging two parties into one page.
 *
 * 2. **Precedence is registry order.** The first site in `SITES` carrying a party is its
 *    **primary** reading. That puts the reference build first — the deepest record, and the one
 *    whose network-global inventories (`lei`, `defense-contractors`) the wiki's other pages already
 *    read. Declared and deterministic: not feed order, not directory iteration.
 *
 * 3. **Set-valued fields union.** `variants`, `signals`, `parcels`, `addresses`, `sources` are
 *    concatenated in precedence order and deduped. Nothing a site contributed is dropped.
 *
 * 4. **Scalar readings take the primary, and every reading is kept.** `display`, `kind`,
 *    `classification`, `relation_class`, `relation_basis` are a site's *reading* of a party.
 *    The primary supplies the headline; every site's reading stays on {@link NetworkEntity.readings},
 *    and any field two sites read differently is recorded in {@link NetworkEntity.disagreements} so
 *    the page can show both rather than silently picking one.
 *
 * 5. **Registry identifiers take the first non-null.** `lei`, `uei`, `federal_obligations` describe
 *    the party, not a site's reading of it: a bundle that hasn't joined the GLEIF/USAspending
 *    inventory contributes `null`, which is an *absence*, not a competing value. Two unequal
 *    non-nulls are a disagreement, surfaced like any other.
 *
 * 6. **Role counts are per site and are NOT summed.** A `roles` tally counts appearances in *that
 *    site's* record, and the graph builder reads network-global reference datasets into every
 *    site's graph — `GENERAL DYNAMICS LAND SYSTEMS` carries `jsmc_operator: 1` in all four
 *    selectable bundles, off one source. Summing would report four operator roles where the record
 *    asserts one, which is fabrication. The merged node keeps the primary's tally for a
 *    single-site party; a party on more than one watershed point shows its tallies **per site** and
 *    the page prints no network total, because none is derivable from what the feeds carry.
 *
 * Edges merge on the same rule: deduped on the full `(src, rel, dst, date, ref, source)` tuple, so
 * one document read into two sites' graphs is one edge carrying both sites. Two edges differing in
 * any field are two assertions, not a duplicate.
 */
import { siteHref } from "./base";
import { hasFeed, loadFeed, manifestOrNull, runWithSite } from "./bundle";
import { slugify, type EntityNode, type PersonItem, type RelationshipEdge } from "./feeds";
import { LIMA_SLUG } from "./routes";
import { SITES } from "./sites";
import {
  hypothesisBacklinks,
  openQuestionBacklinks,
  relatedConcepts,
  type HypothesisBacklink,
  type OpenQuestionBacklink,
  type RelatedConcept,
} from "./wiki";

/** One site's reading of a party — its own `entities` row, kept whole. */
export interface EntityReading {
  /** The registry slug whose bundle carries this reading. */
  site: string;
  node: EntityNode;
  /** That site's role tally, and its total — per site, never summed across sites (rule 6). */
  roles: Record<string, number>;
  roleTotal: number;
}

/** The fields a merge can have to choose between. */
export type MergedField =
  | "display"
  | "kind"
  | "classification"
  | "relation_class"
  | "relation_basis"
  | "lei"
  | "uei"
  | "federal_obligations";

/** A field two sites read differently — recorded, never resolved out of sight. */
export interface EntityDisagreement {
  field: MergedField;
  /** Every distinct reading, in precedence order; the first is the one the headline shows. */
  readings: { site: string; value: string }[];
}

/** A party as the network-global wiki renders it: one merged node plus every site behind it. */
export interface NetworkEntity {
  /** The canonical cross-feed key. */
  key: string;
  /** The route segment — `slugify(key)`. */
  slug: string;
  /** The merged node: the primary reading's scalars over the unioned set fields (rules 3–5). */
  node: EntityNode;
  /** The registry slugs carrying this party, in precedence order. `sites[0]` is the primary. */
  sites: string[];
  readings: EntityReading[];
  disagreements: EntityDisagreement[];
}

/** One edge of the unioned graph, with the sites whose feed carries it. */
export interface NetworkEdge {
  edge: RelationshipEdge;
  sites: string[];
}

/** A curated profile of a party, and the site whose record curates it (`people` is per-site). */
export interface EntityProfile {
  site: string;
  person: PersonItem;
}

/**
 * The sites the network-global wiki unions over: selectable, in registry order, with a bundle on
 * disk. `manifestOrNull` rather than `hasFeed` so a promoted-but-unexported slug degrades to
 * "contributes nothing" instead of throwing out of `getStaticPaths`.
 */
export function wikiSites(): string[] {
  return SITES.filter((s) => s.selectable)
    .map((s) => s.slug)
    .filter((slug) => manifestOrNull(slug) !== null);
}

function feedFor<T>(slug: string, name: string): T[] {
  return runWithSite(slug, () => (hasFeed(name) ? loadFeed<T[]>(name) : []));
}

/** Order-stable dedupe. */
function unique<T>(rows: T[]): T[] {
  return [...new Set(rows)];
}

const roleTotalOf = (roles: Record<string, number> | undefined): number =>
  Object.values(roles ?? {}).reduce((a, b) => a + b, 0);

/** A field's value as a comparable/printable string; `null`/`undefined` collapse to "". */
function fieldValue(node: EntityNode, field: MergedField): string {
  const v = node[field];
  return v == null ? "" : String(v);
}

/** The disagreements across a party's readings — one entry per field two sites read differently. */
function disagreementsOf(readings: EntityReading[]): EntityDisagreement[] {
  const FIELDS: MergedField[] = [
    "display",
    "kind",
    "classification",
    "relation_class",
    "relation_basis",
    "lei",
    "uei",
    "federal_obligations",
  ];
  const out: EntityDisagreement[] = [];
  for (const field of FIELDS) {
    // An absence is not a competing reading (rule 5): a site that carries no value for a field has
    // not disagreed with one that does, it has said nothing. Only *stated* values are compared.
    const stated = readings
      .map((r) => ({ site: r.site, value: fieldValue(r.node, field) }))
      .filter((r) => r.value !== "");
    if (new Set(stated.map((r) => r.value)).size > 1) out.push({ field, readings: stated });
  }
  return out;
}

/** Merge a party's readings into one node — rules 3–6, in precedence order. */
function mergeNode(readings: EntityReading[]): EntityNode {
  const primary = readings[0].node;
  const all = readings.map((r) => r.node);
  /** The first *stated* registry identifier (rule 5) — an absent one is silence, not a value. */
  const firstStated = <K extends "lei" | "uei" | "federal_obligations">(k: K): EntityNode[K] =>
    all.find((n) => n[k] != null && n[k] !== "")?.[k] ?? primary[k];
  return {
    ...primary,
    variants: unique(all.flatMap((n) => n.variants ?? [])),
    signals: unique(all.flatMap((n) => n.signals ?? [])),
    parcels: unique(all.flatMap((n) => n.parcels ?? [])),
    addresses: unique(all.flatMap((n) => n.addresses ?? [])),
    sources: unique(all.flatMap((n) => n.sources ?? [])),
    // Registry identifiers: the first site that HAS one, not the first site (rule 5).
    lei: firstStated("lei"),
    uei: firstStated("uei"),
    federal_obligations: firstStated("federal_obligations"),
  };
}

let entityCache: NetworkEntity[] | null = null;

/**
 * Every party the network publishes, merged, in canonical-key order.
 *
 * Memoized for the build: the union is site-independent by construction (it reads every site
 * explicitly through `runWithSite`), so unlike the per-site feed readers there is nothing to key
 * the cache by.
 */
export function networkEntities(): NetworkEntity[] {
  if (entityCache) return entityCache;

  const byKey = new Map<string, EntityReading[]>();
  for (const site of wikiSites()) {
    for (const node of feedFor<EntityNode>(site, "entities")) {
      const readings = byKey.get(node.key) ?? [];
      readings.push({ site, node, roles: node.roles ?? {}, roleTotal: roleTotalOf(node.roles) });
      byKey.set(node.key, readings);
    }
  }

  const bySlug = new Map<string, NetworkEntity>();
  for (const [key, readings] of byKey) {
    const slug = slugify(key);
    const clash = bySlug.get(slug);
    if (clash) {
      // Two distinct keys, one route. Merging them would publish two parties as one — the exact
      // fabrication the key-only rule exists to prevent — and silently picking one would drop the
      // other with no trace, so this is a build error naming both.
      throw new Error(
        `Two entity keys resolve to the same wiki route /wiki/entities/${slug}/: ` +
          `"${clash.key}" (${clash.sites.join(", ")}) and "${key}" ` +
          `(${readings.map((r) => r.site).join(", ")}). Resolve them in the entity pipeline ` +
          "(watermark.pipeline.entities) — the frontend must not merge two parties into one page.",
      );
    }
    bySlug.set(slug, {
      key,
      slug,
      node: mergeNode(readings),
      sites: readings.map((r) => r.site),
      readings,
      disagreements: disagreementsOf(readings),
    });
  }

  entityCache = [...bySlug.values()].sort((a, b) => a.key.localeCompare(b.key));
  return entityCache;
}

let slugCache: Set<string> | null = null;

/** The slugs that have a generated entity page — what `entityHref` checks against. */
export function networkEntitySlugs(): Set<string> {
  if (!slugCache) slugCache = new Set(networkEntities().map((e) => e.slug));
  return slugCache;
}

let edgeCache: NetworkEdge[] | null = null;

/** Every relationship edge the network publishes, deduped on the full tuple. */
export function networkEdges(): NetworkEdge[] {
  if (edgeCache) return edgeCache;
  const byTuple = new Map<string, NetworkEdge>();
  for (const site of wikiSites()) {
    for (const edge of feedFor<RelationshipEdge>(site, "relationships")) {
      const tuple = [edge.src, edge.rel, edge.dst, edge.date, edge.ref, edge.source].join(" ");
      const hit = byTuple.get(tuple);
      if (hit) {
        if (!hit.sites.includes(site)) hit.sites.push(site);
      } else {
        byTuple.set(tuple, { edge, sites: [site] });
      }
    }
  }
  edgeCache = [...byTuple.values()];
  return edgeCache;
}

/** A party's edges, partitioned the way the entity page renders them. */
export function networkEdgesFor(key: string): { outgoing: NetworkEdge[]; incoming: NetworkEdge[] } {
  const edges = networkEdges();
  return {
    outgoing: edges.filter((e) => e.edge.src === key),
    incoming: edges.filter((e) => e.edge.dst === key),
  };
}

/**
 * The curated profiles of a party — every site whose `people` feed keys a profile to it.
 *
 * Scanned across all wiki sites rather than only the ones carrying the entity node: a profile is a
 * per-site record of an individual, and the site that curated it is the one that must be linked
 * (`/network/<that site>/site/people/<slug>/`), which the page's ambient `withSite` could not have
 * got right from outside a `runWithSite` scope.
 */
export function entityProfiles(key: string): EntityProfile[] {
  const out: EntityProfile[] = [];
  for (const site of wikiSites()) {
    for (const person of feedFor<PersonItem>(site, "people")) {
      if (person.entity_key === key) out.push({ site, person });
    }
  }
  return out;
}

/** `key` → merged `display`, for labelling an edge's far end. Unknown keys fall back to the key. */
export function networkEntityLabels(): Record<string, string> {
  return Object.fromEntries(networkEntities().map((e) => [e.key, e.node.display]));
}

// --- backlinks ------------------------------------------------------------------------------
//
// The three prose-matched backlink rails an entity page carries were all Lima-scoped reads, for
// the same reason the paths were: they ran outside `runWithSite`. Widening them is not one rule,
// because the three targets are scoped differently, and a backlink whose destination doesn't
// carry the row is worse than no backlink at all.

/**
 * The build behind the wiki's **single-page** surfaces — the glossary (#1892) and the
 * open-questions board (#1569). Both render one bundle by design: the glossary because 75 of its
 * 77 entries were byte-identical everywhere, the board because it hosts the reference site's own
 * leads plus the network's hypothesis-matrix cells. `search.ts` names the same coupling for the
 * same reason. This is the network-global-host role, not a Lima default.
 *
 * It also hosts the network's GLEIF inventory (`lei`, `/wiki/lei/`), which `entityEnrich` joins
 * against — a corporate register is one register, not a per-site reading.
 */
export const WIKI_CANONICAL = LIMA_SLUG;

/** One open question raising a party, and where it is actually addressable. */
export interface EntityOpenQuestion extends OpenQuestionBacklink {
  /** The site whose feed raises it — the canonical build, or the peer whose leads board holds it. */
  site: string;
}

export interface EntityBacklinks {
  concepts: RelatedConcept[];
  hypotheses: HypothesisBacklink[];
  openQuestions: EntityOpenQuestion[];
}

/**
 * The prose-matched rails for a merged party, each resolved against the build that publishes the
 * page it points at. That is the rule, and it is deliberately **not** "union everything": a
 * backlink whose destination doesn't carry the row is worse than no backlink, and two of the three
 * targets genuinely build once.
 *
 * - **Concepts** — the canonical glossary. It builds once (#1892), so matching against a peer's
 *   `concepts` feed would either point at a page that isn't there or drop a term that is. Every
 *   peer's concept slugs are a subset of the canonical set, so this loses nothing.
 * - **Hypotheses** — the canonical matrix. The three hypothesis nodes are in every bundle, but the
 *   `hypothesis-assessments` cells that name the real operators are the network's, hosted by the
 *   reference build (`is_reference_site`): it carries a cell for *every* site, while a peer carries
 *   only its own row. Reading the canonical matrix is therefore both the fuller haystack and the
 *   symmetric peer of the hypothesis page's own "Entities it bears on" rail, which reads the same
 *   cells — unioning per site would have given a peer-only party a backlink the hypothesis page
 *   could not return.
 * - **Open questions** — the union over the party's own sites, because this feed really is
 *   per-site, with each row pointed at the board that *renders* it: the canonical build's rows deep
 *   link the wiki board, a peer's rows deep link that peer's own leads board
 *   (`/network/<site>/leads#<id>`, which anchors by lead id). A peer row is deduped away when the
 *   canonical feed carries the same id, since the matrix cells for every site are projected into
 *   the canonical feed and unioning would list one cell twice.
 */
export function entityBacklinks(entity: NetworkEntity): EntityBacklinks {
  const names = [entity.node.display, ...entity.node.variants];

  const { concepts, hypotheses } = runWithSite(WIKI_CANONICAL, () => ({
    concepts: relatedConcepts(names),
    hypotheses: hypothesisBacklinks(names),
  }));

  const openQuestions: EntityOpenQuestion[] = [];
  const seen = new Set<string>();
  // Canonical first (it is `sites[0]` whenever the party is on the reference build), so its
  // rendering of a shared row wins the dedupe and a peer never re-points one at its own board.
  const order = entity.sites.includes(WIKI_CANONICAL)
    ? [WIKI_CANONICAL, ...entity.sites.filter((s) => s !== WIKI_CANONICAL)]
    : entity.sites;
  for (const site of order) {
    for (const q of runWithSite(site, () => openQuestionBacklinks(names))) {
      if (seen.has(q.id)) continue;
      // A peer's hypothesis-origin row is a matrix cell the canonical feed also projects; if it
      // somehow isn't there, the peer's leads board has no anchor for it, and minting one would be
      // a 404 with a good snippet — the failure #1890 refused to ship.
      if (site !== WIKI_CANONICAL && q.origin !== "lead") continue;
      seen.add(q.id);
      openQuestions.push(
        site === WIKI_CANONICAL ? { ...q, site } : { ...q, site, url: `${siteHref(site, "/leads")}#${q.id}` },
      );
    }
  }

  return { concepts, hypotheses, openQuestions };
}
