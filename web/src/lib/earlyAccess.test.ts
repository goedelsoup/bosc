// Unit tests for the early-access cookie mint + verify round-trip (#1012/#1013).
// Drives the helper logic extracted from the middleware directly, no HTTP wiring needed.

import { describe, expect, it } from "vitest";

// ─── helpers mirrored from the implementation ────────────────────────────────

function b64url(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

async function mintCookie(sub: string, exp: number, secret: string): Promise<string> {
  const payload = b64url(new TextEncoder().encode(`${sub}|${exp}`));
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = b64url(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)));
  return `${payload}.${sig}`;
}

async function isValidEaCookie(value: string, secret: string, nowSec: number): Promise<boolean> {
  const dot = value.lastIndexOf(".");
  if (dot < 1) return false;
  const payload = value.slice(0, dot);
  const claimedSig = value.slice(dot + 1);

  let exp = 0;
  try {
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const pipe = decoded.lastIndexOf("|");
    if (pipe < 1) return false;
    exp = parseInt(decoded.slice(pipe + 1), 10);
  } catch {
    return false;
  }
  if (!Number.isFinite(exp) || exp < nowSec) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );

  let sigBytes: Uint8Array;
  try {
    const bin = atob(claimedSig.replace(/-/g, "+").replace(/_/g, "/"));
    sigBytes = new Uint8Array(Array.from(bin, (c) => c.charCodeAt(0)));
  } catch {
    return false;
  }

  return crypto.subtle.verify("HMAC", key, sigBytes.buffer as ArrayBuffer, new TextEncoder().encode(payload));
}

// ─── tests ───────────────────────────────────────────────────────────────────

const SECRET = "test-secret-32-bytes-padded-here";
const FUTURE = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
const PAST = Math.floor(Date.now() / 1000) - 1; // already expired

describe("mint + verify round-trip", () => {
  it("valid cookie passes verification", async () => {
    const cookie = await mintCookie("user-sub-123", FUTURE, SECRET);
    const ok = await isValidEaCookie(cookie, SECRET, Math.floor(Date.now() / 1000));
    expect(ok).toBe(true);
  });

  it("expired cookie is rejected", async () => {
    const cookie = await mintCookie("user-sub-123", PAST, SECRET);
    const ok = await isValidEaCookie(cookie, SECRET, Math.floor(Date.now() / 1000));
    expect(ok).toBe(false);
  });

  it("wrong secret is rejected", async () => {
    const cookie = await mintCookie("user-sub-123", FUTURE, SECRET);
    const ok = await isValidEaCookie(cookie, "wrong-secret", Math.floor(Date.now() / 1000));
    expect(ok).toBe(false);
  });

  it("tampered payload is rejected", async () => {
    const cookie = await mintCookie("user-sub-123", FUTURE, SECRET);
    const [, sig] = cookie.split(".");
    const tamperedPayload = b64url(new TextEncoder().encode(`evil-sub|${FUTURE}`));
    const forged = `${tamperedPayload}.${sig}`;
    const ok = await isValidEaCookie(forged, SECRET, Math.floor(Date.now() / 1000));
    expect(ok).toBe(false);
  });

  it("malformed cookie (no dot) is rejected", async () => {
    const ok = await isValidEaCookie("nodot", SECRET, Math.floor(Date.now() / 1000));
    expect(ok).toBe(false);
  });

  it("empty string is rejected", async () => {
    const ok = await isValidEaCookie("", SECRET, Math.floor(Date.now() / 1000));
    expect(ok).toBe(false);
  });
});
