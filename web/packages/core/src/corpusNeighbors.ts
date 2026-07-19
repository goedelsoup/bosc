/**
 * Scope a concept to its corpus neighborhood — the candidate set the wiki "ask this concept"
 * affordance retrieves over (#1575, epic #1560 workstream D2).
 *
 * The `corpus-nodes` feed (`bosc.site.corpus_nodes`) ships every yidam mirror node with its
 * searchable text + evidence tag + curated 1-hop adjacency. A concept's neighborhood is assembled
 * from two signals, because the mirror's concept nodes only link to *other concepts* — the graph
 * alone never reaches the evidence:
 *
 *   1. **Curated graph neighbors** — the concept's `related` links (high-signal, hand-curated).
 *   2. **Lexical mentions** — every node whose searchable text *names* the concept (its title or a
 *      specific alias). This is what pulls in the permits, records, entities, and open questions
 *      that the concept actually sits in — the same whole-phrase, specificity-floored matching the
 *      wiki backlink graph uses (`wiki.ts`).
 *
 * The result is a small candidate set (self + neighbors + mentions) the caller ranks at query time
 * with the shared BM25 kernel — all client-side, offline, no server (the D3 spike's verdict, #1576).
 * Pure and DOM-free; the retrieval wiring that imports the BM25 kernel lives site-side.
 */

import type { CorpusRetrievalNodeItem } from "./feeds";
import { norm } from "./wiki";

/** Default cap on a neighborhood's candidate set — a bound, not a ranking (BM25 ranks at query). */
export const DEFAULT_NEIGHBORHOOD_LIMIT = 60;

/** The concept the widget scopes to — the fields lifted from its `ConceptItem`. */
export interface ConceptRef {
  slug: string;
  title: string;
  aliases?: string[];
}

/**
 * Whether a name is specific enough to raise a mention. A very short single token (`pH`, a
 * two-letter initialism) matches noise, so only multi-word names or single tokens of ≥4 chars
 * qualify — the same floor `wiki.ts` applies to prose backlinks.
 */
function specific(name: string): boolean {
  const n = norm(name);
  return n.length > 0 && (n.includes(" ") || n.length >= 4);
}

/** Whether `text` names any of the (already-normalized) `terms` as a whole phrase. */
function mentionsAny(text: string, terms: string[]): boolean {
  const hay = ` ${norm(text)} `;
  return terms.some((t) => hay.includes(` ${t} `));
}

/** The concept's own node in the `corpus-nodes` feed (matched by slug↔`ref`), or null. */
export function conceptNode(slug: string, nodes: CorpusRetrievalNodeItem[]): CorpusRetrievalNodeItem | null {
  return nodes.find((n) => n.kind === "concept" && n.ref === slug) ?? null;
}

/**
 * The corpus neighborhood of a concept — the candidate set for scoped retrieval, in a stable,
 * deterministic order: the concept's own node first (its definition answers "what is X"), then its
 * curated graph neighbors, then the nodes that mention it, capped at `limit`. Deduplicated by id.
 */
export function neighborhoodFor(
  concept: ConceptRef,
  nodes: CorpusRetrievalNodeItem[],
  opts: { limit?: number } = {},
): CorpusRetrievalNodeItem[] {
  const limit = opts.limit ?? DEFAULT_NEIGHBORHOOD_LIMIT;
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const self = conceptNode(concept.slug, nodes);

  const ordered: CorpusRetrievalNodeItem[] = [];
  const seen = new Set<string>();
  const add = (node: CorpusRetrievalNodeItem | null | undefined): void => {
    if (node && !seen.has(node.id)) {
      seen.add(node.id);
      ordered.push(node);
    }
  };

  add(self);
  // Curated graph neighbors — sorted for determinism (the feed already sorts `neighbors`).
  for (const id of self?.neighbors ?? []) add(byId.get(id));
  // Lexical mentions — nodes whose text names the concept, in feed order (sorted by id).
  const terms = [concept.title, ...(concept.aliases ?? [])].map(norm).filter(specific);
  if (terms.length > 0) {
    for (const node of nodes) {
      if (seen.has(node.id)) continue;
      if (mentionsAny(node.text, terms)) add(node);
    }
  }
  return ordered.slice(0, limit);
}
