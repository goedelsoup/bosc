// search_passages MCP tool handler (#1589, epic #1579 Phase 3).
// Page-level excerpt retrieval over the published source PDFs: returns the exact supporting
// page(s) with a citation, not a whole extracted record — the deeper peer of search_corpus
// (which finds WHICH item is relevant; this finds WHICH PAGE says it). Hybrid BM25 + vector
// (all-MiniLM-L6-v2) ranking via the shared retrieval kernel, degrading to BM25-only when the
// Workers AI binding or the committed passage-embeddings feed is unavailable. The `passages`
// feed only carries published documents (the default-deny publish allowlist, #280), so this
// never surfaces non-published source text.
//
// Response-size governance (#1581): rendered excerpts are fitted to an explicit budget
// (max_results / max_tokens / max_tokens_per_result, or an `intent` preset) and returned in the
// uniform `{ results, token_estimate, truncated, next_cursor }` envelope; an over-cap excerpt is
// trimmed to the room left after its citation, and the cursor pages through the ranked pool.

import { type HybridRetrievalEnv, hybridSearch } from "../hybridRetrieve";
import {
  type Governed,
  decodeCursorOffset,
  estimateTokens,
  govern,
  governedContent,
  resolveKnobs,
  truncateToTokens,
} from "../mcpGovern";
import { type PassageRow, loadPassages } from "../passagesLoad";
import type { AskUnit } from "../retrieval";
import { prepare } from "../retrieval";

interface SearchPassagesParams {
  query?: unknown;
  document_ids?: unknown;
  // Governance knobs (#1581) — resolved via mcpGovern.
  intent?: unknown;
  max_results?: unknown;
  max_tokens?: unknown;
  max_tokens_per_result?: unknown;
  cursor?: unknown;
}

/** A page-cited passage hit — the excerpt plus its provenance and rank score. */
interface PassageHit {
  id: string;
  document_id: string;
  collection: string;
  title: string;
  page: number;
  section: string | null;
  text: string;
  score: number;
}

function roundScore(score: number): number {
  return Math.round(score * 1000) / 1000;
}

/** Project a passage row into a retrieval unit for the BM25/vector kernel (id/title/text only). */
function toUnit(p: PassageRow): AskUnit {
  return { id: p.id, feed: "passages", title: p.title, url: "", text: p.text };
}

/** The optional document_ids filter as a set of rels, or null when not supplied / empty. */
function parseDocumentIds(v: unknown): Set<string> | null {
  if (!Array.isArray(v)) return null;
  const ids = v.filter((x): x is string => typeof x === "string" && x.length > 0);
  return ids.length > 0 ? new Set(ids) : null;
}

/**
 * Per-result shrink: trim the excerpt to the room left under `capTokens` after the hit's citation
 * metadata (document_id/page/…), which is never dropped — the evidentiary contract requires the
 * page cite even when the excerpt collapses to a marker.
 */
function shrinkPassageHit(item: PassageHit, capTokens: number): PassageHit {
  const budget = Math.max(0, capTokens - estimateTokens({ ...item, text: "" }));
  return { ...item, text: truncateToTokens(item.text, budget) };
}

const EMPTY: Governed<PassageHit> = {
  results: [],
  token_estimate: 0,
  truncated: false,
  next_cursor: null,
};

export async function handleSearchPassages(
  params: unknown,
  requestUrl: string,
  env: HybridRetrievalEnv = {},
): Promise<Array<{ type: "text"; text: string }>> {
  const p = (params ?? {}) as SearchPassagesParams;
  const query = typeof p.query === "string" ? p.query.trim() : "";
  if (!query) return governedContent(EMPTY);

  const knobs = resolveKnobs({
    intent: p.intent,
    max_results: p.max_results,
    max_tokens: p.max_tokens,
    max_tokens_per_result: p.max_tokens_per_result,
  });
  const offset = decodeCursorOffset(p.cursor);

  let rows = await loadPassages(requestUrl);
  const docFilter = parseDocumentIds(p.document_ids);
  if (docFilter) rows = rows.filter((r) => docFilter.has(r.document_id));
  if (rows.length === 0) return governedContent(EMPTY);

  // Rank the whole (filtered) pool at full depth so the hybrid RRF order is stable across cursor
  // pages (same rationale as search_corpus), then render only the sliced window (+1 look-ahead).
  const byId = new Map(rows.map((r) => [r.id, r]));
  const prepared = prepare(rows.map(toUnit));
  const embeddingsUrl = new URL("/feeds/passage-embeddings.json", requestUrl).toString();
  const pool = await hybridSearch(prepared, query, prepared.n, env, requestUrl, embeddingsUrl);

  const window: PassageHit[] = [];
  for (const h of pool.slice(offset, offset + knobs.maxResults + 1)) {
    const row = byId.get(h.unit.id);
    if (!row) continue; // unreachable — every unit came from a row — but keeps the map lookup total
    window.push({
      id: row.id,
      document_id: row.document_id,
      collection: row.collection,
      title: row.title,
      page: row.page,
      section: row.section,
      text: row.text,
      score: roundScore(h.score),
    });
  }
  const governed = govern(window, { knobs, baseOffset: offset, shrink: shrinkPassageHit });
  return governedContent(governed);
}
