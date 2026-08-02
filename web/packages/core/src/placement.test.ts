import { describe, expect, it } from "vitest";
import {
  BASINS,
  basinForSlug,
  basinsOfDivide,
  basinsOfRegion,
  DIVIDES,
  type Placeable,
  placementViolations,
  REGIONS,
  STATE_NAMES,
} from "./placement";

describe("the major-basin table — one row per basin (#1863)", () => {
  it("keys are unique: no basin slug, label, or code is claimed twice", () => {
    for (const key of ["slug", "label", "abbr"] as const) {
      const values = BASINS.map((b) => b[key]);
      expect(new Set(values).size, `duplicate basin ${key}`).toBe(values.length);
    }
  });

  it("every basin resolves by its registry slug", () => {
    for (const b of BASINS) expect(basinForSlug(b.slug)).toBe(b);
    expect(basinForSlug("nowhere-creek")).toBeUndefined();
  });

  // The guard the issue asks for by name: a basin the selector groups by but no divide claims
  // would render in the switcher and vanish from the water lens. Structurally impossible now —
  // `divide` is a required field on the row — but the coverage is what actually matters, so
  // assert it rather than the type.
  it("every basin belongs to exactly one divide, and the divides cover the table", () => {
    const covered = DIVIDES.flatMap((d) => basinsOfDivide(d.key));
    expect(covered).toHaveLength(BASINS.length);
    expect(new Set(covered.map((b) => b.slug))).toEqual(new Set(BASINS.map((b) => b.slug)));
  });

  it("every basin belongs to exactly one region, and the regions cover the table", () => {
    const covered = REGIONS.flatMap((r) => basinsOfRegion(r.key));
    expect(covered).toHaveLength(BASINS.length);
    expect(new Set(covered.map((b) => b.slug))).toEqual(new Set(BASINS.map((b) => b.slug)));
  });
});

describe("the two orderings both derive from the one array (#1863)", () => {
  // BASINS is written in divide order, and the region order falls out of filtering it. Both
  // sequences are load-bearing display order, so both are pinned here: a new row inserted in the
  // wrong run of the array fails one of these instead of quietly reshuffling a rendered panel.
  it("divide order — Lake Erie drains first, then the Ohio River basins", () => {
    expect(DIVIDES.map((d) => d.key)).toEqual(["erie", "ohio"]);
    expect(basinsOfDivide("erie").map((b) => b.label)).toEqual(["Maumee", "Portage", "Sandusky", "Cuyahoga"]);
    expect(basinsOfDivide("ohio").map((b) => b.label)).toEqual([
      "Great Miami",
      "Little Miami",
      "Scioto",
      "Muskingum",
      "Mahoning",
      "Hocking",
      "Ohio Brush Creek",
    ]);
  });

  it("region order — the selector's panel sequence, derived from the same rows", () => {
    expect(REGIONS.map((r) => r.key)).toEqual(["maumee", "miamis", "southeast", "northeast"]);
    expect(REGIONS.flatMap((r) => basinsOfRegion(r.key)).map((b) => b.label)).toEqual([
      "Maumee",
      "Portage",
      "Great Miami",
      "Little Miami",
      "Scioto",
      "Muskingum",
      "Hocking",
      "Ohio Brush Creek",
      "Sandusky",
      "Cuyahoga",
      "Mahoning",
    ]);
  });

  it("the two axes genuinely cross-cut — the northeast region straddles both divides", () => {
    // This is why neither ordering is a sub-sequence of the other, and why the array is written
    // in divide order. If this ever stops being true the derivation gets simpler, not broken.
    const northeast = basinsOfRegion("northeast");
    expect(new Set(northeast.map((b) => b.divide))).toEqual(new Set(["erie", "ohio"]));
  });
});

describe("placementViolations — the named completeness guard (#1863)", () => {
  const ok: Placeable = { slug: "somewhere", state: "OH", basinMajor: "maumee" };

  it("says nothing about a site the registry places in a known state and basin", () => {
    expect(placementViolations([ok])).toEqual([]);
  });

  it("names the site and the unknown basin — not an indirect count mismatch", () => {
    const v = placementViolations([{ ...ok, slug: "new-site", basinMajor: "kokosing" }]);
    expect(v).toHaveLength(1);
    expect(v[0]).toContain('site "new-site"');
    expect(v[0]).toContain('basin "kokosing"');
    expect(v[0]).toContain("data/sites.yaml");
  });

  it("names an unknown state the same way", () => {
    const v = placementViolations([{ ...ok, slug: "out-of-network", state: "MI" }]);
    expect(v).toHaveLength(1);
    expect(v[0]).toContain('state "MI"');
    expect(STATE_NAMES.MI).toBeUndefined();
  });

  it("reports both axes of the same site, and every site, in one pass", () => {
    expect(
      placementViolations([
        { slug: "a", state: "MI", basinMajor: "kokosing" },
        ok,
        { slug: "b", state: "KY", basinMajor: "licking" },
      ]),
    ).toHaveLength(4);
  });
});
