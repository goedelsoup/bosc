// Hybrid retrieval orchestration: BM25 keyword ranking fused with vector (semantic)
// similarity via Reciprocal Rank Fusion (#329, #1586).
//
// The scoring kernel (`search`, `vectorSearch`, `rrf`) lives in `retrieval.ts` and is a
// pure, dependency-free module. This layer wires that kernel to the Workers runtime: it
// embeds the query with the Workers AI binding and loads the precomputed ask-embeddings
// asset over `fetch`. Both `/api/ask` and the `search_corpus` MCP tool call it so the two
// share one degradation contract and one embedding-model id.
//
// Graceful degradation is the invariant: the vector path is strictly additive. Any missing
// piece — no AI binding, no committed embeddings feed, an empty query vector, or a runtime
// error embedding the query — falls back to BM25-only ranking, never a failure.

import { loadAskEmbeddings } from "./askEmbeddingsLoad";
import { type Hit, type PreparedIndex, rrf, search, vectorSearch } from "./retrieval";

// Workers AI text-embedding model — the same one that produced the committed
// ask-embeddings index at build time, so query and corpus vectors share a space.
export const EMBED_MODEL = "@cf/sentence-transformers/all-minilm-l6-v2";

/** The Workers AI binding surface hybrid retrieval needs (query embedding only). */
export interface AiEmbeddingBinding {
  run(model: string, input: { text: string[] }): Promise<{ data: number[][] }>;
}

/** The env slice hybrid retrieval reads — both optional, so it degrades to BM25-only. */
export interface HybridRetrievalEnv {
  /** Cloudflare Workers AI binding. Absent ⇒ BM25-only keyword retrieval. */
  AI?: AiEmbeddingBinding;
  /** Optional override for the ask-embeddings asset URL (e.g. CDN-hosted). */
  ASK_EMBEDDINGS_URL?: string;
}

/**
 * Rank `prepared` against `query`, returning the top `k` hits. Baseline is BM25; when the
 * AI binding and the precomputed ask-embeddings are both available, the query is embedded
 * and the vector-cosine ranking is fused with BM25 via Reciprocal Rank Fusion. Degrades to
 * BM25-only — silently, never throwing — when any part of the vector path is unavailable.
 *
 * `requestUrl` locates the same-origin `/ask-embeddings.json` asset (overridable via
 * `env.ASK_EMBEDDINGS_URL`). Vector similarity is scored over `prepared.units`, so any
 * site/collection filtering the caller applied before `prepare` carries through both paths.
 */
export async function hybridSearch(
  prepared: PreparedIndex,
  query: string,
  k: number,
  env: HybridRetrievalEnv,
  requestUrl: string,
): Promise<Hit[]> {
  const bm25Hits = search(prepared, query, k);
  if (!env.AI) return bm25Hits;
  try {
    const embeddings = await loadAskEmbeddings(requestUrl, env.ASK_EMBEDDINGS_URL);
    if (!embeddings) return bm25Hits; // no committed embeddings feed → keyword-only
    const aiRes = await env.AI.run(EMBED_MODEL, { text: [query] });
    const qv = aiRes.data[0];
    if (!qv?.length) return bm25Hits; // empty embedding → keyword-only
    const vecHits = vectorSearch(prepared.units, embeddings, qv, k);
    return rrf(bm25Hits, vecHits, k);
  } catch (e) {
    // Vector path failed — log and fall through to the BM25-only ranking.
    console.warn("hybrid retrieval failed, using BM25:", String(e));
    return bm25Hits;
  }
}
