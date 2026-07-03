import { describe, expect, it } from "vitest";
import { EVIDENCE_PRIMARY } from "./evidence";
import {
  APPROX_MARKER,
  CUSTODY,
  DOMAINS,
  domainBySlug,
  EVIDENCE_GRAMMAR,
  PIPELINE,
  SKILLS,
  THESIS_FLOW,
} from "./methodology";

// The 12 analytical domains the network Methodology section covers (epic #1126).
const EXPECTED_DOMAIN_COUNT = 12;

describe("evidence grammar", () => {
  it("mirrors the canonical taxonomy in reading order — the legend can't drift from the data", () => {
    expect(EVIDENCE_GRAMMAR.map((g) => g.kind)).toEqual([...EVIDENCE_PRIMARY]);
    for (const g of EVIDENCE_GRAMMAR) {
      expect(g.gloss.length).toBeGreaterThan(0);
    }
  });

  it("names the approximate marker", () => {
    expect(APPROX_MARKER.symbol).toBe("~");
    expect(APPROX_MARKER.gloss.length).toBeGreaterThan(0);
  });
});

describe("thesis + pipeline + custody", () => {
  it("states the four-step thesis flow", () => {
    expect(THESIS_FLOW).toEqual(["source", "structured read", "meaning", "verify"]);
  });

  it("is the three named stages, in order, each with a body", () => {
    expect(PIPELINE.map((s) => s.id)).toEqual(["ingest", "extract", "analyze"]);
    for (const stage of PIPELINE) {
      expect(stage.num).toMatch(/^0[123]$/);
      expect(stage.body.length).toBeGreaterThan(0);
    }
  });

  it("lists the three chain-of-custody guarantees", () => {
    expect(CUSTODY).toHaveLength(3);
    for (const c of CUSTODY) {
      expect(c.title.length).toBeGreaterThan(0);
      expect(c.body.length).toBeGreaterThan(0);
    }
  });
});

describe("the method layer", () => {
  it("is the seven skills, evidentiary-discipline first (the spine)", () => {
    expect(SKILLS).toHaveLength(7);
    expect(SKILLS[0].slug).toBe("evidentiary-discipline");
    expect(new Set(SKILLS.map((s) => s.slug)).size).toBe(SKILLS.length);
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

  it("carries complete, well-formed content for every domain", () => {
    for (const d of DOMAINS) {
      expect(d.slug).toMatch(/^[a-z][a-z-]*[a-z]$/);
      expect(d.method.length).toBeGreaterThan(0);
      expect(d.guardrail.length).toBeGreaterThan(0);
      expect(d.dataSources.length).toBeGreaterThan(0);
      for (const src of d.dataSources) expect(src.trim()).toBe(src);
      // Deep content is fully filled for every domain (the design's structure).
      expect(d.sections.length).toBeGreaterThanOrEqual(1);
      for (const section of d.sections) {
        expect(section.heading.length).toBeGreaterThan(0);
        expect(section.body.length).toBeGreaterThan(0);
      }
    }
  });

  it("gives every domain a two-tag worked example using canonical evidence kinds", () => {
    for (const d of DOMAINS) {
      expect(d.example.before.length).toBeGreaterThan(0);
      expect(d.example.after.length).toBeGreaterThan(0);
      expect(EVIDENCE_PRIMARY).toContain(d.example.first);
      expect(EVIDENCE_PRIMARY).toContain(d.example.second);
    }
  });

  it("resolves each slug via domainBySlug and misses cleanly", () => {
    for (const d of DOMAINS) {
      expect(domainBySlug(d.slug)).toBe(d);
    }
    expect(domainBySlug("no-such-domain")).toBeUndefined();
  });
});
