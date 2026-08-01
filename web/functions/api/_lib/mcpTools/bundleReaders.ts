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
//
// Structured citations (#1584): the readers that carry provenance — get_timeline, get_document
// and get_facts (with include_evidence) — return it as the uniform `citation` object from
// `../mcpCitation`, the same shape search_corpus and search_passages emit, rather than each
// passing through whatever shape its own feed happens to use.

import {
  FACT_METRICS,
  type FactAggregate,
  aggregateFacts,
  listMetrics,
  parseGroupBy,
  resolveMetric,
} from "@watermark/core/factAggregate";
import {
  FACT_FEEDS,
  isFactFeed,
  listFactCategories,
  resolveFactCategory,
} from "@watermark/core/factCategories";
import type {
  Citation,
  DocumentCollectionItem,
  DocumentEntry,
  FactItem,
  RecordItem,
} from "@watermark/core/feeds";
import { fetchWithTimeout } from "../http";
import { type McpCitation, buildCitation } from "../mcpCitation";
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
  citation?: Citation | null;
}

/** The emitted row: the feed entry with its raw feed `Citation` replaced by the uniform
 * structured one (#1584), so every tool speaks the same provenance shape. */
type TimelineView = Omit<TimelineEntry, "citation"> & { citation: McpCitation };

interface GetTimelineParams {
  since?: unknown;
  until?: unknown;
  category?: unknown;
}

/** A timeline row carries an explicit `source` string even where `citation` is null (the same
 * asymmetry `@watermark/core/askIndex` handles), so fall back to it rather than emitting an
 * uncited event for a row that names its source. */
function timelineCitation(e: TimelineEntry): McpCitation {
  const c = e.citation;
  return buildCitation({
    source: c?.source ?? e.source,
    source_kind: c?.source_kind ?? "document",
    page: c?.page,
    pages: c?.pages,
    note: c?.note,
    confidence: c?.confidence,
    verified: c?.verified,
  });
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
  const views: TimelineView[] = [...entries]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((e) => ({ ...e, citation: timelineCitation(e) }));

  return paginate(views, knobs, offset, (e, cap) => dropKeysUntilUnderCap(e, ["detail", "parties"], cap));
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
  /** The record's provenance as the uniform structured citation (#1584) — the record's own
   * `Citation` joined to the document file it was extracted from, so the caller holds a
   * page-level, addressable cite without a second call. */
  citation?: McpCitation;
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
  if (record && sections.has("citation")) {
    // The record supplies the page cite; the joined document entry supplies the addressable id
    // and the URL its bytes are served at — neither half is complete on its own.
    view.citation = buildCitation(
      {
        document_id: record.source_doc_rel,
        source: record.citation?.source ?? record.rel,
        source_kind: record.citation?.source_kind,
        page: record.citation?.page,
        pages: record.citation?.pages,
        note: record.citation?.note,
        source_url: doc?.entry.download_url,
        confidence: record.citation?.confidence ?? record.confidence,
        verified: record.citation?.verified,
      },
      requestUrl,
    );
  }
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

// --- get_facts (#1587) -----------------------------------------------------------
// Normalized `(subject, predicate, value, unit, status)` facts, projected from the bundle's
// provenanced values. A fact question is a tiny retrieval + arithmetic instead of a whole-record
// pull: filter by subject/predicate/status, and only attach the evidence block on request.

interface GetFactsParams {
  subject?: unknown;
  predicate?: unknown;
  status?: unknown;
  include_evidence?: unknown;
  fact_category?: unknown;
  feed?: unknown;
}

/** The compact result: the tuple minus the evidence block (attached only when requested). A
 * present-but-absent optional field (unit/low/high/approximate) is dropped so the row stays lean. */
interface FactView {
  subject: string;
  subject_label: string;
  subject_kind: string;
  predicate: string;
  value: number | null;
  unit?: string | null;
  status: string;
  low?: number | null;
  high?: number | null;
  approximate?: boolean;
  feed: string;
  evidence?: FactItem["evidence"];
  /** The evidence block as the uniform structured citation (#1584), attached with it. A
   * projected fact usually has no path and no page — a `ProvenancedValue` records provenance as
   * one free-text string — so that text rides in `citation.note` and becomes the label rather
   * than being dropped in the name of structure. */
  citation?: McpCitation;
}

/** Flexible subject match (case-insensitive substring over the key + human label + kind) — the
 * caller can pass "Allen County" or "facility" without knowing the `<kind>:<id>` grammar. Shared
 * by get_facts and aggregate_facts. */
function factMatchesSubject(f: FactItem, needle: string): boolean {
  return (
    f.subject.toLowerCase().includes(needle) ||
    f.subject_label.toLowerCase().includes(needle) ||
    f.subject_kind.toLowerCase().includes(needle)
  );
}

/** Normalize a name-list param (`predicate`, `feed`) to a lowercased set — a single string or a
 * string[]; null when nothing usable was passed. `foldUnderscores` is for the hyphenated
 * vocabularies (feed/category names); it is NOT applied to `predicate`, whose snake_case
 * underscores are part of the field name. */
function parseNameSet(raw: unknown, foldUnderscores = false): Set<string> | null {
  const list = Array.isArray(raw) ? raw : typeof raw === "string" ? [raw] : [];
  const cleaned = list
    .filter((x): x is string => typeof x === "string" && x.trim() !== "")
    .map((s) => {
      const name = s.trim().toLowerCase();
      return foldUnderscores ? name.replace(/_/g, "-") : name;
    });
  return cleaned.length ? new Set(cleaned) : null;
}

// --- the fact-category / feed gate (#1827) -----------------------------------------
// `FactItem.feed` is the category axis, and the `fact_category` vocabulary
// (@watermark/core/factCategories) is the written-down grouping over it. Both `get_facts` and
// `aggregate_facts` gate on it through this one resolver so the two can't diverge.
//
// The discipline the issue exists to enforce: a constraint that names nothing real must FAIL
// LOUDLY. An unknown category, an unknown feed, or a category/feed pair that can't both hold
// would each otherwise return an empty result set — indistinguishable from "the corpus has no
// such facts", for a question the corpus can answer. So each returns an error envelope carrying
// the vocabulary instead.

interface FeedGate {
  /** The `FactItem.feed` values a fact must be projected from; null ⇒ unconstrained. */
  feeds: Set<string> | null;
  /** A ready-to-return envelope when the caller named a vocabulary that doesn't exist. */
  error: McpContent[] | null;
}

const UNCONSTRAINED: FeedGate = { feeds: null, error: null };

/** An error envelope shaped like `unknownMetric`: name the miss, hand back the vocabulary. */
function vocabularyError(row: Record<string, unknown>): FeedGate {
  return {
    feeds: null,
    error: governedContent({ results: [row], token_estimate: 0, truncated: false, next_cursor: null }),
  };
}

function resolveFeedGate(p: { fact_category?: unknown; feed?: unknown }): FeedGate {
  const categoryRaw = typeof p.fact_category === "string" ? p.fact_category.trim() : "";
  const feedNames = parseNameSet(p.feed, true);
  if (!categoryRaw && !feedNames) return UNCONSTRAINED;

  let allowed: Set<string> | null = null;

  if (categoryRaw) {
    const category = resolveFactCategory(categoryRaw);
    if (!category) {
      return vocabularyError({
        error: `unknown fact_category "${categoryRaw}"`,
        available_categories: listFactCategories(),
        hint: isFactFeed(categoryRaw)
          ? `"${categoryRaw}" is a source feed, not a category — pass it as \`feed\` instead.`
          : "Or filter on the exact source feed with `feed`.",
      });
    }
    allowed = new Set(category.feeds);
  }

  if (feedNames) {
    const unknown = [...feedNames].filter((f) => !isFactFeed(f));
    if (unknown.length) {
      return vocabularyError({
        error: `unknown fact feed${unknown.length > 1 ? "s" : ""} ${unknown.map((f) => `"${f}"`).join(", ")}`,
        available_feeds: FACT_FEEDS,
        hint: "Or filter on the grouped vocabulary with `fact_category`.",
      });
    }
    // Both given ⇒ AND, like every other filter here. An impossible pair is a contradiction,
    // not an empty corpus, so say so rather than returning zero rows.
    allowed = allowed ? new Set([...allowed].filter((f) => feedNames.has(f))) : feedNames;
    if (!allowed.size) {
      return vocabularyError({
        error: `fact_category "${categoryRaw}" and feed ${[...feedNames].map((f) => `"${f}"`).join(", ")} cannot both hold`,
        available_categories: listFactCategories(),
      });
    }
  }

  return { feeds: allowed, error: null };
}

/** A fact's evidence block as the uniform citation object (#1584). `evidence.citation` is the
 * `ProvenancedValue`'s free-text provenance, not a path, so it lands in `note` — for most rows it
 * is the ONLY provenance there is, and the structured cite would otherwise be empty. */
function factCitation(e: FactItem["evidence"]): McpCitation {
  return buildCitation({
    source: e.source,
    source_kind: e.source_kind,
    page: e.page,
    note: e.citation,
    confidence: e.confidence,
    verified: e.verified,
  });
}

function toView(f: FactItem, includeEvidence: boolean): FactView {
  const view: FactView = {
    subject: f.subject,
    subject_label: f.subject_label,
    subject_kind: f.subject_kind,
    predicate: f.predicate,
    value: f.value ?? null,
    status: f.status,
    feed: f.feed,
  };
  if (f.unit != null) view.unit = f.unit;
  if (f.low != null) view.low = f.low;
  if (f.high != null) view.high = f.high;
  if (f.approximate) view.approximate = true;
  if (includeEvidence) {
    view.evidence = f.evidence;
    view.citation = factCitation(f.evidence);
  }
  return view;
}

export async function handleGetFacts(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as GetFactsParams;
  // `subject` matches flexibly (case-insensitive substring over the key + label + kind) so a
  // caller can pass a human subject ("Allen County", "facility") without knowing the key grammar.
  const subject = typeof p.subject === "string" && p.subject.trim() ? p.subject.trim().toLowerCase() : null;
  const predicates = parseNameSet(p.predicate);
  const status = typeof p.status === "string" && p.status.trim() ? p.status.trim().toLowerCase() : null;
  const includeEvidence = p.include_evidence === true;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);

  // Resolved BEFORE the fetch: a constraint that names nothing real is answered with the
  // vocabulary, never with an empty page of real facts (#1827).
  const gate = resolveFeedGate(p);
  if (gate.error) return gate.error;
  const gateFeeds = gate.feeds;

  let facts = await fetchFeed<FactItem[]>("facts", requestUrl);

  if (gateFeeds) facts = facts.filter((f) => gateFeeds.has(f.feed.toLowerCase()));
  if (subject) facts = facts.filter((f) => factMatchesSubject(f, subject));
  if (predicates) facts = facts.filter((f) => predicates.has(f.predicate.toLowerCase()));
  if (status) facts = facts.filter((f) => f.status.toLowerCase() === status);

  // Deterministic order (the feed is already sorted; re-sort so filtering can't perturb it).
  facts = [...facts].sort((a, b) =>
    a.subject === b.subject ? a.predicate.localeCompare(b.predicate) : a.subject.localeCompare(b.subject),
  );

  const views = facts.map((f) => toView(f, includeEvidence));
  // Over-cap shed: drop the raw evidence block first (the structured `citation` says the same
  // thing more compactly), then the uncertainty band — never the subject/predicate/value/status
  // that make the fact answerable, and never `citation` while any cheaper field remains.
  return paginate(views, knobs, offset, (v, cap) =>
    dropKeysUntilUnderCap(v, ["evidence", "low", "high", "subject_label"], cap),
  );
}

// --- aggregate_facts (#1588) -----------------------------------------------------
// The arithmetic tier on top of the facts feed: the server does the sum / count / mean /
// product so the model never pulls every row just to total something. Given a `metric`
// (a registered recipe like backup_generation_capacity_mw, or the generic `<op>:<predicate>`
// grammar) and a `group_by` dimension, it returns one grouped total per group — value, unit,
// a human-readable `derivation`, `confidence`, `caveat`, and the `evidence_ids` that fed it.
// Called with no `metric`, it lists the registered metrics (discovery). Pure arithmetic lives
// in @watermark/core/factAggregate; this handler is the facts.json fetch + filter + envelope.

interface AggregateFactsParams {
  metric?: unknown;
  group_by?: unknown;
  subject?: unknown;
  status?: unknown;
  fact_category?: unknown;
  feed?: unknown;
}

/** The unknown-metric envelope: name the miss and hand back the vocabulary the caller can use. */
function unknownMetric(metric: string): McpContent[] {
  return governedContent({
    results: [
      {
        error: `unknown metric "${metric}"`,
        available_metrics: FACT_METRICS.map((m) => m.key),
        grammar: "or use sum:<predicate> | count:<predicate> | mean:<predicate> | product:<a>,<b>",
      },
    ],
    token_estimate: 0,
    truncated: false,
    next_cursor: null,
  });
}

export async function handleAggregateFacts(params: unknown, requestUrl: string): Promise<McpContent[]> {
  const p = (params ?? {}) as AggregateFactsParams;
  const { knobs, offset } = governanceOf(p as Record<string, unknown>);
  const metricRaw = typeof p.metric === "string" ? p.metric.trim() : "";

  // Discovery: no metric ⇒ advertise the registered recipes so the caller can pick one.
  if (!metricRaw) return paginate(listMetrics(), knobs, offset);

  const metric = resolveMetric(metricRaw);
  if (!metric) return unknownMetric(metricRaw);

  const groupBy = parseGroupBy(p.group_by);
  const subject = typeof p.subject === "string" && p.subject.trim() ? p.subject.trim().toLowerCase() : null;
  const status = typeof p.status === "string" && p.status.trim() ? p.status.trim().toLowerCase() : null;

  // The same category/feed gate get_facts uses — the two share the whole pre-filter pair
  // (#1827), so a total and the tuples behind it are always taken over the same rows.
  const gate = resolveFeedGate(p);
  if (gate.error) return gate.error;
  const gateFeeds = gate.feeds;

  let facts = await fetchFeed<FactItem[]>("facts", requestUrl);
  if (gateFeeds) facts = facts.filter((f) => gateFeeds.has(f.feed.toLowerCase()));
  if (subject) facts = facts.filter((f) => factMatchesSubject(f, subject));
  if (status) facts = facts.filter((f) => f.status.toLowerCase() === status);

  const aggregates = aggregateFacts(facts, metric, groupBy);

  // Over-cap shed: drop the evidence ids first, then the prose (caveat, derivation, label) —
  // never value/unit/group/status, the answer itself.
  return paginate(aggregates, knobs, offset, (a: FactAggregate, cap) =>
    dropKeysUntilUnderCap(a, ["evidence_ids", "caveat", "derivation", "group_label"], cap),
  );
}
