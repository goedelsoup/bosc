// Unit tests for the MCP auth middleware (#916).
// Drives verifyToken() directly (no HTTP handler wiring needed — pure logic over KVLike).

import { describe, expect, it } from "vitest";
import { verifyToken } from "@watermark/functions/api/_lib/mcpAuth";
import type { KVLike } from "@watermark/functions/api/_lib/ratelimit";

function fakeKV(seed: Record<string, string> = {}): KVLike {
  const store = new Map(Object.entries(seed));
  return {
    get: (k) => Promise.resolve(store.get(k) ?? null),
    put: (k, v) => {
      store.set(k, v);
      return Promise.resolve();
    },
  };
}

function bearerRequest(token?: string): Request {
  const headers: Record<string, string> = {};
  if (token !== undefined) headers.authorization = `Bearer ${token}`;
  return new Request("https://example.com/api/mcp", { method: "POST", headers });
}

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

describe("verifyToken — public tier", () => {
  it("returns public when no Authorization header is present", async () => {
    const result = await verifyToken(new Request("https://example.com/api/mcp"), {});
    expect(result).toEqual({ tier: "public" });
  });

  it("returns public when MCP_KEYS is not bound (keys not provisioned)", async () => {
    const result = await verifyToken(bearerRequest("any-token"), {});
    expect(result).toEqual({ tier: "public" });
  });
});

describe("verifyToken — cognito tier", () => {
  it("returns cognito tier for a valid, non-revoked key", async () => {
    const token = "valid-secret-key-abc";
    const hash = await sha256Hex(token);
    const kv = fakeKV({
      [`key:${hash}`]: JSON.stringify({
        owner: "researcher@example.com",
        tier: "cognito",
        created_at: "2026-06-29T00:00:00Z",
        revoked: false,
      }),
    });
    const result = await verifyToken(bearerRequest(token), { MCP_KEYS: kv });
    expect(result).toEqual({ tier: "cognito", keyHash: hash, owner: "researcher@example.com" });
  });

  it("returns revoked error for a revoked key", async () => {
    const token = "revoked-key";
    const hash = await sha256Hex(token);
    const kv = fakeKV({
      [`key:${hash}`]: JSON.stringify({
        owner: "bad-actor@example.com",
        tier: "cognito",
        created_at: "2026-06-01T00:00:00Z",
        revoked: true,
      }),
    });
    const result = await verifyToken(bearerRequest(token), { MCP_KEYS: kv });
    expect(result).toEqual({ error: "revoked" });
  });

  it("returns invalid_token for an unknown token", async () => {
    const kv = fakeKV(); // empty — no registered keys
    const result = await verifyToken(bearerRequest("unknown-token"), { MCP_KEYS: kv });
    expect(result).toEqual({ error: "invalid_token" });
  });

  it("returns invalid_token for a malformed Authorization header (not Bearer)", async () => {
    const req = new Request("https://example.com/api/mcp", {
      headers: { authorization: "Basic dXNlcjpwYXNz" },
    });
    const result = await verifyToken(req, { MCP_KEYS: fakeKV() });
    expect(result).toEqual({ error: "invalid_token" });
  });

  it("returns invalid_token when KV returns corrupt JSON", async () => {
    const token = "corrupt-entry";
    const hash = await sha256Hex(token);
    const kv = fakeKV({ [`key:${hash}`]: "{{not valid json" });
    const result = await verifyToken(bearerRequest(token), { MCP_KEYS: kv });
    expect(result).toEqual({ error: "invalid_token" });
  });
});
