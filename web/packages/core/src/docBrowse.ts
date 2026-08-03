/**
 * The document-browse model (#1887, epic #1884 phase 3) — how 3,247 catalogued files become a
 * few dozen readable pages instead of one 2.0 MB index and a 16-segment directory walk.
 *
 * Three levels, and no more:
 *
 *   collection            `legal`                    — a first-level dir under data/documents
 *     container           `legal/prr-mandamus`       — the SECOND path segment, and the last one
 *                                                      that becomes a route
 *       folder            everything below           — provenance metadata to display, never a route
 *
 * The container level exists because the corpus is not evenly shaped: one public-records
 * production (`legal/prr-mandamus`, 1,619 files across 238 internal folders) is half the entire
 * Lima catalog, while `aedg` holds five files at the top level. A single flat list serves neither.
 * Cutting at the second segment gives the big production its own front door and leaves the small
 * collections a single page.
 *
 * Below the container, nesting stops being navigation and becomes evidence *about* a document —
 * "Phase 1 SECAP Constr Projects / Ph 1 Shawnee Force Main / Bid and Construction Corr" says what
 * a file is, and belongs on its page and in a facet, not in its URL.
 *
 * Pure and DOM-free: the Astro pages render from it and the client-side facet script filters with
 * the same functions, so SSR and the interactive view can't disagree about what a folder contains.
 */

import { isRoutableDoc } from "./docRouting";
import type { DocumentCollectionItem, DocumentEntry } from "./feeds";

/**
 * Rows per paginated page — sized so a listing's own CONTENT stays around 150 KB. A row measures
 * ~1.0 KB on the deepest production (the as-received folder trail is long, and today the link
 * still carries the full path; #1887's permalink drops it to eight characters).
 *
 * Note what this does NOT do: it cannot by itself meet the issue's "no index.html over ~250 KB"
 * acceptance criterion, because that is not a document-layer problem. Every page in this build
 * carries ~219 KB of shared chrome before a single row is rendered — 188 KB of it the topbar site
 * switcher, which inlines all 38 network sites with their metadata and 162 inline SVG icons into
 * every page. Measured on the build: the switcher is 86% of an average page and ~0.80 GB of the
 * 0.96 GB deploy. Retiring it is #1893 (nav diet), and it is the single biggest lever on #1894's
 * Pages file/size cap. Until then no page of any kind is under 250 KB.
 */
export const DOCS_PER_PAGE = 150;

/**
 * The pagination path segment for a 1-based page number, or `null` for page 1 (which is the
 * bare landing). `page-2` rather than a bare `2` so it can never be mistaken for — or collide
 * with — a container whose as-received directory name happens to be a number. The sanitary
 * production's batches are literally named `9`, `11`, `14` and `15`, so this is not hypothetical.
 */
export function pageSegment(page: number): string | null {
  return page <= 1 ? null : `page-${page}`;
}

/** Inverse of {@link pageSegment}: the 1-based page a segment addresses, or `null` if it isn't one. */
export function parsePageSegment(segment: string): number | null {
  const match = /^page-([2-9]\d*)$/.exec(segment);
  return match ? Number(match[1]) : null;
}

/** Total pages for `total` rows — always at least 1, so an empty container still has a landing. */
export function pageCount(total: number, perPage: number = DOCS_PER_PAGE): number {
  return Math.max(1, Math.ceil(total / perPage));
}

/** The 1-based `page` slice of `items`. */
export function pageSlice<T>(items: readonly T[], page: number, perPage: number = DOCS_PER_PAGE): T[] {
  const start = (page - 1) * perPage;
  return items.slice(start, start + perPage);
}

/**
 * A document's container: the second path segment, or `null` when the file sits directly in the
 * collection (`aedg/PRR-01-bundle.ocr.pdf`) and so has no container of its own.
 */
export function containerOf(rel: string): string | null {
  const segments = rel.split("/");
  return segments.length >= 3 ? segments[1] : null;
}

/**
 * The folder path *below* the container, as segments — the provenance trail the URL no longer
 * carries. Empty for a file sitting directly in its container or collection.
 */
export function folderPathOf(rel: string): string[] {
  const segments = rel.split("/");
  // Drop the collection, the container (if any), and the filename.
  return segments.length >= 3 ? segments.slice(2, -1) : [];
}

/** One container within a collection. `slug` is the as-received directory name, never rewritten. */
export interface ContainerSummary {
  slug: string;
  count: number;
  bytes: number;
  /** Distinct folder paths beneath it — the nesting this refactor stops routing. */
  folders: number;
  /** Deepest folder nesting beneath it, for the "N levels deep" provenance note. */
  maxDepth: number;
}

/** One collection: its containers, plus any files sitting loose directly beneath it. */
export interface CollectionSummary {
  slug: string;
  title: string;
  description: string;
  count: number;
  bytes: number;
  containers: ContainerSummary[];
  /** Files with no container — rendered as a table on the collection landing itself. */
  looseCount: number;
  /** Catalogued but not routed (OS artifacts, Office sidecars) — listed, never a page. */
  nonRoutableCount: number;
}

function summarizeContainer(slug: string, entries: readonly DocumentEntry[]): ContainerSummary {
  const folders = new Set<string>();
  let maxDepth = 0;
  let bytes = 0;
  for (const entry of entries) {
    const path = folderPathOf(entry.rel);
    if (path.length > 0) folders.add(path.join("/"));
    maxDepth = Math.max(maxDepth, path.length);
    bytes += entry.size_bytes;
  }
  return { slug, count: entries.length, bytes, folders: folders.size, maxDepth };
}

/**
 * Summarize every collection in the feed for the documents index and the collection landings.
 *
 * Counts include non-routable entries: a public-records production has to stay provably complete,
 * so `Thumbs.db` is still counted and still listed — it just doesn't get a page. `nonRoutableCount`
 * carries that split so a landing can say so out loud rather than quietly reporting a smaller
 * corpus than the custodian produced.
 */
export function summarizeCollections(feed: readonly DocumentCollectionItem[]): CollectionSummary[] {
  return feed.map((collection) => {
    const byContainer = new Map<string, DocumentEntry[]>();
    let loose = 0;
    let bytes = 0;
    let nonRoutable = 0;
    for (const entry of collection.entries) {
      bytes += entry.size_bytes;
      if (!isRoutableDoc(entry)) nonRoutable += 1;
      const container = containerOf(entry.rel);
      if (container === null) {
        loose += 1;
        continue;
      }
      const bucket = byContainer.get(container);
      if (bucket) bucket.push(entry);
      else byContainer.set(container, [entry]);
    }
    const containers = [...byContainer.entries()]
      .map(([slug, entries]) => summarizeContainer(slug, entries))
      .sort((a, b) => b.count - a.count || a.slug.localeCompare(b.slug));
    return {
      slug: collection.slug,
      title: collection.title,
      description: collection.description ?? "",
      count: collection.entries.length,
      bytes,
      containers,
      looseCount: loose,
      nonRoutableCount: nonRoutable,
    };
  });
}

/**
 * How a collection's landing presents itself.
 *
 * `flat` — one table of every file in the collection, paginated if it needs it.
 * `containers` — a card per container, each with its own landing.
 *
 * The container level is **earned, not assumed**. Measured on the committed corpus, 19 of 21
 * collections hold fewer files than a single page: `aedg` has five. Routing those through a
 * container hop would recreate in miniature exactly the walk this issue exists to remove — a
 * reader clicking `aedg` → `data-center-updates` → four files. Only `legal` (1,732) and
 * `commissioners` (995) are big enough that a flat list stops being readable, and those are
 * precisely the two that have real containers to break out.
 */
export type CollectionLayout = "flat" | "containers";

/** Resolve a collection's layout. A single container is no navigation at all, so it stays flat. */
export function collectionLayout(summary: CollectionSummary): CollectionLayout {
  return summary.count > DOCS_PER_PAGE && summary.containers.length > 1 ? "containers" : "flat";
}

/** The entries a given landing lists: a container's files, or a collection's loose files. */
export function entriesFor(collection: DocumentCollectionItem, container: string | null): DocumentEntry[] {
  return collection.entries.filter((entry) => containerOf(entry.rel) === container);
}

/** One node of the folder facet — a distinct folder path beneath a container. */
export interface FolderFacet {
  /** Slash-joined path relative to the container. Never empty (the root is implicit). */
  path: string;
  /** Last segment, for indented display. */
  name: string;
  /** Nesting level, 1-based. */
  depth: number;
  /** Documents directly in this folder. Descendants are counted by prefix at filter time. */
  count: number;
}

/**
 * Every distinct folder beneath a set of entries, depth-first in path order — the facet that
 * replaces walking the tree as URLs.
 *
 * Ancestors are materialized even when they hold no files of their own, so the facet reads as a
 * tree rather than a list of leaves with gaps.
 */
export function folderFacets(entries: readonly DocumentEntry[]): FolderFacet[] {
  const direct = new Map<string, number>();
  for (const entry of entries) {
    const segments = folderPathOf(entry.rel);
    if (segments.length === 0) continue;
    for (let i = 1; i <= segments.length; i++) {
      const path = segments.slice(0, i).join("/");
      // Only the full path holds the file; ancestors are materialized with zero direct count.
      direct.set(path, (direct.get(path) ?? 0) + (i === segments.length ? 1 : 0));
    }
  }
  return [...direct.entries()]
    .map(([path, count]) => {
      const segments = path.split("/");
      return { path, name: segments[segments.length - 1], depth: segments.length, count };
    })
    .sort((a, b) => a.path.localeCompare(b.path));
}
