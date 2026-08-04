/**
 * The fifth document facet (#1898, epic #1884 phase 3) — **extraction status**.
 *
 * The other four say something about a *file*: which collection it arrived in, what kind of
 * artifact it is, how big it is, whether its bytes are public. This one says something about the
 * *investigation*: has anyone read it yet?
 *
 * Measured on the committed Lima bundle, that turns out not to be a uniform property. Extraction
 * is close to complete on the small instrument collections — 26 of 35 `permits`, 11 of 18 `oepa`,
 * 6 of 7 `recorder` — and essentially absent from the two collections that are 84% of the catalog:
 * 8 of 1,732 `legal`, 0 of 995 `commissioners`. A reader browsing a thousand meeting documents had
 * no way to learn that none of them have been through the extract stage, and a researcher looking
 * for what is already structured had no way to find it but to guess.
 *
 * **"Extracted" means the join, and nothing more.** A document is extracted when a row of the
 * `records` feed names it in `source_doc_rel` — the #276 join, already carried per record, needing
 * no feed change and no `CONTRACT_VERSION` bump. The issue asked whether it should instead mean
 * something richer from the records feed's own `confidence` / `warnings`: it should not. Those
 * describe how well a *record* reads, which is a property of the extraction, not of whether the
 * source has been read at all — folding them in here would make a document with a low-confidence
 * record indistinguishable from one nobody has opened. The facet answers exactly one question and
 * a reader can check its answer by following the link.
 *
 * Gated like every other per-site read: the index is built only from records this site can
 * actually open (`facetAvailable(slug, "records")`), so the facet can never mint a link into a
 * locked facet's 404. Where that gate is shut the index is empty and the counts read `0 of N` —
 * which is the true answer, not a fabricated one: a documents landing only builds when the record
 * domain is present, so a locked `records` facet there means the feed is genuinely empty.
 *
 * NOT client-safe (reads the bundle through `bundle.ts`). `extractionIndex` itself is pure; the
 * pages resolve at build and hand the client script the plain strings via `catalog.json`.
 */
import { activeSite, hasFeed, loadFeed } from "./bundle";
import { docPermalinkForRel } from "./documentId";
import { slugify, type DocumentEntry, type RecordItem } from "./feeds";
import { facetAvailable } from "./readiness";

/** Whether a catalogued document has been through the extract stage. */
export type ExtractionStatus = "extracted" | "catalogued";

/**
 * The prefix every record screen shares, site-relative and pre-deploy-base. Exported because
 * `catalog.json` stores each row's record path with this trimmed off and the client script
 * re-applies it from the table's `data-rec-base` — a shared constant is what keeps the asset from
 * repeating 15 bytes 52 times, without letting the two halves invent different routes.
 */
export const RECORD_ROUTE_BASE = "/site/records/";

/** One record read from a document — enough to name it and open it. */
export interface ExtractionRef {
  /** The record's `data/extracted/` rel — its identity in the corpus. */
  rel: string;
  /** The record group, e.g. `permits-epa` — the index it is filed under. */
  group: string;
  title: string;
  /** The record screen, site-relative and pre-deploy-base. Callers wrap it in `withSite`. */
  href: string;
}

/**
 * Doc rel → the records read from it, in feed order. Pure: the caller supplies the records, so a
 * test can drive it from a fixture and the build drives it from the bundle.
 *
 * Records with no `source_doc_rel` are skipped — 4 of Lima's 56 today. Those are real extractions
 * whose source is a connector pull rather than a file in `data/documents/`, so they belong to no
 * document and must not be attributed to one.
 */
export function extractionIndex(records: readonly RecordItem[]): Map<string, ExtractionRef[]> {
  const index = new Map<string, ExtractionRef[]>();
  for (const record of records) {
    const docRel = record.source_doc_rel;
    if (!docRel) continue;
    const ref: ExtractionRef = {
      rel: record.rel,
      group: record.group,
      title: record.title,
      href: `${RECORD_ROUTE_BASE}${record.group}/${slugify(record.rel)}/`,
    };
    const bucket = index.get(docRel);
    if (bucket) bucket.push(ref);
    else index.set(docRel, [ref]);
  }
  return index;
}

/** Per-site index cache — the feed is read once per build, not once per landing. */
const cached = new Map<string, Map<string, ExtractionRef[]>>();

/**
 * The extraction index for a site, built once. Empty when the site's `records` facet is locked —
 * see the module header: that is the honest zero, not a missing answer.
 */
export function siteExtractions(slug: string = activeSite()): Map<string, ExtractionRef[]> {
  const hit = cached.get(slug);
  if (hit) return hit;
  const records =
    facetAvailable(slug, "records") && hasFeed("records", slug)
      ? loadFeed<RecordItem[]>("records", slug)
      : [];
  const index = extractionIndex(records);
  cached.set(slug, index);
  return index;
}

/** A document's status against an index. */
export function extractionStatus(rel: string, index: Map<string, ExtractionRef[]>): ExtractionStatus {
  return index.has(rel) ? "extracted" : "catalogued";
}

/** How many of `entries` have been extracted — the numerator of a landing's "26 of 35". */
export function countExtracted(
  entries: readonly DocumentEntry[],
  index: Map<string, ExtractionRef[]>,
): number {
  let n = 0;
  for (const entry of entries) if (index.has(entry.rel)) n += 1;
  return n;
}

/**
 * The ratio a listing opens with — "26 of 35 extracted". One helper rather than the same
 * interpolation on four landings, so the collection, container, page and index pages can't come
 * to phrase or round the same number differently.
 */
export function extractionSummary(extracted: number, total: number): string {
  const n = (v: number): string => v.toLocaleString("en-US");
  return `${n(extracted)} of ${n(total)} extracted`;
}

/** The statuses actually present in a listing — a facet with one value is not a facet. */
export function extractionStatusesIn(
  entries: readonly DocumentEntry[],
  index: Map<string, ExtractionRef[]>,
): ExtractionStatus[] {
  const extracted = countExtracted(entries, index);
  const statuses: ExtractionStatus[] = [];
  if (extracted > 0) statuses.push("extracted");
  if (extracted < entries.length) statuses.push("catalogued");
  return statuses;
}

/** What a row's (or a page's) extraction chip says, and where it goes. */
export interface ExtractionMark {
  status: ExtractionStatus;
  /** Chip text. */
  label: string;
  /**
   * Site-relative destination, pre-deploy-base; `null` for a catalogued-only document, which has
   * nothing to open.
   *
   * One record is the whole corpus today (52 documents, 52 records, no document backing two), so
   * the chip lands directly on the record — one click from a listing row to the structured read.
   * The model does not forbid a second, though: a single bundle can hold six OPC estimates from
   * one PDF. Where that happens the chip lands on the *document's* page instead, which lists every
   * record read from it, rather than picking one of them and calling it the extraction.
   */
  href: string | null;
}

/** The mark for one document. `refs` is its bucket from the index (absent or empty = catalogued). */
export function extractionMark(rel: string, refs: readonly ExtractionRef[] | undefined): ExtractionMark {
  if (!refs || refs.length === 0) {
    return { status: "catalogued", label: "not extracted", href: null };
  }
  if (refs.length === 1) return { status: "extracted", label: "extracted", href: refs[0].href };
  return {
    status: "extracted",
    label: `extracted · ${refs.length} records`,
    href: docPermalinkForRel(rel),
  };
}
