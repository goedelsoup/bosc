// Tier A integration test for the /api/doc/<rel> Pages Function
// (functions/api/doc/[[path]].ts): drive the exported `onRequest` with a faked R2 binding
// + a stubbed `fetch` for the publish allowlist. Covers the wiring the pure docServe.test.ts
// leaves out: the method/kill-switch/binding gates, path resolution, the production publish
// gate (allowlist 404), and HEAD / full-GET / ranged-206 / 416 byte serving against real
// in-memory bytes.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetPublishedCache } from "@watermark/functions/api/_lib/docAllowlist";
import { onRequest } from "@watermark/functions/api/doc/[[path]]";
import { type FetchRoute, fakeR2, jsonResponse, routingFetch } from "./_routeHarness";

const KEY = "recorder/deeds/2019-deed.pdf";
const DOC_URL = `https://bosc.test/api/doc/${KEY}`;
const BYTES = new TextEncoder().encode("ABCDEFGHIJKLMNOPQRSTUVWXYZ"); // 26 bytes

const docs = () => fakeR2({ [KEY]: { bytes: BYTES, contentType: "application/pdf" } });

const get = (headers?: Record<string, string>) => new Request(DOC_URL, { method: "GET", headers });

const publishedRoute = (rels: string[]): FetchRoute => ({
  test: (url) => url.pathname === "/published-documents.json",
  respond: () => jsonResponse(200, { rels }),
});

// dev-mode env (no publish gate): serves the whole corpus, like `wrangler pages dev`.
const devEnv = (overrides: Record<string, unknown> = {}) => ({
  DOCS_ENABLED: "true",
  DOCS: docs(),
  ...overrides,
});

const call = (request: Request, env: unknown, path: string | string[] = KEY) =>
  onRequest({ request, env, params: { path } } as never);

beforeEach(() => {
  _resetPublishedCache();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("/api/doc route", () => {
  it("405s on a non-GET/HEAD method", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(new Request(DOC_URL, { method: "POST" }), devEnv());
    expect(res.status).toBe(405);
  });

  it("405s on OPTIONS (no preflight handler — non-GET/HEAD)", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(new Request(DOC_URL, { method: "OPTIONS" }), devEnv());
    expect(res.status).toBe(405);
  });

  it("503s when the kill switch is off", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(get(), { DOCS: docs() });
    expect(res.status).toBe(503);
  });

  it("500s when no R2 bucket is bound", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(get(), { DOCS_ENABLED: "true" });
    expect(res.status).toBe(500);
  });

  it("400s on a traversal/invalid path", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(get(), devEnv(), "../../etc/passwd");
    expect(res.status).toBe(400);
  });

  it("serves a full object (200) with inline + nosniff headers in dev mode", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(get(), devEnv());
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("application/pdf");
    expect(res.headers.get("content-length")).toBe(String(BYTES.byteLength));
    expect(res.headers.get("content-disposition")).toBe("inline");
    expect(res.headers.get("x-content-type-options")).toBe("nosniff");
    expect(new Uint8Array(await res.arrayBuffer())).toEqual(BYTES);
  });

  it("answers HEAD with metadata and no body", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(new Request(DOC_URL, { method: "HEAD" }), devEnv());
    expect(res.status).toBe(200);
    expect(res.headers.get("content-length")).toBe(String(BYTES.byteLength));
    expect((await res.arrayBuffer()).byteLength).toBe(0);
  });

  it("serves a satisfiable byte range as 206", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(get({ Range: "bytes=0-3" }), devEnv());
    expect(res.status).toBe(206);
    expect(res.headers.get("content-range")).toBe(`bytes 0-3/${BYTES.byteLength}`);
    expect(res.headers.get("content-length")).toBe("4");
    expect(new TextDecoder().decode(await res.arrayBuffer())).toBe("ABCD");
  });

  it("416s an unsatisfiable range", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(get({ Range: "bytes=100-200" }), devEnv());
    expect(res.status).toBe(416);
    expect(res.headers.get("content-range")).toBe(`bytes */${BYTES.byteLength}`);
  });

  it("404s when the object is absent", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const res = await call(
      new Request("https://bosc.test/api/doc/recorder/nope.pdf", { method: "GET" }),
      devEnv(),
      "recorder/nope.pdf",
    );
    expect(res.status).toBe(404);
  });

  it("falls back to the media-type metadata for Content-Type", async () => {
    vi.stubGlobal("fetch", routingFetch([]));
    const env = { DOCS_ENABLED: "true", DOCS: fakeR2({ [KEY]: { bytes: BYTES, mediaType: "text/html" } }) };
    const res = await call(get(), env);
    expect(res.headers.get("content-type")).toBe("text/html");
  });

  describe("production publish gate (DOCS_PUBLIC_GATE on)", () => {
    it("404s a key absent from the allowlist", async () => {
      vi.stubGlobal("fetch", routingFetch([publishedRoute(["recorder/other.pdf"])]));
      const res = await call(get(), devEnv({ DOCS_PUBLIC_GATE: "on" }));
      expect(res.status).toBe(404);
    });

    it("serves a key present in the allowlist", async () => {
      vi.stubGlobal("fetch", routingFetch([publishedRoute([KEY])]));
      const res = await call(get(), devEnv({ DOCS_PUBLIC_GATE: "on" }));
      expect(res.status).toBe(200);
    });

    it("fails closed (503) when the allowlist asset is unavailable", async () => {
      vi.stubGlobal(
        "fetch",
        routingFetch([
          {
            test: (url) => url.pathname === "/published-documents.json",
            respond: () => new Response("nope", { status: 500 }),
          },
        ]),
      );
      const res = await call(get(), devEnv({ DOCS_PUBLIC_GATE: "on" }));
      expect(res.status).toBe(503);
    });

    it("enforces the gate on the production branch (CF_PAGES_BRANCH=main, no override)", async () => {
      // No DOCS_PUBLIC_GATE override — the gate turns on purely from the branch, and the
      // allowlist (which omits KEY) 404s it. Exercises the branch-driven gate path.
      const fetchStub = routingFetch([publishedRoute(["recorder/other.pdf"])]);
      vi.stubGlobal("fetch", fetchStub);
      const res = await call(get(), devEnv({ CF_PAGES_BRANCH: "main" }));
      expect(res.status).toBe(404);
      expect(fetchStub.calls.some((c) => c.url.includes("/published-documents.json"))).toBe(true);
    });

    it('the DOCS_PUBLIC_GATE="off" override serves a non-allowlisted key, even on main', async () => {
      // Operator escape hatch: gate explicitly off ⇒ no allowlist fetch, serve everything.
      const fetchStub = routingFetch([]); // any allowlist fetch would throw (unmatched)
      vi.stubGlobal("fetch", fetchStub);
      const res = await call(get(), devEnv({ CF_PAGES_BRANCH: "main", DOCS_PUBLIC_GATE: "off" }));
      expect(res.status).toBe(200);
      expect(fetchStub.calls.some((c) => c.url.includes("/published-documents.json"))).toBe(false);
    });
  });
});
