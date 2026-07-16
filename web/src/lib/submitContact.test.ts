import { describe, expect, it } from "vitest";
import { buildIssue, dedupeInput } from "@watermark/functions/api/_lib/issue";
import { LIMITS, type Submission, validateSubmission } from "@watermark/functions/api/_lib/schema";

// A contact value with both an email and a phone, so absence assertions catch either piece.
const CONTACT = "secret@private.example / +15551234567";

const base = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  kind: "tip",
  body: "The ROADWAY subtotal looks off by $20k.",
  turnstile_token: "tok",
  ...over,
});

describe("submission contact field — schema validation (#242)", () => {
  it("accepts an optional contact and trims it", () => {
    const r = validateSubmission(base({ contact: `  ${CONTACT}  ` }));
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.value.contact).toBe(CONTACT);
  });

  it("omits contact when absent or blank — not an error", () => {
    const r1 = validateSubmission(base());
    expect(r1.ok && r1.value.contact).toBeUndefined();
    const r2 = validateSubmission(base({ contact: "   " }));
    expect(r2.ok).toBe(true);
    if (r2.ok) expect(r2.value.contact).toBeUndefined();
  });

  it("rejects a non-string or over-long contact", () => {
    expect(validateSubmission(base({ contact: 42 })).ok).toBe(false);
    expect(validateSubmission(base({ contact: "x".repeat(LIMITS.contact + 1) })).ok).toBe(false);
  });

  it("still rejects any field outside the allowlist (no abuse-surface growth)", () => {
    const r = validateSubmission(base({ email: "x@y.z" }));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toContain("unexpected field");
  });
});

describe("submission contact — provably absent from the public issue (#242 acceptance)", () => {
  const sub: Submission = {
    kind: "correction",
    body: "The subtotal disputes the detail sum.",
    target: { ref_kind: "record", ref_id: "recorder/deeds", ref_label: "A Deed" },
    evidence_url: "https://example.gov/x.pdf",
    contact: CONTACT,
    turnstile_token: "tok",
  };

  it("buildIssue never echoes the contact into the title, body, or labels", () => {
    const issue = buildIssue(sub, "deadbeefcafe");
    for (const surface of [issue.title, issue.body, JSON.stringify(issue.labels)]) {
      expect(surface).not.toContain(CONTACT);
      expect(surface).not.toContain("secret@private.example");
      expect(surface).not.toContain("15551234567");
    }
  });

  it("the dedupe input ignores contact (same body+target ⇒ identical hash input)", () => {
    const withContact = dedupeInput(sub);
    const without = dedupeInput({ ...sub, contact: undefined });
    expect(withContact).toBe(without);
    expect(withContact).not.toContain("secret@private.example");
  });
});
