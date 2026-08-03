import { describe, expect, it } from "vitest";
import type { FacilityStatus } from "./feeds";
import {
  buildNetworkIndex,
  NETWORK_SORTS,
  networkCounts,
  networkFacets,
  rowData,
  type SortKey,
} from "./networkIndex";
import { SITES, type NetworkSite, type SiteRollup } from "./sites";

// Pure stubs for the two bundle-backed lookups — the real page passes `siteRollup` (#1861) and
// `facilityStatusOrNull` (#1888). These keep the unit test offline, and cover the four states the
// index must keep apart: a worked reference build, a built-but-empty site (real zeros), a built
// site with no facility on the record, and a registered site with no bundle at all (nulls).
const ROLLUPS: Record<string, SiteRollup> = {
  lima: { documents: 3247, records: 56, tier: "reference" },
  "fort-wayne": { documents: 168, records: 24, tier: "case" },
  defiance: { documents: 0, records: 0, tier: "backdrop" },
  sandusky: { documents: 0, records: 0, tier: "stub" },
};
const NO_BUNDLE: SiteRollup = { documents: null, records: null, tier: null };
const ROLLUP = (slug: string): SiteRollup => ROLLUPS[slug] ?? NO_BUNDLE;

const FACILITIES: Record<string, FacilityStatus> = {
  lima: "construction",
  "fort-wayne": "live",
};
// `defiance`/`sandusky` are built with no facility block — "none disclosed", NOT "not measured".
const FACILITY = (slug: string): FacilityStatus | null => FACILITIES[slug] ?? null;

const rows = buildNetworkIndex(ROLLUP, FACILITY);

describe("buildNetworkIndex", () => {
  it("emits exactly one row per registered site, in registry order", () => {
    expect(rows).toHaveLength(SITES.length);
    expect(rows.map((r) => r.slug)).toEqual(SITES.map((s) => s.slug));
  });

  it("carries the registry href, so a row lands where the switcher would send it", () => {
    for (const site of SITES) {
      expect(rows.find((r) => r.slug === site.slug)?.href).toBe(site.href);
    }
  });

  it("leaves an unmeasured site null rather than scoring it zero", () => {
    // Every slug outside ROLLUPS has no committed bundle: nothing has been measured there, which
    // is a different claim from an export that ran and found none.
    const unbuilt = rows.filter((r) => !(r.slug in ROLLUPS));
    expect(unbuilt.length).toBeGreaterThan(0);
    for (const r of unbuilt) {
      expect(r.tier).toBeNull();
      expect(r.documents).toBeNull();
      expect(r.records).toBeNull();
      expect(r.facility).toBeNull();
      expect(r.facilityFacet).toBe("unmeasured");
    }
  });

  it("keeps a real zero distinct from an absent measurement", () => {
    const defiance = rows.find((r) => r.slug === "defiance");
    expect(defiance?.documents).toBe(0);
    expect(defiance?.records).toBe(0);
    expect(defiance?.tier).toBe("backdrop");
  });

  it("distinguishes an undisclosed facility from an unmeasured one", () => {
    // Exported, nothing on the record → "undisclosed"; never floored to `investigation`, and never
    // collapsed into the no-bundle bucket.
    expect(rows.find((r) => r.slug === "defiance")?.facilityFacet).toBe("undisclosed");
    expect(rows.find((r) => r.slug === "lima")?.facilityFacet).toBe("construction");
  });

  it("throws by name on a site it cannot place", () => {
    const orphan = { ...SITES[0], slug: "atlantis", basinMajor: "nowhere" } as NetworkSite;
    expect(() => buildNetworkIndex(ROLLUP, FACILITY, [orphan])).toThrow(/atlantis.*UNKNOWN/s);
  });
});

describe("sort orders", () => {
  it("resolves every sort to a total order over the rows", () => {
    for (const { key } of NETWORK_SORTS) {
      const positions = rows.map((r) => r.order[key]).sort((a, b) => a - b);
      expect(positions).toEqual(rows.map((_, i) => i));
    }
  });

  it("ranks the deepest-assembled record first and the unmeasured last", () => {
    const byTier = [...rows].sort((a, b) => a.order.tier - b.order.tier);
    expect(byTier[0]?.slug).toBe("lima");
    expect(byTier[1]?.slug).toBe("fort-wayne");
    expect(byTier.at(-1)?.tier).toBeNull();
  });

  it("sorts a real zero above an unmeasured site", () => {
    const byRecords = [...rows].sort((a, b) => a.order.records - b.order.records);
    const zero = byRecords.findIndex((r) => r.slug === "defiance");
    const unmeasured = byRecords.findIndex((r) => r.records === null);
    expect(zero).toBeLessThan(unmeasured);
  });

  it("orders places alphabetically", () => {
    const byPlace = [...rows].sort((a, b) => a.order.place - b.order.place).map((r) => r.place);
    expect(byPlace).toEqual([...byPlace].sort((a, b) => a.localeCompare(b, "en-US")));
  });

  it("keeps registry order as the stable tiebreak", () => {
    // Registry sort changes nothing; and two sites sharing a phase keep their registry sequence.
    expect([...rows].sort((a, b) => a.order.registry - b.order.registry).map((r) => r.slug)).toEqual(
      rows.map((r) => r.slug),
    );
    const tracking = [...rows]
      .filter((r) => r.status === "tracking")
      .sort((a, b) => a.order.phase - b.order.phase);
    expect(tracking.map((r) => r.slug)).toEqual(
      rows.filter((r) => r.status === "tracking").map((r) => r.slug),
    );
  });
});

describe("networkFacets", () => {
  const facets = networkFacets(rows);

  it("offers the six axes the page filters on", () => {
    expect(facets.map((f) => f.key)).toEqual(["access", "state", "basin", "tier", "phase", "facility"]);
  });

  it("places every site on every axis — no site falls out of the listing that exists to be complete", () => {
    for (const facet of facets) {
      const total = facet.options.reduce((n, o) => n + o.count, 0);
      expect(total, `axis "${facet.key}" drops ${rows.length - total} site(s)`).toBe(rows.length);
    }
  });

  it("matches every row's data attribute to an offered option", () => {
    for (const facet of facets) {
      const offered = new Set(facet.options.map((o) => o.value));
      for (const row of rows) {
        const value = rowData(row)[facet.attr];
        expect(offered.has(value), `${row.slug} has ${facet.attr}="${value}", which no option offers`).toBe(
          true,
        );
      }
    }
  });

  it("offers no empty option, so no single filter can empty the table", () => {
    for (const facet of facets) {
      for (const option of facet.options) {
        expect(option.count, `${facet.key}/${option.value}`).toBeGreaterThan(0);
      }
    }
  });
});

describe("networkCounts", () => {
  const counts = networkCounts(rows);

  it("counts open as the registry's `selectable`, not as bundle presence", () => {
    // Deliberate: the offline gate reads 26 committed fixtures while a production build exports
    // three slugs, so a bundle-derived headline would advertise a different network in CI than in
    // the deploy. The registry is the same in both.
    expect(counts.open).toBe(SITES.filter((s) => s.selectable).length);
    expect(counts.open).toBeGreaterThan(0);
  });

  it("splits the whole registry into open and watch", () => {
    expect(counts.total).toBe(SITES.length);
    expect(counts.open + counts.watch).toBe(counts.total);
  });

  it("sums every clock back to the registry total", () => {
    const byStatus = Object.values(counts.byStatus).reduce((a, b) => a + b, 0);
    expect(byStatus).toBe(counts.total);
    const byTier = Object.values(counts.byTier).reduce((a, b) => a + b, 0);
    expect(byTier + counts.unmeasured).toBe(counts.total);
  });

  it("agrees with the switcher's grouping axes", () => {
    expect(counts.basins).toBe(new Set(SITES.map((s) => s.basinMajor)).size);
    expect(counts.states).toBe(new Set(SITES.map((s) => s.state)).size);
  });
});

describe("rowData", () => {
  it("emits one attribute per filter axis", () => {
    const attrs = Object.keys(rowData(rows[0] as (typeof rows)[number]));
    expect(attrs.sort()).toEqual(
      networkFacets(rows)
        .map((f) => f.attr)
        .sort(),
    );
  });
});

// A guard on the sort-key union: every key in NETWORK_SORTS must be present on every row's order
// map, so adding a sort without a comparator can't ship a silently-unordered control.
describe("NETWORK_SORTS", () => {
  it("has a resolved position on every row for every declared key", () => {
    const keys: SortKey[] = NETWORK_SORTS.map((s) => s.key);
    for (const row of rows) {
      for (const key of keys) {
        expect(typeof row.order[key], `${row.slug}.order.${key}`).toBe("number");
      }
    }
  });
});
