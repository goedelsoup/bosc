// The full /search results page (#308) — the "see all N results" surface. Shares the
// matcher + record-row grammar with the topbar dropdown via searchEngine.ts. Reads ?q from
// the URL, renders every match grouped by section, keeps the URL in sync as you type.
//
// This is the surface that owns the scope CHOICE (#1890). The dropdown states its scope and moves
// on; here a reader can widen from the site they arrived from to the whole network and back, and
// the choice rides in the URL so a shared link searches what the sender was looking at.
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

const input = document.getElementById("search-page-input") as HTMLInputElement | null;
const out = document.getElementById("search-page-results");
const form = document.getElementById("search-page-form") as HTMLFormElement | null;
const scopeBox = document.getElementById("search-page-scope");

if (input && out) {
  const indexUrl = input.dataset.index || "/search-index.json";
  const base = (input.dataset.base || "/").replace(/\/$/, "");

  let shards: SiteShard[] = [];
  try {
    shards = JSON.parse(input.dataset.shards || "[]") as SiteShard[];
  } catch (err) {
    console.error("search: malformed shard list", err);
  }
  const siteNames = new Map(shards.map((s) => [s.slug, s.label]));

  // Where the reader came from. `?site=` is set by the header box's hand-off; with no site in play
  // there is nothing to narrow to, so the scope control doesn't render and the search is network-wide.
  const params = new URLSearchParams(window.location.search);
  const homeSlug = params.get("site") || input.dataset.site || null;
  const home = homeSlug ? shards.find((s) => s.slug === homeSlug) : undefined;
  let scope: SearchScope = params.get("scope") === "network" || !home ? "network" : "site";

  const load = makeIndexLoader(indexUrl, shards, home?.slug ?? null);

  const renderScope = (): void => {
    if (!scopeBox) return;
    if (!home) {
      scopeBox.innerHTML =
        `<span class="search-scope-label">Searching <strong>the whole network</strong> — ` +
        `${shards.length} site${shards.length === 1 ? "" : "s"}, plus the wiki and the long-form record.</span>`;
      return;
    }
    const opt = (value: SearchScope, label: string): string =>
      `<button type="button" class="search-scope-opt${scope === value ? " is-on" : ""}" ` +
      `data-scope="${value}" aria-pressed="${scope === value}">${esc(label)}</button>`;
    scopeBox.innerHTML =
      '<span class="search-scope-label">Searching</span>' +
      '<span class="search-scope-opts">' +
      opt("site", home.label) +
      opt("network", `The whole network (${shards.length} sites)`) +
      "</span>";
  };

  const syncUrl = (q: string): void => {
    const url = new URL(window.location.href);
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    if (home) {
      url.searchParams.set("site", home.slug);
      url.searchParams.set("scope", scope);
    }
    // Keep the address bar shareable without spamming history.
    window.history.replaceState({}, "", url);
  };

  const run = (): void => {
    const q = input.value.trim();
    syncUrl(q);

    if (q.length < 2) {
      out.innerHTML = '<p class="search-page-hint">Type at least two characters to search the record.</p>';
      return;
    }
    // Capture the scope this run is for. Toggling scope re-runs immediately, and the two loads
    // resolve in whatever order they finish — a cached shard set resolves in a microtask while a
    // cold one waits on the network — so without this the *previous* scope's results can land last
    // and overwrite the ones the reader just asked for.
    const at = scope;
    void load(at).then((docs) => {
      if (input.value.trim() !== q || scope !== at) return;
      const { hits, terms } = rank(docs, q, home?.slug ?? null);
      const ask = hits.length <= THIN_RESULTS ? renderAskHandoff(q, base, hits.length) : "";
      if (!hits.length) {
        out.innerHTML = `<p class="search-page-hint">No matches for “${esc(q)}”.</p>${ask}`;
        return;
      }
      // Label rows by site only when the results can span more than one.
      const names = at === "network" ? siteNames : undefined;
      out.innerHTML =
        `<p class="search-page-count">${hits.length} result${hits.length === 1 ? "" : "s"} for “${esc(q)}”</p>` +
        renderGroups(hits, terms, base, names) +
        ask;
    });
  };

  scopeBox?.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-scope]");
    if (!btn) return;
    const next = btn.dataset.scope as SearchScope;
    if (next === scope) return;
    scope = next;
    renderScope();
    run();
  });

  renderScope();
  input.addEventListener("input", run);
  // With JS on, submitting shouldn't reload — the results are already live.
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    run();
  });
  if (input.value.trim()) run();
}
