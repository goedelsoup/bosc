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
import { basinForSlug } from "@watermark/core/placement";
import { SITES, sitePoint } from "@watermark/core/sites";

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
