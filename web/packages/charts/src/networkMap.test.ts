/**
 * Geometry tests for the network locator map (#2034).
 *
 * Fixtures, not the live registry — deliberately. This package is DOM-free and node-free (its
 * tsconfig sets `"types": []`), and `@watermark/core/sites` reaches `./bundle`, which reads
 * `node:fs`. The tests that must run against the *real* 38 sites — nothing dropped, no site on
 * the wrong side of its own drainage, the phase vocabulary still in sync — live in
 * `src/lib/networkMap.test.ts`, where the registry is in scope.
 */
import { describe, expect, it } from "vitest";
import {
  buildNetworkMap,
  divideLatAt,
  MAP_BOUNDS,
  type MappableSite,
  projector,
  STANDARD_PARALLEL,
} from "./networkMap";

const site = (slug: string, point: { lat: number; lon: number } | null): MappableSite => ({
  slug,
  place: slug,
  badge: slug.slice(0, 3).toUpperCase(),
  basin: `${slug} river`,
  basinMajor: "maumee",
  divide: "erie",
  status: "queued",
  href: `/network/${slug}`,
  open: false,
  point,
});

// Two real coordinates from the registry, and two rows with none.
const LIMA = { lat: 40.792, lon: -84.122 };
const TOLEDO = { lat: 41.6529, lon: -83.5378 };
const WEST_UNION = { lat: 38.6067, lon: -83.4 };

const rows = [
  site("lima", LIMA),
  site("toledo", TOLEDO),
  site("west-union", WEST_UNION),
  site("akron", null),
  site("athens", null),
];
const model = buildNetworkMap(rows);
const at = (slug: string) => model.markers.find((m) => m.slug === slug);

describe("network locator map geometry (#2034)", () => {
  it("projects a coordinate inside the frame", () => {
    const lima = at("lima");
    expect(lima).toBeDefined();
    expect(lima?.x).toBeGreaterThan(0);
    expect(lima?.x).toBeLessThan(model.width);
    expect(lima?.y).toBeGreaterThan(0);
    expect(lima?.y).toBeLessThan(model.height);
  });

  // Latitude climbs north, SVG y climbs south. The easiest thing in the module to get backwards.
  it("inverts y: the northern point sits above the southern one", () => {
    expect(at("toledo")!.y).toBeLessThan(at("west-union")!.y);
  });

  it("puts a western point left of an eastern one", () => {
    // Lima (−84.12) is west of Toledo (−83.54).
    expect(at("lima")!.x).toBeLessThan(at("toledo")!.x);
  });

  it("scales x and y uniformly, so the frame is not stretched to fit a layout", () => {
    const { project } = projector(MAP_BOUNDS, 640);
    const perDegreeLat = project(40, -83).y - project(41, -83).y;
    // A degree of longitude covers cos(φ) of a degree of latitude on the ground; the projection
    // must reproduce that ratio rather than filling whatever box the layout offered.
    const perDegreeLon = project(40, -82).x - project(40, -83).x;
    expect(perDegreeLon / perDegreeLat).toBeCloseTo(Math.cos((STANDARD_PARALLEL * Math.PI) / 180), 6);
  });

  it("derives height from the frame's aspect, not from the caller", () => {
    const narrow = buildNetworkMap(rows, { width: 320 });
    expect(narrow.width).toBe(320);
    // Halving the width halves the drawn extent; only the fixed padding keeps it off exactly 2:1.
    expect(narrow.height).toBeLessThan(model.height);
    expect(narrow.viewBox).toBe(`0 0 320 ${narrow.height}`);
  });

  // The completeness guarantee: `unplaced` is a return value, not a filter.
  it("places or names every site — nothing is dropped", () => {
    expect(model.markers.length + model.unplaced.length).toBe(rows.length);
  });

  it("never guesses a coordinate: a row with none lands in unplaced", () => {
    expect(model.unplaced.map((u) => u.slug)).toEqual(["akron", "athens"]);
    expect(at("akron")).toBeUndefined();
    expect(at("athens")).toBeUndefined();
  });

  it("carries the row through to the marker, so the caller keeps its destination", () => {
    for (const m of model.markers) {
      expect(m.href).toBeTruthy();
      expect(m.badge).toBeTruthy();
      expect(m.point).not.toBeNull();
    }
  });

  it("keeps the projected outline, frame, and divide inside the viewBox", () => {
    for (const path of [model.outline, model.frame, model.divide]) {
      expect(path.points.length).toBeGreaterThan(1);
      for (const p of path.points) {
        expect(p.x).toBeGreaterThanOrEqual(0);
        expect(p.x).toBeLessThanOrEqual(model.width);
        expect(p.y).toBeGreaterThanOrEqual(0);
        expect(p.y).toBeLessThanOrEqual(model.height);
      }
    }
    expect(model.outline.d.endsWith(" Z")).toBe(true); // the border closes
    expect(model.divide.d.endsWith(" Z")).toBe(false); // the divide runs off both ends
  });

  it("labels Indiana and nothing else", () => {
    // The drainage is explained in the component's key, not on the map: an on-map label has to be
    // re-tuned every time a site is registered, on a component whose point is that it never is.
    expect(model.stateLabels.map((s) => s.code)).toEqual(["IN"]);
    const [ind] = model.stateLabels;
    expect(ind.x).toBeGreaterThanOrEqual(0);
    expect(ind.x).toBeLessThanOrEqual(model.width);
    expect(ind.y).toBeGreaterThanOrEqual(0);
    expect(ind.y).toBeLessThanOrEqual(model.height);
  });

  describe("divideLatAt", () => {
    it("interpolates between vertices", () => {
      const lat = divideLatAt(-83.0);
      expect(lat).not.toBeNull();
      expect(lat!).toBeGreaterThan(40.3);
      expect(lat!).toBeLessThan(41.4);
    });

    it("rises west-to-east across the state", () => {
      expect(divideLatAt(-80.6)!).toBeGreaterThan(divideLatAt(-83.0)!);
    });

    // The divide is drawn across Ohio and stops at the state line. Outside that span it returns
    // null rather than extrapolating a drainage claim into geography it does not cover.
    it("declines to answer outside its span", () => {
      expect(divideLatAt(-85.14)).toBeNull(); // Fort Wayne, in Indiana
      expect(divideLatAt(-79.0)).toBeNull(); // east of Pennsylvania
    });
  });
});

describe("badge placement (#2044)", () => {
  const open = (slug: string, lat: number, lon: number): MappableSite => ({
    ...site(slug, { lat, lon }),
    open: true,
  });

  // Real coordinates from the registry, at the width the collisions actually appeared: the
  // homepage's 420-unit compact instance.
  const SIDNEY = open("sidney", 40.284, -84.156);
  const TROY = open("troy", 40.0921, -84.2024);
  const BOWLING_GREEN = open("bgn", 41.402, -83.64);
  const FINDLAY = open("fin", 41.0428, -83.6422);
  const TOLEDO = { ...site("tol", { lat: 41.6529, lon: -83.5378 }), open: false };
  const at = (m: ReturnType<typeof buildNetworkMap>, slug: string) => m.markers.find((k) => k.slug === slug);

  it("keeps a lone badge above its marker", () => {
    const m = buildNetworkMap([open("alone", 40.0, -83.0)], { width: 420 });
    expect(m.markers[0].badgePlacement).toBe("above");
  });

  it("moves the shadowed label below — the Sidney / Troy-Piqua case", () => {
    const m = buildNetworkMap([SIDNEY, TROY], { width: 420 });
    expect(at(m, "sidney")!.y).toBeLessThan(at(m, "troy")!.y);
    expect(at(m, "sidney")!.badgePlacement).toBe("above");
    expect(at(m, "troy")!.badgePlacement).toBe("below");
  });

  /**
   * The regression that killed the one-pass version. Toledo's square shadows Bowling Green, so
   * Bowling Green flips down — straight onto Findlay's label, which a single flip pass never
   * reconsiders. Greedy placement sees the placed label as an obstacle and resolves it.
   */
  it("never drops a flipped label onto another label", () => {
    const m = buildNetworkMap([TOLEDO, BOWLING_GREEN, FINDLAY, SIDNEY, TROY], { width: 420 });
    const placed = m.markers.filter((k) => k.open && k.badgePlacement !== "none");
    const boxes = placed.map((k) => {
      const baseline = k.badgePlacement === "below" ? k.y + 18 : k.y - 11;
      const halfW = Math.max(12, (k.badge.length * 6.2) / 2);
      return { slug: k.slug, x0: k.x - halfW, x1: k.x + halfW, y0: baseline - 10, y1: baseline + 2 };
    });
    const overlaps: string[] = [];
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i];
        const b = boxes[j];
        if (a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0) {
          overlaps.push(`${a.slug}×${b.slug}`);
        }
      }
    }
    expect(overlaps).toEqual([]);
  });

  it("clears every marker square, not just the labelled ones", () => {
    const m = buildNetworkMap([TOLEDO, BOWLING_GREEN, FINDLAY, SIDNEY, TROY], { width: 420 });
    for (const k of m.markers.filter((x) => x.open && x.badgePlacement !== "none")) {
      const baseline = k.badgePlacement === "below" ? k.y + 18 : k.y - 11;
      const halfW = Math.max(12, (k.badge.length * 6.2) / 2);
      for (const o of m.markers) {
        if (o === k) continue;
        const clear =
          k.x - halfW >= o.x + 5.5 ||
          k.x + halfW <= o.x - 5.5 ||
          baseline - 10 >= o.y + 5.5 ||
          baseline + 2 <= o.y - 5.5;
        expect(clear, `${k.slug}'s label runs through ${o.slug}'s marker`).toBe(true);
      }
    }
  });

  it("labels nothing that is not open — the rest reveal on hover", () => {
    const m = buildNetworkMap([TOLEDO, BOWLING_GREEN], { width: 420 });
    // A non-open marker keeps the default and never participates in placement.
    expect(at(m, "tol")!.badgePlacement).toBe("above");
  });

  it("withholds a label rather than drawing it through a neighbour", () => {
    // Five open sites stacked on one meridian, closer together than a label is tall: some of them
    // cannot be labelled at all, and `none` is the honest answer.
    const stack = [40.5, 40.44, 40.38, 40.32, 40.26].map((lat, i) => open(`s${i}`, lat, -83.0));
    const m = buildNetworkMap(stack, { width: 420 });
    expect(m.markers.some((k) => k.badgePlacement === "none")).toBe(true);
    // And every site is still on the map with its link intact.
    expect(m.markers).toHaveLength(5);
    expect(m.markers.every((k) => k.href)).toBe(true);
  });
});
