// Unit tests for the MCP budget helpers (#912).
// Same pattern as askBudget.test.ts — pure logic over an in-memory KVLike.

import { describe, expect, it } from "vitest";
import {
  addBudgetUsage,
  isOverBudget,
  keyedBudgetKey,
  publicBudgetKey,
} from "@watermark/functions/api/_lib/mcpBudget";
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

const brokenKV: KVLike = {
  get: () => Promise.reject(new Error("kv down")),
  put: () => Promise.reject(new Error("kv down")),
};

const T = Date.parse("2026-06-29T12:00:00Z");

describe("publicBudgetKey", () => {
  it("returns a stable per-UTC-day key", () => {
    expect(publicBudgetKey(T)).toBe("public:2026-06-29");
    expect(publicBudgetKey(Date.parse("2026-06-29T23:59:59Z"))).toBe("public:2026-06-29");
    expect(publicBudgetKey(Date.parse("2026-06-30T00:00:00Z"))).toBe("public:2026-06-30");
  });
});

describe("keyedBudgetKey", () => {
  it("returns a stable per-key per-UTC-day key", () => {
    expect(keyedBudgetKey("abc123", T)).toBe("key:abc123:2026-06-29");
    expect(keyedBudgetKey("abc123", Date.parse("2026-06-30T00:00:00Z"))).toBe("key:abc123:2026-06-30");
  });

  it("isolates different keys on the same day", () => {
    expect(keyedBudgetKey("aaa", T)).not.toBe(keyedBudgetKey("bbb", T));
  });
});

describe("isOverBudget / addBudgetUsage", () => {
  it("starts under budget and goes over once spend ≥ limit", async () => {
    const kv = fakeKV();
    const key = publicBudgetKey(T);
    expect(await isOverBudget(kv, key, 1000)).toBe(false);
    await addBudgetUsage(kv, key, 600);
    expect(await isOverBudget(kv, key, 1000)).toBe(false);
    await addBudgetUsage(kv, key, 400);
    expect(await isOverBudget(kv, key, 1000)).toBe(true);
  });

  it("keyed and public tiers are independent", async () => {
    const kv = fakeKV();
    const pub = publicBudgetKey(T);
    const keyed = keyedBudgetKey("hash-x", T);
    await addBudgetUsage(kv, pub, 900);
    expect(await isOverBudget(kv, keyed, 1000)).toBe(false);
  });

  it("accumulates only within the same UTC day", async () => {
    const kv = fakeKV();
    const key = publicBudgetKey(T);
    await addBudgetUsage(kv, key, 900);
    const nextDay = keyedBudgetKey("x", Date.parse("2026-06-30T01:00:00Z"));
    expect(await isOverBudget(kv, nextDay, 1000)).toBe(false);
  });

  it("fails open when KV is unavailable", async () => {
    expect(await isOverBudget(brokenKV, "any-key", 1)).toBe(false);
    await expect(addBudgetUsage(brokenKV, "any-key", 100)).resolves.toBeUndefined();
  });

  it("ignores zero-token increments", async () => {
    const kv = fakeKV();
    const key = publicBudgetKey(T);
    await addBudgetUsage(kv, key, 0);
    expect((kv as ReturnType<typeof fakeKV>).store.size).toBe(0);
  });
});
