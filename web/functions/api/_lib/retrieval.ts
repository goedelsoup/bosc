// Dependency-free BM25 retrieval over the build-time ask-index (#209).
//
// Tokenization + scoring happen here, at *query* time, on the Workers runtime — so
// the build (@watermark/core/askIndex) only ships raw text units and there is no
// way for build-time and query-time tokenization to drift apart. Mirrors the
// no-dependency posture of the site search (src/scripts/search.ts): plain JS, no lunr,
// no CDN, runs on Web platform globals only.
//
// The corpus is small (the citation-bearing bundle feeds — low hundreds of units), so
// preparing the postings once per loaded index and scoring linearly per request is
// cheap. The Worker caches the prepared index across requests in the same isolate.
//
// The one import is `@watermark/core/askFacets` — the facet normalizers the build-time producer
// stamped the index with (#1691). It is deliberately node-free for exactly this reason: sharing
// the definition is what keeps a filter from being stricter or looser than the index it queries.

import { agencyMatches, countyKey, facetKey, permitMatches, projectKey } from "@watermark/core/askFacets";

/**
 * One retrieval unit — a citation-bearing thing in the bundle (a record, timeline
 * event, entity, …). The shape is duplicated in `@watermark/core/askIndex` (the build-time
 * producer), exactly as `SearchDoc` is duplicated between `lib/search.ts` and
 * `scripts/search.ts`: the emitted `/ask-index.json` is the contract between them.
 */
export interface AskUnit {
  /** Stable id, `${feed}:${localId}` — what the model and the page cite by. */
  id: string;
  /** The bundle feed this came from (records, timeline, entities, …). */
  feed: string;
  title: string;
  /** Root-absolute deep link (pre-base) to the page this unit lives on. */
  url: string;
  /** The searchable blob (title is indexed separately, weighted). */
  text: string;
  /** Provenance lifted from the item's Citation (#213 resolves these). */
  source?: string | null;
  page?: number | null;
  /** Every 1-based page the claim was read from, when the read spanned more than one (#1584). */
  pages?: number[] | null;
  source_kind?: string | null;
  confidence?: string | null;
  verified?: boolean;
  /** Site slug this unit belongs to (e.g. "lima"). Absent on legacy index entries. */
  site?: string;
  /** Structured event/record date, when the source feed carries one (timeline/meetings).
   * Surfaced on compact discovery cards (#1580); absent on units with no dated source. */
  date?: string | null;
  /** The `data/documents` rel of this unit's source document — the version/duplicate-cluster
   * dedup join key (#1590), matching `DocumentItem.rel`. Built into the ask-index; absent for a
   * unit with no documents-feed source. */
  doc_rel?: string | null;
  /** The site's county, e.g. "Allen County, OH" — stamped at build time like `site` (#1691). */
  county?: string | null;
  /** The issuing/administering body, verbatim from the record ("Ohio EPA, Division of Surface
   * Water"). Records only; free text, so `agencyMatches` compares it by containment (#1691). */
  agency?: string | null;
  /** Every permit / case / filing identifier the unit is filed under (#1691). */
  permit_numbers?: string[] | null;
  /** The document genre — record group / timeline category / meeting kind. Distinct from `feed`,
   * which names the bundle collection rather than the instrument (#1691). */
  document_type?: string | null;
  /** The entity-graph keys this unit touches, joined exactly at build time (#1691). */
  entities?: string[] | null;
  /** The campus / named project slug this unit belongs to (#1691). */
  project?: string | null;
}

/** One scored hit: the unit plus its BM25 score. */
export interface Hit {
  unit: AskUnit;
  score: number;
}

/**
 * Structured facet filters over indexed AskUnit fields (#1582, extended by #1691). Every field is
 * optional; an absent field imposes no constraint, and every present constraint must hold
 * (AND-combined).
 *
 * Every facet here is backed by a **real indexed field** — that was the rule #1582 set when it
 * stopped at six, and #1691 kept it by enriching the index rather than by widening the schema.
 * The one facet still missing is `fact_category`: the `facts` feed is not part of the ask-index
 * at all (`buildAskIndex` covers the citation-bearing feeds), so a category constraint over these
 * units would filter on nothing. `get_facts` / `aggregate_facts` are the tools for that axis.
 */
export interface CorpusFilters {
  /** Site slug (e.g. "lima"). */
  site?: string;
  /** Bundle feed name (records, documents, timeline, …) — NOT a document-collection slug. */
  feed?: string;
  /** Provenance class: "document" (primary source) vs "derived" (editorial synthesis). */
  source_kind?: string;
  /** Keep only [verified] units (true) or only unverified units (false). */
  verified?: boolean;
  /** Inclusive ISO-8601 lower bound on the unit's structured `date`. */
  date_from?: string;
  /** Inclusive ISO-8601 upper bound on the unit's structured `date`. */
  date_to?: string;
  /** Citation confidence band (e.g. "high"), matched exactly. */
  confidence?: string;
  /** County the records were filed in — "Allen", "allen county" and "Allen County, OH" are one
   * constraint (`countyKey`). */
  county?: string;
  /** Issuing/administering body, matched as a substring of the record's own agency string, so
   * "Ohio EPA" reaches "Ohio EPA, Division of Surface Water" (`agencyMatches`). */
  agency?: string;
  /** Permit / case / filing identifier. Separators are ignored and a base number matches every
   * modification filed under it (`2PH00006` → `2PH00006*LD`) — see `permitMatches`. */
  permit_number?: string;
  /** Document genre — record group (`permits-npdes`, `deeds`, `enforcement`, …), timeline
   * category, or meeting kind. */
  document_type?: string;
  /** Entity-graph key, as returned by `get_entities`. */
  entity?: string;
  /** Campus / named project slug (`project-bosc`). `project` and `campus` are one facet. */
  project?: string;
}

/**
 * Narrow `units` to those satisfying every present facet in `filters` (#1582).
 *
 * `site` is special: it filters strictly only when the index actually carries site tags — an
 * untagged (legacy) index skips the site constraint rather than silently returning nothing.
 * Every other facet compares directly against the indexed field, so a unit missing that field
 * fails the constraint: `verified:true` drops untagged units, and either date bound drops
 * undated units (a date filter can't be satisfied by a unit with no date). ISO-8601 dates sort
 * lexically, so string comparison is a correct date comparison.
 */
export function applyCorpusFilters(units: AskUnit[], filters: CorpusFilters): AskUnit[] {
  let out = units;

  if (filters.site) {
    // Only filter when the index is site-tagged — `!u.site` would silently leak cross-site
    // results on a mixed index, but a wholly untagged (legacy) index means "single site".
    const site = filters.site;
    const hasTaggedUnits = out.some((u) => typeof u.site === "string" && u.site.length > 0);
    if (hasTaggedUnits) out = out.filter((u) => u.site === site);
  }
  if (filters.feed) {
    const feed = filters.feed;
    out = out.filter((u) => u.feed === feed);
  }
  if (filters.source_kind) {
    const kind = filters.source_kind;
    out = out.filter((u) => u.source_kind === kind);
  }
  if (filters.verified !== undefined) {
    const verified = filters.verified;
    out = out.filter((u) => (u.verified ?? false) === verified);
  }
  if (filters.date_from) {
    const from = filters.date_from;
    out = out.filter((u) => typeof u.date === "string" && u.date >= from);
  }
  if (filters.date_to) {
    const to = filters.date_to;
    out = out.filter((u) => typeof u.date === "string" && u.date <= to);
  }
  if (filters.confidence) {
    const confidence = filters.confidence;
    out = out.filter((u) => u.confidence === confidence);
  }

  // --- Enrichment facets (#1691) -------------------------------------------------------------
  // Same contract as the block above: a unit missing the field fails the constraint. The
  // difference is the comparison — these facets carry values written by the record rather than by
  // the exporter, so each compares through the normalizer `@watermark/core/askFacets` defines for
  // it, and the producer stamps the index with the same functions. See that module for why exact
  // string equality would answer "no results" to questions the corpus can plainly answer.
  if (filters.county) {
    const county = countyKey(filters.county);
    out = out.filter((u) => typeof u.county === "string" && countyKey(u.county) === county);
  }
  if (filters.agency) {
    const agency = filters.agency;
    out = out.filter((u) => typeof u.agency === "string" && agencyMatches(u.agency, agency));
  }
  if (filters.permit_number) {
    const permit = filters.permit_number;
    out = out.filter((u) => Array.isArray(u.permit_numbers) && permitMatches(u.permit_numbers, permit));
  }
  if (filters.document_type) {
    const kind = facetKey(filters.document_type);
    out = out.filter((u) => typeof u.document_type === "string" && facetKey(u.document_type) === kind);
  }
  if (filters.entity) {
    const entity = facetKey(filters.entity);
    out = out.filter((u) => (u.entities ?? []).some((e) => facetKey(e) === entity));
  }
  if (filters.project) {
    const project = projectKey(filters.project);
    out = out.filter((u) => typeof u.project === "string" && projectKey(u.project) === project);
  }

  return out;
}

// A compact English stoplist — enough to keep BM25 from rewarding filler, small enough
// to stay honest about a record-search vocabulary (kept words like "no"/"not" matter).
const STOPWORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "by",
  "for",
  "from",
  "has",
  "have",
  "in",
  "into",
  "is",
  "it",
  "its",
  "of",
  "on",
  "or",
  "that",
  "the",
  "to",
  "was",
  "were",
  "what",
  "when",
  "where",
  "which",
  "who",
  "why",
  "will",
  "with",
  "this",
  "these",
  "those",
  "they",
  "their",
  "there",
  "about",
  "how",
  "did",
  "does",
  "do",
]);

/**
 * Lowercase → alphanumeric runs → drop stopwords + 1-char noise, fold a trailing plural
 * "s" so "roundabouts" matches "roundabout". Deterministic and pure; the single source
 * of truth for both indexing and querying.
 */
export function tokenize(text: string): string[] {
  const out: string[] = [];
  for (const m of text.toLowerCase().matchAll(/[a-z0-9]+/g)) {
    let t = m[0];
    if (t.length < 2 || STOPWORDS.has(t)) continue;
    if (t.length > 3 && t.endsWith("s")) t = t.slice(0, -1);
    out.push(t);
  }
  return out;
}

// The title is high-signal, so its tokens are counted with extra weight.
const TITLE_WEIGHT = 2;
const K1 = 1.5;
const B = 0.75;

/** Token counts for one document, plus its length. */
interface Doc {
  tf: Map<string, number>;
  len: number;
}

/** A prepared index: postings + corpus stats, ready to score many queries against. */
export interface PreparedIndex {
  units: AskUnit[];
  docs: Doc[];
  df: Map<string, number>;
  avgdl: number;
  n: number;
}

function addTokens(tf: Map<string, number>, tokens: string[], weight: number): number {
  for (const tok of tokens) tf.set(tok, (tf.get(tok) ?? 0) + weight);
  return tokens.length * weight;
}

/** Precompute term frequencies, document frequencies, and the mean document length. */
export function prepare(units: AskUnit[]): PreparedIndex {
  const docs: Doc[] = [];
  const df = new Map<string, number>();
  let total = 0;
  for (const u of units) {
    const tf = new Map<string, number>();
    let len = addTokens(tf, tokenize(u.text), 1);
    len += addTokens(tf, tokenize(u.title), TITLE_WEIGHT);
    for (const tok of tf.keys()) df.set(tok, (df.get(tok) ?? 0) + 1);
    docs.push({ tf, len });
    total += len;
  }
  const n = units.length;
  return { units, docs, df, avgdl: n > 0 ? total / n : 0, n };
}

/** Robertson–Sparck-Jones idf, the BM25+ non-negative form. */
function idf(df: number, n: number): number {
  return Math.log(1 + (n - df + 0.5) / (df + 0.5));
}

/**
 * Score every unit against `query` and return the top `k` with a positive score,
 * highest first. Empty/irrelevant queries return `[]` — the caller treats that as
 * "not in the record" (the grounding layer refuses rather than inventing context).
 */
export function search(prepared: PreparedIndex, query: string, k = 6): Hit[] {
  const terms = tokenize(query);
  if (terms.length === 0 || prepared.n === 0) return [];
  const { docs, df, avgdl, n, units } = prepared;
  const qterms = [...new Set(terms)];

  const hits: Hit[] = [];
  for (let i = 0; i < docs.length; i++) {
    const { tf, len } = docs[i];
    let score = 0;
    for (const t of qterms) {
      const f = tf.get(t);
      if (!f) continue;
      const denom = f + K1 * (1 - B + (B * len) / (avgdl || 1));
      score += idf(df.get(t) ?? 0, n) * ((f * (K1 + 1)) / denom);
    }
    if (score > 0) hits.push({ unit: units[i], score });
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, k);
}

/** Convenience for tests / cold paths: prepare + search in one call. */
export function retrieve(units: AskUnit[], query: string, k = 6): Hit[] {
  return search(prepare(units), query, k);
}

// --- Hybrid retrieval: vector search + Reciprocal Rank Fusion (#329) ---------------

/** Cosine similarity between two vectors; returns 0 when lengths differ or either is the zero vector. */
export function cosineScore(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb);
  return denom === 0 ? 0 : dot / denom;
}

/** An id + precomputed embedding vector from the ask-embeddings index (#329). */
export interface EmbeddingEntry {
  id: string;
  embedding: number[];
}

/**
 * Score units by cosine similarity to `queryEmbedding` and return the top `k`.
 * Units without a matching entry in `embeddings` are skipped — a partial index is OK
 * and the function degrades gracefully toward zero results.
 */
export function vectorSearch(
  units: AskUnit[],
  embeddings: EmbeddingEntry[],
  queryEmbedding: number[],
  k = 6,
): Hit[] {
  const byId = new Map(embeddings.map((e) => [e.id, e.embedding]));
  const hits: Hit[] = [];
  for (const unit of units) {
    const emb = byId.get(unit.id);
    if (!emb) continue;
    const score = cosineScore(queryEmbedding, emb);
    if (score > 0) hits.push({ unit, score });
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, k);
}

const RRF_K = 60; // standard smoothing constant (prevents rank-1 from dominating)

/**
 * Reciprocal Rank Fusion of two scored hit lists (#329).
 *
 *   fused_score(d) = 1 / (k + rank_bm25(d)) + 1 / (k + rank_vec(d))
 *
 * A document absent from a list gets rank = list.length + 1 (last-place penalty).
 * Returns the top `topK` hits by fused score, highest first.
 */
export function rrf(bm25: Hit[], vec: Hit[], topK = 6): Hit[] {
  const r1 = new Map(bm25.map((h, i) => [h.unit.id, i + 1]));
  const r2 = new Map(vec.map((h, i) => [h.unit.id, i + 1]));
  const absent1 = bm25.length + 1;
  const absent2 = vec.length + 1;

  const seen = new Map<string, Hit>();
  for (const h of [...bm25, ...vec]) if (!seen.has(h.unit.id)) seen.set(h.unit.id, h);

  return [...seen.values()]
    .map((h) => ({
      unit: h.unit,
      score: 1 / (RRF_K + (r1.get(h.unit.id) ?? absent1)) + 1 / (RRF_K + (r2.get(h.unit.id) ?? absent2)),
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}
