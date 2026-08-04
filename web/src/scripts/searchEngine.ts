// Shared client search engine (#308): the matcher + the record-row render grammar,
// used by BOTH the topbar dropdown (search.ts) and the full-page results (search-page.ts)
// so the two never drift. Dependency-free; operates on the build-time index shards.
//
// Two shards, not one (#1890). `/search-index.json` is the network-global half — root sections,
// the site directory, the `/docs/` prose, the wiki nouns. `/network/<id>/search-index.json` is one
// site's own record. A page loads the network shard plus whichever site shards its scope names,
// so the box on a Fort Wayne page searches Fort Wayne rather than, as it did before, Lima.
export interface SearchDoc {
  title: string;
  url: string;
  section: string;
  text: string;
  kind: string;
  id?: string;
  tag?: "verified" | "inference" | "open";
  /** Registry slug of the site this row's record belongs to; absent on a network-global row. */
  site?: string;
}

/** One selectable site's shard, as the server hands it to the client. */
export interface SiteShard {
  slug: string;
  /** Display name — the registry `place`, as the switcher chip shows it. */
  label: string;
  url: string;
}

/** What a surface is currently searching. `site` also loads the network shard — the wiki and the
 *  long-form prose are part of every site's context; `network` loads every site's shard too. */
export type SearchScope = "site" | "network";

export const esc = (s: string): string =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** Fetch + parse one shard. A failure is logged and degrades to no rows, so one missing shard
 *  narrows the results instead of breaking the box. */
function loadShard(url: string): Promise<SearchDoc[]> {
  return fetch(url)
    .then((r) => r.json())
    .then((d: SearchDoc[]) => (Array.isArray(d) ? d : []))
    .catch((err: unknown) => {
      console.error(`search: failed to load index ${url}`, err);
      return [];
    });
}

/**
 * Lazy, per-scope-cached loader over the shards — shared by the dropdown and the results page so
 * the fetch/cache/fallback behavior never drifts.
 *
 * `networkUrl` is always loaded. Under `site` scope the current site's shard joins it; under
 * `network` scope every selectable site's does. Each shard is fetched at most once and the merged
 * result per scope is memoized, so toggling scope back and forth costs nothing after the first pass
 * and the big shard — the reference build's, ~3,200 documents and ~114 KB gzipped — is never
 * re-fetched. That memoization is the reason the scope control on /search can be a toggle rather
 * than a page load.
 */
export function makeIndexLoader(
  networkUrl: string,
  shards: SiteShard[],
  currentSlug: string | null,
): (scope: SearchScope) => Promise<SearchDoc[]> {
  const fetched = new Map<string, Promise<SearchDoc[]>>();
  const merged = new Map<SearchScope, Promise<SearchDoc[]>>();

  const once = (url: string): Promise<SearchDoc[]> => {
    let p = fetched.get(url);
    if (!p) {
      p = loadShard(url);
      fetched.set(url, p);
    }
    return p;
  };

  return (scope: SearchScope) => {
    let p = merged.get(scope);
    if (p) return p;
    const wanted = scope === "network" ? shards : shards.filter((s) => s.slug === currentSlug);
    p = Promise.all([once(networkUrl), ...wanted.map((s) => once(s.url))]).then((parts) => parts.flat());
    merged.set(scope, p);
    return p;
  };
}

// A ~140-char window around the first matched term, with the term marked.
export function snippet(text: string, terms: string[]): string {
  const lower = text.toLowerCase();
  let at = -1;
  let hit = "";
  for (const t of terms) {
    const p = lower.indexOf(t);
    if (p >= 0 && (at < 0 || p < at)) {
      at = p;
      hit = t;
    }
  }
  if (at < 0) return esc(text.slice(0, 140));
  const start = Math.max(0, at - 50);
  const frag = `${(start > 0 ? "…" : "") + text.slice(start, at + 90)}…`;
  const re = new RegExp(`(${hit.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig");
  return esc(frag).replace(re, "<mark>$1</mark>");
}

/**
 * All-terms substring match across title + body; title hits rank first. Returns every
 * match, ranked (callers slice if they want a cap). Ported from the legacy search.js.
 *
 * Under network scope the current site's rows win ties (`homeSlug`), so a reader standing on Fort
 * Wayne who widens the search still sees Fort Wayne first — the widening adds results underneath
 * rather than burying the ones they were already looking at.
 */
export function rank(
  docs: SearchDoc[],
  query: string,
  homeSlug: string | null = null,
): { hits: SearchDoc[]; terms: string[] } {
  const q = query.trim().toLowerCase();
  const terms = q.split(/\s+/).filter(Boolean);
  if (!terms.length) return { hits: [], terms };
  const scored: [number, number, SearchDoc][] = [];
  for (const d of docs) {
    const title = (d.title || "").toLowerCase();
    const hay = `${title} ${(d.text || "").toLowerCase()}`;
    if (!terms.every((t) => hay.indexOf(t) >= 0)) continue;
    const score = title.indexOf(q) >= 0 ? 0 : terms.every((t) => title.indexOf(t) >= 0) ? 1 : 2;
    const home = homeSlug !== null && d.site !== undefined && d.site !== homeSlug ? 1 : 0;
    scored.push([score, home, d]);
  }
  scored.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return { hits: scored.map((s) => s[2]), terms };
}

// One result = a mini record row: kind eyebrow · title · mono id · evidence dot, with a
// snippet beneath (#307). "A researcher reads provenance before they click."
//
// `siteNames` labels a row with the watershed point it came from — shown only when the results
// can span more than one, so a single-site view isn't stamped with the same chip on every row.
export function renderRow(
  d: SearchDoc,
  terms: string[],
  base: string,
  siteNames?: Map<string, string>,
): string {
  const id = d.id ? `<span class="search-row-id">${esc(d.id)}</span>` : "";
  const dot = d.tag
    ? `<span class="search-row-dot tag-${d.tag}" title="${d.tag}" aria-label="evidence: ${d.tag}"></span>`
    : "";
  const place = siteNames && d.site ? siteNames.get(d.site) : undefined;
  const chip = place ? `<span class="search-row-site">${esc(place)}</span>` : "";
  return (
    `<a class="search-row" href="${base}${esc(d.url)}">` +
    '<span class="search-row-head">' +
    `<span class="search-row-kind">${esc(d.kind)}</span>` +
    `<span class="search-row-title">${esc(d.title)}</span>` +
    chip +
    id +
    dot +
    "</span>" +
    `<span class="search-row-snip">${snippet(d.text, terms)}</span></a>`
  );
}

/**
 * Results grouped by section, preserving relevance order (groups ordered by their first/
 * best hit; rows ordered within). A researcher scans by area, not a flat list. Returns the
 * grouped body only — each surface (dropdown / page) appends its own footer.
 */
export function renderGroups(
  hits: SearchDoc[],
  terms: string[],
  base: string,
  siteNames?: Map<string, string>,
): string {
  const order: string[] = [];
  const groups = new Map<string, SearchDoc[]>();
  for (const d of hits) {
    let g = groups.get(d.section);
    if (!g) {
      g = [];
      groups.set(d.section, g);
      order.push(d.section);
    }
    g.push(d);
  }
  return order
    .map((section) => {
      const docs = groups.get(section)!;
      return (
        '<div class="search-group">' +
        `<div class="search-group-head">${esc(section)} <span class="search-group-count">${docs.length}</span></div>` +
        docs.map((d) => renderRow(d, terms, base, siteNames)).join("") +
        "</div>"
      );
    })
    .join("");
}

/**
 * The hand-off to `/ask` (#1890). Search is lexical: it matches the words a reader typed against
 * titles and metadata, so a question phrased as a question ("how much water does the campus draw")
 * matches nothing even when the corpus answers it — that is `/ask`'s retrieval, over passage text.
 *
 * Before this, each of the three retrieval systems was a dead end on its own terms: a reader who
 * searched and found nothing had no signal that `/ask` existed, let alone that it might hold the
 * answer. Offered whenever results are thin, not only when they are empty — five weak title
 * matches are a miss too.
 */
export const THIN_RESULTS = 3;

export function renderAskHandoff(query: string, base: string, hitCount: number): string {
  const href = `${base}/ask?q=${encodeURIComponent(query)}`;
  const lede =
    hitCount === 0
      ? "No page title or record field matches those words."
      : "Not what you meant? Search matches titles and metadata, not the text inside documents.";
  return (
    `<a class="search-ask" href="${href}">` +
    `<span class="search-ask-kind">Ask the corpus</span>` +
    `<span class="search-ask-lede">${esc(lede)} Ask a question of the record and get a cited answer drawn from the passages themselves.</span>` +
    `<span class="search-ask-q">“${esc(query)}”</span></a>`
  );
}
