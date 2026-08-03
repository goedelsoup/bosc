/**
 * The network index — the canonical listing of every registered site (#1888).
 *
 * The registry holds 38 sites and the root route is called "the network directory", but until
 * now the only place a reader could see all of them was the header switcher: a `<details>` panel,
 * transient, unlinkable, unshareable. The home's "See all N →" pointed at `/research/hypotheses`,
 * which answers a different question (which boom-origin thesis does this site bear on). This
 * module is the model behind the page that finally lists the network.
 *
 * Pure (no bundle read), like {@link ./directory}: the page threads the bundle-backed
 * `siteRollup` / `facilityStatusOrNull` lookups in as resolvers, so this unit-tests offline.
 *
 * ## The three clocks
 *
 * A row carries three independent lifecycle values and the page must never let them read as one:
 *   - **build phase** (`status`) — our progress assembling the *website*, hand-maintained in
 *     `data/sites.yaml`.
 *   - **readiness tier** (`tier`) — how much record the site's OWN export has assembled,
 *     recomputed at every `watermark export` from the manifest `readiness` block.
 *   - **facility status** (`facility`) — the plant in the ground.
 * A queued site can document a live facility; a `live` build can document one still under
 * investigation. They are deliberately different questions.
 *
 * ## What "open" means, and why it is the registry's answer
 *
 * `open` is `selectable` — the registry's own answer to "can a reader enter this site's build".
 * It is deliberately NOT "has a committed bundle": the offline gate reads 26 committed fixtures
 * under `web/sites/`, while a production build only exports the slugs listed in
 * `astro.config.ts`. Keying the headline off bundle presence would make the network's own
 * advertised size differ between CI and the deploy. The registry is the same in both.
 *
 * ## `null` is a claim
 *
 * `tier` / `documents` / `records` / `facility` are `null` for a site with no committed bundle:
 * nothing has been measured there. That is a DIFFERENT claim from `0`, which means the export ran
 * and found none. Both reach the page intact — a fabricated zero reads as a cleared verdict, and
 * a dash over a real zero understates what the network has assembled. Every axis carries an
 * explicit "not yet measured" option rather than flooring an unmeasured site into a real value.
 */
import type { SiteTier } from "./bundle";
import { PHASE_PILL, TIER_DEPTH_ORDER, TIER_PILL } from "./directory";
import type { FacilityStatus } from "./feeds";
import { BASINS, basinForSlug, STATE_NAMES } from "./placement";
import {
  FACILITY_STAGES,
  FACILITY_STATUS_META,
  type NetworkSite,
  SITES,
  siteBadge,
  type SiteRollup,
  type SiteStatus,
} from "./sites";

/** The `data-*` value standing for "no committed bundle measured this". */
export const UNMEASURED = "none";

/**
 * The facility axis's value for a row. Three distinct claims, kept apart on purpose:
 *   - a measured {@link FacilityStatus} — a bundle says so;
 *   - `"undisclosed"` — the site's export RAN and no facility is on the record;
 *   - `"unmeasured"` — no committed bundle, so nothing has been looked at.
 * Collapsing the last two would be the same error as flooring an unexported site to
 * "Investigating": "we looked and found nothing" and "we haven't looked" are not the same
 * finding, and on a facet they'd print one count for two different states of the record.
 */
export type FacilityFacet = FacilityStatus | "undisclosed" | "unmeasured";

/** One site, as the index renders it. */
export interface NetworkIndexRow {
  slug: string;
  place: string;
  /** The switcher badge — codename, else the 3-letter mono. */
  badge: string;
  codename: string | null;
  /** The fine receiving-water subline ("Blanchard River"). */
  basin: string;
  /** The MAJOR basin this site groups under — slug, display label, 3-letter code. */
  basinSlug: string;
  basinLabel: string;
  basinAbbr: string;
  state: string;
  stateName: string;
  county: string | null;
  /** Build phase — our progress on the website. */
  status: SiteStatus;
  /** Can a reader enter this site's build? The registry's `selectable`. */
  open: boolean;
  href: string;
  issue?: string;
  /** Readiness tier from the site's own export — `null` where no bundle is committed. */
  tier: SiteTier | null;
  documents: number | null;
  records: number | null;
  /** The facility in the ground — `null` where no bundle carries one (NOT floored to
   *  `"investigation"`, which on a filter axis would sweep every unmeasured site into a real
   *  stage and make the facet count a claim no export supports). */
  facility: FacilityStatus | null;
  /** {@link FacilityFacet} — `facility`, widened with the two reasons it can be absent. */
  facilityFacet: FacilityFacet;
  /** Precomputed sort positions, one per {@link NETWORK_SORTS} key — the no-JS sort is CSS
   *  `order`, so every ordering has to be resolved at build time. */
  order: Record<SortKey, number>;
}

/** The row's filterable axes, as the `data-*` attributes the no-JS CSS matches on. */
export function rowData(row: NetworkIndexRow): Record<string, string> {
  return {
    "data-access": row.open ? "open" : "watch",
    "data-state": row.state,
    "data-basin": row.basinSlug,
    "data-tier": row.tier ?? UNMEASURED,
    "data-phase": row.status,
    "data-facility": row.facilityFacet,
  };
}

/**
 * Build one row per registered site, in registry order. Every site gets a row — a slug that can't
 * be placed is a `data/sites.yaml` authoring error and throws by name (the discipline
 * `groupSites` already holds: an unplaced site must fail loudly rather than drop silently out of
 * the listing that exists to be complete).
 */
export function buildNetworkIndex(
  rollupOf: (slug: string) => SiteRollup,
  facilityOf: (slug: string) => FacilityStatus | null,
  sites: readonly NetworkSite[] = SITES,
): NetworkIndexRow[] {
  const rows = sites.map((site): Omit<NetworkIndexRow, "order"> => {
    const basin = basinForSlug(site.basinMajor);
    const stateName = STATE_NAMES[site.state];
    if (!basin || !stateName) {
      throw new Error(
        `site "${site.slug}" is unplaced: state "${site.state}" ${stateName ? "known" : "UNKNOWN"}, ` +
          `basin "${site.basinMajor}" ${basin ? "known" : "UNKNOWN"} — see placementViolations() in ./placement`,
      );
    }
    const roll = rollupOf(site.slug);
    const facility = facilityOf(site.slug);
    // `tier === null` IS the no-bundle seam — `siteRollup` returns all-nulls only when
    // `manifestOrNull` found nothing, which is the same test `directory.ts` reads "—" from.
    return {
      slug: site.slug,
      place: site.place,
      badge: siteBadge(site),
      codename: site.codename,
      basin: site.basin,
      basinSlug: basin.slug,
      basinLabel: basin.label,
      basinAbbr: basin.abbr,
      state: site.state,
      stateName,
      county: site.county,
      status: site.status,
      open: site.selectable,
      href: site.href,
      ...(site.issue !== undefined ? { issue: site.issue } : {}),
      tier: roll.tier,
      documents: roll.documents,
      records: roll.records,
      facility,
      facilityFacet: facility ?? (roll.tier === null ? "unmeasured" : "undisclosed"),
    };
  });
  return attachOrders(rows);
}

// --- Sorting ------------------------------------------------------------------------------------
// The no-JS sort is CSS `order` on a flex column, so each ordering is resolved here at build time
// and emitted as a custom property per row. Adding a sort is one row in NETWORK_SORTS plus its
// comparator below — the page maps over the list and never names a key itself.

export type SortKey = "registry" | "place" | "tier" | "records" | "documents" | "phase" | "basin";

export const NETWORK_SORTS: readonly { key: SortKey; label: string }[] = [
  { key: "registry", label: "Registry order" },
  { key: "place", label: "Place A–Z" },
  { key: "tier", label: "Record assembled" },
  { key: "records", label: "Records" },
  { key: "documents", label: "Documents" },
  { key: "phase", label: "Build phase" },
  { key: "basin", label: "Basin" },
];

/** Build-phase order for sorting — the clock's own sequence, not alphabetical. */
const PHASE_ORDER: readonly SiteStatus[] = ["live", "building", "queued", "tracking"];

/** Deepest tier first; a site with no bundle sorts LAST rather than being scored as a `stub` —
 *  nothing has been measured there, and an unmeasured site must never outrank a measured one on
 *  a figure we'd have had to invent for it (the rule {@link featuredSites} holds). */
function tierRank(tier: SiteTier | null): number {
  return tier === null ? TIER_DEPTH_ORDER.length : TIER_DEPTH_ORDER.indexOf(tier);
}

/** `null` sorts below every measured figure, including a real `0`. */
function measuredDesc(a: number | null, b: number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return b - a;
}

type Bare = Omit<NetworkIndexRow, "order">;

const COMPARATORS: Record<SortKey, (a: Bare, b: Bare) => number> = {
  registry: () => 0,
  place: (a, b) => a.place.localeCompare(b.place, "en-US"),
  tier: (a, b) =>
    tierRank(a.tier) - tierRank(b.tier) ||
    measuredDesc(a.records, b.records) ||
    measuredDesc(a.documents, b.documents),
  records: (a, b) => measuredDesc(a.records, b.records),
  documents: (a, b) => measuredDesc(a.documents, b.documents),
  phase: (a, b) => PHASE_ORDER.indexOf(a.status) - PHASE_ORDER.indexOf(b.status),
  // Divide order, the same run `BASINS` is written in (Lake Erie, then Ohio River), so the sort
  // and the switcher's basin lens walk the network the same way.
  basin: (a, b) =>
    BASINS.findIndex((x) => x.slug === a.basinSlug) - BASINS.findIndex((x) => x.slug === b.basinSlug),
};

/** Resolve every ordering over the rows and fold the positions back onto each row. Registry order
 *  is the stable final tiebreak for every sort, so no ordering is left to engine sort stability. */
function attachOrders(rows: Bare[]): NetworkIndexRow[] {
  const registry = new Map(rows.map((r, i) => [r.slug, i]));
  const positions = new Map<string, Partial<Record<SortKey, number>>>(rows.map((r) => [r.slug, {}]));
  for (const { key } of NETWORK_SORTS) {
    const cmp = COMPARATORS[key];
    const sorted = [...rows].sort(
      (a, b) => cmp(a, b) || (registry.get(a.slug) ?? 0) - (registry.get(b.slug) ?? 0),
    );
    sorted.forEach((r, i) => {
      const p = positions.get(r.slug);
      if (p) p[key] = i;
    });
  }
  return rows.map((r) => ({ ...r, order: positions.get(r.slug) as Record<SortKey, number> }));
}

// --- Facets -------------------------------------------------------------------------------------
// One radio group per axis with an "All" default. Single-select within an axis is deliberate: it
// removes the within-axis OR combinatorics (11 basins would need 2^11 rules to express in CSS),
// and because every emitted rule only ever HIDES, the axes then AND together correctly with one
// rule per option. Only options that match at least one site are offered, so no single filter can
// empty the table.

export type FacetKey = "access" | "state" | "basin" | "tier" | "phase" | "facility";

export interface FacetOption {
  /** The `data-*` value this option matches, and the radio's id suffix. */
  value: string;
  label: string;
  count: number;
  /** Swatch dot, on the axes that carry the shared status palettes. */
  dot?: string;
}

export interface Facet {
  key: FacetKey;
  label: string;
  /** The row attribute this axis filters on (`data-tier`, …). */
  attr: string;
  /** What the axis is measuring — one line, so a reader isn't left to guess which clock it is. */
  note: string;
  options: FacetOption[];
}

const ACCESS_LABEL: Record<string, string> = { open: "Open", watch: "Watch" };

/** The label an axis shows for a site with no committed bundle. */
const UNMEASURED_LABEL = "Not yet measured";

/**
 * The six filter axes, counted against `rows`. Options appear in each axis's own meaningful order
 * (the lifecycle sequence, the divide order, deepest tier first) — never alphabetically, and never
 * by count, which would reshuffle the controls as the network grows.
 */
export function networkFacets(rows: readonly NetworkIndexRow[]): Facet[] {
  const count = (pred: (r: NetworkIndexRow) => boolean): number => rows.filter(pred).length;
  const keep = (o: FacetOption): boolean => o.count > 0;

  const access: FacetOption[] = (["open", "watch"] as const)
    .map((v) => ({
      value: v,
      label: ACCESS_LABEL[v],
      count: count((r) => (r.open ? "open" : "watch") === v),
    }))
    .filter(keep);

  // State order follows first appearance in the registry, matching the switcher's state lens.
  const stateCodes = [...new Set(rows.map((r) => r.state))];
  const states: FacetOption[] = stateCodes.map((code) => ({
    value: code,
    label: rows.find((r) => r.state === code)?.stateName ?? code,
    count: count((r) => r.state === code),
  }));

  const basins: FacetOption[] = BASINS.map((b) => ({
    value: b.slug,
    label: b.label,
    count: count((r) => r.basinSlug === b.slug),
  })).filter(keep);

  const tiers: FacetOption[] = [
    ...TIER_DEPTH_ORDER.map((t) => ({
      value: t,
      label: TIER_PILL[t].label,
      dot: TIER_PILL[t].dot,
      count: count((r) => r.tier === t),
    })),
    { value: UNMEASURED, label: UNMEASURED_LABEL, count: count((r) => r.tier === null) },
  ].filter(keep);

  const phases: FacetOption[] = PHASE_ORDER.map((s) => ({
    value: s,
    label: PHASE_PILL[s].label,
    dot: PHASE_PILL[s].dot,
    count: count((r) => r.status === s),
  })).filter(keep);

  const facilities: FacetOption[] = [
    ...FACILITY_STAGES.map(({ status }) => ({
      value: status,
      label: FACILITY_STATUS_META[status].label,
      dot: FACILITY_STATUS_META[status].dot,
      count: count((r) => r.facilityFacet === status),
    })),
    { value: "undisclosed", label: "None disclosed", count: count((r) => r.facilityFacet === "undisclosed") },
    { value: "unmeasured", label: UNMEASURED_LABEL, count: count((r) => r.facilityFacet === "unmeasured") },
  ].filter(keep);

  return [
    {
      key: "access",
      label: "Access",
      attr: "data-access",
      note: "Whether the site's build opens today.",
      options: access,
    },
    {
      key: "state",
      label: "State",
      attr: "data-state",
      note: "The law its records live under.",
      options: states,
    },
    {
      key: "basin",
      label: "Basin",
      attr: "data-basin",
      note: "The major river basin it documents.",
      options: basins,
    },
    {
      key: "tier",
      label: "Record assembled",
      attr: "data-tier",
      note: "How much record this site's own export has assembled.",
      options: tiers,
    },
    {
      key: "phase",
      label: "Build phase",
      attr: "data-phase",
      note: "Our progress assembling the website.",
      options: phases,
    },
    {
      key: "facility",
      label: "Facility",
      attr: "data-facility",
      note: "The plant in the ground — a separate clock.",
      options: facilities,
    },
  ];
}

// --- Counts -------------------------------------------------------------------------------------

export interface NetworkCounts {
  total: number;
  /** Sites a reader can enter today (`selectable`). */
  open: number;
  /** Registered and tracked, but not yet readable. */
  watch: number;
  byStatus: Record<SiteStatus, number>;
  byTier: Record<SiteTier, number>;
  /** Registered sites with no committed bundle — nothing measured. */
  unmeasured: number;
  basins: number;
  states: number;
}

/** The counts the page states out loud. Every one is derived from the rows, so the home, the
 *  switcher, and this page cannot drift: all three read the same registry. */
export function networkCounts(rows: readonly NetworkIndexRow[]): NetworkCounts {
  const counts: NetworkCounts = {
    total: rows.length,
    open: 0,
    watch: 0,
    byStatus: { live: 0, building: 0, queued: 0, tracking: 0 },
    byTier: { stub: 0, backdrop: 0, case: 0, reference: 0 },
    unmeasured: 0,
    basins: new Set(rows.map((r) => r.basinSlug)).size,
    states: new Set(rows.map((r) => r.state)).size,
  };
  for (const r of rows) {
    if (r.open) counts.open += 1;
    else counts.watch += 1;
    counts.byStatus[r.status] += 1;
    if (r.tier === null) counts.unmeasured += 1;
    else counts.byTier[r.tier] += 1;
  }
  return counts;
}
