import { describe, expect, it } from "vitest";
import { addUsage, dayKey, isOverBudget } from "@watermark/functions/api/_lib/budget";
import type { KVLike } from "@watermark/functions/api/_lib/ratelimit";

/** An in-memory KVLike for the pure logic. */
function fakeKV(initial: Record<string, string> = {}): KVLike & { store: Map<string, string> } {
  const store = new Map(Object.entries(initial));
  return {
    store,
    get: (k) => Promise.resolve(store.get(k) ?? null),
    put: (k, v) => {
      store.set(k, v);
      return Promise.resolve();
    },
  };
}

/** A KVLike whose every op rejects — to assert fail-open behavior. */
const brokenKV: KVLike = {
  get: () => Promise.reject(new Error("kv down")),
  put: () => Promise.reject(new Error("kv down")),
};

const T = Date.parse("2026-06-17T12:00:00Z");

describe("dayKey", () => {
  it("is a stable per-UTC-day key", () => {
    expect(dayKey(T)).toBe("ask:budget:2026-06-17");
    expect(dayKey(Date.parse("2026-06-17T23:59:59Z"))).toBe("ask:budget:2026-06-17");
    expect(dayKey(Date.parse("2026-06-18T00:00:00Z"))).toBe("ask:budget:2026-06-18");
  });
});

describe("budget guard", () => {
  it("is under budget when nothing is spent and over once spend ≥ limit", async () => {
    const kv = fakeKV();
    expect(await isOverBudget(kv, T, 1000)).toBe(false);
    await addUsage(kv, T, { input_tokens: 0, output_tokens: 600 });
    expect(await isOverBudget(kv, T, 1000)).toBe(false);
    await addUsage(kv, T, { input_tokens: 0, output_tokens: 400 });
    expect(await isOverBudget(kv, T, 1000)).toBe(true);
  });

  it("accumulates only within the same UTC day", async () => {
    const kv = fakeKV();
    await addUsage(kv, T, { input_tokens: 0, output_tokens: 900 });
    expect(await isOverBudget(kv, Date.parse("2026-06-18T01:00:00Z"), 1000)).toBe(false);
  });

  it("fails open when KV is unavailable (Turnstile stays the primary gate)", async () => {
    expect(await isOverBudget(brokenKV, T, 1)).toBe(false);
    await expect(addUsage(brokenKV, T, { input_tokens: 0, output_tokens: 100 })).resolves.toBeUndefined();
  });
});
