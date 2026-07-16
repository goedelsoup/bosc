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

async function call(args: Record<string, unknown>): Promise<unknown[]> {
  const content = await handleSearchCorpus(args, REQ);
  return JSON.parse(content[0].text) as unknown[];
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
