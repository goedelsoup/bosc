// Unit tests for the early-access cookie mint + verify round-trip (#1012/#1013).
// Imports the real production helpers from eaCookie so the test exercises the
// same code path used by the middleware and the account endpoint.

import { describe, expect, it } from "vitest";
import { mintEaCookie, isValidEaCookie, MAX_AGE_SEC } from "@watermark/functions/api/_lib/eaCookie";

const SECRET = "test-secret-32-bytes-padded-here";

describe("mint + verify round-trip", () => {
  it("valid cookie passes verification", async () => {
    const value = await mintEaCookie("user-sub-123", SECRET);
    const ok = await isValidEaCookie(value, SECRET);
    expect(ok).toBe(true);
  });

  it("expired cookie is rejected", async () => {
    // Build a cookie whose embedded exp is in the past by directly signing a stale payload.
    const pastExp = Math.floor(Date.now() / 1000) - 1;
    // Replicate the mint logic with a past exp to create an already-expired value.
    function b64url(buf: ArrayBuffer | Uint8Array): string {
      const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
      let bin = "";
      for (const b of bytes) bin += String.fromCharCode(b);
      return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
    }
    const payload = b64url(new TextEncoder().encode(`user-sub-123|${pastExp}`));
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const sig = b64url(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)));
    const value = `${payload}.${sig}`;

    const ok = await isValidEaCookie(value, SECRET);
    expect(ok).toBe(false);
  });

  it("wrong secret is rejected", async () => {
    const value = await mintEaCookie("user-sub-123", SECRET);
    const ok = await isValidEaCookie(value, "wrong-secret");
    expect(ok).toBe(false);
  });

  it("tampered payload is rejected", async () => {
    const value = await mintEaCookie("user-sub-123", SECRET);
    const dot = value.lastIndexOf(".");
    const sig = value.slice(dot + 1);
    function b64url(buf: Uint8Array): string {
      let bin = "";
      for (const b of buf) bin += String.fromCharCode(b);
      return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
    }
    const futureExp = Math.floor(Date.now() / 1000) + MAX_AGE_SEC;
    const tamperedPayload = b64url(new TextEncoder().encode(`evil-sub|${futureExp}`));
    const forged = `${tamperedPayload}.${sig}`;
    const ok = await isValidEaCookie(forged, SECRET);
    expect(ok).toBe(false);
  });

  it("malformed cookie (no dot) is rejected", async () => {
    const ok = await isValidEaCookie("nodot", SECRET);
    expect(ok).toBe(false);
  });

  it("empty string is rejected", async () => {
    const ok = await isValidEaCookie("", SECRET);
    expect(ok).toBe(false);
  });

  it("minted cookie embeds a 7-day expiry", async () => {
    const nowSec = Math.floor(Date.now() / 1000);
    const value = await mintEaCookie("user-sub-123", SECRET);
    const payload = value.slice(0, value.lastIndexOf("."));
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const exp = parseInt(decoded.split("|")[1], 10);
    // Expiry should be approximately now + 7 days (allow a few seconds of drift).
    expect(exp).toBeGreaterThanOrEqual(nowSec + MAX_AGE_SEC - 5);
    expect(exp).toBeLessThanOrEqual(nowSec + MAX_AGE_SEC + 5);
  });
});
