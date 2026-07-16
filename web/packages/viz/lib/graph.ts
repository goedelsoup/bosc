/**
 * Build-time entity-graph layout (issue #73). Reads the entities + relationships
 * feeds and runs a deterministic d3-force layout, emitting node coordinates so the
 * client island just renders (no layout cost or first-paint jump). d3-force is
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
import { hasFeed, loadFeed } from "@watermark/core/bundle";
import { slugify, type EntityNode, type RelationshipEdge } from "@watermark/core/feeds";

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

export function buildGraph(): GraphData {
  const entities = hasFeed("entities") ? loadFeed<EntityNode[]>("entities") : [];
  const rels = hasFeed("relationships") ? loadFeed<RelationshipEdge[]>("relationships") : [];
  const known = new Set(entities.map((e) => e.key));

  const nodes: SimNode[] = entities.map((e) => ({
    id: e.key,
    slug: slugify(e.key),
    display: e.display,
    kind: e.kind,
    relationClass: e.relation_class ?? null,
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
