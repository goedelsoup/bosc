/**
 * The hydrated catalog + resolver (epic #1090 / #1093) — the dependency gate for user-authored
 * Stories. A build-time, addressable index of every "grabbable" atom across a site, plus the
 * shared `resolveHandle` the write path (validation) and read path (render) both consume.
 *
 * Handle grammar: `<kind>:<site>:<localId>`, where `localId` reuses each source feed's **existing**
 * stable key — no new ids are minted. Resolution is a *pointer*, not a copy: an atom names the live
 * feed row it addresses, so a Story cites the record without ever forking it (chain of custody).
 *
 * The catalog is assembled in **two tiers** (see `bosc.site.catalog_index`): the Python data tier
 * emits the feed-backed kinds as the `catalog-index` bundle feed; this module overlays the
 * **web-only** kinds (`teardown`/`doc`/`chapter`/`figure`) — teardowns, doc collections, story
 * chapters, and viz widgets the bundle can't see — so the resolver sees one merged catalog.
 */
import { activeSite, hasFeed, loadFeed } from "./bundle";
import { LEGAL } from "./legal";
import { NARRATIVE } from "./narrative";
import { REFERENCE } from "./reference";
import { LIMA_SLUG } from "./routes";
import { ALL_TEARDOWNS } from "./teardowns";
import { STORIES } from "./walk";

/** The closed catalog kind set — one render component + one resolver branch each (#1093). Must
 *  mirror `bosc.site.catalog_index.CATALOG_KINDS` (the Python peer is the other half of the axis). */
export const FEED_BACKED_KINDS = [
  "record",
  "timeline",
  "entity",
  "person",
  "place",
  "meeting",
  "exhibit",
  "concept",
  "lead",
  "dataset",
] as const;
export const WEB_ONLY_KINDS = ["teardown", "doc", "chapter", "figure"] as const;
export const CATALOG_KINDS = [...FEED_BACKED_KINDS, ...WEB_ONLY_KINDS] as const;
export type CatalogKind = (typeof CATALOG_KINDS)[number];

const KIND_SET: ReadonlySet<string> = new Set(CATALOG_KINDS);

/** One addressable atom — the resolver's unit. `feed` + `localId` are the live pointer. */
export interface CatalogAtom {
  handle: string;
  kind: CatalogKind;
  site: string;
  localId: string;
  title: string;
  /** The source feed / collection this atom resolves into (a pointer label, not a copy). */
  feed: string;
}

/** A parsed handle (`<kind>:<site>:<localId>`), kind already validated against the closed set. */
export interface Handle {
  kind: CatalogKind;
  site: string;
  localId: string;
}

/** The merged catalog for one site — feed-backed atoms (bundle) + web-only atoms (overlay). */
export interface Catalog {
  site: string;
  /** The `catalog_version` content hash from the bundle's feed-backed tier (empty if no feed). */
  version: string;
  byHandle: ReadonlyMap<string, CatalogAtom>;
  /** Every site any atom belongs to — so the resolver can tell `unknown_site` from `dangling`. */
  sites: ReadonlySet<string>;
}

/** Parse `<kind>:<site>:<localId>`. `localId` may itself contain `:` (split on the first two only).
 *  Returns `null` for a malformed handle or an unknown kind. */
export function parseHandle(handle: string): Handle | null {
  const first = handle.indexOf(":");
  if (first <= 0) return null;
  const second = handle.indexOf(":", first + 1);
  if (second < 0) return null;
  const kind = handle.slice(0, first);
  const site = handle.slice(first + 1, second);
  const localId = handle.slice(second + 1);
  if (!site || !localId || !KIND_SET.has(kind)) return null;
  return { kind: kind as CatalogKind, site, localId };
}

/** The wire shape of the `catalog-index` object feed (`bosc.site.feeds.CatalogIndex`, snake_case). */
interface CatalogIndexFeed {
  site: string;
  catalog_version: string;
  contract_version: string;
  atoms: {
    handle: string;
    kind: string;
    site: string;
    local_id: string;
    title: string;
    feed: string;
  }[];
}

/** The whole-widget viz figures grabbable in v1 (#1093 locked rough edge: figures grab as **whole
 *  widgets** keyed by builder name — per-scalar object-paths deferred). A small, extensible seed. */
const FIGURES: { localId: string; title: string }[] = [
  { localId: "dilution", title: "Effluent dilution" },
  { localId: "money-flow", title: "Money flow" },
];

function atom(kind: CatalogKind, site: string, localId: string, title: string, feed: string): CatalogAtom {
  return { handle: `${kind}:${site}:${localId}`, kind, site, localId, title: title || localId, feed };
}

/**
 * The web-only overlay (#1093): the four kinds the bundle can't see. Chapters carry their own
 * `story.site`; teardowns, doc collections, and figures are Lima editorial artifacts today (the
 * `narrative`/`legal`/`reference` collections route under Lima's network path), so they overlay
 * only onto the Lima catalog. A sibling site with its own stories still gets its chapters.
 */
function webOnlyAtoms(site: string): CatalogAtom[] {
  const atoms: CatalogAtom[] = [];

  // chapter — the `stories` MDX collection; grabbable as `chapter:<site>:<codename>/<slug>`.
  for (const story of STORIES) {
    if (story.site !== site) continue;
    for (const ch of story.chapters) {
      atoms.push(atom("chapter", site, `${story.codename}/${ch.slug}`, ch.title, "stories"));
    }
  }

  // teardown / doc / figure — Lima-scoped editorial artifacts.
  if (site === LIMA_SLUG) {
    for (const t of ALL_TEARDOWNS) {
      // Grabbable only when it carries a `recordRel` (its stable key); curated-only teardowns
      // have no addressable anchor in v1 (mirrors the Python timeline `ref` gate).
      if (t.recordRel) atoms.push(atom("teardown", site, t.recordRel, t.title, "teardowns"));
    }
    // doc — three collections fold into one `doc` kind; a slug is unique within a collection but
    // could collide *across* them (`narrative`/`legal`/`reference`). Keep the first (narrative →
    // legal → reference order) so a later collection can't silently clobber an earlier doc when
    // `mergeAtoms` collapses by handle. The `feed` label records which collection won.
    const seenDoc = new Set<string>();
    const pushDoc = (slug: string, title: string, feed: string): void => {
      const handle = `doc:${site}:${slug}`;
      if (seenDoc.has(handle)) return;
      seenDoc.add(handle);
      atoms.push(atom("doc", site, slug, title, feed));
    };
    for (const d of NARRATIVE) pushDoc(d.slug, d.title, "narrative");
    for (const d of LEGAL) pushDoc(d.slug, d.title, "legal");
    for (const d of REFERENCE) pushDoc(d.slug, d.title, "reference");
    for (const f of FIGURES) atoms.push(atom("figure", site, f.localId, f.title, "figure"));
  }

  return atoms;
}

function mergeAtoms(feedAtoms: CatalogAtom[], overlay: CatalogAtom[]): Map<string, CatalogAtom> {
  const byHandle = new Map<string, CatalogAtom>();
  // Feed-backed atoms win on a collision — the bundle is the authoritative tier.
  for (const a of overlay) byHandle.set(a.handle, a);
  for (const a of feedAtoms) byHandle.set(a.handle, a);
  return byHandle;
}

/**
 * Assemble the merged catalog for a site: the `catalog-index` bundle feed (feed-backed atoms) plus
 * the web-only overlay. Absent feed (a thin site) degrades to overlay-only — never throws.
 */
export function loadCatalog(site: string = activeSite()): Catalog {
  let version = "";
  let feedAtoms: CatalogAtom[] = [];
  if (hasFeed("catalog-index", site)) {
    const feed = loadFeed<CatalogIndexFeed>("catalog-index", site);
    version = feed.catalog_version;
    feedAtoms = feed.atoms.map((a) => ({
      handle: a.handle,
      kind: a.kind as CatalogKind,
      site: a.site,
      localId: a.local_id,
      title: a.title,
      feed: a.feed,
    }));
  }
  const byHandle = mergeAtoms(feedAtoms, webOnlyAtoms(site));
  const sites = new Set<string>();
  for (const a of byHandle.values()) sites.add(a.site);
  return { site, version, byHandle, sites };
}

/** The resolver contract (#1093): why a handle failed to resolve. */
export type ResolveFailure = "unknown_kind" | "unknown_site" | "dangling";
export type ResolveResult = { ok: true; atom: CatalogAtom } | { ok: false; reason: ResolveFailure };

/**
 * Resolve a handle against a catalog — **live** (pointer, not copy). A hit returns the addressable
 * atom (the caller reads the live feed row from `atom.feed` + `atom.localId`). A miss reports why:
 * `unknown_kind` (malformed or not in the closed set), `unknown_site` (no atom for that site), or
 * `dangling` (well-formed, known site, but the referenced atom is gone — e.g. a record was retired).
 */
export function resolveHandle(handle: string, catalog: Catalog): ResolveResult {
  const parsed = parseHandle(handle);
  if (!parsed) return { ok: false, reason: "unknown_kind" };
  const atom = catalog.byHandle.get(handle);
  if (atom) return { ok: true, atom };
  if (!catalog.sites.has(parsed.site)) return { ok: false, reason: "unknown_site" };
  return { ok: false, reason: "dangling" };
}
