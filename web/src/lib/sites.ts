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
import { runWithSite } from "./bundle";
import { DEFAULT_STORY_CODENAME, SITE_BASE, siteBase } from "./routes";
import sitesRegistry from "./sites-registry.json";

export type SiteStatus = "live" | "building" | "queued" | "tracking";

/**
 * A story a site hosts — the lightweight registry reference (#724/#729). It names the story
 * (codename + title) for the switcher / nav; the full reading path (chapters, anchors) lives
 * in the story store keyed by `(site.slug, codename)` — `storyFor` in `./walk` today, the MDX
 * `stories` collection later (#730).
 */
export interface StoryRef {
  /** Story codename — the URL segment under the site's `stories/` and the store key. */
  codename: string;
  /** Display title, e.g. "Project BOSC". */
  title: string;
  /** One-line description — the on-ramp dek / nav blurb (story-level, not per chapter). */
  dek: string;
  /**
   * Hidden from every *surface* (switcher, site hub, story catalog, atoms) while its content,
   * `/stories/<codename>` routes, and this metadata are all retained (#1256). This is the
   * "hidden, not removed" state — the story stays reachable by direct URL and its title/dek keep
   * feeding the reader pages; it just isn't advertised anywhere. `surfacedStories` filters these
   * out; `storyMetaFor` (title/dek lookup) deliberately still reads them.
   */
  hidden?: boolean;
  /**
   * "Coming soon" — advertised as coming, but not readable (#1526). The distinct, *visible* peer of
   * `hidden`: where `hidden` silently unsurfaces a story (no teaser, still reachable by direct URL),
   * `comingSoon` does the opposite — the story is **advertised** as a visible teaser (title + dek +
   * a coming-soon badge, `comingSoonStories`) but its content is **held** (the `/stories/<codename>`
   * routes serve a coming-soon interstitial, not the narrative; `storyComingSoon`). Like `hidden`, a
   * `comingSoon` story contributes **no readable surfaces**: `surfacedStories` excludes it, so no
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
  stories?: readonly StoryRef[];
}

// TypeScript-only overlays — stories live here, not in the YAML identity registry (#1027).
// The YAML drives slug/place/basin/status/selectable/codename/mono/map defaults; stories
// are authored here because they reference story codemnames + prose that aren't site-identity.
//
// A story surfaces (in the switcher, the hub, the catalog/atoms, the record backlinks) only when
// it's registered here AND readable — neither `hidden` nor `comingSoon` — see `surfacedStories`.
// Two "not-readable" states share this overlay: `hidden` (#1256) unsurfaces a story *silently*
// (reachable by direct URL, no teaser); `comingSoon` (#1526) unsurfaces it *visibly* (a teaser
// advertises title/dek, the routes serve an interstitial). Both keep the story's content, its
// `/stories/<codename>` routes, the `WALK_*` guard, and its title/dek intact.
//
// Both editorial ("in-line") stories are marked `comingSoon` (#1526): the guided walks are held
// behind a visible teaser while the record they teach is finished. `surfacedStories` returns
// neither; `comingSoonStories` returns both.
const STORIES: Partial<Record<string, readonly StoryRef[]>> = {
  lima: [
    {
      codename: DEFAULT_STORY_CODENAME,
      title: "Project BOSC",
      dek: "Project BOSC — read the record one document at a time, no prior knowledge.",
      comingSoon: true,
    },
  ],
  "fort-wayne": [
    {
      codename: "project-zodiac",
      title: "Project Zodiac",
      dek: "Project Zodiac — a $2B Google data center in Fort Wayne, read from the records.",
      comingSoon: true,
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
    status: entry.status as SiteStatus,
    selectable: entry.selectable,
    href: entry.slug === "lima" ? SITE_BASE : `/network/${entry.slug}`,
    ...(entry.issue !== null ? { issue: entry.issue } : {}),
    ...(STORIES[entry.slug] ? { stories: STORIES[entry.slug] } : {}),
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
export type FacilityStatus = "investigation" | "confirmed" | "construction" | "live";

const FACILITY_STATUS: Record<string, FacilityStatus> = {
  lima: "construction", // Shawnee Energy Campus — air-permit-grounded, ~313 MW (the disclosed build)
  "fort-wayne": "live", // GCP — a disclosed facility, not yet a construction record
  urbana: "confirmed", // Urbana Technology Hub (Thor) — disclosed Feb 2026; MW load still [open] (#1327)
  "troy-piqua": "confirmed", // Project Klondike (J5 LLC/Shaytura) — approved 4-0 Nov 2025; MW load still [open] (#1482)
  sidney: "construction", // AWS "Project Galaxy" — grading permit 2026-05-14, groundbreaking ~Jan 2026; MW load still [open] (#1378)
};

/** A site's facility lifecycle stage; "investigation" when no facility is disclosed. */
export function facilityStatus(slug: string): FacilityStatus {
  return FACILITY_STATUS[slug] ?? "investigation";
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
// Canonical (state, basin) placement for every site. The selector pivots the SAME sites by
// either axis — `state` is the legal jurisdiction a record lives under; `basin` is the major
// river basin (one of nine) it documents. Both matter to a researcher, so either can be the
// outer grouping. The per-row `basin` subline carries the finer sub-watershed detail.
const PLACEMENT: Record<string, { state: string; basin: string }> = {
  lima: { state: "Ohio", basin: "Maumee" },
  "fort-wayne": { state: "Indiana", basin: "Maumee" },
  defiance: { state: "Ohio", basin: "Maumee" },
  findlay: { state: "Ohio", basin: "Maumee" },
  toledo: { state: "Ohio", basin: "Maumee" },
  // Bowling Green sits on the Maumee-Portage divide: it drinks the Maumee but discharges to the
  // Portage (a distinct Lake Erie basin), so it groups under its OWN basin, not the Maumee's.
  "bowling-green": { state: "Ohio", basin: "Portage" },
  "van-wert": { state: "Ohio", basin: "Maumee" },
  bryan: { state: "Ohio", basin: "Maumee" },
  ottawa: { state: "Ohio", basin: "Maumee" },
  // The Miami branches (Ohio River sink, not Lake Erie).
  urbana: { state: "Ohio", basin: "Great Miami" },
  springfield: { state: "Ohio", basin: "Great Miami" },
  xenia: { state: "Ohio", basin: "Little Miami" },
  wpafb: { state: "Ohio", basin: "Great Miami" },
  "hamilton-middletown": { state: "Ohio", basin: "Great Miami" },
  "troy-piqua": { state: "Ohio", basin: "Great Miami" },
  sidney: { state: "Ohio", basin: "Great Miami" },
  greenville: { state: "Ohio", basin: "Great Miami" },
  wilmington: { state: "Ohio", basin: "Little Miami" },
  // The Scioto branch (the data-center epicenter) and the remaining major basins.
  "new-albany": { state: "Ohio", basin: "Scioto" },
  columbus: { state: "Ohio", basin: "Scioto" },
  piketon: { state: "Ohio", basin: "Scioto" },
  // The Ohio River (direct) branch — Ohio Brush Creek drains straight to the Ohio, no Scioto/Miami
  // loop. Far-southern unglaciated Appalachian Adams County OH (#1117); grouped with the southern
  // Appalachian basins, adjacent to the Scioto.
  "west-union": { state: "Ohio", basin: "Ohio Brush Creek" },
  newark: { state: "Ohio", basin: "Muskingum" },
  zanesville: { state: "Ohio", basin: "Muskingum" },
  coshocton: { state: "Ohio", basin: "Muskingum" },
  mansfield: { state: "Ohio", basin: "Muskingum" },
  sandusky: { state: "Ohio", basin: "Sandusky" },
  fremont: { state: "Ohio", basin: "Sandusky" },
  tiffin: { state: "Ohio", basin: "Sandusky" },
  bucyrus: { state: "Ohio", basin: "Sandusky" },
  cleveland: { state: "Ohio", basin: "Cuyahoga" },
  akron: { state: "Ohio", basin: "Cuyahoga" },
  lordstown: { state: "Ohio", basin: "Mahoning" },
  youngstown: { state: "Ohio", basin: "Mahoning" },
  lancaster: { state: "Ohio", basin: "Hocking" },
  athens: { state: "Ohio", basin: "Hocking" },
  logan: { state: "Ohio", basin: "Hocking" },
};

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
export function surfacedStories(slug: string): readonly StoryRef[] {
  return siteForSlug(slug)?.stories?.filter((s) => !s.hidden && !s.comingSoon) ?? [];
}

/**
 * The stories a site advertises as **coming soon** (#1526) — the visible-teaser peer of
 * {@link surfacedStories}. These are *not* readable (excluded from every readable surface above)
 * but *are* advertised: the site home renders their title/dek as a teaser card, and their routes
 * serve a coming-soon interstitial. `hidden` still wins — a `hidden` story is silent, never a
 * coming-soon teaser — so this excludes it.
 */
export function comingSoonStories(slug: string): readonly StoryRef[] {
  return siteForSlug(slug)?.stories?.filter((s) => s.comingSoon && !s.hidden) ?? [];
}

/**
 * Whether a site advertises a specific story codename as coming soon — the route-interstitial gate
 * (#1529). The story pages render the held-content interstitial (not the narrative) when this is
 * true for the resolved `(slug, codename)`.
 */
export function storyComingSoon(slug: string, codename: string): boolean {
  return comingSoonStories(slug).some((s) => s.codename === codename);
}

/**
 * The legal jurisdiction (US state) a site's records live under — e.g. `"Ohio"`, `"Indiana"`.
 * The source for per-site datelines/kickers, so the site pages read it instead of hardcoding
 * "Lima, Ohio" (#741). Empty string for an unplaced slug.
 */
export function siteState(slug: string): string {
  return PLACEMENT[slug]?.state ?? "";
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

const STATE_ABBR: Record<string, string> = { Ohio: "OH", Indiana: "IN" };
const BASIN_ABBR: Record<string, string> = {
  Maumee: "MAU",
  Portage: "POR",
  "Great Miami": "GMI",
  "Little Miami": "LMI",
  Scioto: "SCI",
  Muskingum: "MUS",
  Sandusky: "SAN",
  Cuyahoga: "CUY",
  Mahoning: "MAH",
  Hocking: "HOC",
  "Ohio Brush Creek": "OBC",
};

// Region super-groups (design "Site Selector") — the basin lens nests its eleven basins under
// four regions so the panel reads geographically. Keyed by the display basin name.
const BASIN_REGION: Record<string, string> = {
  Maumee: "maumee",
  Portage: "maumee", // NW-Ohio Lake Erie basin adjacent to the Maumee (Bowling Green borders Toledo)
  "Great Miami": "miamis",
  "Little Miami": "miamis",
  Scioto: "southeast",
  Muskingum: "southeast",
  Hocking: "southeast",
  "Ohio Brush Creek": "southeast",
  Cuyahoga: "northeast",
  Mahoning: "northeast",
  Sandusky: "northeast",
};
const REGION_ORDER = ["maumee", "miamis", "southeast", "northeast"] as const;
const REGION_LABEL: Record<string, string> = {
  maumee: "Maumee Basin",
  miamis: "The Two Miamis",
  southeast: "Southeastern Basins",
  northeast: "Northeast Basins",
};
const REGION_ABBR: Record<string, string> = {
  maumee: "MAU",
  miamis: "2MI",
  southeast: "SE",
  northeast: "NE",
};
// Basin order within a region (the panel's row order); the basin lens walks REGION_ORDER then this.
const BASIN_ORDER = [
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
];

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
 * Group the registry by the State (jurisdiction) or Basin (the nine major river basins) axis —
 * the grouped selector's two lenses (#307/#308). The state lens groups by first appearance; the
 * basin lens nests basins under four regions (design "Site Selector"), walking REGION_ORDER then
 * the basin order within each region. Rows keep their registry order, so the same sites pivot
 * without reshuffling.
 */
export function groupSites(by: GroupBy): SiteGroup[] {
  if (by === "state") {
    const groups: SiteGroup[] = [];
    const index = new Map<string, SiteGroup>();
    for (const s of SITES) {
      const p = PLACEMENT[s.slug];
      if (!p) continue;
      let g = index.get(p.state);
      if (!g) {
        g = { label: p.state, tag: STATE_ABBR[p.state] ?? "", sites: [] };
        index.set(p.state, g);
        groups.push(g);
      }
      g.sites.push(s);
    }
    return groups;
  }

  // Basin lens — region super-groups, then basins within each region.
  const byBasin = new Map<string, NetworkSite[]>();
  for (const s of SITES) {
    const p = PLACEMENT[s.slug];
    if (!p) continue;
    const arr = byBasin.get(p.basin);
    if (arr) arr.push(s);
    else byBasin.set(p.basin, [s]);
  }
  const groups: SiteGroup[] = [];
  for (const region of REGION_ORDER) {
    const basins = BASIN_ORDER.filter((b) => BASIN_REGION[b] === region && byBasin.has(b));
    const regionCount = basins.reduce((n, b) => n + (byBasin.get(b)?.length ?? 0), 0);
    basins.forEach((b, i) => {
      groups.push({
        label: b,
        tag: BASIN_ABBR[b] ?? "",
        sites: byBasin.get(b) ?? [],
        region,
        regionLabel: REGION_LABEL[region],
        regionTag: REGION_ABBR[region],
        regionCount,
        showRegion: i === 0,
      });
    });
  }
  return groups;
}
