// Evidence tiering heuristic tests (#1591).
// The pure classifier: evidence class (feed + source_kind) × relevance band (score ÷ top).

import { describe, expect, it } from "vitest";
import { BACKGROUND_BAND, DIRECT_BAND, evidenceClass, tierHit } from "@watermark/functions/api/_lib/mcpTier";

describe("evidenceClass", () => {
  it("classifies extracted document-sourced feeds as primary", () => {
    for (const feed of ["records", "documents", "timeline", "meetings"]) {
      expect(evidenceClass(feed, "document")).toBe("primary");
    }
  });

  it("classifies derived/organizational views as secondary", () => {
    for (const feed of ["entities", "people", "places"]) {
      expect(evidenceClass(feed, "document")).toBe("secondary");
    }
  });

  it("classifies the glossary and any derived source as background", () => {
    expect(evidenceClass("concepts", "derived")).toBe("background");
    // source_kind `derived` outranks the feed — a derived record is still editorial context.
    expect(evidenceClass("records", "derived")).toBe("background");
  });

  it("treats a missing source_kind as non-derived", () => {
    expect(evidenceClass("records", null)).toBe("primary");
    expect(evidenceClass("entities", undefined)).toBe("secondary");
  });
});

describe("tierHit", () => {
  const TOP = 1.0;

  it("promotes top-band primary evidence to direct", () => {
    const v = tierHit("records", "document", DIRECT_BAND * TOP, TOP);
    expect(v.tier).toBe("direct");
    expect(v.reason).toMatch(/primary evidence/);
  });

  it("keeps the pool leader (ratio 1.0) direct when it is primary", () => {
    expect(tierHit("documents", "document", TOP, TOP).tier).toBe("direct");
  });

  it("never promotes a background-class hit, however high it scores", () => {
    // A glossary concept at the very top score is still context, not direct evidence.
    const v = tierHit("concepts", "derived", TOP, TOP);
    expect(v.tier).toBe("background");
    expect(v.reason).toMatch(/context, not evidence/);
  });

  it("tiers a mid-band primary hit as corroborating, not direct", () => {
    const mid = (DIRECT_BAND + BACKGROUND_BAND) / 2; // between the two thresholds
    const v = tierHit("records", "document", mid * TOP, TOP);
    expect(v.tier).toBe("corroborating");
    expect(v.reason).toMatch(/primary evidence/);
  });

  it("tiers a top-band secondary view as corroborating (secondary can't be direct)", () => {
    const v = tierHit("entities", "document", TOP, TOP);
    expect(v.tier).toBe("corroborating");
    expect(v.reason).toMatch(/secondary/);
  });

  it("demotes a weak-relevance primary hit to background", () => {
    const weak = (BACKGROUND_BAND / 2) * TOP; // below the background band
    const v = tierHit("records", "document", weak, TOP);
    expect(v.tier).toBe("background");
    expect(v.reason).toMatch(/weak relevance/);
  });

  it("uses the band boundaries inclusively for direct and exclusively for background", () => {
    // exactly at DIRECT_BAND → direct; exactly at BACKGROUND_BAND → corroborating (not background)
    expect(tierHit("records", "document", DIRECT_BAND * TOP, TOP).tier).toBe("direct");
    expect(tierHit("records", "document", BACKGROUND_BAND * TOP, TOP).tier).toBe("corroborating");
    // just under BACKGROUND_BAND → background
    expect(tierHit("records", "document", (BACKGROUND_BAND - 0.001) * TOP, TOP).tier).toBe("background");
  });

  it("degrades every hit to background when the pool has no positive top score", () => {
    expect(tierHit("records", "document", 0, 0).tier).toBe("background");
  });

  it("normalizes to the pool top, not an absolute scale (works for tiny RRF scores)", () => {
    // RRF fused scores are ~0.03; a hit at 65% of a 0.033 top is still top-band → direct.
    const top = 0.033;
    expect(tierHit("records", "document", 0.65 * top, top).tier).toBe("direct");
  });
});
