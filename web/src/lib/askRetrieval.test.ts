import { describe, expect, it } from "vitest";
import {
  type AskUnit,
  cosineScore,
  type EmbeddingEntry,
  prepare,
  retrieve,
  rrf,
  search,
  tokenize,
  vectorSearch,
} from "@watermark/functions/api/_lib/retrieval";

// A small corpus standing in for the citation-bearing bundle feeds.
const UNITS: AskUnit[] = [
  {
    id: "records:aedg/roundabouts.summary.opc.yaml",
    feed: "records",
    title: "Roundabouts OPC — summary",
    url: "/network/american-sugar-creek-allen-co/site/records/opc/",
    text: "opinion of probable cost estimate roadway subtotal earthwork drainage roundabout intersection",
    source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
    page: 318,
    source_kind: "document",
    verified: true,
  },
  {
    id: "timeline:2019-confidentiality",
    feed: "timeline",
    title: "2019-03-01 — Confidentiality agreement signed",
    url: "/network/american-sugar-creek-allen-co/timeline",
    text: "the parties executed a non-disclosure confidentiality agreement covering the project",
    source: "data/extracted/legal/nda.yaml",
    source_kind: "document",
    verified: true,
  },
  {
    id: "entities:AMAZON",
    feed: "entities",
    title: "Amazon.com Services LLC",
    url: "/wiki/entities/amazon-com-services-llc/",
    text: "cloud hyperscaler datacenter operator candidate consumer",
    source: "data/extracted/entities/graph.yaml",
    source_kind: "document",
  },
];

describe("tokenize", () => {
  it("lowercases, drops stopwords/noise, and folds a trailing plural", () => {
    expect(tokenize("The Roundabouts and a COST")).toEqual(["roundabout", "cost"]);
  });
  it("returns no tokens for whitespace or pure stopwords", () => {
    expect(tokenize("the and of to")).toEqual([]);
  });
});

describe("BM25 retrieve", () => {
  it("ranks the on-topic unit first for a corpus question", () => {
    const hits = retrieve(UNITS, "roundabout cost estimate", 3);
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].unit.id).toBe("records:aedg/roundabouts.summary.opc.yaml");
  });

  it("matches a title term (titles are weighted)", () => {
    const hits = retrieve(UNITS, "confidentiality agreement", 3);
    expect(hits[0].unit.feed).toBe("timeline");
  });

  it("carries each hit's citation through retrieval", () => {
    const [top] = retrieve(UNITS, "roundabout", 1);
    expect(top.unit.source).toBe("data/documents/aedg/PRR-01-bundle.ocr.pdf");
    expect(top.unit.page).toBe(318);
  });

  it("returns nothing for an out-of-corpus question (→ refusal upstream)", () => {
    expect(retrieve(UNITS, "banana bread recipe")).toEqual([]);
  });

  it("returns nothing for an empty query", () => {
    expect(retrieve(UNITS, "   ")).toEqual([]);
  });

  it("respects the top-k cap", () => {
    const prepared = prepare(UNITS);
    expect(search(prepared, "agreement cloud roadway", 2).length).toBeLessThanOrEqual(2);
  });
});

describe("cosineScore", () => {
  it("returns 1 for identical vectors", () => {
    expect(cosineScore([1, 0, 0], [1, 0, 0])).toBeCloseTo(1);
  });

  it("returns 0 for orthogonal vectors", () => {
    expect(cosineScore([1, 0], [0, 1])).toBeCloseTo(0);
  });

  it("returns 0 for a zero vector", () => {
    expect(cosineScore([0, 0], [1, 1])).toBe(0);
  });

  it("is insensitive to magnitude — only direction matters", () => {
    expect(cosineScore([2, 0], [100, 0])).toBeCloseTo(1);
  });
});

describe("vectorSearch", () => {
  // Simple 2-D embeddings: unit[0] points "north", unit[1] "east", unit[2] "diagonal".
  const EMB: EmbeddingEntry[] = [
    { id: UNITS[0].id, embedding: [1, 0] }, // north
    { id: UNITS[1].id, embedding: [0, 1] }, // east
    { id: UNITS[2].id, embedding: [Math.SQRT1_2, Math.SQRT1_2] }, // diagonal (≈ northeast)
  ];

  it("ranks the most similar unit first", () => {
    // Query pointing north — unit[0] should win
    const hits = vectorSearch(UNITS, EMB, [1, 0], 3);
    expect(hits[0].unit.id).toBe(UNITS[0].id);
  });

  it("skips units with no embedding entry", () => {
    const partial: EmbeddingEntry[] = [{ id: UNITS[0].id, embedding: [1, 0] }];
    const hits = vectorSearch(UNITS, partial, [1, 0], 3);
    expect(hits.length).toBe(1);
  });

  it("returns empty for an empty embedding index", () => {
    expect(vectorSearch(UNITS, [], [1, 0], 3)).toEqual([]);
  });
});

describe("rrf", () => {
  const makeHits = (ids: string[]): ReturnType<typeof retrieve> =>
    ids.map((id) => ({ unit: UNITS.find((u) => u.id === id)!, score: 1 }));

  it("promotes a document present in both lists", () => {
    // unit[0] appears in both; unit[1] only in list1; unit[2] only in list2
    const list1 = makeHits([UNITS[0].id, UNITS[1].id]);
    const list2 = makeHits([UNITS[0].id, UNITS[2].id]);
    const merged = rrf(list1, list2, 3);
    expect(merged[0].unit.id).toBe(UNITS[0].id); // double-ranked → first place
    expect(merged.length).toBeLessThanOrEqual(3);
  });

  it("handles one empty list gracefully (degenerates to the other list's ranking)", () => {
    const hits = makeHits([UNITS[0].id, UNITS[1].id]);
    const merged = rrf(hits, [], 3);
    expect(merged.length).toBe(2);
    // First in hits1 should score higher (rank 1 beats rank 2)
    expect(merged[0].unit.id).toBe(UNITS[0].id);
  });

  it("respects the topK cap", () => {
    const list1 = makeHits([UNITS[0].id, UNITS[1].id, UNITS[2].id]);
    const list2 = makeHits([UNITS[2].id, UNITS[1].id, UNITS[0].id]);
    expect(rrf(list1, list2, 2).length).toBe(2);
  });
});
