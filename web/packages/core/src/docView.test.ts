import { describe, expect, it } from "vitest";
import { docAccess, docApiUrl, viewerTier } from "./docView";

describe("docApiUrl", () => {
  it("path-segment-encodes the rel, preserving slashes", () => {
    expect(docApiUrl("recorder/deed.pdf")).toBe("/api/doc/recorder/deed.pdf");
    expect(docApiUrl("legal/prr/School District Notice.pdf")).toBe(
      "/api/doc/legal/prr/School%20District%20Notice.pdf",
    );
    expect(docApiUrl("a/b&c/d#e.pdf")).toBe("/api/doc/a/b%26c/d%23e.pdf");
  });
});

describe("docAccess", () => {
  it("distinguishes published, dev-only, and absent", () => {
    expect(docAccess({ available: true, published: true })).toBe("published");
    expect(docAccess({ available: true, published: false })).toBe("dev-only");
    expect(docAccess({ available: false, published: true })).toBe("absent");
  });
});

describe("viewerTier", () => {
  it("uses render_class when available, else download-only", () => {
    expect(viewerTier({ available: true, render_class: "pdf" })).toBe("pdf");
    expect(viewerTier({ available: true, render_class: "image" })).toBe("image");
    expect(viewerTier({ available: false, render_class: "pdf" })).toBe("other");
  });
});
