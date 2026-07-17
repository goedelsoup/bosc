/**
 * Corpus node index (design "/wiki/corpus") — the presentation vocabulary + reducers for the
 * at-a-glance map of the yidam corpus mirror (issue #1573, epic #1560 workstream C).
 *
 * The node DATA is the `corpus-index` bundle feed (`bosc.site.corpus_index`, one `CorpusNodeItem`
 * per mirror node with its display kind, in/out degree, line count, and freshness). This module is
 * the thin reader on top: the kind presentation map (label + order + a CSS modifier), and the
 * `summarizeByKind` / `groupByKind` reducers the page groups and counts by. No data is minted here
 * — a node with no backing source simply has a null `updated` (never a fabricated date).
 */
import type { CorpusNodeItem, CorpusNodeKind } from "./feeds";

/** Presentation vocab per display kind: the group heading, a one-line gloss, a CSS modifier key. */
export const KIND_META: Record<CorpusNodeKind, { label: string; blurb: string; mod: string }> = {
  site: { label: "Site anchor", blurb: "The watershed-point hub every node hangs from.", mod: "site" },
  entity: { label: "Entities", blurb: "Resolved parties, parcels, and identifiers.", mod: "entity" },
  person: { label: "People", blurb: "Profiled individuals in the record.", mod: "person" },
  concept: { label: "Concepts", blurb: "Glossary terms and methods, cross-linked.", mod: "concept" },
  hypothesis: { label: "Hypotheses", blurb: "Boom-origin reading lenses.", mod: "hypothesis" },
  lead: { label: "Leads", blurb: "Open threads on the site's leads board.", mod: "lead" },
  "open-question": { label: "Open questions", blurb: "Documented gaps with no nexus yet.", mod: "open" },
  relation: { label: "Relationships", blurb: "One node per entity-to-entity edge.", mod: "relation" },
  node: { label: "Other nodes", blurb: "Uncategorized corpus nodes.", mod: "node" },
};

/** The display order kinds are grouped in (the corpus's spine first, edges last). */
export const KIND_ORDER: CorpusNodeKind[] = [
  "site",
  "hypothesis",
  "entity",
  "person",
  "concept",
  "lead",
  "open-question",
  "relation",
  "node",
];

/** One `{kind, count}` tally, in `KIND_ORDER`, over the nodes present (empty kinds dropped). */
export interface KindTally {
  kind: CorpusNodeKind;
  label: string;
  mod: string;
  count: number;
}

/** Tally the nodes by display kind, in `KIND_ORDER` — the summary tiles at the top of the page. */
export function summarizeByKind(nodes: readonly CorpusNodeItem[]): KindTally[] {
  const counts = new Map<CorpusNodeKind, number>();
  for (const node of nodes) counts.set(node.kind, (counts.get(node.kind) ?? 0) + 1);
  return KIND_ORDER.filter((kind) => counts.has(kind)).map((kind) => ({
    kind,
    label: KIND_META[kind].label,
    mod: KIND_META[kind].mod,
    count: counts.get(kind) ?? 0,
  }));
}

/** One kind's group of nodes, sorted most-connected first (degree desc, then id). */
export interface KindGroup {
  kind: CorpusNodeKind;
  label: string;
  blurb: string;
  mod: string;
  nodes: CorpusNodeItem[];
}

/** Group nodes by display kind (in `KIND_ORDER`), each group sorted by total degree then id. */
export function groupByKind(nodes: readonly CorpusNodeItem[]): KindGroup[] {
  const byKind = new Map<CorpusNodeKind, CorpusNodeItem[]>();
  for (const node of nodes) {
    const bucket = byKind.get(node.kind);
    if (bucket) bucket.push(node);
    else byKind.set(node.kind, [node]);
  }
  return KIND_ORDER.filter((kind) => byKind.has(kind)).map((kind) => ({
    kind,
    label: KIND_META[kind].label,
    blurb: KIND_META[kind].blurb,
    mod: KIND_META[kind].mod,
    nodes: (byKind.get(kind) ?? []).sort(
      (a, b) => b.links_in + b.links_out - (a.links_in + a.links_out) || a.id.localeCompare(b.id),
    ),
  }));
}

/** The most-connected nodes across every kind (total degree desc) — the "hubs" of the corpus. */
export function topByDegree(nodes: readonly CorpusNodeItem[], limit = 10): CorpusNodeItem[] {
  return [...nodes]
    .sort((a, b) => b.links_in + b.links_out - (a.links_in + a.links_out) || a.id.localeCompare(b.id))
    .slice(0, limit);
}
