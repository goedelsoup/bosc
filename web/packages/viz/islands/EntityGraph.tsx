/**
 * Entity-graph island (issue #73). A node/edge view of the entities +
 * relationships feeds, laid out at build time (d3-force → /feeds/graph.json) and
 * rendered with deck.gl on a non-geo OrthographicView. Mounted client:only over
 * the page's SSR entity-list fallback.
 *
 * A node click navigates to that entity's wiki page; an optional `focus` slug
 * highlights one entity and its neighborhood (the rest dim). Driven entirely by
 * the emitted graph — no client layout.
 */
import { useEffect, useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { OrthographicView, type Layer, type PickingInfo } from "@deck.gl/core";
import { LineLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { relationClassLabel, relationClassRgb } from "@watermark/viz/relationClasses";
import { withBase } from "@watermark/core/base";

interface GNode {
  key: string;
  slug: string;
  display: string;
  kind: string;
  relationClass: string | null;
  degree: number;
  x: number;
  y: number;
}
interface GEdge {
  source: string;
  target: string;
  rel: string;
}
interface Graph {
  nodes: GNode[];
  edges: GEdge[];
}

type RGB = [number, number, number];
// Nodes are coloured by their relation to Project BOSC (the dimension the legacy
// graph grouped + coloured by); the page legend explains the classes. Unclassified
// entities fall back to a neutral grey, so the colour highlights the entities that
// actually have a defined relation to the project.
const DIM: RGB = [205, 207, 214];

export default function EntityGraph({ src, focus: focusProp }: { src: string; focus?: string }): JSX.Element {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [hovered, setHovered] = useState<GNode | null>(null);
  // Deep-link: entity pages link to /wiki/graph#<slug> to focus a neighborhood.
  const focus =
    focusProp ??
    (typeof window !== "undefined" && window.location.hash
      ? decodeURIComponent(window.location.hash.slice(1))
      : undefined);

  useEffect(() => {
    let live = true;
    fetch(src)
      .then((r) => r.json())
      .then((g: Graph) => live && setGraph(g))
      .catch(() => setGraph({ nodes: [], edges: [] }));
    return () => {
      live = false;
    };
  }, [src]);

  const nodes = graph?.nodes ?? [];
  const byKey = useMemo(() => new Map(nodes.map((n) => [n.key, n])), [graph]);

  // The focused node + its 1-hop neighborhood (for highlight/dim).
  const { focusKey, neighborhood } = useMemo(() => {
    const fk = focus ? nodes.find((n) => n.slug === focus)?.key : undefined;
    const nbh = new Set<string>();
    if (fk && graph) {
      nbh.add(fk);
      for (const e of graph.edges) {
        if (e.source === fk) nbh.add(e.target);
        if (e.target === fk) nbh.add(e.source);
      }
    }
    return { focusKey: fk, neighborhood: nbh };
  }, [graph, focus]);

  const lit = (key: string): boolean => neighborhood.size === 0 || neighborhood.has(key);

  const view = useMemo(() => {
    if (!nodes.length) return { target: [0, 0, 0] as [number, number, number], zoom: 0 };
    const xs = nodes.map((n) => n.x);
    const ys = nodes.map((n) => n.y);
    const minX = Math.min(...xs),
      maxX = Math.max(...xs),
      minY = Math.min(...ys),
      maxY = Math.max(...ys);
    const span = Math.max(maxX - minX, maxY - minY) || 1;
    return {
      target: [(minX + maxX) / 2, (minY + maxY) / 2, 0] as [number, number, number],
      zoom: Math.log2(640 / span),
    };
  }, [graph]);

  const layers = useMemo(() => {
    if (!graph) return [] as Layer[];
    const edges = graph.edges
      .map((e) => ({ ...e, s: byKey.get(e.source), t: byKey.get(e.target) }))
      .filter((e) => e.s && e.t);
    const labelled = nodes.filter((n) => n.degree >= 3 || (focusKey ? neighborhood.has(n.key) : false));

    return [
      new LineLayer({
        id: "edges",
        data: edges,
        getSourcePosition: (e) => [e.s!.x, e.s!.y],
        getTargetPosition: (e) => [e.t!.x, e.t!.y],
        getColor: (e) =>
          focusKey && (e.source === focusKey || e.target === focusKey)
            ? [191, 90, 0, 220]
            : [180, 182, 190, lit(e.source) && lit(e.target) ? 150 : 40],
        getWidth: (e) => (focusKey && (e.source === focusKey || e.target === focusKey) ? 2 : 1),
        widthUnits: "pixels",
        pickable: false,
      }),
      new ScatterplotLayer<GNode>({
        id: "nodes",
        data: nodes,
        getPosition: (n) => [n.x, n.y],
        getRadius: (n) => 4 + Math.sqrt(n.degree) * 3,
        radiusUnits: "common",
        radiusMinPixels: 3,
        radiusMaxPixels: 22,
        getFillColor: (n) =>
          n.key === focusKey
            ? [191, 90, 0]
            : lit(n.key)
              ? [...relationClassRgb(n.relationClass), 255]
              : [...DIM, 255],
        stroked: true,
        getLineColor: [255, 255, 255],
        lineWidthUnits: "pixels",
        getLineWidth: 1,
        pickable: true,
        onHover: (info: PickingInfo<GNode>) => setHovered(info.object ?? null),
        onClick: (info: PickingInfo<GNode>) => {
          const n = info.object;
          if (n) window.location.href = `${withBase("/wiki/entities/")}${n.slug}/`;
        },
      }),
      new TextLayer<GNode>({
        id: "labels",
        data: labelled,
        getPosition: (n) => [n.x, n.y],
        getText: (n) => n.display,
        getSize: 11,
        sizeUnits: "pixels",
        getColor: (n) => (lit(n.key) ? [40, 40, 40] : [170, 172, 180]),
        getTextAnchor: "start",
        getAlignmentBaseline: "center",
        getPixelOffset: [8, 0],
        billboard: true,
      }),
    ];
  }, [graph, focusKey, neighborhood]);

  return (
    <div
      className="deck-surface"
      role="figure"
      aria-label="Interactive network graph of entities and their relationships (deck.gl); the same entities are linked as text on this page."
    >
      <DeckGL
        views={new OrthographicView({})}
        initialViewState={{ target: view.target, zoom: view.zoom }}
        controller
        layers={layers}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
      />
      <div className="deck-controls">
        <strong>Entity graph</strong>
        {nodes.length} entities · click a node to open its page
        {focus && <div>Focused on the neighborhood of one entity.</div>}
      </div>
      {hovered && (
        <aside className="deck-popup">
          <strong>{hovered.display}</strong>
          <div className="card-meta">
            {hovered.kind} · {hovered.degree} link(s)
            {hovered.relationClass && <> · {relationClassLabel(hovered.relationClass)}</>}
          </div>
        </aside>
      )}
    </div>
  );
}
