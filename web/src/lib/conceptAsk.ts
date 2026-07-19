/**
 * Client-side lexical retrieval for the wiki "ask this concept" widget (#1575, epic #1560 D2).
 *
 * A concept page ships its corpus neighborhood (`neighborhoodFor`, `@watermark/core`) as a small set
 * of `corpus-nodes` rows; this wires that subset to the **same** pure BM25 kernel the server `/ask`
 * uses (`@watermark/functions/api/_lib/retrieval`), so a typed question ranks the neighborhood
 * entirely in the browser — offline, no server, no generation (the D3 spike's verdict, #1576).
 *
 * Lives site-side (not in `@watermark/core`) because the dependency order is
 * `core → functions → site`: only the site tier may import the functions BM25 kernel.
 */

import type { CorpusRetrievalNodeItem } from "@watermark/core/feeds";
import { type AskUnit, prepare, search } from "@watermark/functions/api/_lib/retrieval";

/** A neighborhood node with the page-computed link (concept nodes deep-link; others are null). */
export interface NeighborNode extends CorpusRetrievalNodeItem {
  href?: string | null;
}

/** Adapt a corpus node to the BM25 kernel's `AskUnit` shape — `label` is the weighted title. */
function toAskUnit(node: NeighborNode): AskUnit {
  return { id: node.id, feed: node.kind, title: node.label, url: node.href ?? "", text: node.text };
}

/**
 * Build a retriever over a concept's neighborhood: `(query) => ranked nodes`. The BM25 index is
 * prepared once; each query is a linear scan over the (few dozen) neighborhood nodes — instant.
 * An empty/whitespace query returns `[]` (the widget shows the un-ranked neighborhood by default).
 */
export function makeRetriever(nodes: NeighborNode[]): (query: string, k?: number) => NeighborNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const prepared = prepare(nodes.map(toAskUnit));
  return (query: string, k = 8): NeighborNode[] => {
    if (!query.trim()) return [];
    return search(prepared, query, k)
      .map((hit) => byId.get(hit.unit.id))
      .filter((n): n is NeighborNode => Boolean(n));
  };
}
