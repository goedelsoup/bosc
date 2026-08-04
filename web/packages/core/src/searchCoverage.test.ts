// The search-coverage declaration (#1890) — the internal consistency the post-build guard assumes.
//
// `scripts/check-routes.mjs` measures the fraction against the real build; this asserts the
// declaration it measures against is well-formed and, more to the point, that it can't be gamed
// into reporting a number it hasn't earned.
import { describe, expect, it } from "vitest";
import { COVERAGE_FAMILIES, COVERAGE_FLOOR, searchCoverage, SHARD_GZIP_BUDGET } from "./searchCoverage";

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
    });
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
