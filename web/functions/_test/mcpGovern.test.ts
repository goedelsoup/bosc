// Unit tests for the MCP response-size governance core (#1581).
// Pure logic — no fetch, no KV: token estimation, intent/knob resolution, the opaque
// cursor round-trip, and the govern() paginator's count/token/shrink guarantees.

import { describe, expect, it } from "vitest";
import {
  DEFAULT_KNOBS,
  INTENTS,
  decodeCursorOffset,
  dropKeysUntilUnderCap,
  encodeCursor,
  estimateTokens,
  govern,
  governedContent,
  parseIntent,
  resolveKnobs,
  truncateToTokens,
} from "@watermark/functions/api/_lib/mcpGovern";

describe("estimateTokens", () => {
  it("measures strings directly and objects via JSON", () => {
    expect(estimateTokens("abcd")).toBe(1); // 4 chars / 4
    expect(estimateTokens("")).toBe(0);
    expect(estimateTokens({ a: 1 })).toBeGreaterThan(0);
    // A bigger object costs more.
    expect(estimateTokens({ a: "x".repeat(400) })).toBeGreaterThan(estimateTokens({ a: "x" }));
  });
});

describe("truncateToTokens", () => {
  it("returns short text unchanged and marks a cut", () => {
    expect(truncateToTokens("short", 100)).toBe("short");
    const cut = truncateToTokens("x".repeat(1000), 10);
    expect(cut.endsWith("…")).toBe(true);
    expect(cut.length).toBeLessThan(1000);
  });
});

describe("dropKeysUntilUnderCap", () => {
  it("drops low-priority keys in order until under cap, keeping the rest", () => {
    const item = { id: "e1", detail: "y".repeat(2000), parties: ["a", "b"] };
    const capTokens = 20;
    const out = dropKeysUntilUnderCap(item, ["detail", "parties"], capTokens);
    expect(out.id).toBe("e1"); // identity field retained
    expect(out).not.toHaveProperty("detail"); // heaviest dropped first
    expect(estimateTokens(out)).toBeLessThanOrEqual(capTokens);
  });

  it("returns the item untouched when it already fits", () => {
    const item = { id: "e1", detail: "small" };
    expect(dropKeysUntilUnderCap(item, ["detail"], 1000)).toEqual(item);
  });
});

describe("parseIntent / resolveKnobs", () => {
  it("recognizes known intents and rejects the rest", () => {
    expect(parseIntent("fact_lookup")).toBe("fact_lookup");
    expect(parseIntent("nonsense")).toBeNull();
    expect(parseIntent(42)).toBeNull();
  });

  it("falls back to the neutral default with no intent or knobs", () => {
    expect(resolveKnobs({})).toEqual(DEFAULT_KNOBS);
  });

  it("seeds from the intent preset", () => {
    expect(resolveKnobs({ intent: "fact_lookup" })).toEqual(INTENTS.fact_lookup.knobs);
  });

  it("lets explicit knobs override the preset", () => {
    const knobs = resolveKnobs({ intent: "fact_lookup", max_results: 7 });
    expect(knobs.maxResults).toBe(7);
    expect(knobs.maxTokens).toBe(INTENTS.fact_lookup.knobs.maxTokens); // untouched knob keeps preset
  });

  it("clamps knobs into range and ignores non-numbers", () => {
    expect(resolveKnobs({ max_results: 9999 }).maxResults).toBe(100); // ceiling
    expect(resolveKnobs({ max_results: 0 }).maxResults).toBe(1); // floor
    expect(resolveKnobs({ max_tokens: 5 }).maxTokens).toBe(100); // floor
    expect(resolveKnobs({ max_results: "lots" }).maxResults).toBe(DEFAULT_KNOBS.maxResults);
  });
});

describe("cursor round-trip", () => {
  it("encodes and decodes an offset", () => {
    for (const o of [0, 1, 10, 250]) {
      expect(decodeCursorOffset(encodeCursor(o))).toBe(o);
    }
  });

  it("reads garbage/empty cursors as offset 0", () => {
    expect(decodeCursorOffset(undefined)).toBe(0);
    expect(decodeCursorOffset("")).toBe(0);
    expect(decodeCursorOffset("not-base64!!")).toBe(0);
    expect(decodeCursorOffset(encodeCursor(-5))).toBe(0); // negative rejected upstream anyway
  });
});

describe("govern", () => {
  const items = Array.from({ length: 5 }, (_, i) => ({ id: `n${i}`, v: i }));
  const wide = { maxResults: 100, maxTokens: 1_000_000, maxTokensPerResult: 1_000_000 };

  it("returns everything under budget with no cursor", () => {
    const g = govern(items, { knobs: wide });
    expect(g.results).toHaveLength(5);
    expect(g.truncated).toBe(false);
    expect(g.next_cursor).toBeNull();
    expect(g.token_estimate).toBe(estimateTokens(items));
  });

  it("caps at maxResults and points the cursor at the next absolute index", () => {
    const g = govern(items, { knobs: { ...wide, maxResults: 2 } });
    expect(g.results).toHaveLength(2);
    expect(g.truncated).toBe(true);
    expect(decodeCursorOffset(g.next_cursor)).toBe(2);
  });

  it("folds baseOffset into the emitted cursor", () => {
    const g = govern(items.slice(3), { knobs: { ...wide, maxResults: 1 }, baseOffset: 3 });
    expect(g.results).toHaveLength(1);
    expect(decodeCursorOffset(g.next_cursor)).toBe(4);
  });

  it("stops before the token ceiling but always returns at least one", () => {
    const big = Array.from({ length: 3 }, (_, i) => ({ id: `b${i}`, blob: "x".repeat(400) }));
    const g = govern(big, { knobs: { maxResults: 100, maxTokens: 50, maxTokensPerResult: 1_000 } });
    expect(g.results).toHaveLength(1); // one item ~100 tokens > 50, still returned
    expect(g.truncated).toBe(true);
    expect(decodeCursorOffset(g.next_cursor)).toBe(1);
  });

  it("shrinks an over-cap item before counting it", () => {
    const heavy = [{ id: "h", text: "x".repeat(4000) }];
    const shrink = (it: { id: string; text: string }, cap: number) => ({
      ...it,
      text: truncateToTokens(it.text, cap),
    });
    const g = govern(heavy, { knobs: { maxResults: 100, maxTokens: 1000, maxTokensPerResult: 20 }, shrink });
    expect((g.results[0].text as string).length).toBeLessThan(4000);
    expect((g.results[0].text as string).endsWith("…")).toBe(true);
  });
});

describe("governedContent", () => {
  it("wraps an envelope as a single MCP text element", () => {
    const g = govern([{ id: "a" }], { knobs: DEFAULT_KNOBS });
    const content = governedContent(g);
    expect(content).toHaveLength(1);
    expect(content[0].type).toBe("text");
    expect(JSON.parse(content[0].text)).toEqual(g);
  });
});
