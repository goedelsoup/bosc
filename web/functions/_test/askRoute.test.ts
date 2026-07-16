// Tier A integration test for the /api/ask Pages Function (functions/api/ask.ts): drive
// the exported `onRequestPost` end-to-end with a faked Env + a stubbed `fetch`. Covers the
// wiring the pure-`_lib` suites (ask.test.ts, askRetrieval.test.ts, askStream.test.ts)
// leave out: the kill-switch/misconfig gates, the deterministic no-model refusal, both the
// JSON and SSE answer paths (real retrieval + real stream parsing), and the rate-limit /
// daily-budget guards — all offline, no Anthropic spend. Exercises the ANTHROPIC_API_BASE
// seam by pointing the model call at a stubbed host.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetAskIndexCache } from "@watermark/functions/api/_lib/askIndexLoad";
import { dayKey } from "@watermark/functions/api/_lib/budget";
import { windowKey } from "@watermark/functions/api/_lib/ratelimit";
import type { AskUnit } from "@watermark/functions/api/_lib/retrieval";
import { onRequestPost } from "@watermark/functions/api/ask";
import { type FetchRoute, fakeKV, jsonResponse, postJson, routingFetch } from "./_routeHarness";

const ASK_URL = "https://bosc.test/api/ask";
const ANTHROPIC_API_BASE = "https://anthropic.test/v1/messages";

const ASK_INDEX: AskUnit[] = [
  {
    id: "records:opc-1",
    feed: "records",
    title: "Roundabout OPC estimate",
    url: "/network/x/records/opc-1",
    text: "Tetra Tech opinion of probable cost for the roundabout at SR-309. Total $1,234,567.",
    source: "PRR-01-bundle.ocr.pdf",
    page: 318,
    verified: true,
  },
  {
    id: "timeline:npdes",
    feed: "timeline",
    title: "NPDES permit issued",
    url: "/network/x/timeline/npdes",
    text: "Ohio EPA issued an NPDES permit for the wastewater outfall in 2019.",
    source: "eDoc-555",
    page: 2,
    verified: true,
  },
];

const askIndexRoute: FetchRoute = {
  test: (url) => url.pathname === "/ask-index.json",
  respond: () => jsonResponse(200, ASK_INDEX),
};

const turnstileRoute = (success: boolean): FetchRoute => ({
  test: (url) => url.pathname === "/turnstile/v0/siteverify",
  respond: () => jsonResponse(200, { success }),
});

const anthropicJsonRoute = (text: string): FetchRoute => ({
  test: (url) => url.pathname === "/v1/messages",
  respond: () =>
    jsonResponse(200, {
      content: [{ type: "text", text }],
      usage: { input_tokens: 50, output_tokens: 12 },
      stop_reason: "end_turn",
    }),
});

// A well-formed Anthropic SSE body so the route's real streamMessage/drainSse/mapAnthropicEvent
// path runs against actual bytes.
const anthropicSseRoute = (text: string): FetchRoute => ({
  test: (url) => url.pathname === "/v1/messages",
  respond: () => {
    const enc = new TextEncoder();
    const events: Array<[string, unknown]> = [
      [
        "message_start",
        { type: "message_start", message: { usage: { input_tokens: 50, output_tokens: 0 } } },
      ],
      ["content_block_delta", { type: "content_block_delta", index: 0, delta: { type: "text_delta", text } }],
      ["message_delta", { type: "message_delta", usage: { output_tokens: 12 } }],
      ["message_stop", { type: "message_stop" }],
    ];
    const body = new ReadableStream({
      start(c) {
        for (const [ev, data] of events)
          c.enqueue(enc.encode(`event: ${ev}\ndata: ${JSON.stringify(data)}\n\n`));
        c.close();
      },
    });
    return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
  },
});

function askEnv(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    ASK_ENABLED: "true",
    ANTHROPIC_API_KEY: "sk-ant-test",
    TURNSTILE_SECRET_KEY: "1x0000000000000000000000000000000AA",
    ANTHROPIC_API_BASE,
    // The suite runs without a KV binding; opt into the uncapped path explicitly so the
    // fail-closed guard (#587) doesn't 503 every test. The dedicated guard test omits this.
    ASK_ALLOW_UNCAPPED: "true",
    ...overrides,
  };
}

const ask = (body: unknown, headers?: Record<string, string>) => postJson(ASK_URL, body, headers);

async function readStream(res: Response): Promise<string> {
  const reader = (res.body as ReadableStream).getReader();
  const dec = new TextDecoder();
  let out = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    out += dec.decode(value, { stream: true });
  }
  return out;
}

beforeEach(() => {
  _resetAskIndexCache();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("/api/ask route", () => {
  it("503s when the kill switch is off", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({ request: ask({ question: "anything here" }), env: {} } as never);
    expect(res.status).toBe(503);
  });

  it("500s when misconfigured (no API key / Turnstile secret)", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({
      request: ask({ question: "anything here" }),
      env: { ASK_ENABLED: "true" },
    } as never);
    expect(res.status).toBe(500);
  });

  it("400s on a too-short question", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await onRequestPost({ request: ask({ question: "hi" }), env: askEnv() } as never);
    expect(res.status).toBe(400);
  });

  it("403s when no Turnstile token is supplied (no model call)", async () => {
    const fetchStub = routingFetch([askIndexRoute, anthropicJsonRoute("x")]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?" }),
      env: askEnv(),
    } as never);
    expect(res.status).toBe(403);
    expect(fetchStub.calls.some((c) => c.url.includes("/v1/messages"))).toBe(false);
  });

  it("403s when Turnstile verification fails", async () => {
    vi.stubGlobal("fetch", routingFetch([turnstileRoute(false), askIndexRoute]));
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: askEnv(),
    } as never);
    expect(res.status).toBe(403);
  });

  it("refuses deterministically (no model call) when retrieval is empty", async () => {
    const fetchStub = routingFetch([
      turnstileRoute(true),
      askIndexRoute,
      anthropicJsonRoute("should not run"),
    ]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "bananas pajamas xyzzy quux", turnstile_token: "tok" }),
      env: askEnv(),
    } as never);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.refused).toBe(true);
    expect(data.citations).toEqual([]);
    expect(fetchStub.calls.some((c) => c.url.includes("/v1/messages"))).toBe(false);
  });

  it("answers (non-streaming) with citations, honoring ANTHROPIC_API_BASE", async () => {
    const answer = "The roundabout opinion of probable cost totals $1,234,567 [1].";
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute, anthropicJsonRoute(answer)]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: askEnv(),
    } as never);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.answer).toBe(answer);
    expect(data.refused).toBe(false);
    expect(data.model).toBe("claude-opus-4-8");
    expect(data.citations).toHaveLength(1);
    expect(data.citations[0].id).toBe("records:opc-1");
    expect(fetchStub.calls.some((c) => c.url === ANTHROPIC_API_BASE)).toBe(true);
  });

  it("streams meta/delta/done frames over SSE", async () => {
    const answer = "The estimate totals $1,234,567 [1].";
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute, anthropicSseRoute(answer)]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask(
        { question: "what is the roundabout cost?", turnstile_token: "tok" },
        { Accept: "text/event-stream" },
      ),
      env: askEnv(),
    } as never);
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const out = await readStream(res);
    expect(out).toContain("event: meta");
    expect(out).toContain("event: delta");
    expect(out).toContain("event: done");
    expect(out).toContain("$1,234,567");
    expect(out).toContain('"refused":false');
  });

  it("streams a refusal (meta searched:0, no model call) over SSE when retrieval is empty", async () => {
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask(
        { question: "bananas pajamas xyzzy quux", turnstile_token: "tok" },
        { Accept: "text/event-stream" },
      ),
      env: askEnv(),
    } as never);
    const out = await readStream(res);
    expect(out).toContain('"searched":0');
    expect(out).toContain('"refused":true');
    expect(fetchStub.calls.some((c) => c.url.includes("/v1/messages"))).toBe(false);
  });

  it("429s (before Turnstile) when the per-IP window is exhausted", async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const ip = "203.0.113.7";
    const kv = fakeKV({ [windowKey(ip, Math.floor(fixedMs / 1000), 3600)]: "10" }); // default ask max = 10
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask(
        { question: "what is the roundabout cost?", turnstile_token: "tok" },
        { "CF-Connecting-IP": ip },
      ),
      env: askEnv({ ASK_RATE_LIMIT: kv }),
    } as never);
    expect(res.status).toBe(429);
    expect(fetchStub.calls.some((c) => c.url.includes("/siteverify"))).toBe(false);
  });

  it("503s when the daily token budget is exhausted", async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const ip = "203.0.113.8";
    const kv = fakeKV({ [dayKey(fixedMs)]: "999999" }); // > default 200k budget
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask(
        { question: "what is the roundabout cost?", turnstile_token: "tok" },
        { "CF-Connecting-IP": ip },
      ),
      env: askEnv({ ASK_RATE_LIMIT: kv }),
    } as never);
    expect(res.status).toBe(503);
    expect(fetchStub.calls.some((c) => c.url.includes("/v1/messages"))).toBe(false);
  });

  // --- #587: fail-closed when uncapped -----------------------------------------------------
  it("503s (fail-closed) when no budget KV is bound and uncapped isn't allowed", async () => {
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      // No ASK_RATE_LIMIT / ASK_BUDGET KV, and the uncapped escape hatch withdrawn.
      env: askEnv({ ASK_ALLOW_UNCAPPED: undefined }),
    } as never);
    expect(res.status).toBe(503);
    // Refused before any paid call OR Turnstile verification.
    expect(fetchStub.calls.some((c) => c.url.includes("/v1/messages"))).toBe(false);
    expect(fetchStub.calls.some((c) => c.url.includes("/siteverify"))).toBe(false);
  });

  it("enforces the daily budget on its own KV, independent of per-IP limiting (#587)", async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const budgetKv = fakeKV({ [dayKey(fixedMs)]: "999999" }); // > default 200k
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      // Only the budget KV is bound — no ASK_RATE_LIMIT — yet the budget still gates.
      env: askEnv({ ASK_BUDGET: budgetKv }),
    } as never);
    expect(res.status).toBe(503);
    expect(fetchStub.calls.some((c) => c.url.includes("/v1/messages"))).toBe(false);
  });

  // --- #588: a configured "0" is honored, not coerced back to the default ------------------
  it('treats ASK_DAILY_TOKEN_BUDGET="0" as a hard stop (not the 200k default)', async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const kv = fakeKV({}); // zero spend recorded
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: askEnv({ ASK_RATE_LIMIT: kv, ASK_DAILY_TOKEN_BUDGET: "0" }),
    } as never);
    expect(res.status).toBe(503); // 0 budget ⇒ over budget even with no spend
    expect(fetchStub.calls.some((c) => c.url.includes("/v1/messages"))).toBe(false);
  });

  it('treats ASK_RATE_LIMIT_MAX="0" as block-all (not the default 10)', async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const ip = "203.0.113.9";
    const kv = fakeKV({}); // no prior requests
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask(
        { question: "what is the roundabout cost?", turnstile_token: "tok" },
        { "CF-Connecting-IP": ip },
      ),
      env: askEnv({ ASK_RATE_LIMIT: kv, ASK_RATE_LIMIT_MAX: "0" }),
    } as never);
    expect(res.status).toBe(429); // 0 allowed ⇒ first request already over
  });

  // --- #592: previously-untested failure + accounting branches ----------------------------
  it("500s when the ask-index asset can't be loaded", async () => {
    const askIndex500: FetchRoute = {
      test: (url) => url.pathname === "/ask-index.json",
      respond: () => new Response("nope", { status: 500 }),
    };
    const fetchStub = routingFetch([turnstileRoute(true), askIndex500]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: askEnv(),
    } as never);
    expect(res.status).toBe(500);
  });

  it("502s (non-streaming) when the model call fails", async () => {
    const anthropic500: FetchRoute = {
      test: (url) => url.pathname === "/v1/messages",
      respond: () => jsonResponse(500, { error: { message: "upstream boom" } }),
    };
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute, anthropic500]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: askEnv(),
    } as never);
    expect(res.status).toBe(502);
  });

  it("emits an SSE error frame when the stream fails to start", async () => {
    const anthropic500: FetchRoute = {
      test: (url) => url.pathname === "/v1/messages",
      respond: () => new Response("boom", { status: 500 }),
    };
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute, anthropic500]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask(
        { question: "what is the roundabout cost?", turnstile_token: "tok" },
        { Accept: "text/event-stream" },
      ),
      env: askEnv(),
    } as never);
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const out = await readStream(res);
    expect(out).toContain("event: meta"); // the pre-answer frame always ships first
    expect(out).toContain("event: error"); // …then the failure is relayed, not thrown
  });

  it("records the answer's total tokens (input + output) against the daily budget (addUsage)", async () => {
    const fixedMs = 1_750_000_000_000;
    vi.spyOn(Date, "now").mockReturnValue(fixedMs);
    const budgetKv = fakeKV({}); // no prior spend
    const answer = "The estimate totals $1,234,567 [1].";
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute, anthropicJsonRoute(answer)]);
    vi.stubGlobal("fetch", fetchStub);
    const res = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: askEnv({ ASK_BUDGET: budgetKv }),
    } as never);
    expect(res.status).toBe(200);
    // anthropicJsonRoute reports { input_tokens: 50, output_tokens: 12 } → counter increments by 62.
    expect(budgetKv.store.get(dayKey(fixedMs))).toBe("62");
  });

  // --- #332: answer cache -------------------------------------------------------------------

  // In-memory Cache API stub — mirrors the Workers Cache API surface used by the route.
  // The route calls `caches.open("ask-answers")`, so we stub `open` returning a cache object.
  function fakeAnswerCache() {
    const store = new Map<string, Response>();
    const cache = {
      match: async (req: Request) => store.get(req.url)?.clone(),
      put: async (req: Request, res: Response) => {
        store.set(req.url, res.clone());
      },
    };
    return { open: async (_name: string) => cache };
  }

  // Collect waitUntil promises and flush them synchronously so cache.put completes in tests.
  function makeWaitUntil() {
    const pending: Array<Promise<unknown>> = [];
    const waitUntil = (p: Promise<unknown>) => {
      pending.push(p);
    };
    const flush = () => Promise.all(pending);
    return { waitUntil, flush };
  }

  it("serves a cached JSON answer on a repeated question (no model call on cache hit)", async () => {
    vi.stubGlobal("caches", fakeAnswerCache());
    const answer = "The estimate totals $1,234,567 [1].";
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute, anthropicJsonRoute(answer)]);
    vi.stubGlobal("fetch", fetchStub);
    const wu = makeWaitUntil();

    // First request — populates the cache.
    const r1 = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: askEnv(),
      waitUntil: wu.waitUntil,
    } as never);
    expect(r1.status).toBe(200);
    await wu.flush(); // ensure cache.put completes

    // Second request — Turnstile still runs (abuse gate), but model + index are skipped.
    const _callsBefore = fetchStub.calls.length;
    const r2 = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok2" }),
      env: askEnv(),
      waitUntil: wu.waitUntil,
    } as never);
    expect(r2.status).toBe(200);
    const body = (await r2.json()) as { answer: string; refused: boolean };
    expect(body.answer).toContain("$1,234,567");
    expect(body.refused).toBe(false);
    // +1 for Turnstile verify; no index load or model call on a cache hit.
    expect(fetchStub.calls.filter((c) => c.url.includes("/siteverify")).length).toBe(2);
    expect(fetchStub.calls.filter((c) => c.url.includes("/v1/messages")).length).toBe(1);
  });

  it("serves a cached answer as SSE on a streaming cache hit", async () => {
    vi.stubGlobal("caches", fakeAnswerCache());
    const answer = "The estimate totals $1,234,567 [1].";
    const fetchStub = routingFetch([turnstileRoute(true), askIndexRoute, anthropicSseRoute(answer)]);
    vi.stubGlobal("fetch", fetchStub);
    const wu = makeWaitUntil();

    // First request (streaming) — populates the cache.
    const r1 = await onRequestPost({
      request: ask(
        { question: "what is the roundabout cost?", turnstile_token: "tok" },
        { Accept: "text/event-stream" },
      ),
      env: askEnv(),
      waitUntil: wu.waitUntil,
    } as never);
    expect(r1.headers.get("content-type")).toContain("text/event-stream");
    await readStream(r1); // drain
    await wu.flush();

    // Second streaming request — served from cache.
    const _callsBefore = fetchStub.calls.length;
    const r2 = await onRequestPost({
      request: ask(
        { question: "  What Is the ROUNDABOUT cost? ", turnstile_token: "tok2" },
        { Accept: "text/event-stream" },
      ),
      env: askEnv(),
      waitUntil: wu.waitUntil,
    } as never);
    expect(r2.headers.get("content-type")).toContain("text/event-stream");
    const out = await readStream(r2);
    expect(out).toContain("event: meta");
    expect(out).toContain("event: delta");
    expect(out).toContain("event: done");
    expect(out).toContain("$1,234,567");
    // Turnstile still runs on a cache hit; model + index are skipped.
    expect(fetchStub.calls.filter((c) => c.url.includes("/siteverify")).length).toBe(2);
    expect(fetchStub.calls.filter((c) => c.url.includes("/v1/messages")).length).toBe(1);
  });

  it("bypasses the cache when ASK_CACHE_MAX_AGE=0", async () => {
    vi.stubGlobal("caches", fakeAnswerCache());
    const answer = "The estimate totals $1,234,567 [1].";
    const fetchStub = routingFetch([
      turnstileRoute(true),
      askIndexRoute,
      anthropicJsonRoute(answer),
      turnstileRoute(true),
      askIndexRoute,
      anthropicJsonRoute(answer),
    ]);
    vi.stubGlobal("fetch", fetchStub);
    const wu = makeWaitUntil();

    const opts = askEnv({ ASK_CACHE_MAX_AGE: "0" });
    const r1 = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok" }),
      env: opts,
      waitUntil: wu.waitUntil,
    } as never);
    await wu.flush();
    expect(r1.status).toBe(200);

    // Second request — cache disabled so model must be called again.
    const modelCallsBefore = fetchStub.calls.filter((c) => c.url.includes("/v1/messages")).length;
    const r2 = await onRequestPost({
      request: ask({ question: "what is the roundabout cost?", turnstile_token: "tok2" }),
      env: opts,
      waitUntil: wu.waitUntil,
    } as never);
    expect(r2.status).toBe(200);
    expect(fetchStub.calls.filter((c) => c.url.includes("/v1/messages")).length).toBe(modelCallsBefore + 1);
  });
});
