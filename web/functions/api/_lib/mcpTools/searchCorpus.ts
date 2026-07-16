// search_corpus MCP tool handler (#913).
// BM25 retrieval over the ask-index, with optional site and collection filters.
// Every result carries full provenance; clients must cite source + page, and
// must not paraphrase beyond what the source text says ([verified]/[inference] discipline).
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

import { loadAskIndex } from "../askIndexLoad";
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
import type { AskUnit, Hit } from "../retrieval";
import { prepare, search, tokenize } from "../retrieval";

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
  site?: unknown;
  collection?: unknown;
  limit?: unknown;
  response_mode?: unknown;
  snippet_tokens?: unknown;
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

function compactCard(h: Hit, terms: string[], snippetTokens: number): CompactHit {
  const u = h.unit;
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
  };
}

function fullHit(h: Hit): FullHit {
  const u = h.unit;
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
  };
}

function renderHits(hits: Hit[], query: string, mode: ResponseMode, snippetTokens: number): SearchHit[] {
  switch (mode) {
    case "ids_only":
      return hits.map((h) => ({ id: h.unit.id, score: roundScore(h.score) }));
    case "full":
      return hits.map(fullHit);
    case "snippets":
      return hits.map((h) => compactCard(h, tokenize(query), snippetTokens));
    default: // compact — short generic head preview, no query windowing
      return hits.map((h) => compactCard(h, [], COMPACT_SNIPPET_TOKENS));
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

  let units = await loadAskIndex(requestUrl);

  // Site filter: if any units carry a site tag (i.e. this is a tagged index build),
  // filter strictly — `!u.site` would silently leak cross-site results in a mixed
  // index. If NO units have a site tag (legacy index), skip filtering entirely.
  const siteFilter = typeof p.site === "string" && p.site ? p.site : null;
  if (siteFilter) {
    const hasTaggedUnits = units.some((u) => typeof u.site === "string" && u.site.length > 0);
    if (hasTaggedUnits) {
      units = units.filter((u) => u.site === siteFilter);
    }
  }

  // Collection filter maps to the `feed` field (e.g. "timeline", "entities", "records").
  const collectionFilter = typeof p.collection === "string" && p.collection ? p.collection : null;
  if (collectionFilter) {
    units = units.filter((u) => u.feed === collectionFilter);
  }

  // Rank just deep enough to serve this page and detect a next one; the corpus is small
  // (low hundreds of units) so ranking cost is linear and cheap. Render only the window
  // from the cursor offset onward so `full` mode never materializes hits we'll drop.
  const pool = search(prepare(units), query, offset + knobs.maxResults + 1);
  const window = renderHits(pool.slice(offset), query, mode, snippetTokens);
  const governed = govern(window, { knobs, baseOffset: offset, shrink: shrinkSearchHit });

  return governedContent(governed);
}
