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

import { loadAskIndex } from "../askIndexLoad";
import type { AskUnit, Hit } from "../retrieval";
import { prepare, search, tokenize } from "../retrieval";

const MAX_LIMIT = 30;
const DEFAULT_LIMIT = 10;

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

function parseMode(v: unknown): ResponseMode {
  return typeof v === "string" && (RESPONSE_MODES as readonly string[]).includes(v)
    ? (v as ResponseMode)
    : DEFAULT_MODE;
}

function parseSnippetTokens(v: unknown): number {
  const n = typeof v === "number" && Number.isFinite(v) ? Math.floor(v) : DEFAULT_SNIPPET_TOKENS;
  return Math.min(Math.max(MIN_SNIPPET_TOKENS, n), MAX_SNIPPET_TOKENS);
}

function roundScore(score: number): number {
  return Math.round(score * 1000) / 1000;
}

/** Estimate the token cost of pulling this unit's full text (what `full` mode returns). */
function estimateTokens(u: AskUnit): number {
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
    estimated_tokens: estimateTokens(u),
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

function renderHits(
  hits: Hit[],
  query: string,
  mode: ResponseMode,
  snippetTokens: number,
): IdsOnlyHit[] | CompactHit[] | FullHit[] {
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

export async function handleSearchCorpus(
  params: unknown,
  requestUrl: string,
): Promise<Array<{ type: "text"; text: string }>> {
  const p = (params ?? {}) as SearchCorpusParams;
  const query = typeof p.query === "string" ? p.query.trim() : "";
  if (!query) {
    return [{ type: "text", text: JSON.stringify([]) }];
  }

  const mode = parseMode(p.response_mode);
  const snippetTokens = parseSnippetTokens(p.snippet_tokens);
  const rawLimit = typeof p.limit === "number" ? p.limit : DEFAULT_LIMIT;
  const limit = Math.min(Math.max(1, Math.floor(rawLimit)), MAX_LIMIT);

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

  const hits = search(prepare(units), query, limit);
  const results = renderHits(hits, query, mode, snippetTokens);

  return [{ type: "text", text: JSON.stringify(results) }];
}
