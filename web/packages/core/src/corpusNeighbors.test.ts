import { describe, expect, it } from "vitest";
import { loadFeed } from "./bundle";
import { DEFAULT_NEIGHBORHOOD_LIMIT, conceptNode, neighborhoodFor } from "./corpusNeighbors";
import type { CorpusRetrievalNodeItem } from "./feeds";

/** A small synthetic corpus: two related concepts, an entity that names one, and two unrelated nodes. */
const NODES: CorpusRetrievalNodeItem[] = [
  {
    id: "concept/dilution",
    kind: "concept",
    label: "Dilution",
    text: "Dilution · mixing of an effluent with receiving water",
    ref: "dilution",
    neighbors: ["concept/7q10"],
  },
  {
    id: "concept/7q10",
    kind: "concept",
    label: "7Q10",
    text: "7Q10 · the design low flow",
    ref: "7q10",
    neighbors: ["concept/dilution"],
  },
  {
    id: "artifact/acme",
    kind: "entity",
    label: "Acme LLC",
    text: "Acme LLC · a permittee whose dilution factor is contested",
    ref: null,
    neighbors: [],
  },
  {
    id: "question/ph",
    kind: "open-question",
    label: "What is the pH margin?",
    text: "what is the pH margin at the outfall",
    ref: null,
    neighbors: [],
  },
  {
    id: "artifact/widget",
    kind: "entity",
    label: "Widget Co",
    text: "Widget Co · sells widgets",
    ref: null,
    neighbors: [],
  },
];

describe("conceptNode", () => {
  it("finds the concept node by its slug↔ref join", () => {
    expect(conceptNode("dilution", NODES)?.id).toBe("concept/dilution");
    expect(conceptNode("missing", NODES)).toBeNull();
  });
});

describe("neighborhoodFor", () => {
  it("puts the concept's own node first, then graph neighbors, then lexical mentions", () => {
    const hood = neighborhoodFor({ slug: "dilution", title: "Dilution" }, NODES);
    expect(hood.map((n) => n.id)).toEqual(["concept/dilution", "concept/7q10", "artifact/acme"]);
  });

  it("pulls in nodes that name the concept but excludes unrelated ones", () => {
    const ids = neighborhoodFor({ slug: "dilution", title: "Dilution" }, NODES).map((n) => n.id);
    expect(ids).toContain("artifact/acme"); // names "dilution" in its text
    expect(ids).not.toContain("artifact/widget"); // no mention, no graph edge
    expect(ids).not.toContain("question/ph"); // no mention, no graph edge
  });

  it("ignores a too-short alias so it never matches noise", () => {
    // "pH" is a 2-char single token — below the specificity floor, so it must not pull in the
    // pH question via the alias even though that node's text contains "ph".
    const ids = neighborhoodFor({ slug: "acidity", title: "Acidity", aliases: ["pH"] }, NODES).map(
      (n) => n.id,
    );
    expect(ids).not.toContain("question/ph");
  });

  it("dedupes a node that is both a graph neighbor and a mention", () => {
    // 7q10 is dilution's graph neighbor; give it text that also mentions "dilution".
    const nodes = NODES.map((n) =>
      n.id === "concept/7q10" ? { ...n, text: `${n.text} relative to dilution` } : n,
    );
    const ids = neighborhoodFor({ slug: "dilution", title: "Dilution" }, nodes).map((n) => n.id);
    expect(ids.filter((id) => id === "concept/7q10")).toHaveLength(1);
  });

  it("caps the candidate set at the limit", () => {
    const many: CorpusRetrievalNodeItem[] = [
      {
        id: "concept/xylophone",
        kind: "concept",
        label: "Xylophone",
        text: "Xylophone",
        ref: "xylophone",
        neighbors: [],
      },
      ...Array.from({ length: 100 }, (_, i) => ({
        id: `artifact/n${i}`,
        kind: "entity" as const,
        label: `N${i}`,
        text: "mentions xylophone here",
        ref: null,
        neighbors: [],
      })),
    ];
    const hood = neighborhoodFor({ slug: "xylophone", title: "Xylophone" }, many, { limit: 10 });
    expect(hood).toHaveLength(10);
    expect(hood[0].id).toBe("concept/xylophone"); // self is always kept
  });

  it("returns an empty neighborhood when the concept has no node", () => {
    expect(neighborhoodFor({ slug: "ghost", title: "Ghost" }, NODES)).toEqual([]);
  });
});

describe("neighborhoodFor over the committed Lima corpus-nodes feed", () => {
  const FEED = loadFeed<CorpusRetrievalNodeItem[]>("corpus-nodes", "lima");

  it("scopes a concept to a non-trivial neighborhood of real feed nodes, self first", () => {
    const self = conceptNode("dilution", FEED);
    expect(self).not.toBeNull();
    const hood = neighborhoodFor({ slug: "dilution", title: "Dilution" }, FEED, {
      limit: DEFAULT_NEIGHBORHOOD_LIMIT,
    });
    expect(hood[0].id).toBe(self?.id);
    expect(hood.length).toBeGreaterThan(1);
    const ids = new Set(FEED.map((n) => n.id));
    expect(hood.every((n) => ids.has(n.id))).toBe(true); // every node is a real feed node
  });

  it("reaches non-concept evidence where the corpus names the concept (npdes)", () => {
    // NPDES is named across the record (permits, relationships, leads), so the lexical-mention arm
    // reaches beyond the glossary into the evidence the concept graph alone never touches. (Many
    // concepts the record barely names have a thinner, concept-only neighborhood — faithfully so.)
    const hood = neighborhoodFor({ slug: "npdes", title: "NPDES" }, FEED);
    expect(hood.some((n) => n.kind !== "concept")).toBe(true);
  });
});
