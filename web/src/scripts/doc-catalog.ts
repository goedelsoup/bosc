// Documents catalog filtering (#725, rebuilt for #1887).
//
// The old version filtered the rows of one giant SSR'd table, because there WAS only one table —
// all 3,247 documents on a single 2.0 MB page. Listings are paginated now, so filtering the
// visible rows would quietly search 250 of 1,619 files and report a confident, wrong count.
//
// Instead this fetches the per-site `catalog.json` (built by
// `pages/network/[site]/site/documents/catalog.json.ts`) the first time a filter is touched, and
// renders matches across the WHOLE listing — scoped to this page's collection/container. The
// fetch is lazy so a reader who never filters never pays for it, and everything degrades to the
// SSR page plus its pager with JS off.
import { compareDocs, type DocFilters, matchesDoc } from "@watermark/core/docCatalog";
import { documentId } from "@watermark/core/documentId";

/** A row of the compact catalog asset; see `catalog.json.ts` for the field encoding. */
interface CatalogRow {
  n: string;
  c: string;
  k: string;
  f: string;
  t: string;
  a: string;
  s: number;
  x: string;
}

const ACCESS_CHIP: Record<string, { cls: string; label: string }> = {
  published: { cls: "dchip--present", label: "● published" },
  "dev-only": { cls: "dchip--devonly", label: "dev-only" },
  absent: { cls: "dchip--lfs", label: "LFS pointer" },
};
const EXCLUDED_LABEL: Record<string, string> = {
  "os-artifact": "OS artifact",
  "inline-image": "inline image",
  "web-page-sidecar": "page sidecar",
};

const tools = document.querySelector<HTMLElement>("[data-doc-filters]");
const table = document.querySelector<HTMLTableElement>(".doccat table");

if (tools && table) {
  const tbody = table.tBodies[0];
  const ssrRows = Array.from(tbody.rows);
  const search = tools.querySelector<HTMLInputElement>(".doccat-search");
  const selects = Array.from(tools.querySelectorAll<HTMLSelectElement>("select[data-filter]"));
  const count = tools.querySelector<HTMLElement>(".doccat-count");
  const empty = document.querySelector<HTMLElement>(".doccat-empty");
  const pager = document.querySelector<HTMLElement>(".docpager");
  const showFolder = (table.tHead?.rows[0].cells.length ?? 0) > 4;

  const catalogUrl = tools.dataset.catalog ?? "";
  const scopeCollection = tools.dataset.collection ?? "";
  const scopeContainer = tools.dataset.container ?? "";
  // `loose` scopes to files with no container — the "outside a production" table, which must not
  // silently widen to the whole collection when filtered.
  const scopeLoose = tools.dataset.loose === "true";

  // The toolbar is inert without JS, so it ships hidden — reveal it now.
  tools.hidden = false;

  let listing: CatalogRow[] | null = null;
  let loading: Promise<CatalogRow[]> | null = null;

  /** Fetch (once) and narrow the catalog to the listing this page shows. */
  const loadListing = (): Promise<CatalogRow[]> => {
    if (listing) return Promise.resolve(listing);
    if (loading) return loading;
    loading = fetch(catalogUrl)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data: { rows: CatalogRow[] }) => {
        listing = data.rows.filter((row) => {
          if (row.c !== scopeCollection) return false;
          if (scopeContainer !== "") return row.k === scopeContainer;
          return scopeLoose ? row.k === "" : true;
        });
        return listing;
      })
      .catch(() => {
        // Offline or a stale asset: fall back to filtering the SSR page rather than blanking it.
        listing = null;
        loading = null;
        return [];
      });
    return loading;
  };

  /** Mirrors `formatBytes` in @watermark/core/feeds — kept local so the script stays dependency-light. */
  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let value = bytes / 1024;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
  };

  const relOf = (row: CatalogRow): string =>
    [row.c, row.k, row.f, row.n].filter((part) => part !== "").join("/");

  /** The `/api/doc/<rel>` byte URL — path-segment-encoded, matching `docApiUrl`. */
  const apiUrl = (rel: string): string => `/api/doc/${rel.split("/").map(encodeURIComponent).join("/")}`;

  /** The document's permalink — the handle is derived, so no lookup table rides along. */
  const pagePath = (rel: string): string => `${table.dataset.docBase ?? ""}${documentId(rel)}/`;

  const renderRow = (row: CatalogRow): HTMLTableRowElement => {
    const rel = relOf(row);
    const tr = document.createElement("tr");
    const chip = ACCESS_CHIP[row.a] ?? ACCESS_CHIP.absent;

    const file = document.createElement("td");
    file.className = "file";
    const link = document.createElement("a");
    link.textContent = row.n;
    link.href = row.x ? apiUrl(rel) : pagePath(rel);
    file.appendChild(link);
    if (row.x) {
      const mark = document.createElement("span");
      mark.className = "dchip dchip--lfs doccat-excluded";
      mark.textContent = EXCLUDED_LABEL[row.x] ?? row.x;
      file.appendChild(mark);
    }
    tr.appendChild(file);

    if (showFolder) {
      const folder = document.createElement("td");
      folder.className = "doccat-folder";
      folder.textContent = row.f || "—";
      tr.appendChild(folder);
    }

    const type = document.createElement("td");
    const typeChip = document.createElement("span");
    typeChip.className = "dchip dchip--type";
    typeChip.textContent = row.t;
    type.appendChild(typeChip);
    tr.appendChild(type);

    const size = document.createElement("td");
    size.className = "num";
    size.textContent = formatBytes(row.s);
    tr.appendChild(size);

    const access = document.createElement("td");
    const accessChip = document.createElement("span");
    accessChip.className = `dchip ${chip.cls}`;
    accessChip.textContent = chip.label;
    access.appendChild(accessChip);
    tr.appendChild(access);

    return tr;
  };

  const currentFilters = (): { query: string; filters: DocFilters; folder: string } => {
    const filters: DocFilters = {};
    let folder = "";
    for (const select of selects) {
      const key = select.dataset.filter;
      if (key === "folder") folder = select.value;
      else if (key) filters[key as keyof DocFilters] = select.value;
    }
    return { query: search?.value ?? "", filters, folder };
  };

  const isActive = (): boolean => {
    const { query, filters, folder } = currentFilters();
    return query.trim() !== "" || folder !== "" || Object.values(filters).some((v) => v);
  };

  /** Restore the untouched SSR page — the pager is meaningful again. */
  const reset = (): void => {
    tbody.replaceChildren(...ssrRows);
    for (const row of ssrRows) row.hidden = false;
    if (pager) pager.hidden = false;
    if (count) count.textContent = "";
    if (empty) empty.hidden = true;
  };

  const apply = async (): Promise<void> => {
    if (!isActive()) {
      reset();
      return;
    }
    const { query, filters, folder } = currentFilters();
    const rows = await loadListing();
    if (rows.length === 0 && listing === null) {
      // Couldn't load the index — degrade to filtering what's on screen and say so.
      let shown = 0;
      tbody.replaceChildren(...ssrRows);
      for (const row of ssrRows) {
        // The folder trail isn't duplicated into a data attribute (it runs ~200 bytes on a deep
        // production), so read it from its own cell rather than silently dropping the facet.
        const cell = showFolder ? (row.querySelector(".doccat-folder")?.textContent ?? "") : "";
        const inFolder =
          !folder ||
          cell === folder.replace(/\//g, " / ") ||
          cell.startsWith(`${folder.replace(/\//g, " / ")} / `);
        const visible = inFolder && matchesDoc(row.dataset, query, filters);
        row.hidden = !visible;
        if (visible) shown += 1;
      }
      if (count) count.textContent = `${shown} of ${ssrRows.length} on this page`;
      if (empty) empty.hidden = shown !== 0;
      return;
    }

    const q = query.trim().toLowerCase();
    const matches = rows.filter((row) => {
      if (q && !row.n.toLowerCase().includes(q)) return false;
      if (filters.type && row.t !== filters.type) return false;
      if (filters.access && row.a !== filters.access) return false;
      // A folder facet includes its descendants — selecting a branch selects the subtree.
      if (folder && row.f !== folder && !row.f.startsWith(`${folder}/`)) return false;
      return true;
    });

    tbody.replaceChildren(...matches.map(renderRow));
    // Filtering spans the whole listing, so the page's pager no longer describes what's shown.
    if (pager) pager.hidden = true;
    if (count) count.textContent = `${matches.length} of ${rows.length}`;
    if (empty) empty.hidden = matches.length !== 0;
  };

  const sortBy = (header: HTMLTableCellElement): void => {
    const key = header.dataset.sort;
    if (!key) return;
    const numeric = header.hasAttribute("data-numeric");
    const dir = header.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
    for (const cell of Array.from(table.tHead?.rows[0].cells ?? [])) {
      cell.setAttribute("aria-sort", "none");
    }
    header.setAttribute("aria-sort", dir);
    const sign = dir === "ascending" ? 1 : -1;
    const rows = Array.from(tbody.rows);
    rows.sort((a, b) => sign * compareDocs(a.dataset, b.dataset, key, numeric));
    tbody.replaceChildren(...rows);
  };

  search?.addEventListener("input", () => void apply());
  for (const select of selects) select.addEventListener("change", () => void apply());
  for (const header of Array.from(table.tHead?.rows[0].cells ?? [])) {
    if (!header.dataset.sort) continue;
    header.classList.add("doccat-sortable");
    header.addEventListener("click", () => sortBy(header));
  }
}
