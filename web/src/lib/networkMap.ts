/**
 * The registry → locator-map adapter (#2034, epic #2033).
 *
 * `@watermark/charts`'s `buildNetworkMap` takes a structural `MappableSite[]` and knows nothing
 * about the site registry — that package is DOM-free and node-free, and `@watermark/core/sites`
 * reaches `./bundle`, which reads `node:fs`. This module is where the two meet: it reads the
 * registry, resolves each site's drainage from its major basin, and hands the geometry package
 * plain rows.
 *
 * Both the homepage band (#2036) and the `/network` mount (#2038) build from here, so the two
 * surfaces cannot drift into two maps of two different networks.
 */
import { buildNetworkMap, type MappableSite, type NetworkMapModel } from "@watermark/charts/networkMap";
import { basinForSlug, BASINS, DIVIDES } from "@watermark/core/placement";
import { SITE_STATUS_META, SITES, sitePoint } from "@watermark/core/sites";

/**
 * Every registered site, in registry order, in the shape the map reads.
 *
 * Registry order is deliberate: the DOM order is the crawlable one, and any ranking is a
 * presentation decision the caller makes — the same reasoning `/network` gives for resolving its
 * sorts into CSS `order` rather than reordering the markup.
 */
export function networkMapRows(): MappableSite[] {
  return SITES.map((s) => ({
    slug: s.slug,
    place: s.place,
    badge: s.codename ?? s.mono,
    basin: s.basin,
    basinMajor: s.basinMajor,
    // `groupSites` throws on an unplaceable basin and `placementViolations` enumerates them, so a
    // slug missing from BASINS is already a hard authoring error caught upstream. Falling back to
    // the Lake Erie side here would only decide which wrong half of the map it landed on; the
    // divide test names it instead.
    divide: basinForSlug(s.basinMajor)?.divide ?? "erie",
    status: s.status,
    href: s.href,
    open: s.selectable,
    point: sitePoint(s.slug),
  }));
}

/** The built model for the whole network, at a given viewBox width. */
export function networkMapModel(width?: number): NetworkMapModel {
  return buildNetworkMap(networkMapRows(), width === undefined ? {} : { width });
}

/** One selectable value on a filter axis. */
export interface MapFacetOption {
  value: string;
  label: string;
  count: number;
}

/** One filter axis — a radio group over the markers. */
export interface MapFacet {
  /** Axis key; also the `data-` attribute the generated CSS matches on. */
  key: "basin" | "divide" | "phase";
  label: string;
  /** The marker attribute this axis filters on, e.g. `data-basin`. */
  attr: string;
  options: MapFacetOption[];
}

/**
 * The filter axes for the map's chips (#2038), built from the placed markers.
 *
 * Counts are over `markers`, not the whole registry: a chip claims how many sites it will leave
 * lit on the map, and a site the map could not place is not one of them. The off-map list stays
 * beside the map saying so — the chips narrow what is drawn, they do not redefine the network.
 *
 * Options are dropped when empty rather than shown at zero, so no axis offers a chip that blanks
 * the map. Basins keep `BASINS` order (divide order, then region), phases keep depth order —
 * neither is alphabetised, because both vocabularies are already sequenced elsewhere and a third
 * ordering would read as a fourth clock.
 */
export function networkMapFacets(model: NetworkMapModel): MapFacet[] {
  const tally = <T extends string>(pick: (m: NetworkMapModel["markers"][number]) => T) => {
    const counts = new Map<T, number>();
    for (const m of model.markers) counts.set(pick(m), (counts.get(pick(m)) ?? 0) + 1);
    return counts;
  };

  const basinCounts = tally((m) => m.basinMajor);
  const divideCounts = tally((m) => m.divide);
  const phaseCounts = tally((m) => m.status);

  return [
    {
      key: "basin",
      label: "Basin",
      attr: "data-basin",
      options: BASINS.filter((b) => basinCounts.get(b.slug)).map((b) => ({
        value: b.slug,
        label: b.label,
        count: basinCounts.get(b.slug) ?? 0,
      })),
    },
    {
      key: "divide",
      label: "Drains to",
      attr: "data-divide",
      options: DIVIDES.filter((d) => divideCounts.get(d.key)).map((d) => ({
        value: d.key,
        label: d.label,
        count: divideCounts.get(d.key) ?? 0,
      })),
    },
    {
      key: "phase",
      label: "Build phase",
      attr: "data-phase",
      options: (["live", "building", "queued", "tracking"] as const)
        .filter((p) => phaseCounts.get(p))
        .map((p) => ({
          value: p,
          label: SITE_STATUS_META[p].label,
          count: phaseCounts.get(p) ?? 0,
        })),
    },
  ];
}
