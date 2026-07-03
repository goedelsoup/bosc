/**
 * Resolve a curated Record Teardown against the live content bundle, at build
 * time. This is what keeps the guided walk and the reference library reading the
 * SAME feeds — the teardown's editorial framing stays curated, but its figures,
 * links and provenance are confirmed against the actual bundle rows:
 *
 *   - load-bearing rows carrying a `path` get their value from the anchor
 *     record's `fields` (the same datum + approximate-marker the library renders),
 *     formatted by `unit` — so a checkable number can never fork from the source.
 *   - the `① source` panel surfaces the record's real extraction (`sourceFields`),
 *     retiring the placeholder ghost.
 *   - `verify` deep-links to the exact `records` row (`/network/american-sugar-creek-allen-co/site/records/<group>#<rel>`)
 *     when that row is in the bundle; the row's `citation` is surfaced on the
 *     source card so the provenance is the library's own, not a restatement.
 *   - failing a records row, `verify` deep-links to the backing legal page.
 *   - `connect` concept chips deep-link to `/wiki/concepts/<slug>` when the slug
 *     exists in the `concepts` feed.
 *
 * Everything is PRESENT-CHECKED against the bundle being built, so a minimal
 * fixture (CI) gracefully falls back to the curated value/link rather than
 * forking or 404-ing.
 */
import { hasFeed, loadFeed } from "./bundle";
import {
  type Citation,
  type ConceptItem,
  type DocumentCollectionItem,
  type DocumentEntry,
  type RecordItem,
  slugify,
} from "./feeds";
import { legalBySlug } from "./legal";
import { type BlockField, recordToBlock } from "./recordBlock";
import { formatScalar } from "./records";
import { withBase, withSite } from "./site";
import type { TeardownConnect, TeardownRecord, TeardownRow, TeardownUnit } from "./teardown";

/** Records in the bundle being built, by `rel` (built once). */
const recordsByRel: Map<string, RecordItem> = (() => {
  const map = new Map<string, RecordItem>();
  if (hasFeed("records")) for (const r of loadFeed<RecordItem[]>("records")) map.set(r.rel, r);
  return map;
})();

/** Source documents in the bundle, by `data/documents` rel (built once). The A2 join
 *  on each record gives `source_doc_rel`; this resolves it to the full catalog entry so
 *  the teardown can embed the real document via <DocViewer> (#284). */
const documentsByRel: Map<string, DocumentEntry> = (() => {
  const map = new Map<string, DocumentEntry>();
  if (hasFeed("documents"))
    for (const c of loadFeed<DocumentCollectionItem[]>("documents"))
      for (const e of c.entries) map.set(e.rel, e);
  return map;
})();

/** Concept slugs present in the bundle being built (built once). */
const conceptSlugs: Set<string> = (() => {
  const set = new Set<string>();
  if (hasFeed("concepts")) for (const c of loadFeed<ConceptItem[]>("concepts")) set.add(c.slug);
  return set;
})();

/** Pull the slug out of a `[[wiki-link]]` connect label, slugified. */
function conceptSlugOf(label: string): string | null {
  const m = label.match(/\[\[([^\]]+)\]\]/);
  return m ? slugify(m[1]) : null;
}

/** Resolve a dotted `path` into a record's `fields` (e.g. "meta.summary_total");
 *  `undefined` when any segment is missing — the signal to keep the curated value. */
function getPath(fields: Record<string, unknown>, path: string): unknown {
  let cur: unknown = fields;
  for (const seg of path.split(".")) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[seg];
  }
  return cur;
}

/** Whether a dotted `path` is flagged approximate (`~`) in the record. */
function isApproxPath(record: RecordItem, path: string): boolean {
  return record.approximate_paths.some((p) => p === path || p.startsWith(`${path}.`));
}

/** Group an integer part with thousands separators (deterministic, no locale). */
function groupThousands(n: number): string {
  const neg = n < 0;
  const [int, frac] = Math.abs(n).toString().split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${neg ? "-" : ""}${grouped}${frac ? `.${frac}` : ""}`;
}

/** Present a feed-sourced figure with its display `unit`; the digits are the
 *  bundle's, the unit/grouping is presentation only (never fabricates a value). */
function formatBound(raw: unknown, unit: TeardownUnit | undefined): string {
  if (raw == null) return "—";
  const num = typeof raw === "number" ? raw : Number(raw);
  const isNum =
    typeof raw === "number" || (typeof raw === "string" && raw.trim() !== "" && !Number.isNaN(num));
  switch (unit) {
    case "usd":
      return isNum ? `$${groupThousands(num)}` : formatScalar(raw);
    case "pct":
      return isNum ? `${groupThousands(num)}%` : formatScalar(raw);
    case "tpy":
      return isNum ? `${groupThousands(num)} tpy` : formatScalar(raw);
    case "cfs":
      return isNum ? `${groupThousands(num)} cfs` : formatScalar(raw);
    case "count":
      return isNum ? groupThousands(num) : formatScalar(raw);
    default:
      return formatScalar(raw);
  }
}

/** Rewrite a teardown row from the anchor record when it carries a `path` that
 *  resolves; otherwise return it unchanged (curated framing / graceful fallback). */
function bindRow(row: TeardownRow, record: RecordItem): TeardownRow {
  if (!row.path) return row;
  const raw = getPath(record.fields, row.path);
  if (raw === undefined) return row; // path absent in this record → keep curated value
  return {
    ...row,
    value: formatBound(raw, row.unit),
    warn: row.warn ?? (raw === null || isApproxPath(record, row.path)),
    live: true,
  };
}

export interface ResolvedTeardown {
  teardown: TeardownRecord;
  /** The backing record's bundle citation, when the row is present. */
  liveCitation: Citation | null;
  /** True when `verify` was deep-linked to a real bundle target. */
  verifyResolved: boolean;
  /** The anchor record's real scalar fields (the library's own row output), for
   *  the source viewer — empty when the record isn't in the bundle. */
  sourceFields: BlockField[];
  /** The record's real source document (#284), resolved from `source_doc_rel`
   *  against the documents catalog — `null` for connector-only records or when the
   *  source isn't catalogued. The teardown embeds it (gated on `published`). */
  sourceDoc: DocumentEntry | null;
}

export function resolveTeardown(t: TeardownRecord): ResolvedTeardown {
  let check = t.check;
  let liveCitation: Citation | null = null;
  let verifyResolved = false;
  let extraction = t.extraction;
  let sourceFields: BlockField[] = [];
  let sourceDoc: DocumentEntry | null = null;

  // 1. records-backed → bind load-bearing figures + the source viewer to the live
  //    record, deep-link verify, and surface its citation.
  if (t.recordRel && recordsByRel.has(t.recordRel)) {
    const row = recordsByRel.get(t.recordRel) as RecordItem;
    liveCitation = row.citation;
    check = {
      ...check,
      verifyHref: withSite(`/site/records/${row.group}/${slugify(t.recordRel)}`),
    };
    verifyResolved = true;
    extraction = t.extraction.map((r) => bindRow(r, row));
    // Source card shows the substantive extraction (skip empty "—" scalars); the
    // full record screen still renders every field. Deliberate blanks are carried
    // as the ② curated warn rows / the redaction-reveal crop, not buried here.
    sourceFields = recordToBlock(row).fields.filter((f) => f.value !== "—");
    // The real source document this record was read from (#284), when catalogued.
    sourceDoc = row.source_doc_rel ? (documentsByRel.get(row.source_doc_rel) ?? null) : null;
  } else if (t.legalSlug && legalBySlug.has(t.legalSlug)) {
    // 2. legal-backed → deep-link verify to the legal-history page.
    check = {
      ...check,
      verifyHref: withSite(`/site/legal/${t.legalSlug}`),
    };
    verifyResolved = true;
  }

  // 3. concept connect chips → deep-link when the slug is in the bundle.
  const connect: TeardownConnect[] = t.connect.map((c) => {
    if (c.kind !== "concept") return c;
    const slug = conceptSlugOf(c.label);
    return slug && conceptSlugs.has(slug) ? { ...c, href: withBase(`/wiki/concepts/${slug}`) } : c;
  });

  // 4. redaction-reveal → default its deep link to the resolved verify target.
  const redaction = t.redaction ? { ...t.redaction, href: t.redaction.href ?? check.verifyHref } : undefined;

  return {
    teardown: { ...t, check, connect, extraction, redaction },
    liveCitation,
    verifyResolved,
    sourceFields,
    sourceDoc,
  };
}
