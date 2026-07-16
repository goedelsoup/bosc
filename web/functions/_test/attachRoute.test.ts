// Tier A integration test for the /api/attach Pages Function (functions/api/attach.ts):
// drive onRequestPost end-to-end with a faked Env + an in-memory R2. No wrangler,
// no network, no real R2 bucket. Pure _lib logic (MIME/filename) is unit-tested in
// attachments.test.ts; this covers the wiring those leave out.

import { describe, expect, it } from "vitest";
import { onRequestPost } from "@watermark/functions/api/attach";
import type { R2Like } from "@watermark/functions/api/_lib/attachments";

const ATTACH_URL = "https://bosc.test/api/attach";

// Minimal in-memory R2 for the attach endpoint — tracks puts by key.
function fakeAttachR2(): R2Like & {
  stored: Map<string, { bytes: Uint8Array; contentType?: string; contentDisposition?: string }>;
} {
  const stored = new Map<string, { bytes: Uint8Array; contentType?: string; contentDisposition?: string }>();
  return {
    stored,
    put: async (key, value, opts) => {
      const bytes =
        value instanceof ArrayBuffer
          ? new Uint8Array(value)
          : value instanceof Uint8Array
            ? value
            : new Uint8Array(0);
      stored.set(key, {
        bytes,
        contentType: opts?.httpMetadata?.contentType,
        contentDisposition: opts?.httpMetadata?.contentDisposition,
      });
    },
    head: async (key) => (stored.has(key) ? { size: stored.get(key)!.bytes.length } : null),
  };
}

function attachEnv(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return { SUBMISSIONS_ENABLED: "true", SUBMISSION_ATTACHMENTS: fakeAttachR2(), ...overrides };
}

function multipartRequest(file: File, url = ATTACH_URL): Request {
  const fd = new FormData();
  fd.append("file", file);
  return new Request(url, { method: "POST", body: fd });
}

// A minimal valid JPEG (just magic bytes + enough to pass the size check).
const JPEG_MAGIC = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x01]);
const PNG_MAGIC = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const PDF_MAGIC = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31]);

describe("/api/attach route", () => {
  it("503s when the kill switch is off", async () => {
    const res = await onRequestPost({
      request: multipartRequest(new File([JPEG_MAGIC], "photo.jpg", { type: "image/jpeg" })),
      env: {},
    } as never);
    expect(res.status).toBe(503);
  });

  it("503s when SUBMISSION_ATTACHMENTS is not bound", async () => {
    const res = await onRequestPost({
      request: multipartRequest(new File([JPEG_MAGIC], "photo.jpg", { type: "image/jpeg" })),
      env: { SUBMISSIONS_ENABLED: "true" },
    } as never);
    expect(res.status).toBe(503);
  });

  it("400s when the body is not multipart", async () => {
    const req = new Request(ATTACH_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
    });
    const res = await onRequestPost({ request: req, env: attachEnv() } as never);
    expect(res.status).toBe(400);
  });

  it("400s when the file field is missing", async () => {
    const fd = new FormData();
    fd.append("other", "value");
    const req = new Request(ATTACH_URL, { method: "POST", body: fd });
    const res = await onRequestPost({ request: req, env: attachEnv() } as never);
    expect(res.status).toBe(400);
  });

  it("400s for an empty file", async () => {
    const res = await onRequestPost({
      request: multipartRequest(new File([], "empty.jpg", { type: "image/jpeg" })),
      env: attachEnv(),
    } as never);
    expect(res.status).toBe(400);
  });

  it("413s when the file exceeds the size cap", async () => {
    const big = new Uint8Array(11 * 1024 * 1024); // 11 MB
    big[0] = 0xff;
    big[1] = 0xd8;
    big[2] = 0xff; // valid JPEG magic
    const res = await onRequestPost({
      request: multipartRequest(new File([big], "huge.jpg", { type: "image/jpeg" })),
      env: attachEnv({ ATTACH_MAX_BYTES: "10485760" }),
    } as never);
    expect(res.status).toBe(413);
  });

  it("415s for a disallowed MIME type", async () => {
    const res = await onRequestPost({
      request: multipartRequest(new File([JPEG_MAGIC], "script.js", { type: "application/javascript" })),
      env: attachEnv(),
    } as never);
    expect(res.status).toBe(415);
  });

  it("415s when magic bytes don't match declared type", async () => {
    // Declare image/png but send JPEG magic bytes
    const res = await onRequestPost({
      request: multipartRequest(new File([JPEG_MAGIC], "fake.png", { type: "image/png" })),
      env: attachEnv(),
    } as never);
    expect(res.status).toBe(415);
  });

  it("201s and returns a key for a valid JPEG", async () => {
    const r2 = fakeAttachR2();
    const res = await onRequestPost({
      request: multipartRequest(new File([JPEG_MAGIC], "photo.jpg", { type: "image/jpeg" })),
      env: attachEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    expect(res.status).toBe(201);
    const body = (await res.json()) as { key?: string };
    expect(body.key).toMatch(/^submissions\/\d{4}-\d{2}-\d{2}\/.+\/photo\.jpg$/);
    expect(r2.stored.size).toBe(1);
  });

  it("201s and returns a key for a valid PDF", async () => {
    const r2 = fakeAttachR2();
    const res = await onRequestPost({
      request: multipartRequest(new File([PDF_MAGIC], "report.pdf", { type: "application/pdf" })),
      env: attachEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    expect(res.status).toBe(201);
    const body = (await res.json()) as { key?: string };
    expect(body.key).toMatch(/^submissions\/.+\/report\.pdf$/);
  });

  it("201s for text/plain (no magic bytes — trusted as-declared)", async () => {
    const text = new TextEncoder().encode("plain text content");
    const r2 = fakeAttachR2();
    const res = await onRequestPost({
      request: multipartRequest(new File([text], "notes.txt", { type: "text/plain" })),
      env: attachEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    expect(res.status).toBe(201);
  });

  it("201s for valid PNG", async () => {
    const res = await onRequestPost({
      request: multipartRequest(new File([PNG_MAGIC], "image.png", { type: "image/png" })),
      env: attachEnv(),
    } as never);
    expect(res.status).toBe(201);
  });

  it("stores file with Content-Disposition: attachment", async () => {
    const r2 = fakeAttachR2();
    const file = new File([PDF_MAGIC], "doc.pdf", { type: "application/pdf" });
    await onRequestPost({
      request: multipartRequest(file),
      env: attachEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    expect(r2.stored.size).toBe(1);
    const stored = [...r2.stored.values()][0];
    expect(stored.contentType).toBe("application/pdf");
    expect(stored.contentDisposition).toMatch(/^attachment;\s*filename="/);
  });

  it("sanitizes the filename in the key", async () => {
    const r2 = fakeAttachR2();
    const res = await onRequestPost({
      request: multipartRequest(new File([JPEG_MAGIC], "../../etc/passwd.jpg", { type: "image/jpeg" })),
      env: attachEnv({ SUBMISSION_ATTACHMENTS: r2 }),
    } as never);
    expect(res.status).toBe(201);
    const body = (await res.json()) as { key?: string };
    // Should not contain path traversal
    expect(body.key).not.toContain("..");
    expect(body.key).not.toContain("/etc/");
  });

  it("ATTACH_MAX_BYTES override is respected", async () => {
    // Set a tiny 5-byte cap
    const big = new Uint8Array(10).fill(0x41); // 10 bytes of 'A'
    big[0] = 0xff;
    big[1] = 0xd8;
    big[2] = 0xff; // JPEG magic
    const res = await onRequestPost({
      request: multipartRequest(new File([big], "small.jpg", { type: "image/jpeg" })),
      env: attachEnv({ ATTACH_MAX_BYTES: "5" }),
    } as never);
    expect(res.status).toBe(413);
  });
});
