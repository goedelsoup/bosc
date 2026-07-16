// Unit tests for the attachments lib helpers: MIME detection, filename sanitization,
// and key generation — all pure functions, no runtime dependency.

import { describe, expect, it } from "vitest";
import {
  ATTACH_MAX_BYTES,
  ATTACH_MAX_COUNT,
  ATTACH_MIME_ALLOWLIST,
  attachmentKey,
  detectMime,
  sanitizeFilename,
} from "@watermark/functions/api/_lib/attachments";

describe("detectMime", () => {
  it("detects JPEG", () => {
    const bytes = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10]);
    expect(detectMime(bytes)).toBe("image/jpeg");
  });

  it("detects PNG", () => {
    const bytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    expect(detectMime(bytes)).toBe("image/png");
  });

  it("detects GIF", () => {
    // GIF89a
    const bytes = new Uint8Array([0x47, 0x49, 0x46, 0x38, 0x39, 0x61]);
    expect(detectMime(bytes)).toBe("image/gif");
  });

  it("detects WebP", () => {
    const bytes = new Uint8Array([
      0x52,
      0x49,
      0x46,
      0x46, // RIFF
      0x00,
      0x00,
      0x00,
      0x00, // size (placeholder)
      0x57,
      0x45,
      0x42,
      0x50, // WEBP
    ]);
    expect(detectMime(bytes)).toBe("image/webp");
  });

  it("detects PDF", () => {
    const bytes = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d]); // %PDF-
    expect(detectMime(bytes)).toBe("application/pdf");
  });

  it("returns null for plain text (no magic bytes)", () => {
    const bytes = new TextEncoder().encode("hello world");
    expect(detectMime(bytes)).toBeNull();
  });

  it("returns null for unknown binary", () => {
    const bytes = new Uint8Array([0x00, 0x01, 0x02, 0x03]);
    expect(detectMime(bytes)).toBeNull();
  });
});

describe("sanitizeFilename", () => {
  it("preserves a safe filename", () => {
    expect(sanitizeFilename("document.pdf")).toBe("document.pdf");
  });

  it("strips path separators and parent-directory sequences", () => {
    // path components and .. both collapse to _; consecutive _ fold to one
    expect(sanitizeFilename("../../etc/passwd")).toBe("_etc_passwd");
  });

  it("replaces leading dot to prevent hidden-file names", () => {
    expect(sanitizeFilename(".htaccess")).toBe("_htaccess");
  });

  it("collapses whitespace", () => {
    expect(sanitizeFilename("my document.pdf")).toBe("my_document.pdf");
  });

  it("caps at 100 characters", () => {
    const long = `${"a".repeat(150)}.pdf`;
    expect(sanitizeFilename(long).length).toBeLessThanOrEqual(100);
  });

  it("returns 'attachment' for empty or whitespace-only input", () => {
    expect(sanitizeFilename("")).toBe("attachment");
    expect(sanitizeFilename("   ")).toBe("attachment");
    expect(sanitizeFilename("../../")).toBe("attachment");
  });

  it("strips double quotes (unsafe in Content-Disposition quoted strings)", () => {
    expect(sanitizeFilename('file"name.pdf')).toBe("filename.pdf");
    expect(sanitizeFilename('"injected".pdf')).toBe("injected.pdf");
  });

  it("strips CR/LF and other control characters (unsafe in HTTP headers)", () => {
    expect(sanitizeFilename("file\r\nname.pdf")).toBe("filename.pdf");
    expect(sanitizeFilename("file\x01name.pdf")).toBe("filename.pdf");
    expect(sanitizeFilename("file\x7fname.pdf")).toBe("filename.pdf");
  });
});

describe("attachmentKey", () => {
  it("produces the expected path structure", () => {
    const key = attachmentKey("2026-06-29", "abc-123", "photo.jpg");
    expect(key).toBe("submissions/2026-06-29/abc-123/photo.jpg");
  });

  it("starts with the submissions/ prefix required by schema.ts", () => {
    expect(attachmentKey("2026-06-29", "uuid", "file.pdf")).toMatch(/^submissions\//);
  });
});

describe("constants", () => {
  it("ATTACH_MAX_BYTES is 10 MB", () => {
    expect(ATTACH_MAX_BYTES).toBe(10 * 1024 * 1024);
  });

  it("ATTACH_MAX_COUNT is 3", () => {
    expect(ATTACH_MAX_COUNT).toBe(3);
  });

  it("ATTACH_MIME_ALLOWLIST contains expected types", () => {
    expect(ATTACH_MIME_ALLOWLIST).toContain("image/jpeg");
    expect(ATTACH_MIME_ALLOWLIST).toContain("application/pdf");
    expect(ATTACH_MIME_ALLOWLIST).toContain("text/plain");
    expect(ATTACH_MIME_ALLOWLIST).not.toContain("text/html");
    expect(ATTACH_MIME_ALLOWLIST).not.toContain("application/javascript");
  });
});
