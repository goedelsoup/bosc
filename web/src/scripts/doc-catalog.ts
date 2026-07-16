// Documents catalog (#725) — progressive enhancement of the SSR'd single table:
// search + per-column filters + click-to-sort. Dependency-free; the table is fully
// readable with JS off, so this only *adds* the toolbar (un-hides it) and wiring.
// Sort/filter keys read from each row's `data-*` (no cell-text parsing); the pure
// match/compare logic lives in (and is tested via) `lib/docCatalog.ts`.
import { compareDocs, type DocFilters, matchesDoc } from "@watermark/core/docCatalog";

const table = document.querySelector<HTMLTableElement>("#doccat-table");
const tools = document.querySelector<HTMLElement>(".doccat-tools");

if (table && tools) {
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const search = tools.querySelector<HTMLInputElement>(".doccat-search");
  const selects = Array.from(tools.querySelectorAll<HTMLSelectElement>("select[data-filter]"));
  const count = tools.querySelector<HTMLElement>(".doccat-count");
  const empty = document.querySelector<HTMLElement>(".doccat-empty");
  const headers = Array.from(table.tHead?.rows[0].cells ?? []) as HTMLTableCellElement[];

  // The toolbar is inert without JS, so it ships hidden — reveal it now.
  tools.hidden = false;

  const apply = (): void => {
    const query = search?.value ?? "";
    const filters: DocFilters = {};
    for (const s of selects) {
      const key = s.dataset.filter as keyof DocFilters | undefined;
      if (key) filters[key] = s.value;
    }
    let shown = 0;
    for (const row of rows) {
      const visible = matchesDoc(row.dataset, query, filters);
      row.hidden = !visible;
      if (visible) shown++;
    }
    if (count) count.textContent = `${shown} of ${rows.length}`;
    if (empty) empty.hidden = shown !== 0;
  };

  const sortBy = (header: HTMLTableCellElement): void => {
    const key = header.dataset.sort;
    if (!key) return;
    const numeric = header.hasAttribute("data-numeric");
    const dir = header.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
    for (const h of headers) h.setAttribute("aria-sort", "none");
    header.setAttribute("aria-sort", dir);
    const sign = dir === "ascending" ? 1 : -1;
    rows.sort((a, b) => sign * compareDocs(a.dataset, b.dataset, key, numeric));
    for (const row of rows) tbody.appendChild(row); // re-attach in sorted order
  };

  search?.addEventListener("input", apply);
  for (const s of selects) s.addEventListener("change", apply);
  for (const h of headers) {
    if (!h.dataset.sort) continue;
    h.classList.add("doccat-sortable");
    h.addEventListener("click", () => sortBy(h));
  }

  // Preserve the old per-collection deep link (#doc-<slug>, emitted by the search
  // index): land filtered to that collection instead of jumping to an anchor.
  const hash = decodeURIComponent(location.hash.replace(/^#doc-/, ""));
  if (hash && location.hash.startsWith("#doc-")) {
    const row = rows.find((r) => r.dataset.slug === hash);
    const sel = selects.find((s) => s.dataset.filter === "collection");
    if (row && sel) sel.value = row.dataset.collection ?? "";
  }

  apply();
}
