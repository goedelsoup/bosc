// The topbar dropdown search. Matching + the record-row grammar live in the shared engine
// (searchEngine.ts) so the dropdown and the full /search page never drift. Reads config off
// the input's data attributes (set server-side): data-index, data-base.
import { rank, renderGroups, type SearchDoc } from "./searchEngine";

const box = document.getElementById("bosc-search") as HTMLInputElement | null;
const panel = document.getElementById("bosc-search-results");

if (box && panel) {
  const indexUrl = box.dataset.index || "/search-index.json";
  const base = (box.dataset.base || "/").replace(/\/$/, "");
  // The full results page is a network-global route (root, not under the Lima base).
  const allUrl = (q: string): string => `${base}/search?q=${encodeURIComponent(q)}`;

  let index: SearchDoc[] | null = null;
  const load = (): Promise<SearchDoc[]> => {
    if (index) return Promise.resolve(index);
    return fetch(indexUrl)
      .then((r) => r.json())
      .then((d: SearchDoc[]) => {
        index = d;
        return index;
      })
      .catch(() => {
        index = [];
        return index;
      });
  };

  const run = (): void => {
    const q = box.value.trim();
    if (q.length < 2) {
      panel.hidden = true;
      panel.innerHTML = "";
      return;
    }
    void load().then((docs) => {
      const { hits, terms } = rank(docs, q);
      if (!hits.length) {
        panel.innerHTML = '<div class="search-empty">No matches</div>';
        panel.hidden = false;
        return;
      }
      const shown = hits.slice(0, 20);
      const more = hits.length > shown.length ? ` · showing top ${shown.length}` : "";
      const foot =
        `<a class="search-foot" href="${allUrl(q)}">` +
        `${hits.length} result${hits.length === 1 ? "" : "s"}${more}` +
        ' <kbd class="search-foot-kbd">↵</kbd> see all</a>';
      panel.innerHTML = renderGroups(shown, terms, base) + foot;
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
