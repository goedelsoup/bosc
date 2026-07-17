import type { APIRoute } from "astro";
import { hasFeed, loadFeed } from "@watermark/core/bundle";
import type { EmbeddingEntry } from "@watermark/functions/api/_lib/retrieval";

// Static endpoint: emits `/feeds/passage-embeddings.json` at build time (#1589) — the
// all-MiniLM-L6-v2 vector companion to the passages index (the passage-level peer of
// `/ask-embeddings.json`). Fetched by search_passages for the hybrid BM25 + vector rank.
// Empty for offline / `--no-embeddings` builds, in which case the tool degrades to BM25-only.
export const GET: APIRoute = () =>
  new Response(
    JSON.stringify(hasFeed("passage-embeddings") ? loadFeed<EmbeddingEntry[]>("passage-embeddings") : []),
    { headers: { "content-type": "application/json; charset=utf-8" } },
  );
