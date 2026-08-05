/**
 * The hydrated catalog resolver (epic #1090 / #1093) — the **pure, runtime-safe core**: the handle
 * grammar, the closed kind set, the `Catalog` shape, and `resolveHandle`. No `node:fs` / `import.
 * meta.glob`, so this module is safe to import in a Cloudflare Worker (the Walk write-path Function,
 * #1095) as well as at build time. The build-time loader + web-only overlay live in `./catalogBuild`.
 *
 * Handle grammar: `<kind>:<site>:<localId>`, where `localId` reuses each source feed's **existing**
 * stable key — no new ids are minted. Resolution is a *pointer*, not a copy: an atom names the live
 * feed row it addresses, so a Walk cites the record without ever forking it (chain of custody).
 */

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
  "contact",
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

/** Pure atom factory — mints the handle from its parts. `title` defaults to `localId` when blank. */
export function atom(
  kind: CatalogKind,
  site: string,
  localId: string,
  title: string,
  feed: string,
): CatalogAtom {
  return { handle: `${kind}:${site}:${localId}`, kind, site, localId, title: title || localId, feed };
}

/**
 * Assemble a `Catalog` from a flat atom list (last write wins on a handle collision — pass the
 * authoritative tier last). Pure, so both the build-time loader and the Worker's runtime asset
 * loader (#1095) share it.
 */
export function catalogFromAtoms(site: string, version: string, atoms: Iterable<CatalogAtom>): Catalog {
  const byHandle = new Map<string, CatalogAtom>();
  for (const a of atoms) byHandle.set(a.handle, a);
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
