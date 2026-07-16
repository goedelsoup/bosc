import { describe, expect, it } from "vitest";
import { ASK_LIMITS, validateAsk } from "@watermark/functions/api/_lib/askSchema";

describe("validateAsk", () => {
  it("accepts a trimmed question and an optional turnstile token", () => {
    const r = validateAsk({ question: "  Who signed the NDA?  ", turnstile_token: "tok" });
    expect(r).toEqual({ ok: true, value: { question: "Who signed the NDA?", turnstile_token: "tok" } });
  });

  it("rejects a non-object body", () => {
    expect(validateAsk("nope")).toMatchObject({ ok: false });
  });

  it("rejects unexpected fields (allowlist, not denylist)", () => {
    expect(validateAsk({ question: "ok question", role: "system" })).toMatchObject({
      ok: false,
      error: "unexpected field: role",
    });
  });

  it("rejects a missing or too-short question", () => {
    expect(validateAsk({})).toMatchObject({ ok: false });
    expect(validateAsk({ question: "hi" })).toMatchObject({ ok: false });
  });

  it("rejects an oversized question", () => {
    expect(validateAsk({ question: "x".repeat(ASK_LIMITS.question_max + 1) })).toMatchObject({ ok: false });
  });
});
