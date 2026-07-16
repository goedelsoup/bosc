// narrative / legal / reference doc maps (#592) — the `*BySlug` lookups, the publish-gating
// allowlists (MIGRATED / PUBLISHED_LEGAL / PUBLISHED_REFERENCE), the repo-path→slug resolvers
// the rehype link rewriter consults, and narrative's LINK_MAP. Pure data + small transforms,
// previously untested; these pin the invariants the routing + link-rewrite layers assume.
import { describe, expect, it } from "vitest";
import { LEGAL, LEGAL_GROUPS, PUBLISHED_LEGAL, legalBySlug, legalSlugForRepoPath } from "./legal";
import { bySlug, LINK_MAP, MIGRATED, NARRATIVE, slugForRepoPath } from "./narrative";
import { PUBLISHED_REFERENCE, REFERENCE, refBySlug, refSlugForRepoPath } from "./reference";

describe("narrative map (#592)", () => {
  it("has unique slugs, each resolvable via bySlug", () => {
    expect(bySlug.size).toBe(NARRATIVE.length);
    for (const d of NARRATIVE) expect(bySlug.get(d.slug)).toBe(d);
  });

  it("slugForRepoPath round-trips every migrated doc and is empty-safe", () => {
    for (const d of NARRATIVE) expect(slugForRepoPath(`docs/${d.repo}`)).toBe(d.slug);
    expect(slugForRepoPath("docs/DOSSIER.md")).toBe("dossier"); // strips dir + .md, lowercases
  });

  it("MIGRATED is one prefixed entry per doc", () => {
    expect(MIGRATED.size).toBe(NARRATIVE.length);
    for (const d of NARRATIVE) expect(MIGRATED.has(`docs/${d.repo}`)).toBe(true);
  });

  it("LINK_MAP keys are .md targets and values are root-absolute routes", () => {
    for (const [key, value] of Object.entries(LINK_MAP)) {
      expect(key.endsWith(".md")).toBe(true);
      expect(value.startsWith("/")).toBe(true);
    }
  });
});

describe("legal map (#592)", () => {
  it("has unique slugs, each resolvable via legalBySlug", () => {
    expect(legalBySlug.size).toBe(LEGAL.length);
    for (const d of LEGAL) expect(legalBySlug.get(d.slug)).toBe(d);
  });

  it("legalSlugForRepoPath resolves a known extracted path, '' for unknown", () => {
    for (const d of LEGAL) expect(legalSlugForRepoPath(`data/extracted/${d.repo}`)).toBe(d.slug);
    expect(legalSlugForRepoPath("data/extracted/nope.md")).toBe("");
  });

  it("PUBLISHED_LEGAL is one prefixed entry per doc", () => {
    expect(PUBLISHED_LEGAL.size).toBe(LEGAL.length);
    for (const d of LEGAL) expect(PUBLISHED_LEGAL.has(`data/extracted/${d.repo}`)).toBe(true);
  });

  it("LEGAL_GROUPS is the distinct groups, covering every doc", () => {
    expect(new Set(LEGAL_GROUPS).size).toBe(LEGAL_GROUPS.length); // distinct
    for (const d of LEGAL) expect(LEGAL_GROUPS).toContain(d.group);
  });
});

describe("reference map (#592)", () => {
  it("has unique slugs, each resolvable via refBySlug", () => {
    expect(refBySlug.size).toBe(REFERENCE.length);
    for (const d of REFERENCE) expect(refBySlug.get(d.slug)).toBe(d);
  });

  it("refSlugForRepoPath resolves a known reference path, '' for unknown", () => {
    for (const d of REFERENCE) expect(refSlugForRepoPath(`data/reference/${d.repo}`)).toBe(d.slug);
    expect(refSlugForRepoPath("data/reference/nope/README.md")).toBe("");
  });

  it("PUBLISHED_REFERENCE is one prefixed entry per doc", () => {
    expect(PUBLISHED_REFERENCE.size).toBe(REFERENCE.length);
    for (const d of REFERENCE) expect(PUBLISHED_REFERENCE.has(`data/reference/${d.repo}`)).toBe(true);
  });
});
