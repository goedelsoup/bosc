// Response-size governance for the MCP tools (#1581).
//
// Every tool response is bounded by an explicit budget and reports its own cost. The
// caller sets three knobs — `max_results` (page size), `max_tokens` (whole-response
// ceiling), `max_tokens_per_result` (per-item ceiling) — or names an `intent` that seeds
// sensible defaults for them; an explicit knob always wins over the preset.
//
// `govern()` enforces the budget over an ordered window of already-rendered items by, in
// order: shrinking any over-cap item (drop low-priority metadata / shorten snippets),
// stopping before the token ceiling, and stopping at the page-size cap — then handing back
// an opaque `next_cursor` so the caller can resume. It always returns at least one item so
// pagination can never stall. Cursors carry an absolute offset into the tool's ordered
// result list; they survive a change of page size but not a change of query/filters.

// Rough byte→token heuristic — matches searchCorpus's estimator. Good enough for
// budgeting, not billing.
export const AVG_CHARS_PER_TOKEN = 4;

/** Estimate the token cost of a value from its JSON serialization (strings measured directly). */
export function estimateTokens(value: unknown): number {
  const s = typeof value === "string" ? value : JSON.stringify(value ?? null);
  return Math.ceil(s.length / AVG_CHARS_PER_TOKEN);
}

/** Truncate `text` to about `capTokens` tokens, marking the cut with an ellipsis. */
export function truncateToTokens(text: string, capTokens: number): string {
  const maxChars = Math.max(1, capTokens) * AVG_CHARS_PER_TOKEN;
  return text.length <= maxChars ? text : `${text.slice(0, maxChars).trimEnd()}…`;
}

/**
 * Drop `lowPriorityKeys` (in order) from a shallow clone until it fits `capTokens`.
 * The generic per-result shrink for flat objects — used by the timeline/entity readers to
 * shed their heaviest optional prose without touching provenance fields.
 */
export function dropKeysUntilUnderCap<T extends object>(
  item: T,
  lowPriorityKeys: readonly string[],
  capTokens: number,
): T {
  if (estimateTokens(item) <= capTokens) return item;
  const clone = { ...item } as Record<string, unknown>;
  for (const k of lowPriorityKeys) {
    if (estimateTokens(clone) <= capTokens) break;
    delete clone[k];
  }
  return clone as unknown as T;
}

// --- Budget knobs + intent presets -------------------------------------------------

export interface BudgetKnobs {
  /** Page-size cap — the most results returned in one response. */
  maxResults: number;
  /** Whole-response token ceiling. */
  maxTokens: number;
  /** Per-result token ceiling — an item over this is shrunk before it counts. */
  maxTokensPerResult: number;
}

/** search_corpus-only hints an intent can seed (the generic knobs cover every tool). */
export interface SearchHints {
  responseMode: "ids_only" | "compact" | "snippets" | "full";
  snippetTokens: number;
}

export interface IntentPreset {
  knobs: BudgetKnobs;
  search: SearchHints;
}

export type Intent =
  | "fact_lookup"
  | "evidence_lookup"
  | "timeline_reconstruction"
  | "entity_research"
  | "document_discovery"
  | "cross_document_synthesis"
  | "exhaustive_audit";

/** Neutral defaults when no intent is named and no knob is set. */
export const DEFAULT_KNOBS: BudgetKnobs = {
  maxResults: 10,
  maxTokens: 8_000,
  maxTokensPerResult: 2_000,
};

// Clamp bounds — a caller can't page past the corpus or blow the daily budget in one call.
const MAX_RESULTS_CEIL = 100;
const MIN_TOKENS = 100;
const MAX_TOKENS_CEIL = 40_000;
const MIN_TOKENS_PER_RESULT = 50;
const MAX_TOKENS_PER_RESULT_CEIL = 30_000;

/**
 * `intent` sugar — each preset only seeds defaults for the knobs above (and search shape);
 * it is not a separate retrieval engine. From precise (`fact_lookup`) to widest
 * (`exhaustive_audit`).
 */
export const INTENTS: Record<Intent, IntentPreset> = {
  fact_lookup: {
    knobs: { maxResults: 3, maxTokens: 1_500, maxTokensPerResult: 500 },
    search: { responseMode: "compact", snippetTokens: 40 },
  },
  evidence_lookup: {
    knobs: { maxResults: 6, maxTokens: 4_000, maxTokensPerResult: 800 },
    search: { responseMode: "snippets", snippetTokens: 250 },
  },
  timeline_reconstruction: {
    knobs: { maxResults: 40, maxTokens: 8_000, maxTokensPerResult: 400 },
    search: { responseMode: "compact", snippetTokens: 60 },
  },
  entity_research: {
    knobs: { maxResults: 25, maxTokens: 8_000, maxTokensPerResult: 600 },
    search: { responseMode: "compact", snippetTokens: 60 },
  },
  document_discovery: {
    knobs: { maxResults: 30, maxTokens: 6_000, maxTokensPerResult: 400 },
    search: { responseMode: "compact", snippetTokens: 60 },
  },
  cross_document_synthesis: {
    knobs: { maxResults: 15, maxTokens: 16_000, maxTokensPerResult: 2_000 },
    search: { responseMode: "snippets", snippetTokens: 400 },
  },
  exhaustive_audit: {
    knobs: { maxResults: 50, maxTokens: MAX_TOKENS_CEIL, maxTokensPerResult: 24_000 },
    search: { responseMode: "full", snippetTokens: 250 },
  },
};

export const INTENT_NAMES = Object.keys(INTENTS) as readonly Intent[];

export function parseIntent(v: unknown): Intent | null {
  return typeof v === "string" && v in INTENTS ? (v as Intent) : null;
}

function clampInt(v: unknown, fallback: number, lo: number, hi: number): number {
  if (typeof v !== "number" || !Number.isFinite(v)) return fallback;
  return Math.min(Math.max(lo, Math.floor(v)), hi);
}

interface KnobParams {
  intent?: unknown;
  max_results?: unknown;
  max_tokens?: unknown;
  max_tokens_per_result?: unknown;
}

/** Resolve the effective knobs: intent preset (or neutral default) then explicit overrides, clamped. */
export function resolveKnobs(raw: KnobParams): BudgetKnobs {
  const intent = parseIntent(raw.intent);
  const base = intent ? INTENTS[intent].knobs : DEFAULT_KNOBS;
  return {
    maxResults: clampInt(raw.max_results, base.maxResults, 1, MAX_RESULTS_CEIL),
    maxTokens: clampInt(raw.max_tokens, base.maxTokens, MIN_TOKENS, MAX_TOKENS_CEIL),
    maxTokensPerResult: clampInt(
      raw.max_tokens_per_result,
      base.maxTokensPerResult,
      MIN_TOKENS_PER_RESULT,
      MAX_TOKENS_PER_RESULT_CEIL,
    ),
  };
}

// --- Cursor (opaque absolute offset) ----------------------------------------------

function b64urlEncode(s: string): string {
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlDecode(s: string): string {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  return atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
}

/** Encode an absolute result offset as an opaque continuation cursor. */
export function encodeCursor(offset: number): string {
  return b64urlEncode(JSON.stringify({ o: offset }));
}

/** Decode a cursor to its offset; anything unparseable or out-of-range reads as offset 0. */
export function decodeCursorOffset(v: unknown): number {
  if (typeof v !== "string" || !v) return 0;
  try {
    const d = JSON.parse(b64urlDecode(v)) as { o?: unknown };
    return typeof d.o === "number" && Number.isInteger(d.o) && d.o >= 0 ? d.o : 0;
  } catch {
    return 0;
  }
}

// --- The governed envelope + paginator --------------------------------------------

/** The uniform envelope every governed tool response carries. */
export interface Governed<T> {
  results: T[];
  /** Estimated token cost of the returned `results` array. */
  token_estimate: number;
  /** True when results were withheld for budget — pass `next_cursor` to fetch the rest. */
  truncated: boolean;
  /** Opaque cursor for the next page, or null when the result set is exhausted. */
  next_cursor: string | null;
}

export interface GovernInput<T> {
  knobs: BudgetKnobs;
  /** Absolute index of `window[0]` in the tool's full ordered list (from the caller's cursor). */
  baseOffset?: number;
  /** Optional per-result shrink applied when an item exceeds `maxTokensPerResult`. */
  shrink?: (item: T, capTokens: number) => T;
}

/**
 * Fit `window` (the tool's ordered results from `baseOffset` onward, plus one look-ahead
 * item) inside the budget. Include items until the page-size cap or the token ceiling would
 * be crossed — shrinking any single over-cap item first, and always keeping the first item
 * so a huge lone result can never stall pagination. `next_cursor` points at the first item
 * left out; `truncated` mirrors its presence.
 */
export function govern<T>(window: T[], input: GovernInput<T>): Governed<T> {
  const { knobs, baseOffset = 0, shrink } = input;
  const results: T[] = [];
  let tokens = 0;
  let i = 0;
  for (; i < window.length; i++) {
    if (results.length >= knobs.maxResults) break;
    let item = window[i];
    let cost = estimateTokens(item);
    if (shrink && cost > knobs.maxTokensPerResult) {
      item = shrink(item, knobs.maxTokensPerResult);
      cost = estimateTokens(item);
    }
    // Stop before the token ceiling — but never return an empty page (forward progress).
    if (results.length > 0 && tokens + cost > knobs.maxTokens) break;
    results.push(item);
    tokens += cost;
  }
  const more = i < window.length;
  return {
    results,
    token_estimate: estimateTokens(results),
    truncated: more,
    next_cursor: more ? encodeCursor(baseOffset + i) : null,
  };
}

/** Wrap a governed envelope as the single MCP text content element a tool returns. */
export function governedContent<T>(governed: Governed<T>): Array<{ type: "text"; text: string }> {
  return [{ type: "text", text: JSON.stringify(governed) }];
}
