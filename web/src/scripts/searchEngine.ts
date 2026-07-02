// Shared client search engine (#308): the matcher + the record-row render grammar,
// used by BOTH the topbar dropdown (search.ts) and the full-page results (search-page.ts)
// so the two never drift. Dependency-free; operates on the build-time /search-index.json.
export interface SearchDoc {
  title: string;
  url: string;
  section: string;
  text: string;
  kind: string;
  id?: string;
  tag?: "verified" | "inference" | "open";
}

export const esc = (s: string): string =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

/** Lazy, cached loader for the build-time search index — shared by the dropdown and the
 *  results page so the fetch/cache/fallback behavior never drifts. A failed fetch/parse is
 *  logged and degrades to an empty index (search shows "no matches", the page still works). */
export function makeIndexLoader(indexUrl: string): () => Promise<SearchDoc[]> {
  let index: SearchDoc[] | null = null;
  return () => {
    if (index) return Promise.resolve(index);
    return fetch(indexUrl)
      .then((r) => r.json())
      .then((d: SearchDoc[]) => {
        index = d;
        return index;
      })
      .catch((err: unknown) => {
        console.error(`search: failed to load index ${indexUrl}`, err);
        index = [];
        return index;
      });
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
 */
export function rank(docs: SearchDoc[], query: string): { hits: SearchDoc[]; terms: string[] } {
  const q = query.trim().toLowerCase();
  const terms = q.split(/\s+/).filter(Boolean);
  if (!terms.length) return { hits: [], terms };
  const scored: [number, SearchDoc][] = [];
  for (const d of docs) {
    const title = (d.title || "").toLowerCase();
    const hay = `${title} ${(d.text || "").toLowerCase()}`;
    if (!terms.every((t) => hay.indexOf(t) >= 0)) continue;
    const score = title.indexOf(q) >= 0 ? 0 : terms.every((t) => title.indexOf(t) >= 0) ? 1 : 2;
    scored.push([score, d]);
  }
  scored.sort((a, b) => a[0] - b[0]);
  return { hits: scored.map((s) => s[1]), terms };
}

// One result = a mini record row: kind eyebrow · title · mono id · evidence dot, with a
// snippet beneath (#307). "A researcher reads provenance before they click."
export function renderRow(d: SearchDoc, terms: string[], base: string): string {
  const id = d.id ? `<span class="search-row-id">${esc(d.id)}</span>` : "";
  const dot = d.tag
    ? `<span class="search-row-dot tag-${d.tag}" title="${d.tag}" aria-label="evidence: ${d.tag}"></span>`
    : "";
  return (
    `<a class="search-row" href="${base}${esc(d.url)}">` +
    '<span class="search-row-head">' +
    `<span class="search-row-kind">${esc(d.kind)}</span>` +
    `<span class="search-row-title">${esc(d.title)}</span>` +
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
export function renderGroups(hits: SearchDoc[], terms: string[], base: string): string {
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
        docs.map((d) => renderRow(d, terms, base)).join("") +
        "</div>"
      );
    })
    .join("");
}
