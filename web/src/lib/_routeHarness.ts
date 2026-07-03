// Test-only helpers for driving the Cloudflare Pages Function handlers
// (functions/api/{submit,ask,doc/[[path]]}) in-process under vitest — the "Tier A"
// integration layer (no wrangler, no network). The handlers take `env` as a parameter and
// reach every external (GitHub, Anthropic, Turnstile) + same-origin asset over
// `globalThis.fetch`, so a test constructs a Request, passes a faked `Env`, and stubs
// `fetch` with `routingFetch` to intercept exactly the routes it cares about. Node 24
// supplies the Web globals the handlers use (fetch/Request/Response/FormData/URL/crypto).
//
// Underscore-prefixed so it's never mistaken for a routed Function; lives in src/lib (not
// functions/) so vitest + Biome + astro-check all see it without entering the Workers tree.

import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import type { KVLike } from "@fn/api/_lib/ratelimit";
import type { D1Like, D1PreparedStatement, D1Result } from "@fn/api/_lib/storiesStore";

/** A `fetch`-compatible response carrying JSON. */
export function jsonResponse(status: number, data: unknown, headers?: Record<string, string>): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

/** Build a POST Request with a JSON body (the shape submit/ask receive). */
export function postJson(url: string, body: unknown, headers?: Record<string, string>): Request {
  return new Request(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
}

/** One route the stubbed `fetch` knows how to answer. */
export interface FetchRoute {
  /** Match by parsed URL + uppercased method. */
  test: (url: URL, method: string) => boolean;
  /** Produce the response (the request body is intentionally not surfaced — no route needs it). */
  respond: (url: URL, method: string) => Response | Promise<Response>;
}

/** A stubbed `globalThis.fetch` that dispatches to `routes` and records every call. */
export interface RoutingFetch {
  (input: RequestInfo | URL, init?: RequestInit): Promise<Response>;
  /**
   * Every call seen, in order — assert "the model was never called", count retries, or
   * inspect the request `body` (captured when it's a string, which is all the handlers send).
   */
  calls: Array<{ url: string; method: string; body?: string }>;
}

/**
 * Dispatch `fetch` by URL + method. An unmatched call **throws** rather than hitting the
 * network, so a test that forgets to stub (e.g.) the Anthropic route fails loudly instead
 * of silently reaching out. Install with `vi.stubGlobal("fetch", routingFetch([...]))`.
 */
export function routingFetch(routes: FetchRoute[]): RoutingFetch {
  const calls: RoutingFetch["calls"] = [];
  const impl = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const href =
      typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url;
    const url = new URL(href);
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const body = typeof init?.body === "string" ? init.body : undefined;
    calls.push({ url: url.href, method, body });
    for (const r of routes) if (r.test(url, method)) return r.respond(url, method);
    throw new Error(`routingFetch: unmatched ${method} ${url.href}`);
  };
  return Object.assign(impl, { calls });
}

/** In-memory KV implementing `KVLike`. Exposes `store` for seeding/inspection. TTL is recorded, not enforced (no test spans a window). */
export interface FakeKV extends KVLike {
  store: Map<string, string>;
  puts: Array<{ key: string; value: string; expirationTtl?: number }>;
}

export function fakeKV(seed?: Record<string, string>): FakeKV {
  const store = new Map<string, string>(seed ? Object.entries(seed) : []);
  const puts: FakeKV["puts"] = [];
  return {
    store,
    puts,
    get: async (key) => store.get(key) ?? null,
    put: async (key, value, options) => {
      store.set(key, value);
      puts.push({ key, value, expirationTtl: options?.expirationTtl });
    },
  };
}

/** A stored object for the fake R2 bucket. */
export interface FakeR2File {
  bytes: Uint8Array;
  contentType?: string;
  /** Surfaced as `customMetadata["media-type"]` (what docContentType prefers). */
  mediaType?: string;
}

/**
 * In-memory R2 bucket matching the minimal `{head, get}` surface the /api/doc route binds
 * (functions/api/doc/[[path]].ts). `get` honors the `range` option so the 206/ranged path
 * is exercised against real byte slices.
 */
export function fakeR2(files: Record<string, FakeR2File>) {
  const meta = (key: string, file: FakeR2File) => ({
    size: file.bytes.byteLength,
    httpEtag: `"${key}:${file.bytes.byteLength}"`,
    httpMetadata: file.contentType ? { contentType: file.contentType } : undefined,
    customMetadata: file.mediaType ? { "media-type": file.mediaType } : undefined,
  });
  const stream = (bytes: Uint8Array): ReadableStream =>
    new ReadableStream({
      start(c) {
        c.enqueue(bytes);
        c.close();
      },
    });
  return {
    head: async (key: string) => {
      const file = files[key];
      return file ? meta(key, file) : null;
    },
    get: async (key: string, options?: { range?: { offset: number; length?: number } }) => {
      const file = files[key];
      if (!file) return null;
      const slice = options?.range
        ? file.bytes.subarray(
            options.range.offset,
            options.range.offset + (options.range.length ?? file.bytes.byteLength),
          )
        : file.bytes;
      return { ...meta(key, file), body: stream(slice) };
    },
  };
}

/**
 * Generate a throwaway PKCS#8 RSA private-key PEM so the submit route's real GitHub-App
 * JWT signing path (functions/api/_lib/github.ts → crypto.subtle) runs for real in tests —
 * the GitHub fetches are stubbed, so the JWT is never verified, only minted.
 */
export async function generatePkcs8Pem(): Promise<string> {
  const { privateKey } = await crypto.subtle.generateKey(
    {
      name: "RSASSA-PKCS1-v1_5",
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: "SHA-256",
    },
    true,
    ["sign", "verify"],
  );
  const der = new Uint8Array(await crypto.subtle.exportKey("pkcs8", privateKey));
  let bin = "";
  for (const b of der) bin += String.fromCharCode(b);
  const body = (btoa(bin).match(/.{1,64}/g) ?? []).join("\n");
  return `-----BEGIN PRIVATE KEY-----\n${body}\n-----END PRIVATE KEY-----\n`;
}

// ---------------------------------------------------------------------------
// Cognito test-JWT helpers (Epic #920 B3)
// ---------------------------------------------------------------------------

export interface CognitoTestKeyPair {
  privateKey: CryptoKey;
  kid: string;
  /** The JWK public key — serve from a fake /.well-known/jwks.json route. */
  jwk: { kid: string; kty: string; alg: string; use: string; n: string; e: string };
}

/** Generate an RS256 key pair and the matching JWK for a fake Cognito JWKS endpoint. */
export async function generateCognitoKeyPair(): Promise<CognitoTestKeyPair> {
  const kid = "test-cognito-kid";
  const pair = await crypto.subtle.generateKey(
    {
      name: "RSASSA-PKCS1-v1_5",
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: "SHA-256",
    },
    true,
    ["sign", "verify"],
  );
  const pub = await crypto.subtle.exportKey("jwk", pair.publicKey);
  return {
    privateKey: pair.privateKey,
    kid,
    jwk: { kid, kty: "RSA", alg: "RS256", use: "sig", n: pub.n as string, e: pub.e as string },
  };
}

function b64url(obj: unknown): string {
  return btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

/** Mint a signed Cognito ID token for use in Authorization: Bearer tests. */
export async function mintIdToken(
  keypair: CognitoTestKeyPair,
  claims: {
    sub: string;
    email: string;
    clientId: string;
    userPoolId: string;
    region: string;
    groups?: string[];
    /** Seconds from now; default 3600. */
    expiresIn?: number;
  },
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const header = b64url({ kid: keypair.kid, alg: "RS256" });
  const payload = b64url({
    sub: claims.sub,
    email: claims.email,
    email_verified: true,
    aud: claims.clientId,
    iss: `https://cognito-idp.${claims.region}.amazonaws.com/${claims.userPoolId}`,
    exp: now + (claims.expiresIn ?? 3600),
    iat: now,
    token_use: "id",
    "cognito:groups": claims.groups ?? [],
  });
  const signed = new TextEncoder().encode(`${header}.${payload}`);
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", keypair.privateKey, signed);
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
  return `${header}.${payload}.${sigB64}`;
}

// ---------------------------------------------------------------------------
// Fake D1 for the Story store (Epic #1090 / #1095)
// ---------------------------------------------------------------------------
// An in-memory D1 backed by Node 24's built-in `node:sqlite` — real SQL + real transactions, so
// the store's `batch()` atomicity, FK cascade, and unique-constraint behavior are exercised for
// real (not mocked). The schema is the committed migration, so a schema/store drift fails a test.

const MIGRATION_PATH = fileURLToPath(new URL("../../migrations/0001_create_stories.sql", import.meta.url));

/** A D1Like whose `raw` handle is exposed for direct seeding/inspection in a test. */
export interface FakeD1 extends D1Like {
  raw: DatabaseSync;
}

function d1Statement(db: DatabaseSync, sql: string): D1PreparedStatement {
  let params: unknown[] = [];
  const api: D1PreparedStatement = {
    bind: (...values: unknown[]) => {
      params = values;
      return api;
    },
    first: async <T = unknown>() => {
      const row = db.prepare(sql).get(...(params as never[]));
      return (row ?? null) as T | null;
    },
    all: async <T = unknown>() => {
      const rows = db.prepare(sql).all(...(params as never[]));
      return { results: rows as T[], success: true } satisfies D1Result<T>;
    },
    run: async () => {
      const r = db.prepare(sql).run(...(params as never[]));
      return { success: true, meta: { changes: Number(r.changes) } } satisfies D1Result;
    },
  };
  return api;
}

/** Build an in-memory D1 with the Stories schema applied (FK enforcement on). */
export function fakeD1(): FakeD1 {
  const db = new DatabaseSync(":memory:");
  db.exec("PRAGMA foreign_keys = ON;");
  db.exec(readFileSync(MIGRATION_PATH, "utf-8"));
  return {
    raw: db,
    prepare: (sql: string) => d1Statement(db, sql),
    // node:sqlite has no async transaction API; emulate D1's atomic batch with BEGIN/COMMIT and
    // ROLLBACK on any statement error, so a failed ref-insert rolls the whole write back.
    batch: async (statements: D1PreparedStatement[]) => {
      db.exec("BEGIN;");
      try {
        const out: D1Result[] = [];
        for (const s of statements) out.push(await s.run());
        db.exec("COMMIT;");
        return out;
      } catch (e) {
        db.exec("ROLLBACK;");
        throw e;
      }
    },
  };
}
