import { describe, expect, it } from "vitest";
import { docAccess, docApiUrl, docPagePath, viewerTier } from "./docView";

describe("docApiUrl", () => {
  it("path-segment-encodes the rel, preserving slashes", () => {
    expect(docApiUrl("recorder/deed.pdf")).toBe("/api/doc/recorder/deed.pdf");
    expect(docApiUrl("legal/prr/School District Notice.pdf")).toBe(
      "/api/doc/legal/prr/School%20District%20Notice.pdf",
    );
    expect(docApiUrl("a/b&c/d#e.pdf")).toBe("/api/doc/a/b%26c/d%23e.pdf");
  });
});

describe("docPagePath", () => {
  // The viewer page addresses a static file Astro already wrote, and Astro encodes only what
  // would break path parsing — so this must encode LESS than docApiUrl, not the same.
  it("encodes only the path-structural characters, matching Astro's emitted route", () => {
    expect(docPagePath("recorder/deed.pdf")).toBe("/site/documents/recorder/deed.pdf");
    // Spaces and `&` stay literal: Astro emits them literally in the directory name, so encoding
    // them would address a path that exists nowhere. (`&` is still HTML-escaped in the attribute.)
    expect(docPagePath("legal/SH & AB/School District Notice.pdf")).toBe(
      "/site/documents/legal/SH & AB/School District Notice.pdf",
    );
    // `#` must be encoded or the browser reads it as a fragment and requests a truncated path —
    // the defect this fixes, on 141 as-received public-record filenames.
    expect(docPagePath("legal/prr/Email-PO#_00018640_2026.pdf")).toBe(
      "/site/documents/legal/prr/Email-PO%23_00018640_2026.pdf",
    );
    // An existing `%` is escaped first so it can never be re-read as an escape sequence.
    expect(docPagePath("a/100%_report#2.pdf")).toBe("/site/documents/a/100%25_report%232.pdf");
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
