import { describe, expect, it } from "vitest";
import { loadFeed } from "./bundle";
import { KIND_META, KIND_ORDER, groupByKind, summarizeByKind, topByDegree } from "./corpusIndex";
import type { CorpusNodeItem } from "./feeds";

// The corpus node DATA is the `corpus-index` bundle feed (#1573); the reducers are exercised
// against Lima's committed feed (the reference build — the largest, most-connected mirror).
const NODES = loadFeed<CorpusNodeItem[]>("corpus-index", "lima");

describe("corpus-index feed + helpers", () => {
  it("has nodes, each with a kind, non-negative degrees, and a positive line count", () => {
    expect(NODES.length).toBeGreaterThan(0);
    for (const n of NODES) {
      expect(KIND_ORDER).toContain(n.kind);
      expect(n.links_in).toBeGreaterThanOrEqual(0);
      expect(n.links_out).toBeGreaterThanOrEqual(0);
      expect(n.lines).toBeGreaterThan(0);
      expect(n.label.length).toBeGreaterThan(0);
    }
  });

  it("carries the corpus spine — the site anchor + the three hypothesis lenses", () => {
    expect(NODES.some((n) => n.kind === "site")).toBe(true);
    expect(NODES.filter((n) => n.kind === "hypothesis")).toHaveLength(3);
  });

  it("freshness, where present, is an ISO date (never fabricated for a sourceless node)", () => {
    for (const n of NODES) {
      if (n.updated) expect(n.updated).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
    // entities/concepts derive from committed files, so at least some carry a real date.
    expect(NODES.some((n) => n.updated)).toBe(true);
  });

  it("summarizeByKind tallies every node exactly once, in KIND_ORDER", () => {
    const tally = summarizeByKind(NODES);
    expect(tally.reduce((sum, t) => sum + t.count, 0)).toBe(NODES.length);
    const order = tally.map((t) => KIND_ORDER.indexOf(t.kind));
    expect(order).toEqual([...order].sort((a, b) => a - b));
    for (const t of tally) expect(t.label).toBe(KIND_META[t.kind].label);
  });

  it("groupByKind partitions the nodes and sorts each group by total degree", () => {
    const groups = groupByKind(NODES);
    expect(groups.flatMap((g) => g.nodes)).toHaveLength(NODES.length);
    for (const g of groups) {
      const degrees = g.nodes.map((n) => n.links_in + n.links_out);
      expect(degrees).toEqual([...degrees].sort((a, b) => b - a));
    }
  });

  it("topByDegree returns the most-connected nodes, descending, capped at the limit", () => {
    const top = topByDegree(NODES, 5);
    expect(top).toHaveLength(5);
    const degrees = top.map((n) => n.links_in + n.links_out);
    expect(degrees).toEqual([...degrees].sort((a, b) => b - a));
    const maxDegree = Math.max(...NODES.map((n) => n.links_in + n.links_out));
    expect(degrees[0]).toBe(maxDegree);
  });
});
