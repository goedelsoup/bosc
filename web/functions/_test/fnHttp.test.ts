// Unit tests for the shared Pages-Function HTTP helpers — focus on the external-call
// timeout glue (#590). The envelopes/guards are covered via the route harnesses.
import { describe, expect, it, vi } from "vitest";
import { fetchWithTimeout, isTimeoutError } from "@watermark/functions/api/_lib/http";

describe("isTimeoutError (#590)", () => {
  it("recognizes timeout/abort rejections, rejects everything else", () => {
    expect(isTimeoutError({ name: "TimeoutError" })).toBe(true);
    expect(isTimeoutError({ name: "AbortError" })).toBe(true);
    expect(isTimeoutError(new Error("boom"))).toBe(false);
    expect(isTimeoutError(null)).toBe(false);
    expect(isTimeoutError("nope")).toBe(false);
  });
});

describe("fetchWithTimeout (#590)", () => {
  it("passes an abort signal through to fetch", async () => {
    const fetchMock = vi.fn(async () => new Response("ok"));
    vi.stubGlobal("fetch", fetchMock);
    await fetchWithTimeout("https://x.test/asset.json");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://x.test/asset.json",
      expect.objectContaining({ signal: expect.anything() }),
    );
    vi.unstubAllGlobals();
  });

  it("aborts a hung upstream after the deadline, rejecting with a TimeoutError", async () => {
    // A fetch that never resolves on its own — only the abort signal can end it.
    const fetchMock = vi.fn(
      (_url: string | URL, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(init.signal?.reason));
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const err = await fetchWithTimeout("https://slow.test/x", {}, 20).catch((e) => e);
    expect(isTimeoutError(err)).toBe(true);
    vi.unstubAllGlobals();
  });

  it("composes a caller signal with the deadline (either aborts)", async () => {
    const fetchMock = vi.fn(
      (_url: string | URL, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => reject(init.signal?.reason));
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const caller = new AbortController();
    const p = fetchWithTimeout("https://slow.test/x", { signal: caller.signal }, 10_000).catch((e) => e);
    caller.abort(new DOMException("caller cancelled", "AbortError"));
    expect(isTimeoutError(await p)).toBe(true);
    vi.unstubAllGlobals();
  });
});
