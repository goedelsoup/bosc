import { describe, expect, it } from "vitest";
import { REFERENCE, scopedReference } from "./reference";

// Pinned against the committed fixture pair used across the readiness tests: `sites/lima` (the live
// reference build, which owns the whole catalog) vs `sites/fort-wayne` (a real Maumee-basin peer in
// Indiana). The reference section must scope to the site's OWN datasets (catalog `site_scope`,
// resolved per-site in the bundle) — never leak the reference build's Lima/Allen-County datasets
// verbatim (#1260).

describe("reference dataset scope link", () => {
  it("every published dataset names at least one backing catalog entry", () => {
    // The scope seam: an empty `catalogIds` would silently drop the dataset from every site (it can
    // own no matching entry), so the link is required, not optional.
    for (const d of REFERENCE) expect(d.catalogIds.length).toBeGreaterThan(0);
  });
});

describe("scopedReference", () => {
  it("the reference build keeps its full set (it owns the whole catalog)", () => {
    expect(scopedReference("lima").map((d) => d.slug)).toEqual([
      "echo",
      "allen-gis",
      "lima-gis",
      "rsei",
      "gleif",
      "economics",
      "eia",
      "ohio-waterwells",
      "wbd",
    ]);
  });

  it("a sibling site sees only the datasets it owns — never Lima's `lima-legacy` set", () => {
    const fw = scopedReference("fort-wayne").map((d) => d.slug);
    // Its own / shared datasets surface: the Maumee ECHO inventory (shared basin), its own RSEI +
    // economics baseline (slug-scoped), the GLEIF resolution (basin-shared), and the EIA grid /
    // consumer series every site's backdrop floor is keyed to (#1885).
    expect(fw).toEqual(["echo", "rsei", "gleif", "economics", "eia"]);
    // The reference build's Lima/Allen-County-only datasets (all `lima-legacy`) must NOT leak.
    expect(fw).not.toContain("allen-gis");
    expect(fw).not.toContain("lima-gis");
    expect(fw).not.toContain("wbd");
    // Allen County's well census is `site:lima`, so the groundwater dataset stays home too.
    expect(fw).not.toContain("ohio-waterwells");
  });
});
