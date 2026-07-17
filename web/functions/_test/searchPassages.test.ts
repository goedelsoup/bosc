// search_passages tests (#1589, epic #1579 Phase 3).
// Drives handleSearchPassages in-process: the handler fetches `/feeds/passages.json` (and, for
// the vector upgrade, `/feeds/passage-embeddings.json`) over globalThis.fetch, so each case stubs
// those routes and resets the isolate cache. Mirrors searchCorpus.test.ts.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetAskEmbeddingsCache } from "@watermark/functions/api/_lib/askEmbeddingsLoad";
import { handleSearchPassages } from "@watermark/functions/api/_lib/mcpTools/searchPassages";
import { _resetPassagesCache, type PassageRow } from "@watermark/functions/api/_lib/passagesLoad";
import type { EmbeddingEntry } from "@watermark/functions/api/_lib/retrieval";
import { type FetchRoute, jsonResponse, routingFetch } from "./_routeHarness";

const REQ = "https://directory.example/api/mcp";

// A long page so the per-result trim has something to cut; the query term "phosphorus" sits deep.
const FILLER = "the wastewater treatment facility discharge outfall permit review ".repeat(10);
const LONG_TEXT = `${FILLER} total phosphorus effluent limit 0.5 mg/L monthly average ${FILLER}`;

const PASSAGES: PassageRow[] = [
  {
    id: "oepa/2PE00000.pdf#p12",
    document_id: "oepa/2PE00000.pdf",
    collection: "oepa",
    title: "2PE00000.pdf",
    page: 12,
    section: null,
    text: LONG_TEXT,
  },
  {
    id: "oepa/2PE00000.pdf#p3",
    document_id: "oepa/2PE00000.pdf",
    collection: "oepa",
    title: "2PE00000.pdf",
    page: 3,
    section: null,
    text: "General conditions: the permittee shall operate and maintain all facilities.",
  },
  {
    id: "aedg/PRR-01-bundle.ocr.pdf#p318",
    document_id: "aedg/PRR-01-bundle.ocr.pdf",
    collection: "aedg",
    title: "PRR-01-bundle.ocr.pdf",
    page: 318,
    section: null,
    text: "Roundabout intersection earthwork subtotal opinion of probable cost phosphorus.",
  },
];

const passagesRoute: FetchRoute = {
  test: (url) => url.pathname === "/feeds/passages.json",
  respond: () => jsonResponse(200, PASSAGES),
};

interface Envelope {
  results: Record<string, unknown>[];
  token_estimate: number;
  truncated: boolean;
  next_cursor: string | null;
}

async function envelope(
  args: Record<string, unknown>,
  env: Record<string, unknown> = {},
  routes: FetchRoute[] = [passagesRoute],
): Promise<Envelope> {
  vi.stubGlobal("fetch", routingFetch(routes));
  const content = await handleSearchPassages(args, REQ, env);
  return JSON.parse(content[0].text) as Envelope;
}

beforeEach(() => {
  _resetPassagesCache();
  _resetAskEmbeddingsCache();
});

afterEach(() => {
  vi.unstubAllGlobals();
  _resetPassagesCache();
  _resetAskEmbeddingsCache();
});

describe("handleSearchPassages", () => {
  it("returns an exhausted, zero-cost envelope for an empty query without fetching", async () => {
    // No routes registered — an empty query must short-circuit before any fetch.
    vi.stubGlobal("fetch", routingFetch([]));
    const content = await handleSearchPassages({ query: "  " }, REQ);
    expect(JSON.parse(content[0].text)).toEqual({
      results: [],
      token_estimate: 0,
      truncated: false,
      next_cursor: null,
    });
  });

  it("returns page-cited excerpts with document_id, page, and score", async () => {
    const env = await envelope({ query: "phosphorus effluent limit" });
    expect(env.results.length).toBeGreaterThan(0);
    const hit = env.results.find((r) => r.id === "oepa/2PE00000.pdf#p12");
    expect(hit).toMatchObject({
      id: "oepa/2PE00000.pdf#p12",
      document_id: "oepa/2PE00000.pdf",
      collection: "oepa",
      title: "2PE00000.pdf",
      page: 12,
      section: null,
    });
    expect(typeof hit?.score).toBe("number");
    expect(hit?.id).toBe(`${hit?.document_id}#p${hit?.page}`);
    expect(typeof hit?.text).toBe("string");
    // Every hit is a well-formed page cite.
    for (const r of env.results) expect(r.id).toBe(`${r.document_id}#p${r.page}`);
  });

  it("wraps results in the governed envelope", async () => {
    const env = await envelope({ query: "phosphorus" });
    expect(Array.isArray(env.results)).toBe(true);
    expect(typeof env.token_estimate).toBe("number");
    expect(env.token_estimate).toBeGreaterThan(0);
    expect(typeof env.truncated).toBe("boolean");
    expect("next_cursor" in env).toBe(true);
  });

  it("filters to the requested document_ids", async () => {
    const env = await envelope({
      query: "phosphorus",
      document_ids: ["aedg/PRR-01-bundle.ocr.pdf"],
    });
    expect(env.results.length).toBeGreaterThan(0);
    for (const r of env.results) expect(r.document_id).toBe("aedg/PRR-01-bundle.ocr.pdf");
  });

  it("caps the page at max_results and paginates without repeats", async () => {
    const page1 = await envelope({ query: "phosphorus", max_results: 1 });
    expect(page1.results).toHaveLength(1);
    expect(page1.truncated).toBe(true);
    expect(page1.next_cursor).toBeTruthy();
    const page2 = await envelope({
      query: "phosphorus",
      max_results: 1,
      cursor: page1.next_cursor,
    });
    expect(page2.results[0]?.id).not.toBe(page1.results[0].id);
  });

  it("max_tokens_per_result trims an over-cap excerpt but keeps the citation", async () => {
    // Scope to the long-text page so the over-cap hit is deterministic (BM25 length-normalizes, so
    // for a bare term the shorter pages would otherwise outrank this one).
    const env = await envelope({
      query: "total phosphorus effluent limit",
      document_ids: ["oepa/2PE00000.pdf"],
      max_tokens_per_result: 60,
    });
    const top = env.results.find((r) => r.id === "oepa/2PE00000.pdf#p12");
    expect(top).toBeDefined();
    expect((top?.text as string).length).toBeLessThan(LONG_TEXT.length);
    expect((top?.text as string).endsWith("…")).toBe(true);
    // Provenance is never dropped.
    expect(top?.document_id).toBe("oepa/2PE00000.pdf");
    expect(top?.page).toBe(12);
  });

  it("returns empty when the passages feed is absent (404)", async () => {
    const absent: FetchRoute = {
      test: (url) => url.pathname === "/feeds/passages.json",
      respond: () => new Response("not found", { status: 404 }),
    };
    const env = await envelope({ query: "phosphorus" }, {}, [absent]);
    expect(env.results).toEqual([]);
  });

  it("returns empty when document_ids match nothing", async () => {
    const env = await envelope({ query: "phosphorus", document_ids: ["nonexistent.pdf"] });
    expect(env.results).toEqual([]);
  });
});

describe("handleSearchPassages hybrid retrieval (#1586 kernel over passages)", () => {
  // Three passages exercise the retrieval channels for "phosphorus":
  //   p:both     — BM25 keyword match AND vector-nearest
  //   p:kw       — BM25 keyword only (orthogonal embedding)
  //   p:semantic — vector only (no shared keyword, points near the query)
  const HYBRID: PassageRow[] = [
    {
      id: "oepa/a.pdf#p1",
      document_id: "oepa/a.pdf",
      collection: "oepa",
      title: "a.pdf",
      page: 1,
      section: null,
      text: "phosphorus phosphorus effluent limit monthly",
    },
    {
      id: "oepa/b.pdf#p1",
      document_id: "oepa/b.pdf",
      collection: "oepa",
      title: "b.pdf",
      page: 1,
      section: null,
      text: "phosphorus earthwork subtotal",
    },
    {
      id: "oepa/c.pdf#p1",
      document_id: "oepa/c.pdf",
      collection: "oepa",
      title: "c.pdf",
      page: 1,
      section: null,
      text: "nutrient loading nitrogen at the outfall",
    },
  ];
  const EMB: EmbeddingEntry[] = [
    { id: "oepa/a.pdf#p1", embedding: [1, 0] },
    { id: "oepa/b.pdf#p1", embedding: [0, 1] },
    { id: "oepa/c.pdf#p1", embedding: [0.8, 0.6] },
  ];
  const QUERY_VECTOR = [1, 0];

  const hybridPassages: FetchRoute = {
    test: (url) => url.pathname === "/feeds/passages.json",
    respond: () => jsonResponse(200, HYBRID),
  };
  const embeddingsRoute: FetchRoute = {
    test: (url) => url.pathname === "/feeds/passage-embeddings.json",
    respond: () => jsonResponse(200, EMB),
  };

  interface FakeAI {
    calls: Array<{ model: string; text: string[] }>;
    run(model: string, input: { text: string[] }): Promise<{ data: number[][] }>;
  }
  function fakeAI(data: number[][]): FakeAI {
    const calls: FakeAI["calls"] = [];
    return {
      calls,
      run: async (model, input) => {
        calls.push({ model, text: input.text });
        return { data };
      },
    };
  }

  it("fuses vector + BM25 via RRF over passages — the dual-channel page ranks first", async () => {
    const ai = fakeAI([QUERY_VECTOR]);
    const env = await envelope({ query: "phosphorus", max_results: 10 }, { AI: ai }, [
      hybridPassages,
      embeddingsRoute,
    ]);
    const ids = env.results.map((r) => r.id as string);
    expect(ids).toContain("oepa/b.pdf#p1"); // BM25-only
    expect(ids).toContain("oepa/c.pdf#p1"); // vector-only, surfaced by the vector path
    expect(ids[0]).toBe("oepa/a.pdf#p1"); // scored in both channels → RRF first
    // The passage embeddings were fetched (not the ask-embeddings asset) + the query embedded.
    expect(ai.calls).toHaveLength(1);
    expect(ai.calls[0].model).toBe("@cf/sentence-transformers/all-minilm-l6-v2");
    expect(ai.calls[0].text).toEqual(["phosphorus"]);
  });

  it("degrades to BM25-only with no AI binding (no vector-only hit)", async () => {
    const env = await envelope({ query: "phosphorus", max_results: 10 }, {}, [hybridPassages]);
    const ids = env.results.map((r) => r.id as string);
    expect(ids).toContain("oepa/b.pdf#p1");
    expect(ids).not.toContain("oepa/c.pdf#p1");
  });
});
