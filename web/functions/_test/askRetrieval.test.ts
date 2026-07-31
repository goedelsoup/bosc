import { describe, expect, it } from "vitest";
import {
  applyCorpusFilters,
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

describe("applyCorpusFilters (#1582)", () => {
  // A varied, site-tagged corpus that exercises every facet: two feeds, both source_kinds,
  // verified true/false, dated and undated units, and two confidence bands across two sites.
  const FILTER_UNITS: AskUnit[] = [
    {
      id: "records:permit",
      feed: "records",
      title: "Lima NPDES permit",
      url: "/x",
      text: "npdes permit effluent limit",
      source_kind: "document",
      confidence: "high",
      verified: true,
      site: "lima",
      date: "2019-06-01",
    },
    {
      id: "concepts:dilution",
      feed: "concepts",
      title: "Dilution (definition)",
      url: "/x",
      text: "dilution factor glossary definition",
      source_kind: "derived",
      confidence: "medium",
      verified: false,
      site: "lima",
    },
    {
      id: "timeline:2015-rezone",
      feed: "timeline",
      title: "2015-02-01 — Rezoning",
      url: "/x",
      text: "county rezoning hearing",
      source_kind: "document",
      verified: true,
      site: "lima",
      date: "2015-02-01",
    },
    {
      id: "records:fw",
      feed: "records",
      title: "Fort Wayne estimate",
      url: "/x",
      text: "corridor cost estimate",
      source_kind: "document",
      confidence: "high",
      verified: false,
      site: "fort-wayne",
      date: "2021-01-01",
    },
  ];
  const ids = (units: AskUnit[]) => units.map((u) => u.id).sort();

  it("no filters is a pass-through", () => {
    expect(applyCorpusFilters(FILTER_UNITS, {})).toEqual(FILTER_UNITS);
  });

  it("filters strictly by site on a tagged index", () => {
    const out = applyCorpusFilters(FILTER_UNITS, { site: "fort-wayne" });
    expect(ids(out)).toEqual(["records:fw"]);
  });

  it("skips the site constraint on an untagged (legacy) index", () => {
    const untagged = FILTER_UNITS.map(({ site, ...rest }) => rest);
    expect(applyCorpusFilters(untagged, { site: "lima" })).toEqual(untagged);
  });

  it("filters by feed", () => {
    const out = applyCorpusFilters(FILTER_UNITS, { feed: "records" });
    expect(ids(out)).toEqual(["records:fw", "records:permit"]);
  });

  it("filters by source_kind (document vs derived)", () => {
    expect(ids(applyCorpusFilters(FILTER_UNITS, { source_kind: "derived" }))).toEqual(["concepts:dilution"]);
    expect(applyCorpusFilters(FILTER_UNITS, { source_kind: "document" })).toHaveLength(3);
  });

  it("filters by verified true/false on units with an explicit flag", () => {
    expect(ids(applyCorpusFilters(FILTER_UNITS, { verified: true }))).toEqual([
      "records:permit",
      "timeline:2015-rezone",
    ]);
    expect(ids(applyCorpusFilters(FILTER_UNITS, { verified: false }))).toEqual([
      "concepts:dilution",
      "records:fw",
    ]);
  });

  it("treats a unit with no verified flag as unverified (matches false, excluded from true)", () => {
    // Units whose source carries no verified flag — documents, entities, uncited timeline
    // entries in the real index — render as `verified: false` (`u.verified ?? false`) and ARE
    // "unverified units", so verified:false must return them and verified:true must not. The
    // flag is strictly binary (the output-schema types it a plain boolean), NOT a three-valued
    // field where a missing flag is an "unknown" both filters would drop.
    const noFlag: AskUnit = {
      id: "documents:uncited",
      feed: "documents",
      title: "Uncited",
      url: "/x",
      text: "x",
      site: "lima",
    };
    const pool = [...FILTER_UNITS, noFlag];
    expect(ids(applyCorpusFilters(pool, { verified: true }))).not.toContain("documents:uncited");
    expect(ids(applyCorpusFilters(pool, { verified: false }))).toContain("documents:uncited");
  });

  it("windows by date_from/date_to and excludes undated units", () => {
    const out = applyCorpusFilters(FILTER_UNITS, { date_from: "2016-01-01", date_to: "2020-01-01" });
    // 2019 permit is in-window; 2015 rezone and 2021 estimate are out; the undated concept is dropped.
    expect(ids(out)).toEqual(["records:permit"]);
  });

  it("filters by confidence band, matched exactly", () => {
    expect(ids(applyCorpusFilters(FILTER_UNITS, { confidence: "high" }))).toEqual([
      "records:fw",
      "records:permit",
    ]);
  });

  it("AND-combines every present facet", () => {
    const out = applyCorpusFilters(FILTER_UNITS, {
      site: "lima",
      feed: "records",
      source_kind: "document",
      verified: true,
      confidence: "high",
      date_from: "2019-01-01",
    });
    expect(ids(out)).toEqual(["records:permit"]);
  });
});

// The enrichment facets (#1691). Every one compares through the normalizer @watermark/core/askFacets
// defines for it — the same function the build stamped the index with — so these cases assert the
// kernel's *use* of that contract: which units survive, and that a unit lacking the field is
// excluded rather than passed through.
describe("applyCorpusFilters enrichment facets (#1691)", () => {
  const UNITS: AskUnit[] = [
    {
      id: "records:npdes",
      feed: "records",
      title: "American II NPDES permit",
      url: "/x",
      text: "effluent limits",
      site: "lima",
      county: "Allen County, OH",
      document_type: "permits-npdes",
      permit_numbers: ["2PH00006*LD", "OH0037338"],
      agency: "Ohio EPA, Division of Surface Water",
      entities: ["BISTROZZI LLC"],
      project: "project-bosc",
    },
    {
      id: "records:deed",
      feed: "records",
      title: "Limited Warranty Deed",
      url: "/x",
      text: "grantor grantee",
      site: "lima",
      county: "Allen County, OH",
      document_type: "deeds",
      entities: ["BISTROZZI LLC", "AMAZON COM SERVICES"],
    },
    {
      id: "records:usace",
      feed: "records",
      title: "Section 404 authorization",
      url: "/x",
      text: "wetland fill",
      site: "lima",
      county: "Allen County, OH",
      document_type: "permits-epa",
      permit_numbers: ["DSW401252260W"],
      agency: "U.S. Army Corps of Engineers",
      project: "project-dazzler",
    },
    {
      // A concept unit: carries none of the facets, which is what makes it the exclusion case.
      id: "concepts:dilution",
      feed: "concepts",
      title: "Dilution",
      url: "/x",
      text: "glossary",
      site: "lima",
      county: "Allen County, OH",
    },
  ];
  const ids = (units: AskUnit[]) => units.map((u) => u.id).sort();

  it("matches county however the caller writes it", () => {
    for (const county of ["Allen County, OH", "Allen County", "allen"]) {
      expect(applyCorpusFilters(UNITS, { county })).toHaveLength(4);
    }
    expect(applyCorpusFilters(UNITS, { county: "Hancock" })).toEqual([]);
  });

  it("matches a base permit number to every modification, and the NPDES id to its record", () => {
    expect(ids(applyCorpusFilters(UNITS, { permit_number: "2PH00006" }))).toEqual(["records:npdes"]);
    expect(ids(applyCorpusFilters(UNITS, { permit_number: "oh0037338" }))).toEqual(["records:npdes"]);
    // A unit with no permit id fails the constraint — it is not silently kept.
    expect(applyCorpusFilters(UNITS, { permit_number: "2PH00006" })).toHaveLength(1);
  });

  it("reaches an agency's divisions from the parent name, without merging distinct agencies", () => {
    expect(ids(applyCorpusFilters(UNITS, { agency: "Ohio EPA" }))).toEqual(["records:npdes"]);
    expect(ids(applyCorpusFilters(UNITS, { agency: "army corps" }))).toEqual(["records:usace"]);
  });

  it("separates document genres the `feed` facet cannot", () => {
    // All three are feed:"records" — only document_type tells a deed from a permit.
    expect(ids(applyCorpusFilters(UNITS, { feed: "records" }))).toHaveLength(3);
    expect(ids(applyCorpusFilters(UNITS, { document_type: "deeds" }))).toEqual(["records:deed"]);
  });

  it("returns every unit an entity touches, matched case- and punctuation-insensitively", () => {
    expect(ids(applyCorpusFilters(UNITS, { entity: "BISTROZZI LLC" }))).toEqual([
      "records:deed",
      "records:npdes",
    ]);
    expect(ids(applyCorpusFilters(UNITS, { entity: "bistrozzi llc" }))).toEqual([
      "records:deed",
      "records:npdes",
    ]);
    expect(applyCorpusFilters(UNITS, { entity: "NOT A PARTY" })).toEqual([]);
  });

  it("constrains to one campus", () => {
    expect(ids(applyCorpusFilters(UNITS, { project: "project-bosc" }))).toEqual(["records:npdes"]);
    expect(ids(applyCorpusFilters(UNITS, { project: "Project Dazzler" }))).toEqual(["records:usace"]);
  });

  it("excludes a unit whose feed carries nothing for the facet", () => {
    // The concept unit answers none of these — an absent field fails the constraint, exactly as
    // an absent `date` does under date_from. This is the contract that keeps a facet honest: it
    // never widens to "everything we couldn't check".
    for (const filters of [
      { document_type: "deeds" },
      { permit_number: "2PH00006" },
      { agency: "Ohio EPA" },
      { entity: "BISTROZZI LLC" },
      { project: "project-bosc" },
    ]) {
      expect(ids(applyCorpusFilters(UNITS, filters))).not.toContain("concepts:dilution");
    }
  });

  it("AND-combines an enrichment facet with the #1582 facets", () => {
    expect(
      ids(
        applyCorpusFilters(UNITS, {
          site: "lima",
          feed: "records",
          entity: "BISTROZZI LLC",
          document_type: "deeds",
        }),
      ),
    ).toEqual(["records:deed"]);
  });
});
