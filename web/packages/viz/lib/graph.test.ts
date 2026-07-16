// buildGraph (#592) — the d3-force layout over the entity/relationship feeds, consumed by
// feeds/graph.json.ts. Runs against the committed sample bundle (the same loader the page
// uses). Pins the invariants the unchecked post-simulation `SimNode` casts rely on: every
// edge endpoint is an *id string* that resolves to a real node, and the layout is seeded
// (deterministic) so the island renders without a first-paint jump.
import { describe, expect, it } from "vitest";
import { buildGraph } from "./graph";

describe("buildGraph (#592)", () => {
  const graph = buildGraph();

  it("emits nodes with finite, rounded coordinates and a non-negative degree", () => {
    expect(graph.nodes.length).toBeGreaterThan(0); // the sample bundle carries entities
    for (const n of graph.nodes) {
      expect(typeof n.key).toBe("string");
      expect(n.key.length).toBeGreaterThan(0);
      expect(typeof n.slug).toBe("string");
      expect(Number.isFinite(n.x)).toBe(true);
      expect(Number.isFinite(n.y)).toBe(true);
      // rounded to 2dp by the builder
      expect(n.x).toBeCloseTo(Math.round(n.x * 100) / 100, 10);
      expect(n.degree).toBeGreaterThanOrEqual(0);
    }
  });

  it("emits edges whose endpoints are id strings resolving to real nodes (the SimNode cast)", () => {
    const keys = new Set(graph.nodes.map((n) => n.key));
    for (const e of graph.edges) {
      expect(typeof e.source).toBe("string"); // not a SimNode object leaking through
      expect(typeof e.target).toBe("string");
      expect(keys.has(e.source)).toBe(true);
      expect(keys.has(e.target)).toBe(true);
      expect(e.source).not.toBe(e.target); // self-loops are filtered
      expect(typeof e.rel).toBe("string");
    }
  });

  it("degree equals the number of incident edges", () => {
    const incident = new Map<string, number>();
    for (const e of graph.edges) {
      incident.set(e.source, (incident.get(e.source) ?? 0) + 1);
      incident.set(e.target, (incident.get(e.target) ?? 0) + 1);
    }
    for (const n of graph.nodes) expect(n.degree).toBe(incident.get(n.key) ?? 0);
  });

  it("is deterministic — the seeded layout produces identical coordinates across runs", () => {
    expect(buildGraph()).toEqual(graph);
  });
});
