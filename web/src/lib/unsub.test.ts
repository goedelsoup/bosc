// Unit tests for the unsubscribe token helpers (#939 E2).

import { describe, expect, it } from "vitest";
import { signUnsubToken, verifyUnsubToken } from "@watermark/functions/api/_lib/unsub";

const SECRET = "test-unsub-secret-32-bytes-long!!";
const SUB = "user-sub-abc123";
const CATEGORY = "tip";

describe("signUnsubToken + verifyUnsubToken — round-trip", () => {
  it("verifies a freshly minted token", async () => {
    const token = await signUnsubToken(SUB, CATEGORY, SECRET);
    const result = await verifyUnsubToken(token, SECRET);
    expect(result).toEqual({ sub: SUB, category: CATEGORY });
  });

  it("returns null for a wrong secret", async () => {
    const token = await signUnsubToken(SUB, CATEGORY, SECRET);
    const result = await verifyUnsubToken(token, "wrong-secret");
    expect(result).toBeNull();
  });

  it("returns null for an expired token", async () => {
    const nowSec = Math.floor(Date.now() / 1000);
    const expiredNow = nowSec - 1; // exp is in the past
    const token = await signUnsubToken(SUB, CATEGORY, SECRET, expiredNow - 30 * 24 * 3600);
    const result = await verifyUnsubToken(token, SECRET);
    expect(result).toBeNull();
  });

  it("returns null for a tampered token", async () => {
    const token = await signUnsubToken(SUB, CATEGORY, SECRET);
    const parts = token.split(".");
    // Replace the entire signature with a known-wrong value. Flipping only the last
    // base64url character is unreliable: for 32-byte HMAC output the low 2 bits of the
    // last character are padding and don't affect the decoded bytes.
    parts[3] = parts[3] === "AAAA" ? "BBBB" : "AAAA";
    const tampered = parts.join(".");
    const result = await verifyUnsubToken(tampered, SECRET);
    expect(result).toBeNull();
  });

  it("returns null for a malformed token (wrong segment count)", async () => {
    const result = await verifyUnsubToken("only.three.parts", SECRET);
    expect(result).toBeNull();
  });

  it("preserves sub and category exactly (no truncation)", async () => {
    const longSub = "a".repeat(64);
    const token = await signUnsubToken(longSub, "new_source", SECRET);
    const result = await verifyUnsubToken(token, SECRET);
    expect(result).toEqual({ sub: longSub, category: "new_source" });
  });
});
