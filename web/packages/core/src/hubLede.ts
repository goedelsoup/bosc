/**
 * Hub-lede reducers (#1891, epic #1884 phase 7) — the small, pure readings each section hub
 * leads with, above its door grid.
 *
 * The finding this closes: every hub answered a click with the same object — a grid of doors,
 * each a title, a blurb, and a count — so a reader five clicks from the root had been handed
 * nothing but signposts. Each hub was already loading the manifest to print those counts; it
 * just never showed the content underneath them.
 *
 * These are the reductions that turn a feed the hub ALREADY loads into a sentence. They live
 * here rather than in the templates for the usual reason: they're the testable part, and two
 * of them (`roleTotal`, `topEntities`) are the ranking the wiki's entity index already did
 * inline — now one owner.
 *
 * **Discipline.** Every function is total over an empty/absent feed and returns an EMPTY
 * result, never a filler value: a peer site with no records shows the honest absence and asks
 * for the source (#1220), and the caller renders `HubLede`'s `absent` slot rather than another
 * site's figures. Nothing here mints a date, a count, or a name that isn't in the input — a
 * record with no dated events simply has no span.
 *
 * DOM-free and feed-reader-free (plain inputs in, plain data out) so it stays vitest-native.
 */
import type {
  CatalogItem,
  EconSector,
  EconomicBaseline,
  EntityNode,
  PersonItem,
  RecordItem,
  TimelineEntry,
} from "./feeds";

/** A dated timeline entry — the feed carries undated rows too (`date: ""` / a prose date). */
const isDated = (e: TimelineEntry): boolean => /^\d{4}-\d{2}-\d{2}$/.test(e.date);

/**
 * The record's most recent dated events, newest first. Undated rows are dropped rather than
 * sorted to one end: a lede that says "most recent" must not lead with a row that has no date.
 */
export function recentEvents(entries: readonly TimelineEntry[], n = 3): TimelineEntry[] {
  return entries
    .filter(isDated)
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, n);
}

/** The span the dated record covers — ISO first/last. Null when nothing in it is dated. */
export function recordSpan(entries: readonly TimelineEntry[]): { first: string; last: string } | null {
  const dates = entries.filter(isDated).map((e) => e.date);
  if (dates.length === 0) return null;
  return { first: dates.reduce((a, b) => (a < b ? a : b)), last: dates.reduce((a, b) => (a > b ? a : b)) };
}

/**
 * Records the extraction itself flagged — a validation warning, or a figure transcribed
 * approximately (the `~` marker). This is a **provenance** count, not a quality verdict: it's
 * the subset a reader should open against its source page first.
 */
export function flaggedRecords(records: readonly RecordItem[]): RecordItem[] {
  return records.filter((r) => (r.warnings?.length ?? 0) > 0 || (r.approximate_paths?.length ?? 0) > 0);
}

/** How many times an entity appears in the record, summed over its roles — the graph's degree
 *  proxy the wiki's entity index ranks by. */
export function roleTotal(e: EntityNode): number {
  return Object.values(e.roles ?? {}).reduce((a, b) => a + b, 0);
}

/** The most-appearing entities, by `roleTotal` then display name (the entity index's order). */
export function topEntities(entities: readonly EntityNode[], n = 6): EntityNode[] {
  return [...entities]
    .sort((a, b) => roleTotal(b) - roleTotal(a) || a.display.localeCompare(b.display))
    .slice(0, n);
}

/**
 * The sectors this local economy is actually CONCENTRATED in — ranked by location quotient
 * (employment share against the national share), not by headcount. Sectors whose LQ the feed
 * omits are dropped: an unranked sector can't claim a rank.
 */
export function topSectors(baseline: EconomicBaseline | null | undefined, n = 3): EconSector[] {
  const sectors = baseline?.latest.sectors ?? [];
  return sectors
    .filter((s) => s.location_quotient?.value != null)
    .sort((a, b) => (b.location_quotient?.value ?? 0) - (a.location_quotient?.value ?? 0))
    .slice(0, n);
}

/** Total covered employment across the baseline's sectors, or null when the feed carries none. */
export function sectorEmployment(baseline: EconomicBaseline | null | undefined): number | null {
  const sectors = baseline?.latest.sectors ?? [];
  if (sectors.length === 0) return null;
  return sectors.reduce((sum, s) => sum + (s.annual_avg_employment.value ?? 0), 0);
}

/** One `{label, count}` tally row. */
export interface Tally {
  label: string;
  count: number;
}

/** Tally labels, most common first, ties broken alphabetically. Blank labels are dropped. */
export function tally(labels: readonly string[], n = 6): Tally[] {
  const counts = new Map<string, number>();
  for (const label of labels) {
    const key = label.trim();
    if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
    .slice(0, n);
}

/** The roles the profiled people actually hold, most common first — what this bench IS. */
export function roleTally(people: readonly PersonItem[], n = 5): Tally[] {
  return tally(
    people.flatMap((p) => p.roles ?? []),
    n,
  );
}

/**
 * The newest `last_refreshed` across catalog entries (ISO), or null when none carries one.
 *
 * NB most rows legitimately carry none — a `static` committed extraction has no refresh cadence
 * to be current against — so this is "the most recent pull the set has seen", not a set-wide asof.
 */
export function newestRefresh(items: readonly CatalogItem[]): string | null {
  const dates = items.map((c) => c.last_refreshed).filter((d): d is string => Boolean(d));
  return dates.length > 0 ? dates.reduce((a, b) => (a > b ? a : b)) : null;
}

/** An ISO timestamp as a plain `2026-08-04` date, or null — never a fabricated fallback. */
export function isoDate(value: string | null | undefined): string | null {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value ?? "");
  return match ? match[1] : null;
}
