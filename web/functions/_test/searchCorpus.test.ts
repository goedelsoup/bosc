// search_corpus response_mode tests (#1580).
// Drives handleSearchCorpus in-process: the handler fetches `/ask-index.json` over
// globalThis.fetch, so each case stubs that route and resets the isolate cache.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetAskEmbeddingsCache } from "@watermark/functions/api/_lib/askEmbeddingsLoad";
import { _resetAskIndexCache } from "@watermark/functions/api/_lib/askIndexLoad";
import { _resetDocVersionsCache } from "@watermark/functions/api/_lib/docVersionsLoad";
import { handleSearchCorpus } from "@watermark/functions/api/_lib/mcpTools/searchCorpus";
import type { AskUnit, EmbeddingEntry } from "@watermark/functions/api/_lib/retrieval";
import { type FetchRoute, jsonResponse, routingFetch } from "./_routeHarness";

const REQ = "https://directory.example/api/mcp";

// Long enough to force truncation in both compact (~160 char) and snippets windows; the
// query term "roundabout" sits deep in the middle so a head preview misses it but a
// query-focused window catches it.
const FILLER = "the wastewater treatment facility discharge outfall permit review ".repeat(10);
const LONG_TEXT = `${FILLER} roundabout intersection earthwork subtotal opinion of probable cost ${FILLER}`;

const UNITS: AskUnit[] = [
  {
    id: "records:aedg/roundabouts.summary.opc.yaml",
    feed: "records",
    title: "Roundabouts OPC — summary",
    url: "/network/lima/site/records/opc/",
    text: LONG_TEXT,
    source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
    page: 318,
    pages: [318, 319, 320],
    doc_rel: "aedg/PRR-01-bundle.ocr.pdf",
    source_kind: "document",
    confidence: "high",
    verified: true,
    site: "lima",
  },
  {
    id: "timeline:2019-roundabout-nda",
    feed: "timeline",
    title: "2019-03-01 — Roundabout corridor NDA signed",
    url: "/network/lima/timeline",
    text: "The parties executed a confidentiality agreement covering the roundabout corridor project.",
    source: "data/extracted/legal/nda.yaml",
    source_kind: "document",
    verified: true,
    site: "lima",
    date: "2019-03-01",
  },
  {
    id: "records:fw/roundabout.opc.yaml",
    feed: "records",
    title: "Fort Wayne roundabout estimate",
    url: "/network/fort-wayne/site/records/opc/",
    text: "roundabout intersection cost estimate for the Fort Wayne corridor",
    source_kind: "document",
    verified: false,
    site: "fort-wayne",
  },
];

const askIndexRoute: FetchRoute = {
  test: (url) => url.pathname === "/ask-index.json",
  respond: () => jsonResponse(200, UNITS),
};

interface Envelope {
  results: Record<string, unknown>[];
  token_estimate: number;
  truncated: boolean;
  next_cursor: string | null;
}

/** The full governed envelope (#1581). */
async function envelope(args: Record<string, unknown>): Promise<Envelope> {
  const content = await handleSearchCorpus(args, REQ);
  return JSON.parse(content[0].text) as Envelope;
}

/** Just the `results` array — the shape the pre-envelope tests assert against. */
async function call(args: Record<string, unknown>): Promise<Record<string, unknown>[]> {
  return (await envelope(args)).results;
}

beforeEach(() => {
  _resetAskIndexCache();
  _resetAskEmbeddingsCache();
  vi.stubGlobal("fetch", routingFetch([askIndexRoute]));
});

afterEach(() => {
  vi.unstubAllGlobals();
  _resetAskIndexCache();
  _resetAskEmbeddingsCache();
});

describe("handleSearchCorpus response_mode", () => {
  it("returns [] for an empty query without fetching", async () => {
    expect(await call({ query: "  " })).toEqual([]);
  });

  it("defaults to compact evidence cards with no full text", async () => {
    const results = (await call({ query: "roundabout" })) as Record<string, unknown>[];
    expect(results.length).toBeGreaterThan(0);
    const rec = results.find((r) => r.id === "records:aedg/roundabouts.summary.opc.yaml");
    expect(rec).toBeDefined();
    // Compact card surfaces the discovery fields …
    expect(rec).toMatchObject({
      id: "records:aedg/roundabouts.summary.opc.yaml",
      title: "Roundabouts OPC — summary",
      site: "lima",
      collection: "records",
      source_kind: "document",
      verified: true,
    });
    // … carries a token estimate and a snippet …
    expect(typeof rec?.estimated_tokens).toBe("number");
    expect(rec?.estimated_tokens as number).toBeGreaterThan(100);
    expect(typeof rec?.snippet).toBe("string");
    // … and never the full text blob or legacy-only fields.
    expect(rec).not.toHaveProperty("text");
    expect(rec).not.toHaveProperty("url");
    expect(rec).not.toHaveProperty("feed");
  });

  it("surfaces a structured date when the source feed carries one, else null", async () => {
    const results = (await call({ query: "roundabout" })) as Record<string, unknown>[];
    const timeline = results.find((r) => r.id === "timeline:2019-roundabout-nda");
    const record = results.find((r) => r.id === "records:aedg/roundabouts.summary.opc.yaml");
    expect(timeline?.date).toBe("2019-03-01");
    expect(record?.date).toBeNull();
  });

  it("compact snippet is a short head preview, truncated with an ellipsis", async () => {
    const [rec] = (await call({
      query: "roundabout",
      collection: "records",
      site: "lima",
    })) as Record<string, unknown>[];
    const snippet = rec.snippet as string;
    expect(snippet.length).toBeLessThan(LONG_TEXT.length);
    expect(snippet.endsWith("…")).toBe(true);
    // A head preview of this text starts in the filler, before the query term.
    expect(snippet.toLowerCase()).not.toContain("roundabout");
  });

  it("snippets mode returns a query-focused window around the matched term", async () => {
    const [rec] = (await call({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: "snippets",
    })) as Record<string, unknown>[];
    const snippet = rec.snippet as string;
    expect(snippet.toLowerCase()).toContain("roundabout");
    expect(snippet.length).toBeLessThan(LONG_TEXT.length);
  });

  it("snippets mode honors snippet_tokens (smaller window → shorter snippet)", async () => {
    const small = (await call({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: "snippets",
      snippet_tokens: 30,
    })) as Record<string, unknown>[];
    const large = (await call({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: "snippets",
      snippet_tokens: 400,
    })) as Record<string, unknown>[];
    expect((small[0].snippet as string).length).toBeLessThan((large[0].snippet as string).length);
  });

  it("ids_only mode returns just id + score", async () => {
    const results = (await call({ query: "roundabout", response_mode: "ids_only" })) as Record<
      string,
      unknown
    >[];
    expect(results.length).toBeGreaterThan(0);
    for (const r of results) {
      expect(Object.keys(r).sort()).toEqual(["id", "score"]);
      expect(typeof r.id).toBe("string");
      expect(typeof r.score).toBe("number");
    }
  });

  it("full mode reproduces the legacy full-record shape (text + provenance)", async () => {
    const results = (await call({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: "full",
    })) as Record<string, unknown>[];
    const rec = results[0];
    expect(rec.text).toBe(LONG_TEXT);
    expect(rec).toMatchObject({
      id: "records:aedg/roundabouts.summary.opc.yaml",
      feed: "records",
      url: "/network/lima/site/records/opc/",
      source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
      page: 318,
      confidence: "high",
      verified: true,
    });
    expect(rec).not.toHaveProperty("estimated_tokens");
  });

  it("an unknown response_mode falls back to compact", async () => {
    const [rec] = (await call({ query: "roundabout", response_mode: "nonsense" })) as Record<
      string,
      unknown
    >[];
    expect(rec).toHaveProperty("estimated_tokens");
    expect(rec).not.toHaveProperty("text");
  });

  it("filters by site strictly on a tagged index", async () => {
    const results = (await call({ query: "roundabout", site: "fort-wayne" })) as Record<string, unknown>[];
    expect(results.length).toBeGreaterThan(0);
    for (const r of results) expect(r.site).toBe("fort-wayne");
  });
});

describe("handleSearchCorpus structured citations (#1584)", () => {
  const cited = async (mode: string): Promise<Record<string, unknown>> => {
    const results = (await call({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: mode,
    })) as Record<string, unknown>[];
    return results[0].citation as Record<string, unknown>;
  };

  it("attaches a full citation to a compact discovery card — citable without a fetch", async () => {
    expect(await cited("compact")).toEqual({
      document_id: "aedg/PRR-01-bundle.ocr.pdf",
      source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
      source_kind: "document",
      page: 318,
      pages: [318, 319, 320],
      source_url: "https://directory.example/network/lima/site/records/opc/",
      confidence: "high",
      verified: true,
      evidence: "verified",
      label: "data/documents/aedg/PRR-01-bundle.ocr.pdf pp. 318-320 [verified]",
    });
  });

  it("carries the same citation in snippets and full mode", async () => {
    expect(await cited("snippets")).toEqual(await cited("compact"));
    expect(await cited("full")).toEqual(await cited("compact"));
  });

  it("never presents a flattened-field snippet as a verbatim quote", async () => {
    // The snippet is a window over "key value · key value", not source prose — so `quote` is
    // absent here by design; search_passages is the tool that has real verbatim text.
    expect(await cited("snippets")).not.toHaveProperty("quote");
  });

  it("omits the fields an un-cited unit has no value for, rather than inventing them", async () => {
    const [fw] = (await call({ query: "roundabout", site: "fort-wayne" })) as Record<string, unknown>[];
    const c = fw.citation as Record<string, unknown>;
    expect(c).not.toHaveProperty("page");
    expect(c).not.toHaveProperty("source");
    expect(c).not.toHaveProperty("document_id");
    expect(c).toMatchObject({ verified: false, evidence: "inference", label: "uncited [inference]" });
  });

  it("leaves ids_only a bare candidate list — no citation", async () => {
    const results = (await call({ query: "roundabout", response_mode: "ids_only" })) as Record<
      string,
      unknown
    >[];
    for (const r of results) expect(r).not.toHaveProperty("citation");
  });

  it("keeps the citation when a per-result budget shrinks the hit's text", async () => {
    const [rec] = (await call({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: "full",
      max_tokens_per_result: 60,
    })) as Record<string, unknown>[];
    expect((rec.text as string).length).toBeLessThan(LONG_TEXT.length);
    expect((rec.citation as Record<string, unknown>).page).toBe(318);
  });
});

describe("handleSearchCorpus governance (#1581)", () => {
  it("wraps results in the governed envelope", async () => {
    const env = await envelope({ query: "roundabout" });
    expect(Array.isArray(env.results)).toBe(true);
    expect(typeof env.token_estimate).toBe("number");
    expect(env.token_estimate).toBeGreaterThan(0);
    expect(typeof env.truncated).toBe("boolean");
    expect("next_cursor" in env).toBe(true);
  });

  it("an empty query returns an exhausted, zero-cost envelope", async () => {
    expect(await envelope({ query: "  " })).toEqual({
      results: [],
      token_estimate: 0,
      truncated: false,
      next_cursor: null,
    });
  });

  it("caps the page at max_results and hands back a next_cursor", async () => {
    const env = await envelope({ query: "roundabout", max_results: 1 });
    expect(env.results).toHaveLength(1);
    expect(env.truncated).toBe(true);
    expect(env.next_cursor).toBeTruthy();
  });

  it("paginates the ranked pool across cursor pages without repeats", async () => {
    const page1 = await envelope({ query: "roundabout", max_results: 1 });
    const page2 = await envelope({
      query: "roundabout",
      max_results: 1,
      cursor: page1.next_cursor,
    });
    expect(page1.results[0].id).not.toBe(page2.results[0]?.id);
    // Walk to exhaustion — the final page reports no continuation.
    let cursor = page2.next_cursor;
    let guard = 0;
    while (cursor && guard++ < 10) {
      const next = await envelope({ query: "roundabout", max_results: 1, cursor });
      cursor = next.next_cursor;
    }
    expect(cursor).toBeNull();
  });

  it("the legacy `limit` param acts as the page-size cap", async () => {
    const env = await envelope({ query: "roundabout", limit: 1 });
    expect(env.results).toHaveLength(1);
    expect(env.truncated).toBe(true);
  });

  it("a tiny max_tokens truncates to fewer results (but always at least one)", async () => {
    const full = await envelope({ query: "roundabout", response_mode: "full", max_tokens: 40000 });
    const tiny = await envelope({ query: "roundabout", response_mode: "full", max_tokens: 100 });
    expect(tiny.results.length).toBeGreaterThanOrEqual(1); // forward progress
    expect(tiny.results.length).toBeLessThan(full.results.length);
    expect(tiny.truncated).toBe(true);
    expect(tiny.next_cursor).toBeTruthy();
  });

  it("max_tokens_per_result trims an over-cap full-text hit", async () => {
    const capped = await envelope({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: "full",
      max_tokens_per_result: 80,
    });
    const rec = capped.results[0];
    expect((rec.text as string).length).toBeLessThan(LONG_TEXT.length);
    expect((rec.text as string).endsWith("…")).toBe(true);
  });

  it("collapses the heavy field toward a marker when metadata alone exhausts the cap", async () => {
    // A tiny cap (clamped up to the 50-token floor) is still below this hit's provenance
    // metadata, so the text budget is 0 — the field collapses to a marker instead of being
    // padded back up to a fixed minimum (the pre-fix overshoot).
    const env = await envelope({
      query: "roundabout",
      collection: "records",
      site: "lima",
      response_mode: "full",
      max_tokens_per_result: 1,
    });
    const rec = env.results[0];
    expect((rec.text as string).length).toBeLessThan(20);
  });

  it("intent=fact_lookup seeds compact defaults; explicit knobs still win", async () => {
    const factLookup = await envelope({ query: "roundabout", intent: "fact_lookup" });
    // fact_lookup caps at 3 results and yields compact cards (no full text).
    expect(factLookup.results.length).toBeLessThanOrEqual(3);
    expect(factLookup.results[0]).toHaveProperty("estimated_tokens");
    expect(factLookup.results[0]).not.toHaveProperty("text");

    // An explicit response_mode overrides the intent's compact shape.
    const overridden = await envelope({
      query: "roundabout",
      intent: "fact_lookup",
      response_mode: "full",
      collection: "records",
      site: "lima",
    });
    expect(overridden.results[0]).toHaveProperty("text");
  });

  it("intent=exhaustive_audit seeds full-text results", async () => {
    const env = await envelope({
      query: "roundabout",
      intent: "exhaustive_audit",
      collection: "records",
      site: "lima",
    });
    expect(env.results[0]).toHaveProperty("text");
  });
});

describe("handleSearchCorpus hybrid retrieval (#1586)", () => {
  // Four records exercise every retrieval channel for the query "roundabout":
  //   records:both     — matches BM25 (keyword) AND is the vector-nearest → scores in both lists
  //   records:kw       — BM25 keyword match only (its embedding is orthogonal to the query)
  //   records:semantic — vector-only (shares no query keyword, but points near the query)
  //   records:noise    — neither channel
  // So reciprocal-rank fusion must promote records:both ahead of either single-channel hit.
  const HYBRID_UNITS: AskUnit[] = [
    {
      id: "records:both",
      feed: "records",
      title: "Roundabout corridor summary",
      url: "/u/both",
      text: "roundabout roundabout intersection corridor summary",
      verified: true,
      site: "lima",
    },
    {
      id: "records:kw",
      feed: "records",
      title: "Intersection cost estimate",
      url: "/u/kw",
      text: "roundabout earthwork subtotal",
      verified: true,
      site: "lima",
    },
    {
      id: "records:semantic",
      feed: "records",
      title: "Traffic circle geometry",
      url: "/u/sem",
      text: "traffic circle geometry at the junction",
      verified: true,
      site: "lima",
    },
    {
      id: "records:noise",
      feed: "records",
      title: "Unrelated permit",
      url: "/u/noise",
      text: "wastewater discharge outfall monitoring report",
      verified: false,
      site: "lima",
    },
  ];

  // The query embeds to "north" ([1,0]). records:both points due north (cosine 1) and
  // records:semantic near-north (cosine 0.8) → both are vector hits, records:both ranked
  // first; records:kw and records:noise are orthogonal (cosine 0 → excluded from vector hits).
  const QUERY_VECTOR = [1, 0];
  const EMB: EmbeddingEntry[] = [
    { id: "records:both", embedding: [1, 0] },
    { id: "records:kw", embedding: [0, 1] },
    { id: "records:semantic", embedding: [0.8, 0.6] },
    { id: "records:noise", embedding: [0, 1] },
  ];

  const indexRoute: FetchRoute = {
    test: (url) => url.pathname === "/ask-index.json",
    respond: () => jsonResponse(200, HYBRID_UNITS),
  };
  const embeddingsRoute: FetchRoute = {
    test: (url) => url.pathname === "/ask-embeddings.json",
    respond: () => jsonResponse(200, EMB),
  };
  const embeddings404: FetchRoute = {
    test: (url) => url.pathname === "/ask-embeddings.json",
    respond: () => new Response("not found", { status: 404 }),
  };

  interface FakeAI {
    calls: Array<{ model: string; text: string[] }>;
    run(model: string, input: { text: string[] }): Promise<{ data: number[][] }>;
  }
  /** A Workers AI stub recording each call; `throws` forces the embed to reject. */
  function fakeAI(data: number[][], opts: { throws?: boolean } = {}): FakeAI {
    const calls: FakeAI["calls"] = [];
    return {
      calls,
      run: async (model, input) => {
        calls.push({ model, text: input.text });
        if (opts.throws) throw new Error("workers-ai unavailable");
        return { data };
      },
    };
  }

  /** Run a search with the given env + routes and return the ranked ids. */
  async function ids(
    args: Record<string, unknown>,
    env: { AI?: FakeAI; ASK_EMBEDDINGS_URL?: string },
    routes: FetchRoute[],
  ): Promise<string[]> {
    vi.stubGlobal("fetch", routingFetch(routes));
    const content = await handleSearchCorpus(args, REQ, env);
    const parsed = JSON.parse(content[0].text) as Envelope;
    return parsed.results.map((r) => r.id as string);
  }

  it("fuses vector + BM25 via RRF — a dual-channel record outranks single-channel hits", async () => {
    const ai = fakeAI([QUERY_VECTOR]);
    const got = await ids({ query: "roundabout", response_mode: "ids_only" }, { AI: ai }, [
      indexRoute,
      embeddingsRoute,
    ]);
    // Both channels contribute — the BM25-only and the vector-only hits are each present …
    expect(got).toContain("records:kw"); // BM25-only
    expect(got).toContain("records:semantic"); // vector-only, surfaced by the vector path
    // … and reciprocal-rank fusion ranks the record scored in BOTH lists first, ahead of either
    // single-channel hit — a plain set union / list concatenation could not produce this order.
    expect(got[0]).toBe("records:both");
    expect(got.indexOf("records:both")).toBeLessThan(got.indexOf("records:kw"));
    expect(got.indexOf("records:both")).toBeLessThan(got.indexOf("records:semantic"));
    // The query was embedded with the same Workers AI model /api/ask uses.
    expect(ai.calls).toHaveLength(1);
    expect(ai.calls[0].model).toBe("@cf/sentence-transformers/all-minilm-l6-v2");
    expect(ai.calls[0].text).toEqual(["roundabout"]);
  });

  it("degrades to BM25-only with no AI binding — no embeddings fetch, no semantic hit", async () => {
    // No AI in env → the vector path is skipped entirely; ask-embeddings is never fetched, so
    // the harness (which throws on unmatched routes) proves the fetch never happens.
    const got = await ids({ query: "roundabout", response_mode: "ids_only" }, {}, [indexRoute]);
    expect(got).toContain("records:kw");
    expect(got).not.toContain("records:semantic");
  });

  it("degrades to BM25-only when the embeddings feed is absent (404), without embedding the query", async () => {
    const ai = fakeAI([QUERY_VECTOR]);
    const got = await ids({ query: "roundabout", response_mode: "ids_only" }, { AI: ai }, [
      indexRoute,
      embeddings404,
    ]);
    expect(got).toContain("records:kw");
    expect(got).not.toContain("records:semantic");
    expect(ai.calls).toHaveLength(0); // short-circuits before spending a Workers AI embed
  });

  it("degrades to BM25-only when the AI embed call throws", async () => {
    const ai = fakeAI([QUERY_VECTOR], { throws: true });
    const got = await ids({ query: "roundabout", response_mode: "ids_only" }, { AI: ai }, [
      indexRoute,
      embeddingsRoute,
    ]);
    expect(got).toContain("records:kw");
    expect(got).not.toContain("records:semantic");
  });

  it("degrades to BM25-only when the AI returns an empty query vector", async () => {
    const ai = fakeAI([[]]); // empty embedding
    const got = await ids({ query: "roundabout", response_mode: "ids_only" }, { AI: ai }, [
      indexRoute,
      embeddingsRoute,
    ]);
    expect(got).toContain("records:kw");
    expect(got).not.toContain("records:semantic");
  });
});

// End-to-end proof that the doc_rel join (askIndex) + docVersionsLoad + the dedup kernel connect:
// three records read from one permit filing's final/draft/fact-sheet collapse to the final by
// default, and the draft survives only when the query hits its draft-only evidence (#1590).
describe("handleSearchCorpus duplicate-cluster dedup (#1590)", () => {
  const CLUSTER = "oepa:2PH00006";
  const PERMIT = "oepa/permit.pdf";
  const DRAFT = "oepa/draft.pdf";
  const FACT = "oepa/fact.pdf";

  const DEDUP_UNITS: AskUnit[] = [
    {
      id: "records:permit",
      feed: "records",
      title: "American II NPDES permit",
      url: "/x",
      text: "npdes permit generator count 115 final",
      doc_rel: PERMIT,
      site: "lima",
    },
    {
      id: "records:draft",
      feed: "records",
      title: "American II draft public notice",
      url: "/x",
      text: "npdes permit generator rating 313 mw unredacted draft",
      doc_rel: DRAFT,
      site: "lima",
    },
    {
      id: "records:fact",
      feed: "records",
      title: "American II fact sheet",
      url: "/x",
      text: "npdes permit generator summary fact sheet",
      doc_rel: FACT,
      site: "lima",
    },
  ];

  const DOCUMENTS_FEED = [
    {
      slug: "oepa",
      entries: [
        {
          rel: PERMIT,
          duplicate_cluster: CLUSTER,
          canonical_document_id: PERMIT,
          version: "final",
          supersedes: [DRAFT, FACT],
        },
        {
          rel: DRAFT,
          duplicate_cluster: CLUSTER,
          canonical_document_id: PERMIT,
          version: "draft",
          supersedes: [],
        },
        {
          rel: FACT,
          duplicate_cluster: CLUSTER,
          canonical_document_id: PERMIT,
          version: "fact_sheet",
          supersedes: [],
        },
      ],
    },
  ];

  const routes: FetchRoute[] = [
    { test: (u) => u.pathname === "/ask-index.json", respond: () => jsonResponse(200, DEDUP_UNITS) },
    { test: (u) => u.pathname === "/feeds/documents.json", respond: () => jsonResponse(200, DOCUMENTS_FEED) },
  ];

  async function ids(args: Record<string, unknown>): Promise<string[]> {
    _resetAskIndexCache();
    _resetDocVersionsCache();
    vi.stubGlobal("fetch", routingFetch(routes));
    const content = await handleSearchCorpus({ response_mode: "ids_only", ...args }, REQ);
    return (JSON.parse(content[0].text) as Envelope).results.map((r) => r.id as string);
  }

  it("collapses the draft + fact-sheet into the canonical permit by default", async () => {
    const got = await ids({ query: "npdes permit generator" });
    expect(got).toContain("records:permit");
    expect(got).not.toContain("records:draft");
    expect(got).not.toContain("records:fact");
  });

  it("retains the draft when the query hits its draft-only evidence", async () => {
    const got = await ids({ query: "generator rating unredacted" });
    expect(got).toContain("records:permit"); // canonical always kept
    expect(got).toContain("records:draft"); // carries "rating"/"unredacted" the final lacks
    expect(got).not.toContain("records:fact"); // adds no novel query term
  });

  it("deduplicate:none returns every version separately", async () => {
    const got = await ids({ query: "npdes permit generator", deduplicate: "none" });
    expect(got).toEqual(expect.arrayContaining(["records:permit", "records:draft", "records:fact"]));
  });

  it("version_policy:latest_only keeps only the canonical", async () => {
    const got = await ids({ query: "generator rating unredacted", version_policy: "latest_only" });
    expect(got).toEqual(["records:permit"]);
  });
});

// End-to-end evidence tiering (#1591): a mixed pool of a strong primary record, a secondary
// entity view, and a glossary concept all matching the query — the record tops the ranking and
// is `direct`, the glossary is `background` however it scores, the entity is never `direct`.
describe("handleSearchCorpus evidence tiering (#1591)", () => {
  const TIER_UNITS: AskUnit[] = [
    {
      // Repeats the query terms so BM25 tops it → top relevance band, primary evidence → direct.
      id: "records:genset",
      feed: "records",
      title: "Backup generator inventory",
      url: "/u/genset",
      text: "generator generator generator power power backup diesel rating count",
      source_kind: "document",
      verified: true,
      site: "lima",
    },
    {
      id: "entities:acme",
      feed: "entities",
      title: "Acme Power LLC",
      url: "/u/acme",
      text: "generator operator company power holdings",
      source_kind: "document",
      verified: false,
      site: "lima",
    },
    {
      // The glossary is editorial synthesis (source_kind derived) — background whatever it scores.
      id: "concepts:generator",
      feed: "concepts",
      title: "Generator (definition)",
      url: "/u/def",
      text: "generator power electricity generation definition glossary term",
      source_kind: "derived",
      site: "lima",
    },
  ];

  const routes: FetchRoute[] = [
    { test: (u) => u.pathname === "/ask-index.json", respond: () => jsonResponse(200, TIER_UNITS) },
  ];

  interface TieredHit {
    id: string;
    tier?: string;
    tier_reason?: string;
    [k: string]: unknown;
  }

  async function tieredResults(args: Record<string, unknown>): Promise<TieredHit[]> {
    _resetAskIndexCache();
    vi.stubGlobal("fetch", routingFetch(routes));
    const content = await handleSearchCorpus({ query: "generator power", ...args }, REQ);
    return (JSON.parse(content[0].text) as { results: TieredHit[] }).results;
  }

  it("tiers the top-band primary record as direct evidence", async () => {
    const results = await tieredResults({});
    const rec = results.find((r) => r.id === "records:genset");
    expect(rec?.tier).toBe("direct");
    expect(rec?.tier_reason).toMatch(/primary evidence/);
  });

  it("tiers the glossary concept as background regardless of its score", async () => {
    const results = await tieredResults({});
    const concept = results.find((r) => r.id === "concepts:generator");
    expect(concept?.tier).toBe("background");
    expect(concept?.tier_reason).toMatch(/context, not evidence/);
  });

  it("never tiers a secondary entity view as direct", async () => {
    const results = await tieredResults({});
    const entity = results.find((r) => r.id === "entities:acme");
    expect(entity?.tier).toBeDefined();
    expect(entity?.tier).not.toBe("direct");
  });

  it("carries the tier on full-mode hits too", async () => {
    const results = await tieredResults({ response_mode: "full" });
    const rec = results.find((r) => r.id === "records:genset");
    expect(rec?.tier).toBe("direct");
    expect(rec).toHaveProperty("text"); // still the full-record shape
  });

  it("omits the tier from ids_only hits (stays a bare id + score)", async () => {
    const results = await tieredResults({ response_mode: "ids_only" });
    for (const r of results) {
      expect(Object.keys(r).sort()).toEqual(["id", "score"]);
    }
  });
});

// Structured facet filters (#1582): a `filters` bag over indexed fields narrows the ranked pool
// before scoring. Legacy top-level site/collection still work and fold into the same set; the
// canonical feed key is `filters.feed` (an alias for the historically-named `collection`).
describe("handleSearchCorpus structured filters (#1582)", () => {
  // Every unit matches the query term "corridor" so ranking never drops a facet-eligible unit;
  // the spread across feed/source_kind/verified/date/confidence/site is what the filters select on.
  const FILTER_UNITS: AskUnit[] = [
    {
      id: "records:permit",
      feed: "records",
      title: "Lima corridor NPDES permit",
      url: "/x",
      text: "corridor npdes permit effluent limit",
      source_kind: "document",
      confidence: "high",
      verified: true,
      site: "lima",
      date: "2019-06-01",
    },
    {
      id: "concepts:corridor",
      feed: "concepts",
      title: "Corridor (definition)",
      url: "/x",
      text: "corridor glossary definition derived synthesis",
      source_kind: "derived",
      confidence: "medium",
      verified: false,
      site: "lima",
    },
    {
      id: "timeline:2015-corridor",
      feed: "timeline",
      title: "2015-02-01 — Corridor rezoning",
      url: "/x",
      text: "corridor county rezoning hearing",
      source_kind: "document",
      verified: true,
      site: "lima",
      date: "2015-02-01",
    },
    {
      id: "records:fw",
      feed: "records",
      title: "Fort Wayne corridor estimate",
      url: "/x",
      text: "corridor cost estimate fort wayne",
      source_kind: "document",
      confidence: "high",
      verified: false,
      site: "fort-wayne",
      date: "2021-01-01",
    },
  ];

  const routes: FetchRoute[] = [
    { test: (u) => u.pathname === "/ask-index.json", respond: () => jsonResponse(200, FILTER_UNITS) },
  ];

  async function ids(args: Record<string, unknown>): Promise<string[]> {
    _resetAskIndexCache();
    vi.stubGlobal("fetch", routingFetch(routes));
    const content = await handleSearchCorpus({ query: "corridor", response_mode: "ids_only", ...args }, REQ);
    return (JSON.parse(content[0].text) as Envelope).results.map((r) => r.id as string).sort();
  }

  it("filters.feed restricts to one bundle feed", async () => {
    expect(await ids({ filters: { feed: "records" } })).toEqual(["records:fw", "records:permit"]);
  });

  it("filters.collection is an accepted alias of filters.feed", async () => {
    expect(await ids({ filters: { collection: "records" } })).toEqual(["records:fw", "records:permit"]);
  });

  it("legacy top-level collection still filters on feed (back-compat)", async () => {
    expect(await ids({ collection: "records" })).toEqual(["records:fw", "records:permit"]);
  });

  it("filters.source_kind separates document from derived", async () => {
    expect(await ids({ filters: { source_kind: "derived" } })).toEqual(["concepts:corridor"]);
  });

  it("filters.verified keeps only verified (or only unverified) units", async () => {
    expect(await ids({ filters: { verified: true } })).toEqual(["records:permit", "timeline:2015-corridor"]);
    expect(await ids({ filters: { verified: false } })).toEqual(["concepts:corridor", "records:fw"]);
  });

  it("filters.date_from/date_to windows dated units and excludes undated ones", async () => {
    expect(await ids({ filters: { date_from: "2016-01-01", date_to: "2020-01-01" } })).toEqual([
      "records:permit",
    ]);
  });

  it("filters.confidence matches the citation band exactly", async () => {
    expect(await ids({ filters: { confidence: "high" } })).toEqual(["records:fw", "records:permit"]);
  });

  it("filters.site wins over the legacy top-level site when both are set", async () => {
    // Top-level says fort-wayne, but the structured filter (fort-wayne overridden to lima) wins.
    const got = await ids({ site: "fort-wayne", filters: { site: "lima", feed: "records" } });
    expect(got).toEqual(["records:permit"]);
  });

  it("AND-combines facets across the bag", async () => {
    const got = await ids({
      filters: { site: "lima", feed: "records", verified: true, confidence: "high" },
    });
    expect(got).toEqual(["records:permit"]);
  });
});

// The enrichment facets (#1691) reaching the handler: `parseFilters` must lift each one off the
// bag, and `campus` must resolve to the same facet as `project`. The narrowing behaviour itself is
// askRetrieval.test.ts's; what's asserted here is the seam.
describe("handleSearchCorpus enrichment filters (#1691)", () => {
  // Every unit matches "corridor" so ranking never drops a facet-eligible one.
  const UNITS: AskUnit[] = [
    {
      id: "records:npdes",
      feed: "records",
      title: "American II corridor NPDES permit",
      url: "/x",
      text: "corridor npdes effluent limit",
      source_kind: "document",
      verified: true,
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
      title: "Corridor limited warranty deed",
      url: "/x",
      text: "corridor grantor grantee",
      source_kind: "document",
      verified: true,
      site: "lima",
      county: "Allen County, OH",
      document_type: "deeds",
      entities: ["BISTROZZI LLC"],
    },
    {
      id: "concepts:corridor",
      feed: "concepts",
      title: "Corridor (definition)",
      url: "/x",
      text: "corridor glossary definition",
      source_kind: "derived",
      verified: false,
      site: "lima",
      county: "Allen County, OH",
    },
  ];

  const routes: FetchRoute[] = [
    { test: (u) => u.pathname === "/ask-index.json", respond: () => jsonResponse(200, UNITS) },
  ];

  async function ids(args: Record<string, unknown>): Promise<string[]> {
    _resetAskIndexCache();
    vi.stubGlobal("fetch", routingFetch(routes));
    const content = await handleSearchCorpus({ query: "corridor", response_mode: "ids_only", ...args }, REQ);
    return (JSON.parse(content[0].text) as Envelope).results.map((r) => r.id as string).sort();
  }

  it("filters.permit_number reaches every action filed under a base number", async () => {
    expect(await ids({ filters: { permit_number: "2PH00006" } })).toEqual(["records:npdes"]);
  });

  it("filters.document_type separates genres inside one feed", async () => {
    expect(await ids({ filters: { feed: "records" } })).toEqual(["records:deed", "records:npdes"]);
    expect(await ids({ filters: { document_type: "deeds" } })).toEqual(["records:deed"]);
  });

  it("filters.agency matches the parent agency of a named division", async () => {
    expect(await ids({ filters: { agency: "Ohio EPA" } })).toEqual(["records:npdes"]);
  });

  it("filters.entity returns every unit the party touches", async () => {
    expect(await ids({ filters: { entity: "BISTROZZI LLC" } })).toEqual(["records:deed", "records:npdes"]);
  });

  it("filters.county accepts the bare county name", async () => {
    expect(await ids({ filters: { county: "Allen" } })).toHaveLength(3);
  });

  it("filters.campus is an accepted alias of filters.project", async () => {
    expect(await ids({ filters: { campus: "project-bosc" } })).toEqual(["records:npdes"]);
    expect(await ids({ filters: { project: "project-bosc" } })).toEqual(["records:npdes"]);
  });

  it("AND-combines an enrichment facet with the #1582 facets", async () => {
    expect(
      await ids({
        filters: { site: "lima", verified: true, entity: "BISTROZZI LLC", document_type: "deeds" },
      }),
    ).toEqual(["records:deed"]);
  });
});
