/**
 * Where a site sits — the network's placement vocabulary, in one table each (#1863).
 *
 * A site's placement has two axes, and the selector pivots the SAME sites by either: **state** is
 * the legal jurisdiction its records live under; **basin** is the major river basin it documents.
 * Both are per-site identity, so both are authoritative in `data/sites.yaml` (`state`,
 * `basin_major`) and reach the frontend through `sites-registry.json`. This module holds only what
 * is *about the place rather than the site* — a basin's display label, its three-letter code, the
 * region super-group it nests under, and the continental divide it drains to.
 *
 * Before this, a site's state lived ONLY in a hand-maintained `PLACEMENT` table in `sites.ts`,
 * parallel to the YAML registry, and its major basin was a second copy of the profile's cited
 * `basin`. Registering a site in the YAML without also adding it there silently dropped it from
 * both selector lenses and the water-lens scorecard. Placement is now *derived* from the registry
 * and an unknown basin/state is a named throw — see {@link placementViolations}.
 *
 * Adding a basin is one row in {@link BASINS}. Its two orderings both derive from that one array:
 * the array is written in **divide order** (every Lake Erie basin, then every Ohio River one), and
 * the selector's region order falls out of filtering it by region in {@link REGIONS} order. Keep
 * that property when you add a row — `placement.test.ts` asserts both orders are covered and
 * complete, but only you can keep a new basin in the right run of the array.
 */

/** The two continental divides an Ohio-basin site can drain to. */
export type DivideKey = "erie" | "ohio";
/** The basin lens's four region super-groups (design "Site Selector"). */
export type RegionKey = "maumee" | "miamis" | "southeast" | "northeast";

export interface Divide {
  key: DivideKey;
  label: string;
  /** The direction-of-drainage note under the banner. */
  note: string;
}

export interface Region {
  key: RegionKey;
  label: string;
  /** Short tag beside the region header bar. */
  abbr: string;
}

export interface MajorBasin {
  /** Registry key — the `basin_major` slug in `data/sites.yaml` (and `SiteProfile.basin`). */
  slug: string;
  /** Display label — the basin group heading, and the key the water lens groups by. */
  label: string;
  /** Three-letter code shown beside the heading. */
  abbr: string;
  region: RegionKey;
  divide: DivideKey;
}

/** The two divides, in drainage order — the water lens's top-level banner sequence. */
export const DIVIDES: readonly Divide[] = [
  { key: "erie", label: "Lake Erie drainage", note: "north — into Lake Erie" },
  { key: "ohio", label: "Ohio River drainage", note: "south — into the Ohio & Mississippi" },
];

/** The four region super-groups, in panel order — the basin lens's outer sequence. */
export const REGIONS: readonly Region[] = [
  { key: "maumee", label: "Maumee Basin", abbr: "MAU" },
  { key: "miamis", label: "The Two Miamis", abbr: "2MI" },
  { key: "southeast", label: "Southeastern Basins", abbr: "SE" },
  { key: "northeast", label: "Northeast Basins", abbr: "NE" },
];

/**
 * Every major basin the network places a site in — **in divide order** (see the module note).
 *
 * The region and divide axes genuinely cross-cut: the "northeast" region holds two Lake Erie
 * basins (Sandusky, Cuyahoga) and one Ohio River one (Mahoning), which is why neither ordering is
 * a sub-sequence of the other and why the array is written in divide order — the region order is
 * the one that survives being derived from it.
 */
export const BASINS: readonly MajorBasin[] = [
  // --- Lake Erie drainage ---
  { slug: "maumee", label: "Maumee", abbr: "MAU", region: "maumee", divide: "erie" },
  // NW-Ohio Lake Erie basin adjacent to the Maumee (Bowling Green borders Toledo), so it nests in
  // the Maumee region while grouping under its OWN basin: Bowling Green drinks the Maumee but
  // discharges to the Portage.
  { slug: "portage", label: "Portage", abbr: "POR", region: "maumee", divide: "erie" },
  { slug: "sandusky", label: "Sandusky", abbr: "SAN", region: "northeast", divide: "erie" },
  { slug: "cuyahoga", label: "Cuyahoga", abbr: "CUY", region: "northeast", divide: "erie" },
  // --- Ohio River drainage ---
  { slug: "great-miami", label: "Great Miami", abbr: "GMI", region: "miamis", divide: "ohio" },
  { slug: "little-miami", label: "Little Miami", abbr: "LMI", region: "miamis", divide: "ohio" },
  { slug: "scioto", label: "Scioto", abbr: "SCI", region: "southeast", divide: "ohio" },
  { slug: "muskingum", label: "Muskingum", abbr: "MUS", region: "southeast", divide: "ohio" },
  { slug: "mahoning", label: "Mahoning", abbr: "MAH", region: "northeast", divide: "ohio" },
  { slug: "hocking", label: "Hocking", abbr: "HOC", region: "southeast", divide: "ohio" },
  // Ohio Brush Creek drains straight to the Ohio — no Scioto/Miami loop. Far-southern unglaciated
  // Appalachian Adams County OH (#1117), grouped with the southern Appalachian basins.
  {
    slug: "ohio-brush-creek",
    label: "Ohio Brush Creek",
    abbr: "OBC",
    region: "southeast",
    divide: "ohio",
  },
];

const BY_SLUG: ReadonlyMap<string, MajorBasin> = new Map(BASINS.map((b) => [b.slug, b]));

/** The full state names the network places sites in, keyed by the registry's two-letter code. */
export const STATE_NAMES: Readonly<Record<string, string>> = { OH: "Ohio", IN: "Indiana" };

/** The basin a `basin_major` slug names, or `undefined` if this module doesn't know it. */
export function basinForSlug(slug: string): MajorBasin | undefined {
  return BY_SLUG.get(slug);
}

/** The basins of one divide, in {@link BASINS} order — the water lens's per-divide sequence. */
export function basinsOfDivide(divide: DivideKey): MajorBasin[] {
  return BASINS.filter((b) => b.divide === divide);
}

/** The basins of one region, in {@link BASINS} order — the basin lens's per-region sequence. */
export function basinsOfRegion(region: RegionKey): MajorBasin[] {
  return BASINS.filter((b) => b.region === region);
}

/** The minimum a site has to carry to be placed — the slice of `NetworkSite` this module reads. */
export interface Placeable {
  slug: string;
  /** Two-letter state code, from the registry. */
  state: string;
  /** Major-basin slug, from the registry's `basin_major`. */
  basinMajor: string;
}

/**
 * Every site whose registry placement this module can't resolve, named one per line (#1863).
 *
 * The completeness guard the old parallel table had no room for: `groupSites` used to `continue`
 * past a site missing from `PLACEMENT`, so a newly-registered slug vanished from both lenses and
 * the scorecard, and the only thing that noticed was an indirect `total === SITES.length` count
 * mismatch in a test. Now the same gap is a sentence saying which site and which value.
 *
 * The live path throws instead of skipping (see `groupSites`) — a slug the registry places in an
 * unknown basin is a `data/sites.yaml` authoring error, not a thin peer's missing data, and the
 * "degrade, don't break" rule is about the latter. This enumerates *all* of them at once so the
 * test reports the whole gap rather than the first one.
 */
export function placementViolations(sites: readonly Placeable[]): string[] {
  const out: string[] = [];
  for (const s of sites) {
    if (!STATE_NAMES[s.state]) {
      out.push(
        `site "${s.slug}" is placed in state "${s.state}", which STATE_NAMES doesn't know — ` +
          "add it there (or fix `state` in data/sites.yaml and re-run `watermark sites sync`)",
      );
    }
    if (!BY_SLUG.has(s.basinMajor)) {
      out.push(
        `site "${s.slug}" is placed in basin "${s.basinMajor}", which BASINS doesn't know — ` +
          "add a row there (or fix `basin_major` in data/sites.yaml and re-run " +
          "`watermark sites sync`)",
      );
    }
  }
  return out;
}
