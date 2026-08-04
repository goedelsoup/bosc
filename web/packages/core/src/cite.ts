/**
 * The citation primitive (#1885, epic #1884 phase 1) — the one place that turns a **corpus
 * identifier** into a **site route**.
 *
 * The site leads with the impact study as each site's primary artifact and promises that every
 * figure is checkable. Measured against the committed build, no study chapter linked to a single
 * record, document, or reference dataset: a `[verified]` tag was rendering provenance the page did
 * not provide. This module is the fix's spine.
 *
 * Three things a figure can cite, and exactly three:
 *
 *  - a **record** — a reviewed structured extraction, addressed by its `data/extracted/` rel and
 *    routed at `/site/records/<group>/<id>` (the same `slugify(rel)` the record screens mint);
 *  - a **document** — a source file in the immutable corpus, addressed by its `data/documents/`
 *    rel and routed at `/doc/<handle>/` (`documentId`, #1887);
 *  - a **reference dataset** — an outside authoritative publication, addressed by its published
 *    slug and routed at `/site/reference/<slug>`.
 *
 * **Resolution is per site and never optimistic.** Every resolver reads the *active site's own*
 * bundle and returns `null` when the target is not on that site's record: a rel absent from the
 * feed, a document the route filter excludes (`isRoutableDoc`), a dataset whose catalog entry the
 * site doesn't own, or a facet whose readiness domain hasn't activated. A null is the honest
 * answer — "no committed source here" — and callers render the claim bare rather than mint a link
 * into a 404. That is the whole no-fabricated-citations rule, enforced at the resolver rather than
 * trusted to each caller: **no function here can invent a destination.**
 *
 * The free-text scanner (`citedSourcesIn`) exists because the corpus already writes its citations
 * down. Feed citation strings name the extraction they were read from verbatim — "committed
 * `data/extracted/permits/4132514.epa.yaml` (final, 2026-05-28)" — so a chapter's leaf citations
 * are *derived from the data*, not curated per site. Nothing here parses prose for meaning; it
 * matches one path grammar and hands each hit to the same per-site resolver as everything else.
 *
 * NOT client-safe (reads the bundle through `bundle.ts`) — pages resolve at build and render the
 * plain objects.
 */
import { activeSite, hasFeed, loadFeed } from "./bundle";
import { docPermalinkForRel } from "./documentId";
import { isRoutableDoc } from "./docRouting";
import type { EvidenceKind } from "./evidence";
import { evidenceKind, slugify, type DocumentCollectionItem, type RecordItem } from "./feeds";
import { facetAvailable } from "./readiness";
import { groupLabel } from "./records";
import { scopedReference } from "./reference";

/** What a citation points at. Exactly three kinds — see the module header. */
export type CiteKind = "record" | "document" | "reference";

/**
 * Why a figure carries this citation. A `[verified]` figure was **read** from the source; a
 * modeled one names its **input** instead, so a reader is never told a derivation was a reading
 * (the `[inference]` case the epic calls out — resolve to the inputs, and say so).
 */
export type CiteBasis = "read" | "input";

/** A resolved citation: a real destination on THIS site, with the label to print. */
export interface CitedSource {
  kind: CiteKind;
  /** The stable key — a record rel, a document rel, or a reference dataset slug. */
  key: string;
  /** Site-relative path, pre-deploy-base. Callers wrap it in `withSite`. */
  href: string;
  /** What to print when the caller supplies no text of its own. */
  label: string;
  /** The second line — the record group, the document's collection, or the publisher. */
  detail: string;
  /** The evidence class of the destination itself, NOT of the figure citing it. */
  evidence: EvidenceKind;
}

/** The corpus roots a citation path may name. */
export const EXTRACTED_PREFIX = "data/extracted/";
export const DOCUMENTS_PREFIX = "data/documents/";
export const REFERENCE_PREFIX = "data/reference/";

/**
 * The one path grammar. Matches a corpus root followed by a rel, stopping at whitespace and at
 * the punctuation that reliably ends a path inside a prose citation — quotes, brackets, commas,
 * semicolons, and the backtick a markdown citation wraps it in. A trailing `.` or `)` is trimmed
 * after the match (a sentence-final period is not part of a filename, but `.yaml` is).
 */
const CORPUS_PATH_RE = /data\/(?:extracted|documents|reference)\/[^\s"'`,;<>[\]()]+/g;

/** Trailing sentence punctuation that can never end a corpus rel. */
const TRAILING_PUNCTUATION = /[.:]+$/;

// --- per-kind resolution -------------------------------------------------------------------

/**
 * Every public resolver takes an OPTIONAL slug and falls back to the ambient site, matching
 * `loadFeed`/`hasFeed`. `facetAvailable` and `scopedReference` take a required one, so the
 * default is resolved once, here, rather than spelled differently in each call site.
 */
function site(slug?: string): string {
  return slug ?? activeSite();
}

/** The site's records, or [] when the facet is locked / the feed is absent. */
function siteRecords(slug?: string): RecordItem[] {
  if (!facetAvailable(site(slug), "records")) return [];
  return hasFeed("records", slug) ? loadFeed<RecordItem[]>("records", slug) : [];
}

/** The site's routable documents, or [] when the facet is locked / the feed is absent. */
function siteDocuments(slug?: string): { rel: string; name: string; collection: string }[] {
  if (!facetAvailable(site(slug), "documents")) return [];
  if (!hasFeed("documents", slug)) return [];
  return loadFeed<DocumentCollectionItem[]>("documents", slug).flatMap((collection) =>
    collection.entries
      .filter(isRoutableDoc)
      .map((entry) => ({ rel: entry.rel, name: entry.name, collection: collection.title })),
  );
}

/**
 * A record citation — the `data/extracted/` rel exactly as the records feed carries it.
 * `null` when this site's record domain is locked or the rel isn't on its own record.
 */
export function citeRecord(rel: string, slug?: string): CitedSource | null {
  const record = siteRecords(slug).find((r) => r.rel === rel);
  if (!record) return null;
  return {
    kind: "record",
    key: rel,
    href: `/site/records/${record.group}/${slugify(record.rel)}`,
    label: record.title,
    detail: groupLabel(record.group).replace(/ —.*$/, ""),
    evidence: evidenceKind(record.citation),
  };
}

/**
 * A document citation — the `data/documents/` rel, addressed by its stable handle.
 * `null` when the document facet is locked, the rel isn't in this site's catalog, or the routing
 * filter excludes it (OS exhaust, an inline email image, a web-page sidecar): those are
 * catalogued and fetchable but have no page to link to.
 *
 * Deliberately NOT gated on the publish allowlist. A gated document still has a page — the
 * production record of it is public even where the bytes are not — and citing it is how a reader
 * learns the record exists at all.
 */
export function citeDocument(rel: string, slug?: string): CitedSource | null {
  const entry = siteDocuments(slug).find((d) => d.rel === rel);
  if (!entry) return null;
  return {
    kind: "document",
    key: rel,
    href: docPermalinkForRel(rel),
    label: entry.name,
    detail: entry.collection,
    evidence: "verified",
  };
}

/**
 * A reference-dataset citation by published slug. `null` unless this site OWNS the dataset
 * (`scopedReference` — the catalog `site_scope` seam), so a peer can never cite the reference
 * build's Lima zoning or Allen County parcels.
 */
export function citeDataset(datasetSlug: string, slug?: string): CitedSource | null {
  if (!facetAvailable(site(slug), "reference")) return null;
  const dataset = scopedReference(site(slug)).find((d) => d.slug === datasetSlug);
  if (!dataset) return null;
  return {
    kind: "reference",
    key: dataset.slug,
    href: `/site/reference/${dataset.slug}`,
    label: dataset.title,
    detail: "Reference dataset",
    evidence: "reference",
  };
}

/**
 * Resolve a raw corpus path (`data/extracted/…`, `data/documents/…`, `data/reference/…`) — the
 * form feed citations write. A reference path names a FILE inside a dataset directory
 * (`data/reference/rsei/inventory.yaml`), so it resolves by longest matching dataset directory,
 * which correctly prefers the nested `hydrology/wbd` dataset over a bare `hydrology` one.
 */
export function citeCorpusPath(path: string, slug?: string): CitedSource | null {
  if (path.startsWith(EXTRACTED_PREFIX)) return citeRecord(path.slice(EXTRACTED_PREFIX.length), slug);
  if (path.startsWith(DOCUMENTS_PREFIX)) return citeDocument(path.slice(DOCUMENTS_PREFIX.length), slug);
  if (!path.startsWith(REFERENCE_PREFIX)) return null;
  const rel = path.slice(REFERENCE_PREFIX.length);
  const owned = facetAvailable(site(slug), "reference") ? scopedReference(site(slug)) : [];
  // `repo` is the README's path within data/reference; its directory is the dataset's root.
  const match = owned
    .map((d) => ({ d, dir: d.repo.slice(0, d.repo.lastIndexOf("/") + 1) }))
    .filter(({ dir }) => rel.startsWith(dir))
    .sort((a, b) => b.dir.length - a.dir.length)[0];
  return match ? citeDataset(match.d.slug, slug) : null;
}

// --- the free-text scanner -----------------------------------------------------------------

/**
 * Every distinct corpus path mentioned anywhere inside `value`, in first-seen order.
 *
 * Takes any JSON value and stringifies it, so a caller can hand it a whole feed rather than
 * enumerate which of a row's dozen optional `*_citation` fields might carry a path. Pure string
 * matching — it resolves nothing and reads no bundle.
 */
export function corpusPathsIn(value: unknown): string[] {
  const text = typeof value === "string" ? value : JSON.stringify(value ?? "");
  const seen = new Set<string>();
  for (const raw of text.match(CORPUS_PATH_RE) ?? []) {
    const path = raw.replace(TRAILING_PUNCTUATION, "");
    // A bare directory mention ("data/documents/watershed/") addresses no single source.
    if (path.endsWith("/")) continue;
    seen.add(path);
  }
  return [...seen];
}

/**
 * The sources `value` cites that this site can actually open — scan, resolve, drop the
 * unresolvable, dedupe by destination. This is the derived half of a chapter's evidence: the
 * corpus writes its own citations into the feeds, so the links come out of the data rather than
 * out of a per-site curation list that would rot.
 */
export function citedSourcesIn(value: unknown, slug?: string): CitedSource[] {
  const out = new Map<string, CitedSource>();
  for (const path of corpusPathsIn(value)) {
    const source = citeCorpusPath(path, slug);
    if (source) out.set(`${source.kind}:${source.key}`, source);
  }
  return [...out.values()];
}

// --- authored citations (the MDX notes) ----------------------------------------------------

/** One `<Cite …>` in a study note's source, before resolution. */
export interface CiteSpec {
  kind: CiteKind;
  key: string;
}

/** `<Cite …>` opening tags, attributes captured whole (they may wrap across lines). */
const CITE_TAG_RE = /<Cite\s([^>]*?)>/gs;
/** The one identity attribute inside such a tag. `document` is the raw HTML-ish spelling. */
const CITE_ATTR_RE = /\b(record|document|dataset)\s*=\s*"([^"]*)"/;

/**
 * The citations a study note's MDX source authors by hand — parsed from the source rather than
 * from the compiled output, so the same list is available to the annex at render AND to the
 * test suite without compiling MDX.
 *
 * Deliberately a narrow regex over one known component, not an MDX parse: the note bodies are
 * repo-authored content in a curated component vocabulary, and the only consumer of a
 * mis-parse is a missing annex row (the `<Cite>` itself still resolves at render, where an
 * unresolvable one fails the build).
 */
export function citeSpecsInNote(body: string): CiteSpec[] {
  const out: CiteSpec[] = [];
  const seen = new Set<string>();
  for (const [, attrs] of body.matchAll(CITE_TAG_RE)) {
    const match = attrs.match(CITE_ATTR_RE);
    if (!match) continue;
    const kind = match[1] === "dataset" ? "reference" : (match[1] as CiteKind);
    const spec = `${kind}:${match[2]}`;
    if (seen.has(spec)) continue;
    seen.add(spec);
    out.push({ kind, key: match[2] });
  }
  return out;
}

/** Resolve one parsed spec against a site (the `<Cite>` component's own resolution). */
export function resolveCiteSpec(spec: CiteSpec, slug?: string): CitedSource | null {
  if (spec.kind === "record") return citeRecord(spec.key, slug);
  if (spec.kind === "document") return citeDocument(spec.key, slug);
  return citeDataset(spec.key, slug);
}

/** The resolvable sources a note's prose cites, in first-cited order. */
export function citedSourcesInNote(body: string, slug?: string): CitedSource[] {
  return citeSpecsInNote(body)
    .map((spec) => resolveCiteSpec(spec, slug))
    .filter((source) => source !== null);
}

// --- record groups -------------------------------------------------------------------------

/** A record group that has rows on this site — the "the record behind this chapter" band. */
export interface CitedGroup {
  group: string;
  label: string;
  href: string;
  count: number;
}

/**
 * Resolve declared record groups against this site's own records: a group with no rows here is
 * simply not offered, so a thin peer's chapter shows the groups it actually has and never a door
 * onto an empty index. Returned in the order declared.
 */
export function citeGroups(groups: readonly string[], slug?: string): CitedGroup[] {
  const records = siteRecords(slug);
  return groups
    .map((group) => ({
      group,
      label: groupLabel(group).replace(/ —.*$/, ""),
      href: `/site/records/${group}/`,
      count: records.filter((r) => r.group === group).length,
    }))
    .filter((g) => g.count > 0);
}
