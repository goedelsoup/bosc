// The topbar dropdown search. Matching + the record-row grammar live in the shared engine
// (searchEngine.ts) so the dropdown and the full /search page never drift. Reads config off
// the input's data attributes (set server-side): data-index, data-base, data-shards, data-site.
import {
  esc,
  makeIndexLoader,
  rank,
  renderAskHandoff,
  renderGroups,
  THIN_RESULTS,
  type SearchScope,
  type SiteShard,
} from "./searchEngine";

const box = document.getElementById("bosc-search") as HTMLInputElement | null;
const panel = document.getElementById("bosc-search-results");

if (box && panel) {
  const indexUrl = box.dataset.index || "/search-index.json";
  const base = (box.dataset.base || "/").replace(/\/$/, "");

  let shards: SiteShard[] = [];
  try {
    shards = JSON.parse(box.dataset.shards || "[]") as SiteShard[];
  } catch (err) {
    console.error("search: malformed shard list", err);
  }
  const homeSlug = box.dataset.site || null;
  const homeLabel = box.dataset.siteLabel || "";
  // Standing on a built site → that site + the network-global content. Anywhere else there is no
  // site to scope to, so the box searches every site's record (#1890).
  const scope: SearchScope = homeSlug ? "site" : "network";
  const siteNames = new Map(shards.map((s) => [s.slug, s.label]));

  // The full results page is a network-global route (root, not under a site base). Carry the site
  // the reader is standing on, so "see all" lands on the same scope the dropdown just searched —
  // and gives them the control to widen it there.
  const allUrl = (q: string): string => {
    const p = new URLSearchParams({ q });
    if (homeSlug) p.set("site", homeSlug);
    return `${base}/search?${p.toString()}`;
  };

  // `homeLabel` is a registry `place`, not reader input — but it lands in innerHTML, and every
  // other data-derived string on this path goes through `esc`. The exception is the thing that
  // rots.
  const scopeNote =
    scope === "site"
      ? `Searching <strong>${esc(homeLabel)}</strong> and the network`
      : `Searching <strong>the whole network</strong> · ${shards.length} sites`;

  const load = makeIndexLoader(indexUrl, shards, homeSlug);

  const run = (): void => {
    const q = box.value.trim();
    if (q.length < 2) {
      panel.hidden = true;
      panel.innerHTML = "";
      return;
    }
    void load(scope).then((docs) => {
      // A query can resolve after a later one; only paint if this is still what's typed.
      if (box.value.trim() !== q) return;
      const { hits, terms } = rank(docs, q, homeSlug);
      const head = `<div class="search-scope">${scopeNote}</div>`;
      if (!hits.length) {
        panel.innerHTML = `${head}<div class="search-empty">No matches</div>${renderAskHandoff(q, base, 0)}`;
        panel.hidden = false;
        return;
      }
      const shown = hits.slice(0, 20);
      const more = hits.length > shown.length ? ` · showing top ${shown.length}` : "";
      const foot =
        `<a class="search-foot" href="${allUrl(q)}">` +
        `${hits.length} result${hits.length === 1 ? "" : "s"}${more}` +
        ' <kbd class="search-foot-kbd">↵</kbd> see all</a>';
      // Label rows by site only when the results can span more than one.
      const names = scope === "network" ? siteNames : undefined;
      const ask = hits.length <= THIN_RESULTS ? renderAskHandoff(q, base, hits.length) : "";
      panel.innerHTML = head + renderGroups(shown, terms, base, names) + ask + foot;
      panel.hidden = false;
    });
  };

  box.addEventListener("input", run);
  box.addEventListener("focus", run);
  box.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      box.blur();
      panel.hidden = true;
    }
    // ↵ opens the full results page (the dictate's "see all N results").
    if (e.key === "Enter") {
      const q = box.value.trim();
      if (q.length >= 2) {
        e.preventDefault();
        window.location.href = allUrl(q);
      }
    }
  });
  document.addEventListener("click", (e) => {
    const target = e.target as Node;
    if (!panel.contains(target) && target !== box) panel.hidden = true;
  });
}
