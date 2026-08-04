// The search-coverage declaration (#1890) — the internal consistency the post-build guard assumes.
//
// `scripts/check-routes.mjs` measures the fraction against the real build; this asserts the
// declaration it measures against is well-formed and, more to the point, that it can't be gamed
// into reporting a number it hasn't earned.
import { describe, expect, it } from "vitest";
import { siteBase } from "./routes";
import { searchShardRefs } from "./search";
import { COVERAGE_FAMILIES, COVERAGE_FLOOR, searchCoverage, SHARD_GZIP_BUDGET } from "./searchCoverage";
import { SITES } from "./sites";

describe("the coverage declaration", () => {
  it("gives every family a compilable pattern, a label, a verdict, and a reason", () => {
    expect(COVERAGE_FAMILIES.length).toBeGreaterThan(0);
    for (const f of COVERAGE_FAMILIES) {
      expect(() => new RegExp(f.pattern), `bad pattern: ${f.pattern}`).not.toThrow();
      expect(f.pattern.startsWith("^"), `unanchored pattern: ${f.pattern}`).toBe(true);
      expect(f.label.length).toBeGreaterThan(0);
      expect(["not-content", "represented", "gap"]).toContain(f.verdict);
      // The reason is the whole point — a family with a one-word note is an exemption, not a
      // declaration. Long enough to have said why.
      expect(f.note.length, `${f.label}: note too thin to be a reason`).toBeGreaterThan(60);
    }
  });

  it("keeps at least one family counted as a gap", () => {
    // The guard against the failure mode this module exists to prevent: declaring every remaining
    // miss `not-content` and reporting 100%. If the gaps genuinely close, this test is the place
    // that should have to change, deliberately, alongside the floor.
    expect(COVERAGE_FAMILIES.some((f) => f.verdict === "gap")).toBe(true);
  });

  it("holds the floor high enough to mean something", () => {
    // 13% was the finding. A floor that admits it would be no floor at all.
    expect(COVERAGE_FLOOR).toBeGreaterThan(0.9);
    expect(COVERAGE_FLOOR).toBeLessThanOrEqual(1);
  });

  it("serializes to what the post-build guard reads out of dist/", () => {
    const decl = searchCoverage();
    expect(JSON.parse(JSON.stringify(decl))).toEqual({
      families: COVERAGE_FAMILIES,
      floor: COVERAGE_FLOOR,
      shardGzipBudget: SHARD_GZIP_BUDGET,
      shards: ["/search-index.json", ...searchShardRefs().map((r) => r.path)],
    });
  });

  it("owes a shard for the root and for every selectable site", () => {
    // The guard compares the build against this set rather than counting, so the set has to be
    // derived — a hand-written list would go stale the moment a site is promoted.
    const { shards } = searchCoverage();
    expect(shards[0]).toBe("/search-index.json");
    expect(shards.length).toBe(SITES.filter((s) => s.selectable).length + 1);
    expect(new Set(shards).size).toBe(shards.length);
  });

  it("excludes exactly the sites that ship a shard from the non-selectable gap", () => {
    // The pattern is derived through `siteBase`, so the reference site's URL id
    // (lima → american-sugar-creek-allen-co) has to survive the round trip. A hardcoded list here
    // would silently reclassify a promoted site's pages as an unsearchable gap.
    const family = COVERAGE_FAMILIES.find((f) => f.label === "A non-selectable site's own pages");
    expect(family).toBeDefined();
    const re = new RegExp(family!.pattern);
    for (const site of SITES.filter((s) => s.selectable)) {
      expect(re.test(`${siteBase(site.slug)}/timeline/`), `${site.slug} treated as unsharded`).toBe(false);
    }
    // …and a site that ships no shard still matches, or the gap would be invisible.
    const unsharded = SITES.find((s) => !s.selectable);
    expect(unsharded).toBeDefined();
    expect(re.test(`${siteBase(unsharded!.slug)}/stories/x/`)).toBe(true);
  });

  it("excludes only what it names — the patterns don't swallow the record", () => {
    // A pattern like `^/network/` would exclude the entire corpus from the denominator and make
    // the number meaningless. Assert that the excluding verdicts miss the things search exists for.
    const excluding = COVERAGE_FAMILIES.filter((f) => f.verdict !== "gap").map((f) => new RegExp(f.pattern));
    const mustCount = [
      "/network/american-sugar-creek-allen-co/doc/7k3m9qpb/",
      "/network/american-sugar-creek-allen-co/site/records/deeds/",
      "/network/fort-wayne/site/documents/",
      "/wiki/concepts/consumptive-use/",
      "/docs/course/",
      "/",
    ];
    for (const route of mustCount) {
      expect(
        excluding.some((re) => re.test(route)),
        `"${route}" is excluded from the coverage denominator`,
      ).toBe(false);
    }
  });
});
