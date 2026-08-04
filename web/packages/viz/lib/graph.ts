/**
 * Build-time entity-graph layout (issue #73). Reads the network's unioned entities +
 * relationships (`networkEntities`, #1906) and runs a deterministic d3-force layout, emitting node
 * coordinates so the client island just renders (no layout cost or first-paint jump). d3-force is
 * deterministic — phyllotaxis seeding + a seeded jiggle — so the build is stable.
 *
 * NOT client-safe (imports the node:fs bundle loader); the island consumes the
 * emitted /feeds/graph.json.
 */
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { networkEdges, networkEntities } from "@watermark/core/networkEntities";

interface SimNode extends SimulationNodeDatum {
  id: string;
  slug: string;
  display: string;
  kind: string;
  relationClass: string | null;
  degree: number;
}
interface SimLink extends SimulationLinkDatum<SimNode> {
  rel: string;
}

/** A force link's endpoint is an id string (pre-simulation) or the resolved `SimNode`
 *  (after d3 mutates it); read its id without an unchecked cast (#585). */
const linkEndId = (e: SimNode | string | number): string => (typeof e === "object" ? e.id : String(e));

export interface GraphNode {
  key: string;
  slug: string;
  display: string;
  kind: string;
  relationClass: string | null;
  degree: number;
  x: number;
  y: number;
}
export interface GraphEdge {
  source: string;
  target: string;
  rel: string;
}
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/**
 * The graph is the **network's** (#1906): nodes and edges come from `networkEntities`, the same
 * union the wiki's entity pages are minted from. Reading the ambient bundle rendered one site's
 * slice of a graph declared network-global, so a node's "view in graph" link could land on a graph
 * that didn't contain it — and a party carried only by a peer was invisible in the one
 * visualization whose point is that parties recur across watershed points.
 */
export function buildGraph(): GraphData {
  const entities = networkEntities();
  const rels = networkEdges().map((e) => e.edge);
  const known = new Set(entities.map((e) => e.key));

  const nodes: SimNode[] = entities.map((e) => ({
    id: e.key,
    slug: e.slug,
    display: e.node.display,
    kind: e.node.kind,
    relationClass: e.node.relation_class ?? null,
    degree: 0,
  }));
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const links: SimLink[] = [];
  for (const r of rels) {
    if (!known.has(r.src) || !known.has(r.dst) || r.src === r.dst) continue;
    links.push({ source: r.src, target: r.dst, rel: r.rel });
    byId.get(r.src)!.degree += 1;
    byId.get(r.dst)!.degree += 1;
  }

  if (nodes.length > 0) {
    const sim = forceSimulation(nodes)
      .force(
        "link",
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(60)
          .strength(0.4),
      )
      .force("charge", forceManyBody().strength(-140))
      .force("center", forceCenter(0, 0))
      .force("collide", forceCollide(10))
      .stop();
    for (let i = 0; i < 300; i++) sim.tick();
  }

  return {
    nodes: nodes.map((n) => ({
      key: n.id,
      slug: n.slug,
      display: n.display,
      kind: n.kind,
      relationClass: n.relationClass,
      degree: n.degree,
      x: Math.round((n.x ?? 0) * 100) / 100,
      y: Math.round((n.y ?? 0) * 100) / 100,
    })),
    edges: links.map((l) => ({
      source: linkEndId(l.source),
      target: linkEndId(l.target),
      rel: l.rel,
    })),
  };
}
