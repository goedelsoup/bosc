/**
 * Documents catalog (#725) — the pure filter/sort logic, split from the DOM glue in
 * `scripts/doc-catalog.ts` so it's unit-testable (cf. `searchEngine.ts` vs the
 * `scripts/search.ts` glue). Operates on a dataset-shaped record (`row.dataset`), so
 * the glue passes DOM `dataset` straight in.
 */

/** A row's sort/filter keys, as carried on its `data-*` attributes (all strings). */
export type DocData = Record<string, string | undefined>;

/** The active per-column filters (empty/absent value = "all"). */
export type DocFilters = Partial<Record<"collection" | "type" | "access", string>>;

/** Whether a row survives the free-text search + the active column filters.
 *  `name` is matched as-is (the glue lowercases it into `data-name`); `collection`
 *  is lowercased here so the search box is case-insensitive on both. */
export function matchesDoc(d: DocData, query: string, filters: DocFilters): boolean {
  const q = query.trim().toLowerCase();
  const text = !q || (d.name ?? "").includes(q) || (d.collection ?? "").toLowerCase().includes(q);
  const passes = (["collection", "type", "access"] as const).every((k) => !filters[k] || d[k] === filters[k]);
  return text && passes;
}

/** Comparator for a single column. `numeric` sorts `data-size` by value, not lexically. */
export function compareDocs(a: DocData, b: DocData, key: string, numeric: boolean): number {
  const av = a[key] ?? "";
  const bv = b[key] ?? "";
  return numeric ? Number(av) - Number(bv) : av.localeCompare(bv);
}
