import { describe, expect, it, vi } from "vitest";
import { documentId } from "@watermark/core/documentId";
import {
  legacyRedirectTarget,
  onRequest,
  relFromLegacyPath,
} from "@watermark/functions/network/[site]/site/documents/[[rel]]";

const SITE = "american-sugar-creek-allen-co";

/** Drive the Function with a given `next()` outcome, mimicking the Pages asset server. */
function call(rel: string | string[], assetStatus: number) {
  const next = vi.fn(
    async () => new Response(assetStatus === 404 ? "not found" : "ok", { status: assetStatus }),
  );
  return {
    next,
    res: onRequest({
      request: new Request("https://example.test/"),
      params: { site: SITE, rel },
      next,
    }),
  };
}

describe("relFromLegacyPath", () => {
  it("recovers a plain rel", () => {
    expect(relFromLegacyPath("aedg/PRR-01-bundle.ocr.pdf")).toBe("aedg/PRR-01-bundle.ocr.pdf");
  });

  it("decodes the characters the corpus's as-received names actually contain", () => {
    // 1,739 files with spaces, 1,571 with `&`, 141 with `#` — the reason the old route needed
    // its own encoding contract in the first place.
    expect(relFromLegacyPath("legal/SH%20%26%20AB/Notice.pdf")).toBe("legal/SH & AB/Notice.pdf");
    expect(relFromLegacyPath("legal/prr/Email-PO%23_00018640.pdf")).toBe("legal/prr/Email-PO#_00018640.pdf");
    expect(relFromLegacyPath("odd/100%25_report.pdf")).toBe("odd/100%_report.pdf");
  });

  it("tolerates the trailing slash the directory-format build emits", () => {
    expect(relFromLegacyPath("aedg/bundle.pdf/")).toBe("aedg/bundle.pdf");
  });

  it("rejects a single segment — the catalog has no document directly under data/documents", () => {
    expect(relFromLegacyPath("legal")).toBeNull();
    expect(relFromLegacyPath("")).toBeNull();
  });

  it("rejects traversal, NUL and malformed encoding", () => {
    expect(relFromLegacyPath("legal/../../etc/passwd")).toBeNull();
    expect(relFromLegacyPath("legal/a%00b.pdf")).toBeNull();
    expect(relFromLegacyPath("legal/%E0%A4%A.pdf")).toBeNull();
  });
});

describe("legacyRedirectTarget", () => {
  it("is the site-scoped permalink for the rel's handle", () => {
    const rel = "aedg/PRR-01-bundle.ocr.pdf";
    expect(legacyRedirectTarget(SITE, rel)).toBe(`/network/${SITE}/doc/${documentId(rel)}/`);
  });

  it("collapses a 12-segment corpus path to a 4-segment URL", () => {
    const deep =
      "legal/prr-mandamus/prr-production-2026-07-24-sanitary/9/SH & AB SSO Findings and Orders/Phase 1 SECAP Constr Projects/Ph 1 SECAP American-Bath Trunk Sewer-URS/Construction Corr/Change Order/Final Change Order Correspondence/ConcDr/cap019.bmp";
    expect(deep.split("/")).toHaveLength(12);
    expect(legacyRedirectTarget(SITE, deep).split("/").filter(Boolean)).toHaveLength(4);
  });
});

describe("onRequest — asset-first", () => {
  it("serves a real page rather than redirecting it", async () => {
    // The landings live under this same prefix; only a 404 means "this was a document path".
    const { res, next } = call("legal", 200);
    const response = await res;
    expect(next).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("passes through any non-404, so a container landing at document depth still wins", async () => {
    // 91 documents sit at exactly the depth of a container landing — shape can't tell them apart,
    // which is precisely why this asks the asset server instead of guessing.
    const response = await call("legal/prr-mandamus", 200).res;
    expect(response.status).toBe(200);
  });

  it("301s a legacy document path to its handle", async () => {
    const rel = "aedg/PRR-01-bundle.ocr.pdf";
    const response = await call(rel, 404).res;
    expect(response.status).toBe(301);
    expect(response.headers.get("location")).toBe(`/network/${SITE}/doc/${documentId(rel)}/`);
  });

  it("accepts the array form Cloudflare may pass a catch-all in", async () => {
    const response = await call(["aedg", "PRR-01-bundle.ocr.pdf"], 404).res;
    expect(response.headers.get("location")).toBe(
      `/network/${SITE}/doc/${documentId("aedg/PRR-01-bundle.ocr.pdf")}/`,
    );
  });

  it("redirects a non-routable file's old page too, rather than dead-ending", async () => {
    // Thumbs.db no longer HAS a page, so this lands on a 404 for the handle — but the redirect
    // is still the honest answer: the address moved, and the byte URL is what serves it now.
    const rel = "legal/prr-mandamus/Thumbs.db";
    const response = await call(rel, 404).res;
    expect(response.status).toBe(301);
    expect(response.headers.get("location")).toBe(`/network/${SITE}/doc/${documentId(rel)}/`);
  });

  it("returns the asset 404 untouched when the path can't be a document", async () => {
    const response = await call("legal/../../etc", 404).res;
    expect(response.status).toBe(404);
    expect(response.headers.get("location")).toBeNull();
  });

  it("caches the redirect — the mapping is derived and never changes for a rel", async () => {
    const response = await call("aedg/PRR-01-bundle.ocr.pdf", 404).res;
    expect(response.headers.get("cache-control")).toContain("max-age=");
  });
});
