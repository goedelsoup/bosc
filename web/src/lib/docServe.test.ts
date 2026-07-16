import { afterEach, describe, expect, it, vi } from "vitest";
import { _resetPublishedCache, loadPublishedDocs } from "@watermark/functions/api/_lib/docAllowlist";
import {
  docContentType,
  enforcePublishGate,
  parseByteRange,
  resolveDocKey,
} from "@watermark/functions/api/_lib/docServe";

describe("resolveDocKey", () => {
  it("joins the catch-all and accepts a normal rel", () => {
    expect(resolveDocKey("recorder/deed.pdf")).toBe("recorder/deed.pdf");
    expect(resolveDocKey(["recorder", "deed.pdf"])).toBe("recorder/deed.pdf");
    expect(resolveDocKey("legal/School%20District%20Notice.pdf")).toBe("legal/School District Notice.pdf");
  });

  it("rejects traversal, empty, and leading-slash paths", () => {
    expect(resolveDocKey("../../etc/passwd")).toBeNull();
    expect(resolveDocKey("recorder/../secret.pdf")).toBeNull();
    expect(resolveDocKey("")).toBeNull();
    expect(resolveDocKey(undefined)).toBeNull();
    expect(resolveDocKey("/abs.pdf")).toBe("abs.pdf"); // leading slash stripped, still valid
  });
});

describe("parseByteRange", () => {
  it("returns null for no/unparseable header (full 200)", () => {
    expect(parseByteRange(null, 100)).toBeNull();
    expect(parseByteRange("items=0-9", 100)).toBeNull();
    expect(parseByteRange("bytes=-", 100)).toBeNull();
  });

  it("resolves a closed range", () => {
    expect(parseByteRange("bytes=0-9", 100)).toEqual({ offset: 0, length: 10, end: 9 });
    expect(parseByteRange("bytes=10-19", 100)).toEqual({ offset: 10, length: 10, end: 19 });
  });

  it("resolves an open-ended range, clamping the end to size", () => {
    expect(parseByteRange("bytes=500-", 1000)).toEqual({ offset: 500, length: 500, end: 999 });
    expect(parseByteRange("bytes=0-99999", 1000)).toEqual({ offset: 0, length: 1000, end: 999 });
  });

  it("resolves a suffix range", () => {
    expect(parseByteRange("bytes=-100", 1000)).toEqual({ offset: 900, length: 100, end: 999 });
    expect(parseByteRange("bytes=-5000", 1000)).toEqual({ offset: 0, length: 1000, end: 999 });
  });

  it("flags an unsatisfiable range", () => {
    expect(parseByteRange("bytes=1000-1100", 1000)).toBe("unsatisfiable");
    expect(parseByteRange("bytes=-0", 1000)).toBe("unsatisfiable");
  });
});

describe("docContentType", () => {
  it("prefers the stored content type, then media_type meta, then octet-stream", () => {
    expect(docContentType("application/pdf", "text/plain")).toBe("application/pdf");
    expect(docContentType(undefined, "image/jpeg")).toBe("image/jpeg");
    expect(docContentType(null, null)).toBe("application/octet-stream");
  });
});

describe("enforcePublishGate", () => {
  it("enforces on the production branch, serves all elsewhere", () => {
    expect(enforcePublishGate({ CF_PAGES_BRANCH: "main" })).toBe(true);
    expect(enforcePublishGate({ CF_PAGES_BRANCH: "a-feature" })).toBe(false);
    expect(enforcePublishGate({})).toBe(false); // local wrangler dev
  });

  it("honors the operator override", () => {
    expect(enforcePublishGate({ CF_PAGES_BRANCH: "main", DOCS_PUBLIC_GATE: "off" })).toBe(false);
    expect(enforcePublishGate({ CF_PAGES_BRANCH: "feat", DOCS_PUBLIC_GATE: "on" })).toBe(true);
  });
});

describe("loadPublishedDocs", () => {
  afterEach(() => {
    _resetPublishedCache();
    vi.unstubAllGlobals();
  });

  it("fetches the static asset and caches the parsed set", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ rels: ["aedg/a.pdf"] })));
    vi.stubGlobal("fetch", fetchMock);
    const set = await loadPublishedDocs("https://site.example/api/doc/x");
    expect(set.has("aedg/a.pdf")).toBe(true);
    // the asset fetch carries an abort deadline (#590)
    expect(fetchMock).toHaveBeenCalledWith(
      "https://site.example/published-documents.json",
      expect.objectContaining({ signal: expect.anything() }),
    );
    await loadPublishedDocs("https://site.example/api/doc/y"); // cached → no second fetch
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("throws on a failed fetch (route turns it into a fail-closed 503)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 500 })),
    );
    await expect(loadPublishedDocs("https://site.example/api/doc/x")).rejects.toThrow();
  });
});
