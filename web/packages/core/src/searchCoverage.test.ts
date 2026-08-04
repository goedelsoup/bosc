// The search-coverage declaration (#1890) — the internal consistency the post-build guard assumes.
//
// `scripts/check-routes.mjs` measures the fraction against the real build; this asserts the
// declaration it measures against is well-formed and, more to the point, that it can't be gamed
// into reporting a number it hasn't earned.
import { describe, expect, it } from "vitest";
import { LIMA_SLUG, siteBase } from "./routes";
import { buildSiteSearchIndex, searchShardRefs } from "./search";
import { COVERAGE_FAMILIES, COVERAGE_FLOOR, searchCoverage, SHARD_GZIP_BUDGET } from "./searchCoverage";
import { comingSoonStories, SITES, surfacedStories } from "./sites";

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

  it("declares no gap it hasn't earned the right to leave open", () => {
    // This assertion used to read "keeps at least one family counted as a gap", guarding the
    // failure mode the module exists to prevent: reclassifying every remaining miss `not-content`
    // and reporting 100%. Its own comment named this edit as the one that should have to change it
    // — "if the gaps genuinely close, deliberately, alongside the floor" — and #1908 closed the
    // last two by fixing the wayfinding they described rather than by re-labelling them.
    //
    // So the inverted form is now the honest one: **no `gap` is declared**, and a future one is
    // legitimate only if it arrives with a floor that reflects the misses it admits. The anti-
    // gaming duty passes to `COVERAGE_FLOOR`, which is measured against the real build and cannot
    // be satisfied by writing a better note.
    expect(COVERAGE_FAMILIES.filter((f) => f.verdict === "gap").map((f) => f.label)).toEqual([]);
  });

  it("no longer declares the nav model's uncarried pages a gap (#1908)", () => {
    // Retired by fixing what they named, so a family reappearing over any of them would mean the
    // wayfinding had regressed — which is precisely what this file is for recording.
    //
    // Per site: the enclave and groundwater reads left at #1915 (lens facets), and the record's
    // how-to-read primer is a declared contextual leaf, indexed and linked from every records
    // index. At the root: `/about/sustainability` joined the About menu, `/network/connect` was
    // always in the chrome and is now reachable by the index too, and `/about/data` was retired
    // to `/about/catalog` — the same feed, one address.
    const closed = [
      `${siteBase(LIMA_SLUG)}/site/records/how-to-read/`,
      `${siteBase(LIMA_SLUG)}/environment/groundwater/`,
      "/about/sustainability/",
      "/about/catalog/",
      "/about/contributing/",
      "/privacy/",
      "/network/connect/",
    ];
    for (const route of closed) {
      const claimed = COVERAGE_FAMILIES.filter((f) => new RegExp(f.pattern).test(route));
      expect(
        claimed.map((f) => f.label),
        `"${route}" is still declared`,
      ).toEqual([]);
    }
  });

  it("no longer declares the peer-only entity gap — the wiki builds from the network (#1906)", () => {
    // The family was retired by widening the build, not by reclassifying it. A family reappearing
    // over `/wiki/entities/` would mean the union had regressed to one bundle, and the coverage
    // declaration is exactly where that admission would be written down — so it's asserted here.
    const claimed = COVERAGE_FAMILIES.filter((f) =>
      new RegExp(f.pattern).test("/wiki/entities/general-dynamics/"),
    );
    expect(claimed.map((f) => f.label)).toEqual([]);
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
      contextual: decl.contextual,
      shards: ["/search-index.json", ...searchShardRefs().map((r) => r.path)],
    });
  });

  it("carries every site's contextual leaves, each with a named carrier (#1908)", () => {
    // The guard asserts some built page really links each of these, so the set has to arrive
    // complete: a leaf missing here is a page whose reachability nothing checks, which is the state
    // this register exists to end. Asserted as a UNION over sites — the submit form is one route per
    // site and the how-to-read primer is one route the whole network points at, and a declaration
    // read under a single ambient site would silently drop three of the four submits.
    const { contextual } = searchCoverage();
    const submits = contextual.filter((l) => l.href.endsWith("/submit"));
    expect(submits.length).toBe(SITES.filter((s) => s.selectable).length);
    expect(contextual.some((l) => l.href.endsWith("/site/records/how-to-read"))).toBe(true);
    for (const leaf of contextual) {
      expect(leaf.href.startsWith("/"), leaf.href).toBe(true);
      expect(leaf.via.length, `${leaf.href}: no carrier named`).toBeGreaterThan(20);
    }
    expect(new Set(contextual.map((l) => l.href)).size).toBe(contextual.length);
  });

  it("owes a shard for the root and for every site that ships one", () => {
    // The guard compares the build against this set rather than counting, so the set has to be
    // derived — a hand-written list would go stale the moment a site is promoted.
    const { shards } = searchCoverage();
    expect(shards[0]).toBe("/search-index.json");
    expect(shards.length).toBe(searchShardRefs().length + 1);
    // Every selectable site is owed one, and since #1907 so is a peer publishing a walk.
    expect(shards.length).toBeGreaterThan(SITES.filter((s) => s.selectable).length);
    expect(new Set(shards).size).toBe(shards.length);
  });

  it("no longer declares a non-selectable site's pages a gap — they ship a shard (#1907)", () => {
    // The family was retired by fixing the axis, not by reclassifying it: search shards on what a
    // site publishes rather than on whether it can be switched into. A family reappearing over a
    // peer's story routes would mean the shard list had regressed to `selectable`.
    const peer = SITES.find((s) => !s.selectable && comingSoonStories(s.slug).length > 0);
    expect(peer, "no peer publishes a walk — this asserts nothing").toBeDefined();
    const root = `${siteBase(peer!.slug)}/stories/${comingSoonStories(peer!.slug)[0].codename}/`;
    const claimed = COVERAGE_FAMILIES.filter((f) => new RegExp(f.pattern).test(root));
    expect(claimed.map((f) => f.label)).toEqual([]);
    // …and that root really is indexed, which is what makes leaving it undeclared correct.
    expect(buildSiteSearchIndex(peer!.slug).map((d) => d.url)).toContain(root);
  });

  it("represents a held story's interior by the row that IS indexed", () => {
    // The `represented` contract: the note names the row, and the routes it excuses are exactly the
    // ones that render the same interstitial. Derived from the registry, so a story going readable
    // returns its chapters to the denominator on that edit rather than on a later cleanup.
    const family = COVERAGE_FAMILIES.find((f) => f.label === "A held story's interior routes");
    expect(family).toBeDefined();
    expect(family!.verdict).toBe("represented");
    const re = new RegExp(family!.pattern);
    const held = SITES.flatMap((s) => comingSoonStories(s.slug).map((ref) => ({ s, ref })));
    expect(held.length).toBeGreaterThan(0);
    for (const { s, ref } of held) {
      const root = `${siteBase(s.slug)}/stories/${ref.codename}/`;
      expect(re.test(`${root}contents/`), `${s.slug}: contents not represented`).toBe(true);
      expect(re.test(`${root}water/`), `${s.slug}: a chapter not represented`).toBe(true);
      // The root itself is a real row, so it must stay in the denominator and be counted covered.
      expect(re.test(root), `${s.slug}: the story root excused instead of indexed`).toBe(false);
    }
    // A readable story's chapters are separate destinations and must NOT be excused.
    const readable = SITES.flatMap((s) => surfacedStories(s.slug).map((ref) => ({ s, ref })));
    expect(readable.length).toBeGreaterThan(0);
    for (const { s, ref } of readable) {
      expect(re.test(`${siteBase(s.slug)}/stories/${ref.codename}/water/`)).toBe(false);
    }
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
