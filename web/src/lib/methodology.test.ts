import { describe, expect, it } from "vitest";
import { EVIDENCE_PRIMARY } from "./evidence";
import { DOMAINS, domainBySlug, EVIDENCE_GRAMMAR, PIPELINE, THESIS_FLOW } from "./methodology";

// The 12 analytical domains the network Methodology section covers (epic #1126).
const EXPECTED_DOMAIN_COUNT = 12;

describe("evidence grammar", () => {
  it("mirrors the canonical taxonomy in reading order — the legend can't drift from the data", () => {
    expect(EVIDENCE_GRAMMAR.map((g) => g.kind)).toEqual([...EVIDENCE_PRIMARY]);
    for (const g of EVIDENCE_GRAMMAR) {
      expect(g.gloss.length).toBeGreaterThan(0);
    }
  });
});

describe("thesis + pipeline", () => {
  it("states the four-step thesis flow", () => {
    expect(THESIS_FLOW).toEqual(["source", "structured read", "meaning", "verify"]);
  });

  it("is the three named stages, in order, each with method + discipline", () => {
    expect(PIPELINE.map((s) => s.id)).toEqual(["ingest", "extract", "analyze"]);
    for (const stage of PIPELINE) {
      expect(stage.num).toMatch(/^0[123]$/);
      expect(stage.method.length).toBeGreaterThan(0);
      expect(stage.discipline.length).toBeGreaterThan(0);
    }
  });
});

describe("domains", () => {
  it("covers all twelve", () => {
    expect(DOMAINS).toHaveLength(EXPECTED_DOMAIN_COUNT);
  });

  it("has unique slugs and labels", () => {
    expect(new Set(DOMAINS.map((d) => d.slug)).size).toBe(DOMAINS.length);
    expect(new Set(DOMAINS.map((d) => d.label)).size).toBe(DOMAINS.length);
  });

  it("carries a complete hub-card summary for every domain", () => {
    for (const d of DOMAINS) {
      expect(d.slug).toMatch(/^[a-z][a-z-]*[a-z]$/);
      expect(d.method.length).toBeGreaterThan(0);
      expect(d.guardrail.length).toBeGreaterThan(0);
      expect(d.dataSources.length).toBeGreaterThan(0);
      expect(d.sources.length).toBeGreaterThan(0);
      for (const src of d.dataSources) expect(src.trim()).toBe(src);
    }
  });

  it("resolves each slug via domainBySlug and misses cleanly", () => {
    for (const d of DOMAINS) {
      expect(domainBySlug(d.slug)).toBe(d);
    }
    expect(domainBySlug("no-such-domain")).toBeUndefined();
  });

  it("shape-checks any deep content that is present (filled in #1131)", () => {
    for (const d of DOMAINS) {
      for (const section of d.sections) {
        expect(section.heading.length).toBeGreaterThan(0);
        expect(section.body.length).toBeGreaterThan(0);
      }
      for (const ex of d.examples) {
        expect(ex.claim.length).toBeGreaterThan(0);
        expect(EVIDENCE_PRIMARY).toContain(ex.kind);
      }
    }
  });
});
