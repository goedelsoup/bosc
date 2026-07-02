// The full /search results page (#308) — the "see all N results" surface. Shares the
// matcher + record-row grammar with the topbar dropdown via searchEngine.ts. Reads ?q from
// the URL, renders every match grouped by section, keeps the URL in sync as you type.
import { esc, rank, renderGroups, type SearchDoc } from "./searchEngine";

const input = document.getElementById("search-page-input") as HTMLInputElement | null;
const out = document.getElementById("search-page-results");
const form = document.getElementById("search-page-form") as HTMLFormElement | null;

if (input && out) {
  const indexUrl = input.dataset.index || "/search-index.json";
  const base = (input.dataset.base || "/").replace(/\/$/, "");

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
    const q = input.value.trim();
    // Keep the address bar shareable without spamming history.
    const url = new URL(window.location.href);
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    window.history.replaceState({}, "", url);

    if (q.length < 2) {
      out.innerHTML = '<p class="search-page-hint">Type at least two characters to search the record.</p>';
      return;
    }
    void load().then((docs) => {
      const { hits, terms } = rank(docs, q);
      if (!hits.length) {
        out.innerHTML = `<p class="search-page-hint">No matches for “${esc(q)}”.</p>`;
        return;
      }
      out.innerHTML =
        `<p class="search-page-count">${hits.length} result${hits.length === 1 ? "" : "s"} for “${esc(q)}”</p>` +
        renderGroups(hits, terms, base);
    });
  };

  input.addEventListener("input", run);
  // With JS on, submitting shouldn't reload — the results are already live.
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    run();
  });
  if (input.value.trim()) run();
}
