import { describe, expect, it } from "vitest";
import { type NeighborNode, makeRetriever } from "./conceptAsk";

const NODES: NeighborNode[] = [
  {
    id: "concept/dilution",
    kind: "concept",
    label: "Dilution",
    text: "Dilution · mixing of an effluent with receiving water to meet a permit limit",
    ref: "dilution",
    neighbors: [],
    href: "/wiki/concepts/dilution/",
  },
  {
    id: "concept/7q10",
    kind: "concept",
    label: "7Q10",
    text: "7Q10 · the lowest seven-day average streamflow, the design low flow denominator",
    ref: "7q10",
    neighbors: [],
    href: "/wiki/concepts/7q10/",
  },
  {
    id: "question/open-flow",
    kind: "open-question",
    label: "What design low flow did the permit assume?",
    text: "the permit's assimilative capacity turns on the design low flow it assumed",
    evidence: "open",
    ref: null,
    neighbors: [],
    href: null,
  },
];

describe("makeRetriever (client-side BM25 over a concept neighborhood)", () => {
  it("ranks the best-matching node first", () => {
    const retrieve = makeRetriever(NODES);
    expect(retrieve("effluent mixing to meet a limit")[0].id).toBe("concept/dilution");
    expect(retrieve("lowest seven day streamflow")[0].id).toBe("concept/7q10");
  });

  it("returns nothing for an empty or whitespace query (the default view handles that)", () => {
    const retrieve = makeRetriever(NODES);
    expect(retrieve("")).toEqual([]);
    expect(retrieve("   ")).toEqual([]);
  });

  it("honors the result cap", () => {
    expect(makeRetriever(NODES)("design low flow permit", 1)).toHaveLength(1);
  });

  it("returns full corpus nodes (kind + evidence + href), not bare BM25 units", () => {
    const hit = makeRetriever(NODES)("design low flow the permit assumed")[0];
    expect(hit.kind).toBeDefined();
    expect(hit).toHaveProperty("href");
    // A hit that carries an evidence tag keeps it, for the chip the widget renders.
    const open = makeRetriever(NODES)("assimilative capacity").find((n) => n.evidence);
    expect(open?.evidence).toBe("open");
  });
});
