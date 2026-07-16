// search_corpus response_mode tests (#1580).
// Drives handleSearchCorpus in-process: the handler fetches `/ask-index.json` over
// globalThis.fetch, so each case stubs that route and resets the isolate cache.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetAskIndexCache } from "@watermark/functions/api/_lib/askIndexLoad";
import { handleSearchCorpus } from "@watermark/functions/api/_lib/mcpTools/searchCorpus";
import type { AskUnit } from "@watermark/functions/api/_lib/retrieval";
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
  vi.stubGlobal("fetch", routingFetch([askIndexRoute]));
});

afterEach(() => {
  vi.unstubAllGlobals();
  _resetAskIndexCache();
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
