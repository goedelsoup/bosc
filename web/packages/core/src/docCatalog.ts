/**
 * Documents catalog (#725) — the pure filter/sort logic, split from the DOM glue in
 * `scripts/doc-catalog.ts` so it's unit-testable (cf. `searchEngine.ts` vs the
 * `scripts/search.ts` glue). Operates on a dataset-shaped record (`row.dataset`), so
 * the glue passes DOM `dataset` straight in.
 */

/** A row's sort/filter keys, as carried on its `data-*` attributes (all strings). */
export type DocData = Record<string, string | undefined>;

/** The active per-column filters (empty/absent value = "all"). */
export type DocFilters = Partial<Record<"collection" | "type" | "access" | "extraction", string>>;

/** The filterable columns, in toolbar order. `folder` is not here: it filters by PREFIX (a branch
 *  selects its subtree), so the glue applies it separately rather than by equality. */
const FILTER_KEYS = ["collection", "type", "access", "extraction"] as const;

/** Whether a row survives the free-text search + the active column filters.
 *  `name` is matched as-is (the glue lowercases it into `data-name`); `collection`
 *  is lowercased here so the search box is case-insensitive on both. */
export function matchesDoc(d: DocData, query: string, filters: DocFilters): boolean {
  const q = query.trim().toLowerCase();
  const text = !q || (d.name ?? "").includes(q) || (d.collection ?? "").toLowerCase().includes(q);
  const passes = FILTER_KEYS.every((k) => !filters[k] || d[k] === filters[k]);
  return text && passes;
}

/** Comparator for a single column. `numeric` sorts `data-size` by value, not lexically. */
export function compareDocs(a: DocData, b: DocData, key: string, numeric: boolean): number {
  const av = a[key] ?? "";
  const bv = b[key] ?? "";
  return numeric ? Number(av) - Number(bv) : av.localeCompare(bv);
}

// --- the whole-listing half (#1887, extraction added #1898) --------------------------------
//
// `matchesDoc` above filters the rows a page happens to have SSR'd. That is the fallback: once
// the per-site `catalog.json` loads, the toolbar filters the whole listing instead, and it is
// this pair that decides what a facet means on a 1,619-file production. Both the endpoint that
// writes the asset (`pages/network/[site]/site/documents/catalog.json.ts`) and the glue that
// reads it (`scripts/doc-catalog.ts`) import the row type and these predicates from here, so the
// compact field encoding is declared once and the two halves cannot drift.

/**
 * A row of the per-site `catalog.json`. Fields are single-character to keep the asset small, and
 * `rel` is NOT stored — it is exactly `c/[k/][f/]n`, so the reader reconstructs it rather than
 * paying twice for the corpus's long as-received paths.
 */
export interface CatalogRow {
  /** File name, as received. */
  n: string;
  /** Collection slug. */
  c: string;
  /** Container slug — `""` when the file sits directly in the collection. */
  k: string;
  /** Folder trail below the container — `""` when none. */
  f: string;
  /** `render_class`. */
  t: string;
  /** `docAccess`: published | dev-only | absent. */
  a: string;
  /** Size in bytes. */
  s: number;
  /** Non-routable reason — `""` when the file gets a page. */
  x: string;
  /**
   * Records read from this document (#1898). **Absent, not 0**, when none: only 52 of Lima's
   * 3,247 rows carry it, and spelling `"e":0` on the other 3,195 would add ~25 KB to say "no"
   * three thousand times. Read it as a truthiness test, never as a defined number.
   */
  e?: number;
  /** `<group>/<record-slug>/` under `RECORD_ROUTE_BASE` — present only when `e === 1`. */
  r?: string;
}

/** Which listing a row belongs to — the scope a landing's toolbar must not silently widen past. */
export interface CatalogScope {
  collection: string;
  /** A container landing's slug; `""` means the scope is the whole collection. */
  container: string;
  /** Scope to files with NO container — the "outside a production" table on a container landing. */
  looseOnly: boolean;
}

/** Whether a catalog row is part of the listing a landing shows. */
export function inCatalogScope(row: CatalogRow, scope: CatalogScope): boolean {
  if (row.c !== scope.collection) return false;
  if (scope.container !== "") return row.k === scope.container;
  return scope.looseOnly ? row.k === "" : true;
}

/** A catalog row's extraction status (#1898) — `e` is absent rather than 0 on an unread file. */
export function rowExtraction(row: CatalogRow): "extracted" | "catalogued" {
  return row.e ? "extracted" : "catalogued";
}

/**
 * Whether a catalog row survives the toolbar — the whole-listing peer of `matchesDoc`.
 *
 * Two deliberate differences from the SSR-row version. The free text matches the file NAME only:
 * every row here is already scoped to one collection, so searching the collection name would
 * match all of them or none. And `folder` selects a SUBTREE — picking a branch of the as-received
 * trail selects everything filed beneath it, which is the only reading that makes the folder
 * facet a substitute for walking the tree.
 */
export function matchesCatalogRow(row: CatalogRow, query: string, filters: DocFilters, folder = ""): boolean {
  const q = query.trim().toLowerCase();
  if (q && !row.n.toLowerCase().includes(q)) return false;
  if (filters.type && row.t !== filters.type) return false;
  if (filters.access && row.a !== filters.access) return false;
  if (filters.extraction && rowExtraction(row) !== filters.extraction) return false;
  if (folder && row.f !== folder && !row.f.startsWith(`${folder}/`)) return false;
  return true;
}
