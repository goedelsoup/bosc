import { describe, expect, it } from "vitest";
import { NETWORK_NOUNS, TAXONOMY, canonicalIndex } from "./taxonomy";
import { hypothesisHref } from "./wiki";

// The decision record for #1892 (one taxonomy per noun). These assertions ARE the design call:
// change them only when the boundary itself is being re-settled, not to make a build pass.

describe("the noun taxonomy (#1892)", () => {
  it("declares exactly one canonical per noun, each with stated reasoning", () => {
    for (const noun of Object.values(TAXONOMY)) {
      expect(noun.index.startsWith("/")).toBe(true);
      expect(noun.index.endsWith("/")).toBe(true);
      expect(noun.note.length).toBeGreaterThan(0);
      expect(["network-global", "per-site"]).toContain(noun.scope);
    }
  });

  it("keeps entities, concepts, and hypotheses network-global — the wiki is their one build", () => {
    expect(NETWORK_NOUNS.map((n) => n.kind)).toEqual(["entity", "concept", "hypothesis"]);
    expect(TAXONOMY.entity.index).toBe("/wiki/entities/");
    expect(TAXONOMY.concept.index).toBe("/wiki/concepts/");
    expect(TAXONOMY.hypothesis.index).toBe("/wiki/hypotheses/");
  });

  it("builds concepts ONCE — the per-site glossary render is retired, and the note says why", () => {
    // 75 of 77 glossary entries were byte-identical in every committed bundle; the duplication
    // (#1567's per-site render) is what #1892 removed. `/network/<site>/site/concepts/*` 301s
    // to the wiki (public/_redirects) — no page template may bring the route back.
    expect(TAXONOMY.concept.scope).toBe("network-global");
    expect(TAXONOMY.concept.note).toContain("#1892");
    expect(TAXONOMY.concept.note).toContain("#1567");
  });

  it("keeps people per-site — the site profile is canonical, the wiki entity is the spine", () => {
    expect(TAXONOMY.person.scope).toBe("per-site");
    expect(canonicalIndex("person", "fort-wayne")).toBe("/network/fort-wayne/site/people/");
    expect(canonicalIndex("person", "lima")).toBe("/network/american-sugar-creek-allen-co/site/people/");
    // A per-site noun has no siteless canonical — asking for one is a caller bug, not a default.
    expect(() => canonicalIndex("person")).toThrow(/per-site/);
  });

  it("declares the scorecard as the hypotheses' projection — a second read, not a second record", () => {
    expect(TAXONOMY.hypothesis.projection).toEqual({
      route: "/research/hypotheses",
      label: "Cross-site scorecard",
    });
    // No other noun has one: a projection is the exception that must be declared, not a pattern.
    expect(TAXONOMY.entity.projection).toBeUndefined();
    expect(TAXONOMY.concept.projection).toBeUndefined();
    expect(TAXONOMY.person.projection).toBeUndefined();
  });

  it("agrees with the href helpers the pages actually use", () => {
    expect(hypothesisHref("water").startsWith(TAXONOMY.hypothesis.index)).toBe(true);
    expect(canonicalIndex("concept")).toBe(TAXONOMY.concept.index);
  });
});
