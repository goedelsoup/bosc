// No hub page may be a heading plus a door grid (#1891, epic #1884 phase 7).
//
// The finding was that ten pages answered a click with the same object — a grid of `hub-door`
// cards, each a title, a blurb, and a count — while already holding the real data they were
// counting. The fix is a shared lede slot (`~/components/HubLede.astro`) that leads with what
// the section SAYS; the door grid stays, demoted below it.
//
// The regression this test blocks is a new hub (or a revert of an old one) shipping the grid
// alone. It's a source scan for the same reason `trailCoverage.test.ts` is one: the assertion
// is about a template's SHAPE, which is knowable from the file and cheap to keep true, whereas
// asserting it against built HTML would need a full site build and a bundle per site.
//
// Two checks, deliberately:
//   1. every template that renders a door grid also renders a `HubLede`, ABOVE the grid;
//   2. the named hubs from the issue are all still in the crawl, so a rename can't quietly
//      shrink the set this guards down to nothing.
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** Every `.astro` template under `src/pages`, repo-relative. */
function pageFiles(): string[] {
  const files: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (entry.name.endsWith(".astro")) files.push(path);
    }
  };
  walk("src/pages");
  return files.sort();
}

/** The door-grid containers a hub can use — `.hub-grid` is the shared one, `.doors` the
 *  reports hub's older register. Both are "a grid of cards that go somewhere else". */
const GRID_MARKERS = ['class="hub-grid"', 'class="doors"'];

/** The hubs the audit named (#1891). Asserted present so a route move can't hollow the crawl. */
const NAMED_HUBS = [
  "src/pages/docs/index.astro",
  "src/pages/wiki/index.astro",
  "src/pages/network/[site]/site/index.astro",
  "src/pages/network/[site]/economy/index.astro",
  "src/pages/network/[site]/environment/index.astro",
  "src/pages/network/[site]/reports/index.astro",
];

interface Hub {
  file: string;
  /** Offset of the first door grid, and of the `<HubLede` that must precede it. */
  grid: number;
  lede: number;
}

function hubs(): Hub[] {
  return pageFiles()
    .map((file) => {
      const src = readFileSync(file, "utf8");
      const grid = GRID_MARKERS.map((m) => src.indexOf(m))
        .filter((i) => i >= 0)
        .sort((a, b) => a - b)[0];
      return grid === undefined ? null : { file, grid, lede: src.indexOf("<HubLede") };
    })
    .filter((h): h is Hub => h !== null);
}

describe("hub ledes", () => {
  const found = hubs();

  it("crawled the hub templates", () => {
    // Guard against a vacuous pass: if the crawl finds nothing, the assertions below assert
    // nothing. The issue counted ten door-grid pages; the floor is well under that.
    expect(found.length).toBeGreaterThanOrEqual(6);
    const files = found.map((h) => h.file);
    for (const hub of NAMED_HUBS) expect(files).toContain(hub);
  });

  it("leads every door grid with a HubLede", () => {
    const bare = found.filter((h) => h.lede < 0).map((h) => h.file);
    expect(
      bare,
      "these templates render a door grid with no lede above it — a reader who clicks in gets " +
        "signposts and no information. Add a `<HubLede>` reading off this site's own feeds " +
        "(and its honest `absent` line for a site that has none):\n  " +
        bare.join("\n  "),
    ).toEqual([]);
  });

  it("puts the lede above the doors, not after them", () => {
    const below = found.filter((h) => h.lede >= 0 && h.lede > h.grid).map((h) => h.file);
    expect(
      below,
      `these templates render their HubLede below the door grid — the point is that the ` +
        `reading comes first:\n  ${below.join("\n  ")}`,
    ).toEqual([]);
  });
});
