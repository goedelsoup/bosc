// search_corpus MCP tool handler (#913).
// Hybrid retrieval over the ask-index — BM25 keyword ranking fused with vector (semantic)
// similarity via Reciprocal Rank Fusion (#1586), degrading to BM25-only when the Workers AI
// binding or the committed ask-embeddings feed is unavailable — with optional site and
// collection filters. Every result carries full provenance; clients must cite source + page,
// and must not paraphrase beyond what the source text says ([verified]/[inference] discipline).
//
// Progressive disclosure (#1580): discovery defaults to compact evidence cards — no full
// `text` blob — so a single permit match no longer injects a whole normalized record
// (~18–24k tokens). `full` reproduces the legacy shape; `snippets` adds a query-focused
// windowed excerpt; `ids_only` is the leanest candidate list. Each hit carries an
// `estimated_tokens` cost so the caller can budget a follow-up `full` fetch.
//
// Response-size governance (#1581): the rendered hits are fitted to an explicit budget
// (max_results / max_tokens / max_tokens_per_result, or an `intent` preset) and returned in
// the uniform `{ results, token_estimate, truncated, next_cursor }` envelope. Over-cap hits
// have their snippet/text trimmed; the cursor pages through the ranked candidate pool.
//
// Evidence tiering (#1591): every compact/snippets/full hit carries a `tier`
// (`direct` / `corroborating` / `background`) and a `tier_reason`, so a caller doesn't treat
// every semantic match as equally useful. The tier is an evidence-grounded judgment from the
// hit's evidence class (feed + source_kind) and its relevance band (score ÷ the pool's top
// score) — see `../mcpTier`. `ids_only` stays a bare id + score list (no tier).
//
// Structured citations (#1584): every compact/snippets/full hit carries a `citation` object
// (document_id, source, page/pages, source_url, evidence, label — see `../mcpCitation`), so a
// caller can cite the hit straight off the discovery card instead of fetching the record to find
// out where it came from. That is what makes compact mode a complete answer rather than a stub.

import { loadAskIndex } from "../askIndexLoad";
import { type McpCitation, buildCitation } from "../mcpCitation";
import { type VersionInfo, loadDocVersionsSafe } from "../docVersionsLoad";
import { dedupeByCluster, parseDeduplicate, parseVersionPolicy } from "../mcpDedup";
import {
  type Governed,
  INTENTS,
  decodeCursorOffset,
  estimateTokens,
  govern,
  governedContent,
  parseIntent,
  resolveKnobs,
  truncateToTokens,
} from "../mcpGovern";
import { type HybridRetrievalEnv, hybridSearch } from "../hybridRetrieve";
import type { AskUnit, CorpusFilters, Hit } from "../retrieval";
import { applyCorpusFilters, prepare, tokenize } from "../retrieval";
import { type Tier, tierHit } from "../mcpTier";

// Rough GPT-style byte→token heuristic — good enough for budgeting, not billing.
const AVG_CHARS_PER_TOKEN = 4;
// snippets mode: query-focused excerpt size; compact mode: a short generic head preview.
const DEFAULT_SNIPPET_TOKENS = 250;
const COMPACT_SNIPPET_TOKENS = 40;
const MIN_SNIPPET_TOKENS = 20;
const MAX_SNIPPET_TOKENS = 1000;

type ResponseMode = "ids_only" | "compact" | "snippets" | "full";
const RESPONSE_MODES: readonly ResponseMode[] = ["ids_only", "compact", "snippets", "full"];
const DEFAULT_MODE: ResponseMode = "compact";

interface SearchCorpusParams {
  query?: unknown;
  // Legacy top-level facet shorthands (#1582): mirror `filters.site` / `filters.feed`.
  site?: unknown;
  collection?: unknown;
  // Structured facet filters over indexed fields (#1582) — resolved via `parseFilters`.
  filters?: unknown;
  limit?: unknown;
  response_mode?: unknown;
  snippet_tokens?: unknown;
  // Duplicate-cluster dedup knobs (#1590) — resolved via mcpDedup.
  deduplicate?: unknown;
  version_policy?: unknown;
  // Governance knobs (#1581) — resolved via mcpGovern.
  intent?: unknown;
  max_results?: unknown;
  max_tokens?: unknown;
  max_tokens_per_result?: unknown;
  cursor?: unknown;
}

/** ids_only: the leanest candidate list — an id to fetch and its rank score. */
interface IdsOnlyHit {
  id: string;
  score: number;
}

/** compact / snippets: an evidence card. No full `text` — `estimated_tokens` is the
 * cost of pulling this hit in `full` mode. */
interface CompactHit {
  id: string;
  title: string;
  site: string | null;
  /** The bundle feed (records, timeline, entities, …) — the `collection` axis. */
  collection: string;
  source_kind: string | null;
  date: string | null;
  score: number;
  snippet: string;
  estimated_tokens: number;
  verified: boolean;
  /** Evidence role for the query (#1591) — direct / corroborating / background. */
  tier: Tier;
  tier_reason: string;
  /** Structured provenance (#1584) — cite the hit straight from the card, no fetch required. */
  citation: McpCitation;
}

/** full: the legacy shape — the whole flattened unit text (opt-in, #1580). */
interface FullHit {
  id: string;
  feed: string;
  title: string;
  text: string;
  url: string;
  source: string | null;
  page: number | null;
  source_kind: string | null;
  confidence: string | null;
  verified: boolean;
  score: number;
  /** Evidence role for the query (#1591) — direct / corroborating / background. */
  tier: Tier;
  tier_reason: string;
  /** Structured provenance (#1584). The flat source/page/source_kind/confidence/verified fields
   * above are kept for back-compat and say the same thing; `citation` is the portable object. */
  citation: McpCitation;
}

type SearchHit = IdsOnlyHit | CompactHit | FullHit;

/** Explicit response_mode wins; else the intent preset seeds it; else compact. */
function parseMode(v: unknown): ResponseMode | null {
  return typeof v === "string" && (RESPONSE_MODES as readonly string[]).includes(v)
    ? (v as ResponseMode)
    : null;
}

/** Explicit snippet_tokens (clamped) wins; else null so the intent preset can seed it. */
function parseSnippetTokens(v: unknown): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  return Math.min(Math.max(MIN_SNIPPET_TOKENS, Math.floor(v)), MAX_SNIPPET_TOKENS);
}

const asStr = (v: unknown): string | undefined => (typeof v === "string" && v ? v : undefined);
const asBool = (v: unknown): boolean | undefined => (typeof v === "boolean" ? v : undefined);

/**
 * Resolve the structured facet filters (#1582, extended by #1691), folding the legacy top-level
 * `site`/`collection` shorthands into the same set — an explicit `filters.*` wins, else the legacy
 * top-level param, else unconstrained. `feed` is the canonical bundle-feed key; `collection` is
 * accepted as an alias (both in `filters` and top-level) but always names a BUNDLE FEED, never a
 * document-collection slug — reconciling the historical naming collision with get_documents.
 *
 * `campus` is the second such alias: it and `project` name the one facet, because a caller thinks
 * in whichever word the site uses ("the Cosler Farm campus", "Project Klondike").
 */
function parseFilters(p: SearchCorpusParams): CorpusFilters {
  const f = (p.filters ?? {}) as Record<string, unknown>;
  return {
    site: asStr(f.site) ?? asStr(p.site),
    feed: asStr(f.feed) ?? asStr(f.collection) ?? asStr(p.collection),
    source_kind: asStr(f.source_kind),
    verified: asBool(f.verified),
    date_from: asStr(f.date_from),
    date_to: asStr(f.date_to),
    confidence: asStr(f.confidence),
    county: asStr(f.county),
    agency: asStr(f.agency),
    permit_number: asStr(f.permit_number),
    document_type: asStr(f.document_type),
    entity: asStr(f.entity),
    project: asStr(f.project) ?? asStr(f.campus),
  };
}

function roundScore(score: number): number {
  return Math.round(score * 1000) / 1000;
}

/** Estimate the token cost of pulling this unit's full text (what `full` mode returns). */
function estimateFullTokens(u: AskUnit): number {
  return Math.ceil(((u.title?.length ?? 0) + u.text.length + 1) / AVG_CHARS_PER_TOKEN);
}

/**
 * A `maxTokens`-sized excerpt of `text`. With `terms`, the window is centered on the
 * earliest matched term (query-focused); with `terms = []`, it's a leading head preview.
 * Returns the whole text when it already fits. Ellipses mark truncated ends.
 */
function snippetOf(text: string, terms: string[], maxTokens: number): string {
  const maxChars = maxTokens * AVG_CHARS_PER_TOKEN;
  if (text.length <= maxChars) return text;

  const lower = text.toLowerCase();
  let pos = -1;
  for (const t of terms) {
    const i = lower.indexOf(t);
    if (i >= 0 && (pos < 0 || i < pos)) pos = i;
  }
  // No matched term (title-only hit, or head preview) → excerpt from the start.
  if (pos < 0) return `${text.slice(0, maxChars).trimEnd()}…`;

  let start = Math.max(0, pos - Math.floor(maxChars / 2));
  const end = Math.min(text.length, start + maxChars);
  start = Math.max(0, end - maxChars); // pull the window back if we ran past the tail
  return `${start > 0 ? "…" : ""}${text.slice(start, end).trim()}${end < text.length ? "…" : ""}`;
}

/**
 * The hit's provenance as the uniform citation object (#1584).
 *
 * `document_id` is the unit's joined source document (`doc_rel`) — the addressable thing to pass
 * back to `get_document` / `search_passages` — while `source` stays the citable artifact the
 * ask-index lifted off the item's `Citation` (usually the reviewed extraction, not the PDF).
 * No `quote`: a search_corpus snippet is a window over the record's flattened FIELDS, not source
 * prose, and the citation contract reserves `quote` for verbatim text (see mcpCitation).
 */
function hitCitation(u: AskUnit, requestUrl: string): McpCitation {
  return buildCitation(
    {
      document_id: u.doc_rel,
      source: u.source,
      source_kind: u.source_kind,
      page: u.page,
      pages: u.pages,
      source_url: u.url,
      confidence: u.confidence,
      verified: u.verified,
    },
    requestUrl,
  );
}

function compactCard(
  h: Hit,
  terms: string[],
  snippetTokens: number,
  topScore: number,
  requestUrl: string,
): CompactHit {
  const u = h.unit;
  const verdict = tierHit(u.feed, u.source_kind, h.score, topScore);
  return {
    id: u.id,
    title: u.title,
    site: u.site ?? null,
    collection: u.feed,
    source_kind: u.source_kind ?? null,
    date: u.date ?? null,
    score: roundScore(h.score),
    snippet: snippetOf(u.text, terms, snippetTokens),
    estimated_tokens: estimateFullTokens(u),
    verified: u.verified ?? false,
    tier: verdict.tier,
    tier_reason: verdict.reason,
    citation: hitCitation(u, requestUrl),
  };
}

function fullHit(h: Hit, topScore: number, requestUrl: string): FullHit {
  const u = h.unit;
  const verdict = tierHit(u.feed, u.source_kind, h.score, topScore);
  return {
    id: u.id,
    feed: u.feed,
    title: u.title,
    text: u.text,
    url: u.url,
    source: u.source ?? null,
    page: u.page ?? null,
    source_kind: u.source_kind ?? null,
    confidence: u.confidence ?? null,
    verified: u.verified ?? false,
    score: roundScore(h.score),
    tier: verdict.tier,
    tier_reason: verdict.reason,
    citation: hitCitation(u, requestUrl),
  };
}

/** `topScore` is the pool's top score (deduped[0]) so the relevance band that feeds a hit's
 * tier is stable across cursor pages. `ids_only` stays a bare id + score list — no tier, and no
 * citation: it is the candidate-list mode, and a caller that wants to cite asks for compact. */
function renderHits(
  hits: Hit[],
  query: string,
  mode: ResponseMode,
  snippetTokens: number,
  topScore: number,
  requestUrl: string,
): SearchHit[] {
  switch (mode) {
    case "ids_only":
      return hits.map((h) => ({ id: h.unit.id, score: roundScore(h.score) }));
    case "full":
      return hits.map((h) => fullHit(h, topScore, requestUrl));
    case "snippets":
      return hits.map((h) => compactCard(h, tokenize(query), snippetTokens, topScore, requestUrl));
    default: // compact — short generic head preview, no query windowing
      return hits.map((h) => compactCard(h, [], COMPACT_SNIPPET_TOKENS, topScore, requestUrl));
  }
}

/**
 * Per-result shrink: trim whichever heavy field a hit carries down to the room left under
 * `capTokens` after the hit's provenance metadata. The field budget is the *remaining* room
 * (floored at 0, so metadata that already exhausts the cap collapses the field to a marker
 * rather than adding tokens back on top). Provenance (id/source/page/…) is never dropped, so
 * a hit whose metadata alone exceeds `capTokens` stays marginally over — the evidentiary
 * contract requires the citation, and the response is still hard-bounded by `max_tokens`.
 */
function shrinkSearchHit(item: SearchHit, capTokens: number): SearchHit {
  if ("text" in item) {
    const budget = Math.max(0, capTokens - estimateTokens({ ...item, text: "" }));
    return { ...item, text: truncateToTokens(item.text, budget) };
  }
  if ("snippet" in item) {
    const budget = Math.max(0, capTokens - estimateTokens({ ...item, snippet: "" }));
    return { ...item, snippet: truncateToTokens(item.snippet, budget) };
  }
  return item; // ids_only — nothing to shrink
}

const EMPTY: Governed<SearchHit> = { results: [], token_estimate: 0, truncated: false, next_cursor: null };

export async function handleSearchCorpus(
  params: unknown,
  requestUrl: string,
  env: HybridRetrievalEnv = {},
): Promise<Array<{ type: "text"; text: string }>> {
  const p = (params ?? {}) as SearchCorpusParams;
  const query = typeof p.query === "string" ? p.query.trim() : "";
  if (!query) return governedContent(EMPTY);

  const intent = parseIntent(p.intent);
  const preset = intent ? INTENTS[intent] : null;
  const mode = parseMode(p.response_mode) ?? preset?.search.responseMode ?? DEFAULT_MODE;
  const snippetTokens =
    parseSnippetTokens(p.snippet_tokens) ?? preset?.search.snippetTokens ?? DEFAULT_SNIPPET_TOKENS;

  // `limit` is the legacy page-size knob; `max_results` supersedes it under governance.
  const knobs = resolveKnobs({
    intent: p.intent,
    max_results: p.max_results ?? p.limit,
    max_tokens: p.max_tokens,
    max_tokens_per_result: p.max_tokens_per_result,
  });
  const offset = decodeCursorOffset(p.cursor);

  const units0 = await loadAskIndex(requestUrl);

  // Structured facet filters (#1582): narrow the pool to units matching every present facet
  // over indexed fields (site/feed/source_kind/verified/date/confidence) before ranking, so
  // unrelated feeds and records don't crowd the results. Legacy top-level site/collection are
  // folded in by parseFilters. Site stays a special case (tagged-index guard) inside the helper.
  const units = applyCorpusFilters(units0, parseFilters(p));

  // Rank the whole (filtered) matched pool at a page-independent depth, then slice the
  // cursor window. Ranking the full pool — not just `offset + maxResults` deep — keeps the
  // hybrid order stable across cursor pages: RRF's last-place penalty depends on each input
  // list's length, so truncating the lists to the page depth would let single-list hits
  // drift between pages. The corpus is small (low hundreds of units) so full-depth ranking is
  // cheap, and only the sliced window (`maxResults + 1`, one look-ahead) is rendered, so
  // `full` mode still never materializes hits we'll drop.
  const prepared = prepare(units);
  const pool = await hybridSearch(prepared, query, prepared.n, env, requestUrl);
  // Collapse a filing's version/duplicate cluster to its canonical member (#1590), retaining a
  // superseded version only when it carries a query-relevant term the canonical lacks. Runs over the
  // full ranked pool (before the cursor slice) so the canonical is chosen across every page and
  // pagination stays stable. Default-on; `deduplicate:"none"` reproduces the raw pool.
  const deduplicate = parseDeduplicate(p.deduplicate);
  const versionPolicy = parseVersionPolicy(p.version_policy);
  // Only load the version map when dedup will actually run — `none`/`all` are no-ops, so skip the
  // fetch entirely. Otherwise fail open: an unloadable map degrades dedup to a no-op, never a hard
  // failure (it's a refinement, not an essential like the ask-index).
  const versions: Map<string, VersionInfo> =
    deduplicate === "none" || versionPolicy === "all" ? new Map() : await loadDocVersionsSafe(requestUrl);
  const deduped = dedupeByCluster(pool, {
    deduplicate,
    versionPolicy,
    query,
    versions,
    access: { relOf: (h) => h.unit.doc_rel, textOf: (h) => `${h.unit.title} ${h.unit.text}` },
  });
  // Tier each hit's relevance band against the pool's top score (deduped is score-sorted, so
  // deduped[0] is the strongest match across every page) — not the page-local top, which would
  // spuriously promote page 2's leader to `direct` (#1591).
  const topScore = deduped.length > 0 ? deduped[0].score : 0;
  const window = renderHits(
    deduped.slice(offset, offset + knobs.maxResults + 1),
    query,
    mode,
    snippetTokens,
    topScore,
    requestUrl,
  );
  const governed = govern(window, { knobs, baseOffset: offset, shrink: shrinkSearchHit });

  return governedContent(governed);
}
