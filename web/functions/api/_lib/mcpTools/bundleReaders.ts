// Bundle reader MCP tool handlers (#914): get_timeline, get_entities,
// get_hypotheses, get_documents, get_document.
//
// Each handler fetches its feed from a root-absolute static JSON endpoint emitted at
// build time (src/pages/feeds/*.json.ts), so there is no database or model call —
// these are pure deterministic JSON readers. Tool descriptions embed the evidentiary
// contract: clients must cite sources and must not fabricate missing fields.
//
// Response-size governance (#1581): each reader fits its filtered feed to an explicit
// budget (max_results / max_tokens / max_tokens_per_result, or an `intent` preset) and
// returns the uniform `{ results, token_estimate, truncated, next_cursor }` envelope. The
// cursor pages the deterministic ordered feed; over-cap items shed their heaviest optional
// fields (prose detail, variant lists, assessment internals, entry lists) before counting.

import type { Citation, DocumentCollectionItem, DocumentEntry, RecordItem } from "@watermark/core/feeds";
import { fetchWithTimeout } from "../http";
import {
  type BudgetKnobs,
  type Governed,
  decodeCursorOffset,
  dropKeysUntilUnderCap,
  estimateTokens,
  govern,
  governedContent,
  resolveKnobs,
} from "../mcpGovern";

type McpContent = { type: "text"; text: string };

function feedUrl(name: string, requestUrl: string): string {
  return new URL(`/feeds/${name}.json`, requestUrl).toString();
}

async function fetchFeed<T>(name: string, requestUrl: string): Promise<T> {
  const res = await fetchWithTimeout(feedUrl(name, requestUrl));
  if (!res.ok) throw new Error(`feed ${name} returned ${res.status}`);
  return res.json() as Promise<T>;
}

/** Resolve the governance knobs + cursor offset shared by every reader. */
function governanceOf(p: Record<string, unknown>): { knobs: BudgetKnobs; offset: number } {
  return { knobs: resolveKnobs(p), offset: decodeCursorOffset(p.cursor) };
}

/** Page `items` (the reader's ordered result list) through the budget and wrap the envelope. */
function paginate<T>(
  items: T[],
  knobs: BudgetKnobs,
  offset: number,
  shrink?: (item: T, capTokens: number) => T,
): McpContent[] {
  const window = items.slice(offset, offset + knobs.maxResults + 1);
  return governedContent(govern(window, { knobs, baseOffset: offset, shrink }));
}

// --- get_timeline ----------------------------------------------------------------

interface TimelineEntry {
  date: string;
  category: string;
  title: string;
  ref?: string;
  parties?: string[];
  detail?: string;
  source?: string;
  citation?: { verified?: boolean; confidence?: string; source_kind?: string; page?: number | null };
}

interface GetTimelineParams {
  since?: unknown;
  until?: unknown;
  category?: unknown;
}

export async function handleGetTimeline(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetTimelineParams;
  const since = typeof p.since === "string" ? p.since : null;
  const until = typeof p.until === "string" ? p.until : null;
  const category = typeof p.category === "string" && p.category ? p.category : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  let entries = await fetchFeed<TimelineEntry[]>("timeline", requestUrl);

  if (since) entries = entries.filter((e) => e.date >= since);
  if (until) entries = entries.filter((e) => e.date <= until);
  if (category) entries = entries.filter((e) => e.category === category);

  // Return ascending (oldest-first); clients may reverse as needed.
  entries = [...entries].sort((a, b) => a.date.localeCompare(b.date));

  return paginate(entries, knobs, offset, (e, cap) => dropKeysUntilUnderCap(e, ["detail", "parties"], cap));
}

// --- get_entities ----------------------------------------------------------------

interface EntityNode {
  key: string;
  display: string;
  kind: string;
  classification?: string | null;
  variants?: string[];
  roles?: Record<string, number>;
  parcels?: string[];
  addresses?: string[];
  sources?: string[];
  signals?: string[];
}

interface GetEntitiesParams {
  type?: unknown;
}

export async function handleGetEntities(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetEntitiesParams;
  const typeFilter = typeof p.type === "string" && p.type ? p.type : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  let entities = await fetchFeed<EntityNode[]>("entities", requestUrl);

  if (typeFilter) {
    entities = entities.filter((e) => e.kind === typeFilter);
  }

  return paginate(entities, knobs, offset, (e, cap) =>
    dropKeysUntilUnderCap(e, ["variants", "addresses", "signals", "parcels", "roles"], cap),
  );
}

// --- get_hypotheses --------------------------------------------------------------

interface HypothesisItem {
  id: string;
  number: string;
  name: string;
  claim: string;
  thesis: string;
  status: string;
  signals: string[];
  groups: string[];
}

interface HypothesisAssessmentItem {
  site: string;
  hypothesis: string;
  signal: string;
  tag: string;
  sub_thesis?: string | null;
  group?: string;
  fields?: Record<string, unknown>;
  citations?: unknown[];
}

interface HypothesesPayload {
  hypotheses: HypothesisItem[];
  assessments: HypothesisAssessmentItem[];
}

interface JoinedHypothesis extends HypothesisItem {
  assessments: HypothesisAssessmentItem[];
  /** True total before any per-result shrink — a capped `assessments` list is detectable as
   * `assessments.length < assessments_total` (mirrors documents' `entry_count`). */
  assessments_total: number;
}

interface GetHypothesesParams {
  site?: unknown;
}

/** Shed a joined hypothesis's heaviest payload: assessment internals first, then cap the list. */
function shrinkHypothesis(h: JoinedHypothesis, capTokens: number): JoinedHypothesis {
  if (estimateTokens(h) <= capTokens) return h;
  // Strip each assessment to its identity + tag (drop fields/citations/sub_thesis).
  const lean: JoinedHypothesis = {
    ...h,
    assessments: h.assessments.map((a) => ({
      site: a.site,
      hypothesis: a.hypothesis,
      signal: a.signal,
      tag: a.tag,
      group: a.group,
    })),
  };
  if (estimateTokens(lean) <= capTokens) return lean;
  // Still over: keep as many assessments as fit (count preserved via the array length).
  const kept: HypothesisAssessmentItem[] = [];
  for (const a of lean.assessments) {
    const trial = { ...lean, assessments: [...kept, a] };
    if (kept.length > 0 && estimateTokens(trial) > capTokens) break;
    kept.push(a);
  }
  return { ...lean, assessments: kept };
}

export async function handleGetHypotheses(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetHypothesesParams;
  const siteFilter = typeof p.site === "string" && p.site ? p.site : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  const payload = await fetchFeed<HypothesesPayload>("hypotheses", requestUrl);
  const { hypotheses, assessments } = payload;

  let filteredAssessments = assessments;
  if (siteFilter) {
    filteredAssessments = assessments.filter((a) => a.site === siteFilter);
  }

  const joined: JoinedHypothesis[] = hypotheses.map((h) => {
    const own = filteredAssessments.filter((a) => a.hypothesis === h.id);
    return { ...h, assessments: own, assessments_total: own.length };
  });

  return paginate(joined, knobs, offset, shrinkHypothesis);
}

// --- get_documents ---------------------------------------------------------------
// DocumentEntry / DocumentCollectionItem are the canonical feed types (imported above).

interface ReducedEntry {
  rel: string;
  name: string;
  media_type: string;
  published: boolean;
  available: boolean;
}

interface ReducedCollection {
  slug: string;
  title: string;
  description: string;
  entry_count: number;
  entries: ReducedEntry[];
}

interface GetDocumentsParams {
  collection?: unknown;
}

/** Cap a collection's entry list until it fits; `entry_count` stays the true total. */
function shrinkCollection(c: ReducedCollection, capTokens: number): ReducedCollection {
  if (estimateTokens(c) <= capTokens) return c;
  const kept: ReducedEntry[] = [];
  for (const e of c.entries) {
    const trial = { ...c, entries: [...kept, e] };
    if (kept.length > 0 && estimateTokens(trial) > capTokens) break;
    kept.push(e);
  }
  return { ...c, entries: kept };
}

export async function handleGetDocuments(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetDocumentsParams;
  const collectionFilter = typeof p.collection === "string" && p.collection ? p.collection : null;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  let collections = await fetchFeed<DocumentCollectionItem[]>("documents", requestUrl);

  if (collectionFilter) {
    collections = collections.filter((c) => c.slug === collectionFilter);
  }

  // Strip full entry details for brevity; return metadata only.
  const reduced: ReducedCollection[] = collections.map((c) => ({
    slug: c.slug,
    title: c.title,
    description: c.description ?? "",
    entry_count: c.entries.length,
    entries: c.entries.map((e) => ({
      rel: e.rel,
      name: e.name,
      media_type: e.media_type,
      published: e.published,
      available: e.available,
    })),
  }));

  return paginate(reduced, knobs, offset, shrinkCollection);
}

// --- get_document ----------------------------------------------------------------
// Addressable single fetch (#1583). Resolves one document by id — either a document
// file `collection/rel` or its joined extraction-record id — and returns the document's
// metadata joined to that record's structured `fields` + `Citation`, with field/section
// projection, bounded by max_tokens. The bundle carries record `fields`, not raw source
// body text (that is separate search_passages work), so projection operates over fields.

const DOCUMENT_SECTIONS = ["metadata", "fields", "citation", "warnings"] as const;
type DocumentSection = (typeof DOCUMENT_SECTIONS)[number];

/** File metadata of the source document (present when the id joins a real document entry). */
interface DocumentFile {
  rel: string;
  name: string;
  media_type: string;
  render_class: string;
  size_bytes: number;
  published: boolean;
  available: boolean;
  download_url: string | null;
}

interface DocumentMetadata {
  record_rel: string | null;
  title: string | null;
  group: string | null;
  confidence: string | null;
  source_doc_rel: string | null;
  document_file: DocumentFile | null;
}

interface DocumentView {
  /** Canonical id echoed back (the joined record rel when there is one, else the doc rel). */
  document_id: string;
  collection: string;
  metadata?: DocumentMetadata;
  fields?: Record<string, unknown>;
  /** The record's true field count — a `fields` subset (projection or budget shrink) is
   * detectable as `Object.keys(fields).length < field_count` (mirrors documents' entry_count). */
  field_count?: number;
  citation?: Citation | null;
  warnings?: string[];
  source_text?: string;
}

interface GetDocumentParams {
  document_id?: unknown;
  fields?: unknown;
  sections?: unknown;
  include_source_text?: unknown;
  intent?: unknown;
  max_tokens?: unknown;
}

const NOT_FOUND: Governed<DocumentView> = {
  results: [],
  token_estimate: 0,
  truncated: false,
  next_cursor: null,
};

/** Ids from search_corpus carry a `records:` feed prefix; get_document addresses the bare rel. */
function normalizeDocumentId(id: string): string {
  return id.startsWith("records:") ? id.slice("records:".length) : id;
}

function parseStringList(v: unknown): string[] | null {
  if (!Array.isArray(v)) return null;
  const arr = v.filter((x): x is string => typeof x === "string" && x.length > 0);
  return arr.length > 0 ? arr : null;
}

/** Requested sections (valid names only); an empty/absent list means all sections. */
function parseSections(v: unknown): Set<DocumentSection> {
  const arr = parseStringList(v);
  if (!arr) return new Set(DOCUMENT_SECTIONS);
  const valid = arr.filter((s): s is DocumentSection => (DOCUMENT_SECTIONS as readonly string[]).includes(s));
  return valid.length > 0 ? new Set(valid) : new Set(DOCUMENT_SECTIONS);
}

/** Flatten a record's `fields` into "key value" text — the record's searchable extraction
 * text (mirrors @watermark/core askIndex.fieldText, #327). Recurses into nested objects. */
function flattenFields(fields: Record<string, unknown>): string {
  const bits: string[] = [];
  const collect = (obj: Record<string, unknown>): void => {
    for (const [k, val] of Object.entries(obj)) {
      if (val == null) continue;
      if (Array.isArray(val)) {
        const scalars = val.filter((x) => x != null && typeof x !== "object").map(String);
        if (scalars.length > 0) bits.push(`${k} ${scalars.join(" ")}`);
      } else if (typeof val === "object") {
        collect(val as Record<string, unknown>);
      } else {
        bits.push(`${k} ${String(val)}`);
      }
    }
  };
  collect(fields);
  return bits.join(" · ");
}

/**
 * Shed the document to fit `capTokens` — the single-item peer of the readers' per-result
 * shrink. Sheds heaviest/least-essential first (source_text → warnings → surplus fields),
 * never the `metadata` or `citation` sections (the evidentiary contract keeps provenance,
 * as search hits do). `field_count` stays the true total so a shed `fields` map is detectable.
 */
function boundDocument(view: DocumentView, capTokens: number): { view: DocumentView; truncated: boolean } {
  if (estimateTokens(view) <= capTokens) return { view, truncated: false };
  const v: DocumentView = { ...view };
  if (v.source_text !== undefined && estimateTokens(v) > capTokens) delete v.source_text;
  if (v.warnings !== undefined && estimateTokens(v) > capTokens) v.warnings = [];
  if (v.fields !== undefined && estimateTokens(v) > capTokens) {
    const kept: Record<string, unknown> = {};
    for (const [k, val] of Object.entries(v.fields)) {
      const trial = { ...v, fields: { ...kept, [k]: val } };
      if (Object.keys(kept).length > 0 && estimateTokens(trial) > capTokens) break;
      kept[k] = val;
    }
    v.fields = kept;
  }
  return { view: v, truncated: true };
}

export async function handleGetDocument(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetDocumentParams;
  const rawId = typeof p.document_id === "string" ? p.document_id.trim() : "";
  if (!rawId) return governedContent(NOT_FOUND);
  const id = normalizeDocumentId(rawId);

  const sections = parseSections(p.sections);
  const fieldFilter = parseStringList(p.fields);
  const includeSourceText = p.include_source_text === true;
  const knobs = resolveKnobs({ intent: p.intent, max_tokens: p.max_tokens });

  const [records, collections] = await Promise.all([
    fetchFeed<RecordItem[]>("records", requestUrl),
    fetchFeed<DocumentCollectionItem[]>("documents", requestUrl),
  ]);

  const findDocEntry = (rel: string): { entry: DocumentEntry; slug: string } | null => {
    for (const c of collections) {
      const entry = c.entries.find((e) => e.rel === rel);
      if (entry) return { entry, slug: c.slug };
    }
    return null;
  };

  // Resolve by record id first (the direct, projectable target); else by document rel,
  // reverse-joining the record that was extracted from it.
  let record = records.find((r) => r.rel === id) ?? null;
  let doc = record?.source_doc_rel ? findDocEntry(record.source_doc_rel) : null;
  if (!record) {
    doc = findDocEntry(id);
    if (doc) record = records.find((r) => r.source_doc_rel === id) ?? null;
  }
  if (!record && !doc) return governedContent(NOT_FOUND);

  const canonicalId = record?.rel ?? doc?.entry.rel ?? id;
  const view: DocumentView = {
    document_id: canonicalId,
    collection: canonicalId.split("/")[0] ?? "",
  };

  if (sections.has("metadata")) {
    view.metadata = {
      record_rel: record?.rel ?? null,
      title: record?.title ?? doc?.entry.name ?? null,
      group: record?.group ?? null,
      confidence: record?.confidence ?? null,
      source_doc_rel: record?.source_doc_rel ?? doc?.entry.rel ?? null,
      document_file: doc
        ? {
            rel: doc.entry.rel,
            name: doc.entry.name,
            media_type: doc.entry.media_type,
            render_class: doc.entry.render_class,
            size_bytes: doc.entry.size_bytes,
            published: doc.entry.published,
            available: doc.entry.available,
            download_url: doc.entry.download_url ?? null,
          }
        : null,
    };
  }

  if (record && sections.has("fields")) {
    view.fields = fieldFilter
      ? Object.fromEntries(Object.entries(record.fields).filter(([k]) => fieldFilter.includes(k)))
      : record.fields;
    view.field_count = Object.keys(record.fields).length;
  }
  if (record && sections.has("citation")) view.citation = record.citation;
  if (record && sections.has("warnings")) view.warnings = record.warnings;
  if (record && includeSourceText) view.source_text = flattenFields(record.fields);

  const { view: bounded, truncated } = boundDocument(view, knobs.maxTokens);
  const results = [bounded];
  const governed: Governed<DocumentView> = {
    results,
    token_estimate: estimateTokens(results),
    truncated,
    next_cursor: null,
  };
  return governedContent(governed);
}
