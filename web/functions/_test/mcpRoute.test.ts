// Route-level test for the MCP budget debit wire (#1581).
// Drives onRequestPost end-to-end and asserts that a tools/call response debits the daily
// output-token counter — the inert addBudgetUsage is now actually called. An empty-query
// search_corpus is used so no feed fetch is needed (the handler short-circuits).

import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequestPost } from "@watermark/functions/api/mcp";
import type { KVLike } from "@watermark/functions/api/_lib/ratelimit";

function fakeKV(seed: Record<string, string> = {}): KVLike & { store: Map<string, string> } {
  const store = new Map(Object.entries(seed));
  return {
    store,
    get: (k) => Promise.resolve(store.get(k) ?? null),
    put: (k, v) => {
      store.set(k, v);
      return Promise.resolve();
    },
  };
}

interface Ctx {
  request: Request;
  // biome-ignore lint/suspicious/noExplicitAny: minimal Env shim for the route under test
  env: any;
  waitUntil: (p: Promise<unknown>) => void;
}

function toolCall(name: string, args: Record<string, unknown>): Request {
  return new Request("https://directory.example/api/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", "mcp-session-id": "s-test" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }),
  });
}

/** Run the handler and settle any waitUntil()-scheduled work (the best-effort debit). */
async function drive(ctx: Omit<Ctx, "waitUntil">): Promise<Response> {
  const pending: Promise<unknown>[] = [];
  const res = await onRequestPost({ ...ctx, waitUntil: (p) => pending.push(p) });
  await Promise.all(pending);
  return res;
}

afterEach(() => vi.unstubAllGlobals());

describe("MCP budget debit (#1581)", () => {
  it("debits the daily counter after a tools/call response", async () => {
    const kv = fakeKV();
    const res = await drive({
      request: toolCall("search_corpus", { query: "" }),
      env: { MCP_ENABLED: "true", MCP_BUDGET_ENABLED: "true", MCP_BUDGET: kv },
    });
    expect(res.status).toBe(200);
    expect(kv.store.size).toBe(1);
    const [key, value] = [...kv.store.entries()][0];
    expect(key).toMatch(/^public:\d{4}-\d{2}-\d{2}$/);
    expect(Number(value)).toBeGreaterThan(0);
  });

  it("does not debit when a tool call errors", async () => {
    const kv = fakeKV();
    await drive({
      request: toolCall("does_not_exist", {}),
      env: { MCP_ENABLED: "true", MCP_BUDGET_ENABLED: "true", MCP_BUDGET: kv },
    });
    expect(kv.store.size).toBe(0);
  });

  it("does not debit when budget enforcement is off", async () => {
    const kv = fakeKV();
    await drive({
      request: toolCall("search_corpus", { query: "" }),
      env: { MCP_ENABLED: "true", MCP_BUDGET: kv }, // MCP_BUDGET_ENABLED unset
    });
    expect(kv.store.size).toBe(0);
  });

  it("bypasses the debit under MCP_ALLOW_UNCAPPED", async () => {
    const kv = fakeKV();
    await drive({
      request: toolCall("search_corpus", { query: "" }),
      env: {
        MCP_ENABLED: "true",
        MCP_BUDGET_ENABLED: "true",
        MCP_ALLOW_UNCAPPED: "true",
        MCP_BUDGET: kv,
      },
    });
    expect(kv.store.size).toBe(0);
  });
});
