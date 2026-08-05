/**
 * The Watermark network — the registry of watershed-point sites (the multi-site pivot, #304).
 *
 * Decision (locked): **one build, one site.** This is an *in-build* navigation concept,
 * not separate deployments — every watershed point is a section of the single build, and
 * cross-references between them are real. Lima is the live reference build; the basin
 * sites come online incrementally.
 *
 * Only a `selectable` site can be switched into (today: Lima alone). Every other site —
 * including Fort Wayne, a live facility we can onboard fast but haven't built yet — routes
 * to its coming-soon page (#305) and is never rendered as a switchable destination.
 */

/** Site BUILD lifecycle — our progress assembling the *website* (a separate clock from the data
 *  center's real-world `facilityStatus`). `live` = built + selectable; `building` = scaffold up,
 *  sections coming online; `queued` = registered profile + coming-soon page, in the build queue;
 *  `tracking` = a GitHub-tracked candidate with an issue but no registered profile yet (the
 *  earliest phase — it routes to a lightweight "watch" page). Only `live` is selectable. */
import { loadFeed, manifestOrNull, runWithSite } from "./bundle";
import type { SiteTier } from "./bundle";
import type { DocumentCollectionItem, FacilityStatus } from "./feeds";
import { basinForSlug, basinsOfRegion, type MajorBasin, REGIONS, STATE_NAMES } from "./placement";
import { DEFAULT_STORY_CODENAME, SITE_BASE, siteBase } from "./routes";
import sitesRegistry from "./sites-registry.json";

// The facility lifecycle vocabulary now lives with the bundle feed types (#1628) — re-exported
// here so existing `@watermark/core/sites` importers (the rail, switchers, basin.ts) are unchanged.
export type { FacilityEndUse, FacilityStatus } from "./feeds";

export type SiteStatus = "live" | "building" | "queued" | "tracking";

/**
 * A story a site hosts — the lightweight registry reference (#724/#729). It names the story
 * (codename + title) for the switcher / nav; the full reading path (chapters, anchors) lives
 * in the story store keyed by `(site.slug, codename)` — `walkFor` in `./walk` today, the MDX
 * `stories` collection later (#730).
 */
export interface WalkRef {
  /** Walk codename — the URL segment under the site's `stories/` and the store key. */
  codename: string;
  /** Display title, e.g. "Project BOSC". */
  title: string;
  /** One-line description — the on-ramp dek / nav blurb (story-level, not per chapter). */
  dek: string;
  /**
   * Hidden from every *surface* (switcher, site hub, story catalog, atoms) while its content,
   * `/stories/<codename>` routes, and this metadata are all retained (#1256). This is the
   * "hidden, not removed" state — the story stays reachable by direct URL and its title/dek keep
   * feeding the reader pages; it just isn't advertised anywhere. `surfacedWalks` filters these
   * out; `storyMetaFor` (title/dek lookup) deliberately still reads them.
   */
  hidden?: boolean;
  /**
   * "Coming soon" — advertised as coming, but not readable (#1526). The distinct, *visible* peer of
   * `hidden`: where `hidden` silently unsurfaces a story (no teaser, still reachable by direct URL),
   * `comingSoon` does the opposite — the story is **advertised** as a visible teaser (title + dek +
   * a coming-soon badge, `comingSoonWalks`) but its content is **held** (the `/stories/<codename>`
   * routes serve a coming-soon interstitial, not the narrative; `walkComingSoon`). Like `hidden`, a
   * `comingSoon` story contributes **no readable surfaces**: `surfacedWalks` excludes it, so no
   * catalog atoms, no record/timeline → chapter backlinks, and the story readiness facet locks. Its
   * MDX content, routes, and title/dek all stay intact. `hidden` wins if both are set (silent beats
   * advertised).
   */
  comingSoon?: boolean;
}

export interface NetworkSite {
  /** Registry + URL key (kebab). */
  slug: string;
  /** Per-site codename — the switcher badge. `null` falls back to `mono`. */
  codename: string | null;
  /** Three-letter fallback badge when there's no codename. */
  mono: string;
  place: string;
  /** Receiving water / basin subline shown under the place. */
  basin: string;
  /**
   * The MAJOR river basin this site groups under, as its `basin_major` registry slug (#1863) —
   * the coarser peer of {@link basin} above, and the axis `groupSites("basin")` and the H1
   * scorecard pivot on. Its display label, code, region, and divide live in `./placement`; only
   * the slug is per-site. Authoritative in `data/sites.yaml`, where it also back-stops the Python
   * `SiteProfile.basin` literal — so the grouping can't drift from the basin the site's receiving
   * water is actually screened against.
   */
  basinMajor: string;
  /**
   * The two-letter code of the state whose law this site's records live under (`"OH"`, `"IN"`) —
   * the state lens's grouping axis, and what {@link siteState} resolves to a full name for the
   * per-site dateline. From the registry, not a parallel table (#1863).
   */
  state: string;
  /**
   * The economic/administrative county this site's records are filed in, as it reads in a
   * citation ("Allen County, OH"). Identity, not a bundle value — it names the *place*, so it
   * comes from `data/sites.yaml` (which also back-fills the Python `SiteProfile.county_name`,
   * gated by `watermark sites check`). `null` for a tracking-only entry with no registered
   * profile: an unknown county is left unstated, never guessed. The ask-index stamps it onto
   * every retrieval unit as the `county` search facet (#1691).
   */
  county: string | null;
  status: SiteStatus;
  /** Can a reader switch into this site's build? Only the live reference site today. */
  selectable: boolean;
  /** Tracking issue number (no `#`), when one exists. */
  issue?: string;
  /** Where the switcher row points: the live root, or the coming-soon page. */
  href: string;
  /**
   * Restricted by policy (design "Site Locked") — the record is sealed (source protection,
   * legal sensitivity, or an embargo). Orthogonal to `status`: a locked site can be at any
   * build phase. The switcher marks it with a lock and routes to its request-access page; the
   * directory route renders the locked screen. No real site is locked today (a capability).
   */
  locked?: boolean;
  /** Why a `locked` site is sealed — drives the request-access dek. */
  lockReason?: "sourcing" | "legal" | "embargo";
  /** The stories this site hosts, in display order. Absent until a site has one (#724). */
  stories?: readonly WalkRef[];
}

// TypeScript-only overlays — stories live here, not in the YAML identity registry (#1027).
// The YAML drives slug/place/basin/county/status/selectable/codename/mono/map defaults; stories
// are authored here because they reference story codemnames + prose that aren't site-identity.
//
// A story surfaces (in the switcher, the hub, the catalog/atoms, the record backlinks) only when
// it's registered here AND readable — neither `hidden` nor `comingSoon` — see `surfacedWalks`.
// Two "not-readable" states share this overlay: `hidden` (#1256) unsurfaces a story *silently*
// (reachable by direct URL, no teaser); `comingSoon` (#1526) unsurfaces it *visibly* (a teaser
// advertises title/dek, the routes serve an interstitial). Both keep the story's content, its
// `/stories/<codename>` routes, the `WALK_*` guard, and its title/dek intact.
//
// Lima's Project BOSC walk is now *readable* — its record is finished, so it surfaces (switcher,
// hub, catalog/atoms, record backlinks); `surfacedWalks("lima")` returns it, `comingSoonWalks`
// does not. Fort Wayne's Project Zodiac stays `comingSoon` (#1526): held behind a visible teaser
// while its record is finished — `comingSoonWalks("fort-wayne")` returns it, `surfacedWalks`
// does not. Findlay's Flagpole is `comingSoon` for a different reason (#1466): its record IS
// finished (all five readiness domains live), but the site is not yet `selectable`, and promotion
// is a manual, parity-gated edit to `data/sites.yaml`. Held rather than hidden so the walk is
// advertised — the peer home renders its teaser and the story routes serve the interstitial.
//
// ⚠️ "Flagpole" is an EDITORIAL title, not a developer codename. Zodiac is Google's own local name
// for the Fort Wayne campus, recovered from a permit caption; Findlay has no cloak to lift (host
// and customer are both named in SEC filings), so nothing in that story may imply One Power or MARA
// ever used this word.
//
// ⚠️ "Project Accordion" IS a developer codename, like Zodiac and unlike Flagpole — Meta's own
// NDA-era name for the Bowling Green campus, and it is in a public record: the Middleton Township
// trustees went into executive session on 2023-07-19 "for the purpose of hearing a presentation by
// Project Accordion personnel" (data/documents/bowling-green/middleton-township/07192023.pdf).
// Bowling Green is `comingSoon` for Findlay's reason and one of its own (#1441): the site is not
// `selectable`, and its `facility` domain reads `seeded` rather than `live` because the campus's
// ~180 MW is a disclosed [reference] figure with no instrument behind it (#1630). The record it
// would walk is real — the CRA resolution, the seller-name rezonings, the contested 2026 roll call
// — so the story is advertised rather than hidden.
const WALKS: Partial<Record<string, readonly WalkRef[]>> = {
  // ONE walk survives (#1971, epic #1968). Fort Wayne's Project Zodiac, Findlay's Flagpole and
  // Bowling Green's Project Accordion were ABSORBED into their sites' impact studies (#1970) —
  // the study owns the spine now, and their prose ships as study notes under
  // `src/content/study/<slug>/`. All three were `comingSoon`, so nothing readable was removed.
  //
  // Lima's is deliberately kept standalone as the network's METHOD DEMO: one worked example of
  // reading a record document by document, which is a teaching artifact rather than a per-site
  // obligation. A new site does NOT owe the network a walk — that expectation is exactly what
  // #1968 retired.
  lima: [
    {
      codename: DEFAULT_STORY_CODENAME,
      title: "Project BOSC",
      dek: "Project BOSC — read the record one document at a time, no prior knowledge.",
    },
  ],
};

/** The single source of truth for the switcher, the coming-soon pages, and the basin map.
 *  Order is the display order in the switcher — driven by `data/sites.yaml` order (#1027).
 *  Run `bosc sites sync` to regenerate `sites-registry.json` when the YAML changes. */
export const SITES: readonly NetworkSite[] = sitesRegistry.sites.map(
  (entry): NetworkSite => ({
    slug: entry.slug,
    codename: entry.codename,
    mono: entry.mono,
    place: entry.place,
    basin: entry.basin,
    basinMajor: entry.basin_major,
    state: entry.state,
    county: entry.county,
    status: entry.status as SiteStatus,
    selectable: entry.selectable,
    href: entry.slug === "lima" ? SITE_BASE : `/network/${entry.slug}`,
    ...(entry.issue !== null ? { issue: entry.issue } : {}),
    ...(WALKS[entry.slug] ? { stories: WALKS[entry.slug] } : {}),
  }),
);

/** Build-phase display meta — the switcher row status, the phase pill, and the selector legend
 *  all read from here, so the four phases render identically everywhere. */
export const SITE_STATUS_META: Record<SiteStatus, { label: string; cls: string }> = {
  live: { label: "Live", cls: "is-live" },
  building: { label: "Building", cls: "is-building" },
  queued: { label: "Queued", cls: "is-queued" },
  tracking: { label: "Tracking", cls: "is-tracking" },
};

/** This build is the Lima reference build. */
export const ACTIVE_SITE_SLUG = "lima";

export function activeSite(): NetworkSite {
  const site = SITES.find((s) => s.slug === ACTIVE_SITE_SLUG);
  if (!site) throw new Error(`Active site "${ACTIVE_SITE_SLUG}" missing from the registry`);
  return site;
}

/** The badge shown for a site — its codename, else its 3-letter mono. */
export function siteBadge(site: NetworkSite): string {
  return site.codename ?? site.mono;
}

/**
 * Resolve which network site a route belongs to — the switcher's *current* state (#316), and
 * the site-vs-network chrome tier. Only a **selectable** (built) site triggers the site tier:
 * `/network/american-sugar-creek-allen-co[/…]` → the live build. A coming-soon site lives at
 * `/network/<slug>` too, but it's not selectable, so it stays on neutral **network** chrome
 * (the directory `/`, the `/network/<slug>` watch pages, and the cross-cutting globals all →
 * `null`). `base` strips an Astro base prefix.
 */
export function siteForPath(pathname: string, base = ""): NetworkSite | null {
  return siteForPathIn(SITES, pathname, base);
}

/**
 * The seam of {@link siteForPath} (#746): resolve a route to its site over an explicit `sites`
 * list, so the multi-site chrome logic is testable against a two-selectable-site fixture.
 */
export function siteForPathIn(
  sites: readonly NetworkSite[],
  pathname: string,
  base = "",
): NetworkSite | null {
  return matchSiteByPath(sites, pathname, base, true);
}

/**
 * Resolve the network site a `/network/<…>` route belongs to **regardless of `selectable`** — so
 * the switcher reflects the *current* site even on a coming-soon / watch page (`/network/<slug>`),
 * where {@link siteForPath} returns `null` because the full site tier isn't built yet (#793). Use
 * this for the switcher chip + active row; the site-vs-network *tab tier* still keys off
 * {@link siteForPath} (a non-selectable site has no inner pages to tab into).
 */
export function currentSiteForPath(pathname: string, base = ""): NetworkSite | null {
  return matchSiteByPath(SITES, pathname, base, false);
}

/** Shared core: the first site whose `href` is a prefix of `pathname`. `requireSelectable`
 *  restricts to built sites (the tab-tier resolver) vs any site (the switcher's current state). */
function matchSiteByPath(
  sites: readonly NetworkSite[],
  pathname: string,
  base: string,
  requireSelectable: boolean,
): NetworkSite | null {
  let p = pathname;
  if (base && base !== "/" && p.startsWith(base)) p = p.slice(base.length);
  if (!p.startsWith("/")) p = `/${p}`;
  p = p.replace(/\/+$/, "") || "/";
  return (
    sites.find((s) => {
      if (requireSelectable && !s.selectable) return false;
      const h = s.href.replace(/\/+$/, "");
      return p === h || p.startsWith(`${h}/`);
    }) ?? null
  );
}

/** The sites that need a coming-soon page (everything not switchable). */
export function comingSoonSites(): NetworkSite[] {
  return comingSoonFrom(SITES);
}

/** The seam of {@link comingSoonSites} (#746) over an explicit `sites` list. */
export function comingSoonFrom(sites: readonly NetworkSite[]): NetworkSite[] {
  return sites.filter((s) => !s.selectable);
}

/**
 * `getStaticPaths` entries for the `network/[site]/…` routes (#724/#734): one per *selectable*
 * site, keyed by its URL id (`siteBase(slug)` minus `/network/`), with the registry `slug` passed
 * as a prop so a page can thread it into `siteHref(slug, …)` / `loadFeed(name, slug)` (#739).
 * Today that's Lima alone, so these routes reproduce the live build; a second selectable site
 * (#740) gets its own build with no new page files.
 */
export function selectableSitePaths(): Array<{ params: { site: string }; props: { slug: string } }> {
  return selectablePathsFrom(SITES);
}

/**
 * The seam of {@link selectableSitePaths} (#746) over an explicit `sites` list — the testable core
 * that a two-selectable-site fixture exercises (each site keyed by its own `siteBase`).
 */
export function selectablePathsFrom(
  sites: readonly NetworkSite[],
): Array<{ params: { site: string }; props: { slug: string } }> {
  return sites
    .filter((s) => s.selectable)
    .map((s) => ({
      params: { site: siteBase(s.slug).replace("/network/", "") },
      props: { slug: s.slug },
    }));
}

/**
 * Cross a `network/[site]/…/[item]` route's per-item paths with the selectable sites (#724/#735):
 * each item is emitted once per site, with the `site` param and the registry `slug` prop folded
 * in. Use it to wrap an existing item enumeration in a dynamic route's `getStaticPaths`. Today,
 * with Lima alone, the result is just the items; a second selectable site multiplies them.
 *
 * Two call forms (#744):
 * - **Array** — *shared* items (content collections: legal/reference/narrative MDX), the same set
 *   for every site, so they're crossed as-is.
 * - **Callback** `(slug) => items` — *per-site* items (feed-derived routes: records/people/places/
 *   documents). `getStaticPaths` runs **outside** the request-time active-site ALS, so a bare
 *   `loadFeed(...)` there resolves Lima's bundle for *every* site. The callback is invoked inside
 *   `runWithSite(slug)`, so its `hasFeed`/`loadFeed` reads bind to **that** site's bundle. With Lima
 *   alone the two forms are identical; a second selectable site is what makes the difference real.
 */
export function withSitePaths<P extends Record<string, unknown>, Q extends Record<string, unknown>>(
  itemPaths: Array<{ params: P; props?: Q }>,
): Array<{ params: P & { site: string }; props: Q & { slug: string } }>;
export function withSitePaths<P extends Record<string, unknown>, Q extends Record<string, unknown>>(
  itemPathsFor: (slug: string) => Array<{ params: P; props?: Q }>,
): Array<{ params: P & { site: string }; props: Q & { slug: string } }>;
export function withSitePaths(
  itemPaths:
    | Array<{ params: Record<string, unknown>; props?: Record<string, unknown> }>
    | ((slug: string) => Array<{ params: Record<string, unknown>; props?: Record<string, unknown> }>),
): Array<{ params: Record<string, unknown>; props: Record<string, unknown> }> {
  return selectableSitePaths().flatMap(({ params: siteParam, props: siteProps }) => {
    const items =
      typeof itemPaths === "function"
        ? runWithSite(siteProps.slug, () => itemPaths(siteProps.slug))
        : itemPaths;
    return items.map((it) => ({
      params: { ...it.params, ...siteParam },
      props: { ...(it.props ?? {}), ...siteProps },
    }));
  });
}

/**
 * The data center's real-world lifecycle — a SEPARATE clock from the site build `status`.
 * The build `status` (live/building/queued) tracks our progress assembling the *website*; this
 * tracks the *facility in the ground* (investigation → confirmed → construction → live). The two
 * are deliberately distinct: a queued site can document a live facility, and a live site can
 * document one still under investigation. A site with no disclosed facility is "investigation"
 * (the data-center dimension is inferential until a project is on the record).
 */
/**
 * A site's facility lifecycle stage, read from its exported bundle (#1628, epic #1626 F2) — the
 * primary campus's status in the manifest `facility` block (`bosc.site.facility.build_facility_summary`,
 * derived from `SiteProfile.facilities`). Retires the hand-maintained `FACILITY_STATUS` per-slug
 * dict that silently drifted from the model. `"investigation"` (the inferential floor) when the
 * site has no disclosed facility OR no committed bundle yet — never a fabricated stage.
 */
/** The four known facility lifecycle stages — the guard that keeps a foreign/newer-minor bundle's
 *  unrecognized `status` string from indexing `FACILITY_STATUS_META` (or the rail) to `undefined`
 *  and crashing the render (#1628 review). */
const FACILITY_STATUSES: ReadonlySet<FacilityStatus> = new Set([
  "investigation",
  "confirmed",
  "construction",
  "live",
]);

export function facilityStatus(slug: string): FacilityStatus {
  return facilityStatusOrNull(slug) ?? "investigation";
}

/**
 * The MEASURED peer of {@link facilityStatus} (#1888) — the facility stage a bundle actually
 * carries, or `null` where none does.
 *
 * `facilityStatus` floors to `"investigation"`, which is the right degrade on a *site's own* page:
 * an undisclosed facility genuinely is inferential. On the network index it is not, because there
 * the value is a **filter axis over 38 sites at once** — flooring would sweep every registered-but-
 * unexported site into "Investigating" and print a facet count that no export supports. Callers
 * that show one site keep the floor; callers that count sites take the `null`.
 */
export function facilityStatusOrNull(slug: string): FacilityStatus | null {
  const status = manifestOrNull(slug)?.facility?.status;
  return status && FACILITY_STATUSES.has(status) ? status : null;
}

/**
 * A site's rolled-up bundle figures — the record depth the network directory shows beside its
 * name (#1861). The peer of {@link facilityStatus}: same `manifestOrNull` seam, so a registered-
 * but-unbuilt slug degrades to nulls instead of throwing the way `readiness.siteTier` would.
 *
 * `null` and `0` are DIFFERENT claims and both are load-bearing. `null` (rendered "—") means the
 * site has no committed bundle, so nothing has been measured; `0` means its export ran and the
 * bundle carries none. Never collapse one into the other — a fabricated zero reads as a cleared
 * verdict, and a dash over a real zero understates the network's assembled state.
 */
export interface SiteRollup {
  /** Individual source files, summed across the `documents` feed's collections — NOT that feed's
   *  manifest `count`, which is the number of *collections* (Lima: 3,247 files in 21). The
   *  scorecard column says "Documents", so it counts documents. */
  documents: number | null;
  /** Structured record rows — the `records` feed's manifest count. */
  records: number | null;
  /** The standing readiness tier from the manifest `readiness` block, recomputed at every export. */
  tier: SiteTier | null;
}

/** The four known readiness tiers — the guard that keeps a foreign/newer-minor bundle's
 *  unrecognized `tier` string from indexing the directory's `TIER_PILL` to `undefined` (the
 *  peer of `FACILITY_STATUSES` above). */
const SITE_TIERS: ReadonlySet<SiteTier> = new Set(["stub", "backdrop", "case", "reference"]);

const NO_BUNDLE: SiteRollup = { documents: null, records: null, tier: null };

// `documents` is the one figure that needs the feed body rather than the manifest index, and
// Lima's is ~1.8 MB — memoize per slug so the three hypothesis builds plus the home ledger parse it
// once per build instead of once per read. (`manifestOrNull` already caches its own side.)
const rollups = new Map<string, SiteRollup>();

/** {@link SiteRollup} for one site — nulls when it has no committed bundle. */
export function siteRollup(slug: string): SiteRollup {
  const cached = rollups.get(slug);
  if (cached) return cached;
  const manifest = manifestOrNull(slug);
  if (!manifest) return NO_BUNDLE;
  const feed = (name: string) => manifest.feeds.find((f) => f.name === name);
  const tier = manifest.readiness?.tier;
  const rollup: SiteRollup = {
    // A bundle with no `documents` feed genuinely carries no documents — 0, not "unmeasured".
    documents: feed("documents")
      ? loadFeed<DocumentCollectionItem[]>("documents", slug).reduce((n, c) => n + c.entries.length, 0)
      : 0,
    records: feed("records")?.count ?? 0,
    // A pre-1.17 bundle without the block is `stub` — the same all-absent floor `readiness.ts` uses.
    tier: tier && SITE_TIERS.has(tier) ? tier : "stub",
  };
  rollups.set(slug, rollup);
  return rollup;
}

/**
 * One feed's manifest row count for a site — the feed-level peer of {@link siteRollup}, with the
 * same `manifestOrNull` seam and the same null-vs-zero discipline (#1914 needs it across all 38
 * registered sites at once, where `readiness`'s private `feedCount` would throw on the ~12 that
 * have no committed bundle).
 *
 * `0` means the export ran and the bundle carries no rows on that feed — a **measurement**.
 * `null` means no bundle is committed, so nothing was measured. Never collapse one into the other.
 */
export function siteFeedCount(slug: string, feed: string): number | null {
  const manifest = manifestOrNull(slug);
  if (!manifest) return null;
  return manifest.feeds.find((f) => f.name === feed)?.count ?? 0;
}

/** The whole network's assembled record, summed over every registered site (#1861) — what the home
 *  ledger reads to answer "how much record has the network actually assembled". A site with no
 *  committed bundle contributes to `unbuilt` and to no tier, so the sums stay measured-only. */
export interface NetworkRollup {
  documents: number;
  records: number;
  /** How many built sites sit at each readiness tier — the ledger's tier bar. */
  byTier: Record<SiteTier, number>;
  /** Registered sites with no committed bundle yet. */
  unbuilt: number;
}

export function networkRollup(): NetworkRollup {
  const total: NetworkRollup = {
    documents: 0,
    records: 0,
    byTier: { stub: 0, backdrop: 0, case: 0, reference: 0 },
    unbuilt: 0,
  };
  for (const site of SITES) {
    const r = siteRollup(site.slug);
    if (r.tier === null) {
      total.unbuilt += 1;
      continue;
    }
    total.documents += r.documents ?? 0;
    total.records += r.records ?? 0;
    total.byTier[r.tier] += 1;
  }
  return total;
}

export const FACILITY_STATUS_META: Record<
  FacilityStatus,
  { label: string; color: string; bg: string; dot: string }
> = {
  investigation: { label: "Investigating", color: "#566159", bg: "#e8e4d8", dot: "#8c9389" },
  confirmed: { label: "Confirmed", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  construction: { label: "Under construction", color: "#9a6a14", bg: "#efe6d0", dot: "#9a6a14" },
  live: { label: "Live", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
};

/**
 * The facility lifecycle in order — the stepped progress rail (#401). The 4-stage indicator
 * on a facility/record header walks this sequence: completed stages are filled, the current
 * stage is highlighted in its status color, and future stages are muted. The short labels are
 * the rail's tick captions (the long forms live in `FACILITY_STATUS_META`).
 */
export const FACILITY_STAGES: readonly { status: FacilityStatus; short: string }[] = [
  { status: "investigation", short: "Investigation" },
  { status: "confirmed", short: "Confirmed" },
  { status: "construction", short: "Construction" },
  { status: "live", short: "Operational" },
];

/** The 0-based position of a facility status within `FACILITY_STAGES` — the rail's current step. */
export function facilityStageIndex(status: FacilityStatus): number {
  return FACILITY_STAGES.findIndex((s) => s.status === status);
}

// --- Grouped switcher (#307/#308 dictate C) --------------------------------------------------
// The selector pivots the SAME sites by either placement axis — `state` is the legal jurisdiction
// a record lives under; `basinMajor` is the major river basin it documents. Both matter to a
// researcher, so either can be the outer grouping, and the per-row `basin` subline carries the
// finer sub-watershed detail underneath.
//
// Both axes are now read off the registry entry (#1863). What used to be here was a hand-
// maintained `PLACEMENT` table parallel to `data/sites.yaml`: the only home for a site's state,
// a second copy of its major basin, and — because the grouping loops skipped a slug it didn't
// hold — a silent-drop path for any site registered in the YAML but not added here. The basin's
// display vocabulary (label, code, region, divide) lives in `./placement`, which is *about the
// basin*, not about a site.

/** A site's resolved placement, or a named throw. Unlike a thin peer's missing feed, an unplaced
 *  slug is a `data/sites.yaml` authoring error — it must fail loudly rather than drop the site
 *  out of the grouping. `placementViolations(SITES)` enumerates every such gap at once (#1863). */
function placementOf(site: NetworkSite): { stateName: string; basin: MajorBasin } {
  const stateName = STATE_NAMES[site.state];
  const basin = basinForSlug(site.basinMajor);
  if (!stateName || !basin) {
    throw new Error(
      `site "${site.slug}" is unplaced: state "${site.state}" ` +
        `${stateName ? "known" : "UNKNOWN"}, basin "${site.basinMajor}" ` +
        `${basin ? "known" : "UNKNOWN"} — see placementViolations() in ./placement`,
    );
  }
  return { stateName, basin };
}

/** The registry entry for a slug (the canonical {@link NetworkSite}), or `undefined`. */
export function siteForSlug(slug: string): NetworkSite | undefined {
  return SITES.find((s) => s.slug === slug);
}

/**
 * The stories a site *surfaces* — the **readable** ones: its registered stories minus any `hidden`
 * (#1256) or `comingSoon` (#1526) ones. Every readable surface (the hub, the story catalog/atoms,
 * the record→chapter backlinks, the readiness `story` gate) resolves through this, so a
 * not-readable story (both editorial walks are `comingSoon` today) contributes nothing readable
 * while its content, routes, and metadata stay intact. Metadata lookups (`storyMetaFor`) read the
 * raw `site.stories` instead, so a not-readable story keeps its title/dek for its teaser.
 */
export function surfacedWalks(slug: string): readonly WalkRef[] {
  return siteForSlug(slug)?.stories?.filter((s) => !s.hidden && !s.comingSoon) ?? [];
}

/**
 * Whether a site **registers** a story codename at all — readable, `hidden`, or `comingSoon` alike.
 *
 * This is the **route-emission** gate (#1466), and it is deliberately NOT `selectable`. Both
 * not-readable states hold a story's *content*, never its URL: `hidden` keeps it "reachable by
 * direct URL, just not advertised," and `comingSoon` serves an interstitial at the same routes
 * (#1529) so links resolve instead of 404ing. Switchability is a different axis — a non-selectable
 * peer still builds its own `/network/<slug>/` home, and that home advertises a held story with a
 * teaser pointing at `/network/<slug>/stories/<codename>/`. While `selectable` gated the story
 * routes, that teaser became a dead link the moment a non-selectable site registered a walk, which
 * Findlay's `flagpole` (#1466) is the first to do.
 */
export function siteRegistersWalk(slug: string, codename: string): boolean {
  return (siteForSlug(slug)?.stories ?? []).some((s) => s.codename === codename);
}

/** Every site registering at least one story, in registry order — the story routes' path source. */
export function walkHostSites(): readonly NetworkSite[] {
  return SITES.filter((s) => (s.stories?.length ?? 0) > 0);
}

/**
 * The stories a site advertises as **coming soon** (#1526) — the visible-teaser peer of
 * {@link surfacedWalks}. These are *not* readable (excluded from every readable surface above)
 * but *are* advertised: the site home renders their title/dek as a teaser card, and their routes
 * serve a coming-soon interstitial. `hidden` still wins — a `hidden` story is silent, never a
 * coming-soon teaser — so this excludes it.
 */
export function comingSoonWalks(slug: string): readonly WalkRef[] {
  return siteForSlug(slug)?.stories?.filter((s) => s.comingSoon && !s.hidden) ?? [];
}

/**
 * Whether a site advertises a specific story codename as coming soon — the route-interstitial gate
 * (#1529). The story pages render the held-content interstitial (not the narrative) when this is
 * true for the resolved `(slug, codename)`.
 */
export function walkComingSoon(slug: string, codename: string): boolean {
  return comingSoonWalks(slug).some((s) => s.codename === codename);
}

/**
 * The legal jurisdiction (US state) a site's records live under, spelled out — e.g. `"Ohio"`,
 * `"Indiana"`. The source for per-site datelines/kickers, so the site pages read it instead of
 * hardcoding "Lima, Ohio" (#741). Resolved from the registry's two-letter `state` (#1863).
 *
 * Empty string for an unknown slug or an unrecognized code — a dateline is prose, so a gap here
 * reads as "Lima" rather than breaking the page. The grouping builders, which would silently *drop*
 * the site instead, throw on the same gap; `placementViolations` is the guard for both.
 */
export function siteState(slug: string): string {
  const code = siteForSlug(slug)?.state;
  return (code && STATE_NAMES[code]) ?? "";
}

/**
 * The default DeckGL map viewport for a site, read from the YAML identity registry (#1027/#1032).
 * Returns `null` for tracking-only sites that have no Python profile yet (no map defaults set).
 */
export function mapView(slug: string): { lat: number; lon: number; zoom: number } | null {
  const entry = sitesRegistry.sites.find((e) => e.slug === slug);
  if (!entry || entry.map_lat == null || entry.map_lon == null || entry.map_zoom == null) return null;
  return { lat: entry.map_lat, lon: entry.map_lon, zoom: entry.map_zoom as number };
}

export type GroupBy = "state" | "basin";

export interface SiteGroup {
  /** Group heading (the state name, or the basin name). */
  label: string;
  /** Short tag shown beside the heading (the state abbr, or the 3-letter basin code). */
  tag: string;
  sites: NetworkSite[];
  /** Region super-group (basin lens only): set on the FIRST basin group of each region so the
   *  panel can render a region header bar before it. Absent in the state lens. */
  region?: string;
  regionLabel?: string;
  regionTag?: string;
  regionCount?: number;
  showRegion?: boolean;
}

/**
 * Group the registry by the State (jurisdiction) or Basin (the major river basins) axis — the
 * grouped selector's two lenses (#307/#308). The state lens groups by first appearance; the basin
 * lens nests basins under the four regions (design "Site Selector"), walking `REGIONS` order then
 * the basins of each. Rows keep their registry order, so the same sites pivot without reshuffling.
 *
 * Both lenses place **every** registered site or throw naming the one they couldn't (#1863). An
 * empty basin (one no site is registered in) is omitted rather than rendered as a bare heading.
 */
export function groupSites(by: GroupBy): SiteGroup[] {
  return groupSitesIn(SITES, by);
}

/**
 * The seam of {@link groupSites} over an explicit `sites` list (the house idiom — cf.
 * {@link comingSoonFrom}, {@link selectablePathsFrom}). The testable core: it is what lets a
 * fixture prove the unplaced-site throw without a malformed committed registry.
 */
export function groupSitesIn(sites: readonly NetworkSite[], by: GroupBy): SiteGroup[] {
  if (by === "state") {
    const groups: SiteGroup[] = [];
    const index = new Map<string, SiteGroup>();
    for (const s of sites) {
      const { stateName } = placementOf(s);
      let g = index.get(stateName);
      if (!g) {
        g = { label: stateName, tag: s.state, sites: [] };
        index.set(stateName, g);
        groups.push(g);
      }
      g.sites.push(s);
    }
    return groups;
  }

  // Basin lens — region super-groups, then basins within each region.
  const byBasin = new Map<string, NetworkSite[]>();
  for (const s of sites) {
    const { basin } = placementOf(s);
    const arr = byBasin.get(basin.slug);
    if (arr) arr.push(s);
    else byBasin.set(basin.slug, [s]);
  }
  const groups: SiteGroup[] = [];
  for (const region of REGIONS) {
    const basins = basinsOfRegion(region.key).filter((b) => byBasin.has(b.slug));
    const regionCount = basins.reduce((n, b) => n + (byBasin.get(b.slug)?.length ?? 0), 0);
    basins.forEach((b, i) => {
      groups.push({
        label: b.label,
        tag: b.abbr,
        sites: byBasin.get(b.slug) ?? [],
        region: region.key,
        regionLabel: region.label,
        regionTag: region.abbr,
        regionCount,
        showRegion: i === 0,
      });
    });
  }
  return groups;
}
