/**
 * The locator map against the REAL registry (#2034, epic #2033).
 *
 * The geometry itself is tested over fixtures in `packages/charts/src/networkMap.test.ts`. These
 * are the assertions that need the actual 38 sites in scope — that nothing is dropped, that the
 * schematic divide does not contradict the registry it is drawn beside, and that the phase
 * vocabulary the chart package restates has not drifted from the one the registry defines.
 */
import { describe, expect, it } from "vitest";
import type { MapPhase } from "@watermark/charts/networkMap";
import { divideLatAt } from "@watermark/charts/networkMap";
import { basinForSlug } from "@watermark/core/placement";
import { SITES, sitePoint, type SiteStatus } from "@watermark/core/sites";
import { networkMapModel, networkMapRows } from "./networkMap";

const model = networkMapModel();

/** Ray casting in the map's own projected coordinates — the space the reader actually sees. */
function insideOutline(x: number, y: number): boolean {
  const pts = model.outline.points;
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[i];
    const b = pts[j];
    if (a.y > y !== b.y > y && x < ((b.x - a.x) * (y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

describe("network locator map, against the registry (#2034)", () => {
  it("places or names every registered site — nothing is dropped", () => {
    expect(model.markers.length + model.unplaced.length).toBe(SITES.length);
    const seen = new Set([...model.markers, ...model.unplaced].map((s) => s.slug));
    expect(seen.size).toBe(SITES.length);
  });

  it("never guesses a coordinate: a site the registry has no point for goes unplaced", () => {
    const without = SITES.filter((s) => sitePoint(s.slug) === null).map((s) => s.slug);
    // Non-empty until #2037 backfills the 12 tracking sites; the assertion holds either way.
    expect(model.unplaced.map((u) => u.slug).sort()).toEqual([...without].sort());
    for (const slug of without) {
      expect(model.markers.some((m) => m.slug === slug)).toBe(false);
    }
  });

  it("gives every marker the registry's own destination", () => {
    for (const m of model.markers) {
      const site = SITES.find((s) => s.slug === m.slug);
      expect(m.href).toBe(site?.href);
      expect(m.href).toBeTruthy();
    }
  });

  it("resolves every site's drainage from its major basin", () => {
    for (const row of networkMapRows()) {
      // No site may reach the `?? "erie"` fallback — that would be a registry authoring error,
      // and it should surface here by name rather than as half the map being quietly wrong.
      expect(basinForSlug(row.basinMajor), `unknown basin for ${row.slug}`).toBeDefined();
      expect(row.divide).toBe(basinForSlug(row.basinMajor)?.divide);
    }
  });

  /**
   * The schematic's accountability. The divide is traced to the county, not the ridge — so rather
   * than assert its vertices, assert what it must never do: contradict the registry drawn beside
   * it. Every Lake Erie-draining site belongs north of the line, every Ohio River-draining site
   * south of it.
   */
  it("draws the divide so no site falls on the wrong side of its own drainage", () => {
    const wrong: string[] = [];
    const unchecked: string[] = [];
    for (const m of model.markers) {
      const lat = divideLatAt(m.point.lon);
      if (lat === null) {
        unchecked.push(m.slug);
        continue;
      }
      if ((m.divide === "erie") !== m.point.lat > lat) {
        wrong.push(`${m.slug} (${m.divide}, ${m.point.lat} vs divide ${lat.toFixed(3)})`);
      }
    }
    expect(wrong).toEqual([]);
    // The line is drawn across OHIO and stops at the state line, so it makes no claim about the
    // network's one Indiana site. Asserted rather than skipped silently: if the divide is ever
    // re-traced, this says out loud how much of the network stopped being covered.
    expect(unchecked).toEqual(["fort-wayne"]);
  });

  /**
   * The guard on the one duplicated type. `@watermark/charts` restates `SiteStatus` as `MapPhase`
   * because importing it would drag `bundle.ts`'s `node:fs` into a package whose tsconfig sets
   * `"types": []` to forbid exactly that. These two assignments fail to compile if either union
   * gains or loses a member, so the duplication is checked rather than trusted.
   */
  it("keeps the chart package's phase vocabulary in sync with the registry's", () => {
    const asPhase: MapPhase = "live" as SiteStatus;
    const asStatus: SiteStatus = "live" as MapPhase;
    expect(asPhase).toBe(asStatus);
    // And every phase the registry actually uses is one the map accepts.
    const used = new Set<string>(SITES.map((s) => s.status));
    expect([...used].sort()).toEqual(
      [...used].filter((p) => ["live", "building", "queued", "tracking"].includes(p)).sort(),
    );
  });
});

/**
 * The registration guarantee, stated as an assertion rather than a claim in a doc comment.
 *
 * The whole reason `networkMap.ts` projects its border instead of shipping a drawn SVG path is
 * that a hand-drawn outline and a projected dot can disagree — and the failure mode is a site
 * rendering visually outside its own state. This checks the thing that would actually be wrong,
 * in the map's own projected coordinates: every Ohio site inside the drawn Ohio, and the one
 * Indiana site outside it.
 *
 * It is also the guard on the simplification budget. The border is ~40 vertices for a boundary
 * with thousands, and it is free to be coarse — right up until coarseness moves a marker across
 * it. Cut a corner near Portsmouth, Cincinnati, or the lake shore and this fails by name.
 */
describe("registration — every marker lands in the state it is filed under", () => {
  it("puts each site inside or outside the drawn Ohio according to its registry state", () => {
    const misplaced: string[] = [];
    for (const m of model.markers) {
      const site = SITES.find((s) => s.slug === m.slug);
      const inside = insideOutline(m.x, m.y);
      if ((site?.state === "OH") !== inside) {
        misplaced.push(`${m.slug} (filed ${site?.state}, drawn ${inside ? "inside" : "outside"} OH)`);
      }
    }
    expect(misplaced).toEqual([]);
  });

  it("covers the sites nearest the border, where a coarse outline would fail first", () => {
    // River and lake towns sit ON the boundary in real geography, so they are the cases a
    // simplified outline is most likely to push across. Named so the coverage is deliberate.
    for (const slug of ["portsmouth", "west-union", "toledo", "sandusky", "cincinnati"]) {
      const m = model.markers.find((k) => k.slug === slug);
      if (!m) continue; // not every one is registered; those that are must be inside
      expect(insideOutline(m.x, m.y), `${slug} drawn outside Ohio`).toBe(true);
    }
    const ftw = model.markers.find((k) => k.slug === "fort-wayne");
    expect(insideOutline(ftw!.x, ftw!.y), "fort-wayne drawn inside Ohio").toBe(false);
  });
});
