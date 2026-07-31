/**
 * Facet normalization for the ask-index's structured search filters (#1691).
 *
 * The one place the *matching semantics* of a corpus facet are defined, shared by the build-time
 * producer (`./askIndex`, which stamps the values onto each `AskUnit`) and the query-time consumer
 * (`functions/api/_lib/retrieval.ts`'s `applyCorpusFilters`). Both sides normalize with the same
 * function, so a filter can never be stricter or looser than what the index was built to answer —
 * the same reason `tokenize` lives once in the retrieval module rather than twice.
 *
 * This module is deliberately node-free (no `./bundle`, no `node:fs`): `askIndex` runs at build
 * time under Astro, but the filter kernel runs in the **Workers runtime**, which cannot import
 * anything that touches the filesystem.
 *
 * Why normalization at all — the alternative was to expose these facets as exact-match strings
 * over the raw feed values, and the raw values don't support it. A record's `agency` is the
 * document's own words ("Ohio EPA (Thomas Poffenbarger, P.E., DSW Northwest District Office)"),
 * an Ohio permit number carries a modification suffix (`2PH00006*LD`) the caller won't know, and
 * `county_name` reads "Allen County, OH" where a caller types "Allen". Exact match on any of
 * those answers "no results" to a query the corpus can plainly answer, which is a worse lie than
 * a documented normalization.
 */

/**
 * A facet's comparison key: lowercased, every run of non-alphanumerics collapsed to one space,
 * trimmed. Punctuation, case, and spacing are presentation, not identity — `Ohio EPA` and
 * `ohio  epa` are the same agency, and `AMAZON COM SERVICES` is the same entity as
 * `amazon.com services`.
 */
export function facetKey(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/**
 * A county's comparison key — `facetKey` with the trailing state token and the word "county"
 * dropped, so every way the network writes one county collapses to the same key:
 * "Allen County, OH", "Richland County" (Mansfield's profile carries no state suffix), and a
 * caller's bare "Allen" all yield `allen`.
 *
 * The state token is stripped only when it's a **trailing two-letter word**, so a county whose
 * name ends in a short word keeps it. It is safe to drop here because the ask-index is scoped by
 * `site` anyway: two same-named counties in different states (Allen, OH and Allen, IN) are never
 * in one index, and `filters.site` is the facet that separates them when they are.
 */
export function countyKey(s: string): string {
  return facetKey(s)
    .replace(/\s+[a-z]{2}$/, "")
    .replace(/\s*\bcounty\b\s*/, " ")
    .trim();
}

/**
 * A permit/case identifier's comparison key: uppercased with every non-alphanumeric removed, so
 * `2PH00006*LD` → `2PH00006LD` and `DSW401252260-W` → `DSW401252260W`. Separators are how a
 * given agency happens to print an id, never part of it.
 */
export function permitKey(s: string): string {
  return s.toUpperCase().replace(/[^A-Z0-9]+/g, "");
}

/**
 * Does any of a unit's permit ids answer a `permit_number` query?
 *
 * Equality **or prefix**, on normalized keys. Prefix is the point: Ohio issues one permit under a
 * base number and prints each modification with its own suffix (`2PH00006`, then `*LD`, `*MD`,
 * `*PD`), and a caller asking about the permit means every action under it. The reverse doesn't
 * hold — a query for `2PH00006LD` matches only that modification, never the bare base — so
 * naming a specific instrument still narrows to it.
 *
 * An empty query matches nothing (rather than everything): a caller who set the facet asked for
 * a constraint, and an empty one silently answering "all units" is the failure mode this whole
 * filter bag exists to avoid.
 */
export function permitMatches(values: readonly string[], query: string): boolean {
  const q = permitKey(query);
  if (!q) return false;
  return values.some((v) => {
    const k = permitKey(v);
    return k === q || k.startsWith(q);
  });
}

/**
 * Does a unit's free-text agency string answer an `agency` query? Substring containment on
 * normalized keys, because the indexed value is the record's own words and the caller has a name:
 * `agency: "Ohio EPA"` must reach "Ohio EPA, Division of Surface Water" and "Ohio EPA (DAPC;
 * Office of the Supervising Attorney)", which no exact match would.
 *
 * The direction is fixed — the query is the substring, the indexed value the haystack — so a
 * narrower query never matches a broader record. Empty query → no match, as with permits.
 */
export function agencyMatches(value: string, query: string): boolean {
  const q = facetKey(query);
  return q.length > 0 && facetKey(value).includes(q);
}

/**
 * A project/campus slug — `facetKey` re-joined with hyphens, so a raw `project_name` from a
 * record ("Project Bosc Lvl 2 IWP") and a facility key from the feed (`project-bosc`) are written
 * in one vocabulary. Resolution of the former to the latter happens at BUILD time (`askIndex`),
 * so the query-time comparison stays exact.
 */
export function projectKey(s: string): string {
  return facetKey(s).replace(/ /g, "-");
}
