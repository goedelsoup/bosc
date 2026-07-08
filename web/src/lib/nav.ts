/**
 * The site's information architecture. Two related models:
 *
 *  - `sections()` — the **content areas**, each with a minimal table of contents
 *    (the per-section TOC rail, the search index, and the docs grouping read it).
 *  - `networkTabs()` / `siteTabs()` / `platformLinks()` — the **header bar**
 *    presentation (design "Global Chrome"): a two-tier bar whose left tabs swap
 *    by tier, plus the constant platform cluster on the right.
 *
 * A page declares its `section`; the header resolves which tab is active via
 * `navItemActive` (so the Environment sub-area lights the Corpus tab, etc.).
 *
 * **Per-site (#724/#740):** these are now functions, not constants — every site-rooted href is
 * built from the **active** site (`siteBase(activeSite())` / the active site's default story), so
 * a second site's chrome points at its own pages. They're evaluated per render (inside the
 * middleware's `runWithSite` scope); nav.ts is build-only, so reading the ambient site is safe.
 * Network-global hrefs (`/about`, `/wiki/`, `/`, …) are unchanged.
 */

import { activeSite } from "./bundle";
import type { HypothesisItem } from "./feeds";
import { sectionStatus } from "./readiness";
import { siteBase, storyBase } from "./routes";
import type { NetworkSite } from "./sites";
import { type Story, activeStory, chapterHref, storyContentsHref } from "./walk";

export type SectionId =
  | "home"
  | "leads"
  | "story"
  | "timeline"
  | "reports"
  | "about"
  | "site"
  | "environment"
  | "economy"
  | "wiki"
  | "ask"
  | "search"
  | "directory"
  | "research"
  | "submit"
  | "connect";

export interface TocEntry {
  /** Visible label in the per-section TOC. */
  label: string;
  /** The `id` of the heading on the section page this entry points to. */
  anchor: string;
  /** Optional rail glyph (e.g. "·", "①"); defaults to a 2-digit running index. */
  num?: string;
}

export interface Section {
  id: SectionId;
  /** Full label (section H1, search). */
  label: string;
  /** Short label for the topbar tab. */
  tab: string;
  /** Root-absolute path to the section landing (pre-deploy-base). */
  href: string;
  /** One-line description (used on the landing and in search). */
  blurb: string;
  toc: TocEntry[];
}

/** The active site's URL root (pre-deploy-base) and its surfaced story's root. When the site
 *  surfaces no story (a thin peer, or Lima with its walk hidden — #1256), `storyRoot` falls back
 *  to the site's OWN home, never Lima's story: a non-story site must not leak into Lima's walk. */
function siteRoots(): { base: string; storyRoot: string; story: Story | undefined } {
  const base = siteBase(activeSite());
  const story = activeStory();
  const storyRoot = story ? storyBase(story.site, story.codename) : base;
  return { base, storyRoot, story };
}

/** The content-area model for the active site (TOC rail / search index / docs grouping). */
export function sections(): Section[] {
  const { base, storyRoot } = siteRoots();
  return [
    {
      id: "home",
      label: "Home",
      tab: "Home",
      href: base,
      blurb: "Landing, disclaimer, corpus at a glance, and the two doors in.",
      toc: [
        { label: "Disclaimer", anchor: "disclaimer" },
        { label: "Corpus at a glance", anchor: "corpus" },
        { label: "The story", anchor: "story" },
      ],
    },
    {
      // Open leads (design "Site Leads") — every gap on the site, in the open, each tracing
      // to a real committed source (the corpus-completeness audit's [open]/withheld items and
      // the boom-origin hypotheses' open questions). A tile in the "The site" mega-menu.
      id: "leads",
      label: "Open leads",
      tab: "Leads",
      href: `${base}/leads`,
      blurb: "Every gap we're chasing on this site — unverified inference until a source corroborates it.",
      toc: [],
    },
    {
      // The story (design "Site Home" → "Story home"): the guided walk, hosted under the site at
      // its story root so a site can carry multiple stories.
      id: "story",
      label: "The story",
      tab: "Story",
      href: storyRoot,
      blurb: "Project BOSC — read the record one document at a time, no prior knowledge.",
      toc: [],
    },
    {
      id: "timeline",
      label: "Timeline",
      tab: "Timeline",
      href: `${base}/timeline`,
      blurb: "Every dated event in the record, ordered — confidentiality first, the public reveal last.",
      toc: [],
    },
    {
      id: "reports",
      label: "Reports",
      tab: "Reports",
      href: `${base}/reports`,
      blurb:
        "Long-form analysis over the corpus — the dossier, the water and economics reads, and the extension narratives.",
      toc: [],
    },
    {
      id: "site",
      label: "The corpus",
      tab: "Corpus",
      href: `${base}/site/`,
      blurb: "Documents, records, exhibits, people & places, legal history, and the environmental data.",
      toc: [
        { label: "Documents", anchor: "documents" },
        { label: "Records", anchor: "records" },
        { label: "Timeline", anchor: "timeline" },
        { label: "Exhibits", anchor: "exhibits" },
        { label: "People & places", anchor: "people" },
        { label: "Legal history", anchor: "legal" },
        { label: "Reference data", anchor: "reference" },
      ],
    },
    {
      id: "environment",
      label: "The environment",
      tab: "Environment",
      href: `${base}/environment/`,
      blurb: "Hydrology dashboards, the watershed map, imagery before/during/after, and RSEI toxics.",
      toc: [
        { label: "Hydrology", anchor: "hydrology" },
        { label: "Watershed map", anchor: "map" },
        { label: "Imagery", anchor: "imagery" },
        { label: "RSEI / toxics", anchor: "rsei" },
        { label: "Air dispersion", anchor: "air" },
        { label: "Seasonal withdrawal", anchor: "seasonal" },
      ],
    },
    {
      // The economy section (design "Chrome", 5-tab site bar) — the economic ground the
      // data-center deal sits on: the localized labor baseline, the grid/load backdrop, the
      // end-use & workloads read, and the cost-of-opacity narrative.
      id: "economy",
      label: "The economy",
      tab: "Economy",
      href: `${base}/economy/`,
      blurb:
        "The local economic ground — labor baseline, the grid/load backdrop, end-use & workloads, and the cost of opacity.",
      toc: [],
    },
    {
      id: "about",
      label: "About",
      tab: "About",
      href: "/about",
      blurb: "What Watermark is, the method behind it, and who's assembling it.",
      toc: [],
    },
    {
      id: "wiki",
      label: "Wiki",
      tab: "Wiki",
      href: "/wiki/",
      blurb: "Entity & concept pages with backlinks and a graph neighborhood.",
      toc: [
        { label: "Entities", anchor: "entities" },
        { label: "People", anchor: "people" },
        { label: "Concepts", anchor: "concepts" },
        { label: "Curated entities", anchor: "curated" },
      ],
    },
    {
      id: "ask",
      label: "Ask the corpus",
      tab: "Ask",
      href: "/ask",
      blurb: "Ask a question of the record and get a cited answer drawn only from the extracted corpus.",
      toc: [],
    },
    {
      // The network directory — the multi-site overview (#304/#307). It IS the root `/`: the
      // landing lists every watershed-point site. The live site is /network/<id>; coming-soon
      // sites are /network/<slug>; research moved to /research/hypotheses. The switcher is the entry.
      id: "directory",
      label: "The network directory",
      tab: "Directory",
      href: "/",
      blurb:
        "Data-center development across Ohio's Maumee watershed, point by point — Lima is the reference build.",
      toc: [],
    },
    {
      // The network's research layer — the boom-origin hypotheses + the MCP playground.
      id: "research",
      label: "Research",
      tab: "Research",
      href: "/research/hypotheses",
      blurb: "Read the network three ways — the boom-origin hypotheses, scored against each site.",
      toc: [],
    },
    {
      // Contribute a lead — a network-tier entry (no account; a document, a name, a correction).
      id: "submit",
      label: "Submit a lead",
      tab: "Submit",
      href: "/submit",
      blurb: "Contribute a document, a name, or a correction — every confirmed figure started as a lead.",
      toc: [],
    },
  ];
}

export function getSection(id: SectionId): Section {
  const section = sections().find((s) => s.id === id);
  if (!section) throw new Error(`Unknown section "${id}"`);
  return section;
}

// --- Header bar model (two-tier chrome, design "Global Chrome") -------------
//
// One bar, two tiers. The `Watermark.` wordmark always links home to the network;
// a chip (the breadcrumb / switcher) sits beside it. The LEFT tabs swap by tier:
//  - network level (the directory + cross-cutting globals) → Directory · Research · About▾
//  - inside a site → The site▾ · The story · The environment · The economy · The record
// The PLATFORM cluster (Docs · Wiki · | · Submit · Ask · Search) sits right and never
// changes — Submit is a right-side affordance present on BOTH tiers (design "Chrome"),
// not a left network tab. The active tier is resolved from the route (`siteForPath` in
// the Header): inside a site → site tier.

/** A link in a dropdown menu (an optional second line), or a horizontal divider. */
export type NavChild = { label: string; href: string; blurb?: string } | { divider: true };

/** A column of links inside the "The site" mega-menu (design "Chrome"). `locked` marks a
 *  destination whose section isn't ready on a thinner peer (#781) — the link still resolves (to a
 *  coherent lock), but the nav flags it so available vs locked is explicit in the menu itself. */
export interface MegaLink {
  label: string;
  href: string;
  blurb?: string;
  num?: string;
  locked?: boolean;
}
/** The "The site" mega-menu: two intro tiles and the story spine. The environment + economy
 *  themes it crosses are now first-class site-tier dropdown tabs (#1307), not a column here.
 *  The spine carries `locked` when the story is locked for the active (peer) site (#781). */
export interface MegaMenu {
  tiles: { label: string; href: string; blurb: string; icon: "home" | "leads" }[];
  spine: {
    title: string;
    href: string;
    count: string;
    blurb: string;
    tocHref: string;
    items: MegaLink[];
    locked?: boolean;
  };
}

export type NavItem =
  | { kind: "link"; label: string; section: SectionId; href: string; match?: SectionId[]; locked?: boolean }
  | { kind: "dropdown"; label: string; section: SectionId; children: NavChild[]; match?: SectionId[] }
  | { kind: "mega"; label: string; section: SectionId; mega: MegaMenu; match?: SectionId[] };

/** Network-tier left tabs — shown at the directory and on cross-cutting globals.
 *  Submit is NOT here — it's a right-cluster affordance (see SUBMIT_LINK / the Header).
 *  Hypotheses come from the live feed so the dropdown labels stay in sync without hardcoding. */
export function networkTabs(hypotheses: HypothesisItem[] = []): NavItem[] {
  // The two framing essays (research course + the bigger picture) are the author's investigation
  // overview, re-homed out of the site-scoped `home` section into this network-global About area
  // (#1308). Their routes stay per-site for now (`<base>/docs/<slug>`, option (a) as in #1305);
  // the entry points at the active site's copy until the docs move global (#1304).
  const docBase = siteBase(activeSite());
  const researchChildren: NavChild[] = [
    ...hypotheses.map((h) => ({ label: h.name, href: `/research/hypotheses?lens=${h.id}` })),
    ...(hypotheses.length > 0 ? [{ divider: true as const }] : []),
    // Basin views (design "Chrome": Research ▾ → Basin views) — Maumee is the one built today;
    // the other eight basins join here as their /basin pages land.
    { label: "The Maumee basin", href: "/basin", blurb: "Basin view — every site against the drainage" },
    { divider: true as const },
    { label: "Methodology", href: "/methodology", blurb: "How the record is built & labeled" },
    { label: CONNECT_LINK.label, href: CONNECT_LINK.href },
  ];
  return [
    { kind: "link", label: "Directory", section: "directory", href: "/" },
    {
      kind: "dropdown",
      label: "Research",
      section: "research",
      match: ["connect"],
      children: researchChildren,
    },
    {
      kind: "dropdown",
      label: "About",
      section: "about",
      children: [
        { label: "About this site", href: "/about", blurb: "What Watermark is, and why" },
        { label: "Who runs this", href: "/about-me", blurb: "The team behind the record" },
        { divider: true as const },
        {
          label: "Research course",
          href: `${docBase}/docs/course`,
          blurb: "What we're investigating — the open threads",
        },
        {
          label: "The bigger picture",
          href: `${docBase}/docs/bigger-picture`,
          blurb: "Placed against the national data-center build-out",
        },
        { divider: true as const },
        { label: "Data catalog", href: "/about/catalog", blurb: "Every dataset: source, license, freshness" },
        { divider: true as const },
        { label: "Contributing", href: "/about/contributing" },
      ],
    },
  ];
}

/** Site-tier left tabs — shown inside a site. A 5-tab bar (#1307): The site · The story ·
 *  The environment · The economy · The record. Environment and Economy are first-class site-tier
 *  dropdowns (promoted out of the "The site" mega, where they used to be "themes it crosses"). */
export function siteTabs(): NavItem[] {
  const { base, storyRoot, story } = siteRoots();
  const chapters = story?.chapters ?? [];
  // Per-site readiness (#781/#1220): on a thinner peer some of these destinations aren't on the
  // record yet. `sectionStatus` reads the bundle's domain-activation block, so Lima's menu is
  // unchanged (every domain live) without any reference-site special-case. A locked theme collapses
  // its dropdown to a non-navigable locked marker (the page isn't there yet), matching the locked
  // `link` tabs a coming-soon peer already shows.
  const slug = activeSite();
  const storyLocked = sectionStatus(slug, "story") === "locked";
  const environmentLocked = sectionStatus(slug, "environment") === "locked";
  const economyLocked = sectionStatus(slug, "economy") === "locked";
  return [
    {
      kind: "mega",
      label: "The site",
      section: "home",
      match: ["leads", "story"],
      mega: {
        tiles: [
          { label: "Overview", href: base, blurb: "The site at a glance — the front door", icon: "home" },
          {
            label: "Open leads",
            href: `${base}/leads`,
            blurb: "Every gap we're chasing, in the open",
            icon: "leads",
          },
        ],
        spine: {
          title: "The story",
          href: storyRoot,
          count: `${chapters.length} chapters · ~18 min`,
          blurb: "One project, read document by document — it crosses the environment and the economy.",
          // With no surfaced story the locked spine points at the site home (a valid target),
          // never a `${base}/contents` that 404s (#1256): `storyRoot` is the site base in that case.
          tocHref: story ? storyContentsHref(story) : storyRoot,
          locked: storyLocked,
          items: chapters.map((c) => ({
            num: String(c.step),
            label: c.title,
            href: story ? chapterHref(story, c.slug) : `${storyRoot}/${c.slug}`,
            blurb: c.skill,
          })),
        },
      },
    },
    { kind: "link", label: "The story", section: "story", href: storyRoot, locked: storyLocked },
    environmentLocked
      ? {
          kind: "link",
          label: "The environment",
          section: "environment",
          href: `${base}/environment/`,
          locked: true,
        }
      : {
          kind: "dropdown",
          label: "The environment",
          section: "environment",
          children: [
            {
              label: "The environment",
              href: `${base}/environment/`,
              blurb: "Section overview — the doors below",
            },
            { divider: true },
            {
              label: "Hydrology",
              href: `${base}/environment/hydrology`,
              blurb: "Low-flow dilution vs the 7Q10",
            },
            { label: "Watershed map", href: `${base}/environment/map`, blurb: "Typed GeoJSON on deck.gl" },
            {
              label: "Imagery",
              href: `${base}/environment/imagery`,
              blurb: "Dated aerials — before / after",
            },
            {
              label: "RSEI / toxics",
              href: `${base}/environment/rsei`,
              blurb: "EPA toxic-release inventory",
            },
            { label: "Air dispersion", href: `${base}/environment/air`, blurb: "AERMOD screening field" },
            {
              label: "Seasonal withdrawal",
              href: `${base}/environment/seasonal`,
              blurb: "Month-by-month climograph",
            },
            { label: "Water flow", href: `${base}/environment/flow`, blurb: "Animated reach-network flow" },
            {
              label: "Economics baseline",
              href: `${base}/environment/economics-baseline`,
              blurb: "BLS QCEW · Census",
            },
          ],
        },
    economyLocked
      ? {
          kind: "link",
          label: "The economy",
          section: "economy",
          href: `${base}/economy/`,
          locked: true,
        }
      : {
          kind: "dropdown",
          label: "The economy",
          section: "economy",
          children: [
            {
              label: "The economy",
              href: `${base}/economy/`,
              blurb: "Section overview — the ground the deal sits on",
            },
            { divider: true },
            {
              label: "Localized labor baseline",
              href: `${base}/environment/economics-baseline`,
              blurb: "BLS QCEW + Census employment",
            },
            {
              label: "End use & workloads",
              href: `${base}/reports/end-use-and-workloads`,
              blurb: "Where the campus load goes",
            },
            {
              label: "The load & the grid",
              href: `${base}/reports/the-load-and-the-grid`,
              blurb: "The grid backdrop",
            },
            {
              label: "The economic ledger",
              href: `${base}/reports/the-economic-ledger`,
              blurb: "The public balance sheet",
            },
            {
              label: "Demand & public benefits",
              href: `${base}/docs/economics`,
              blurb: "The prose companion",
            },
          ],
        },
    { kind: "link", label: "The record", section: "site", href: `${base}/site/`, match: ["timeline"] },
  ];
}

/**
 * Site-tier tabs for a COMING-SOON (non-selectable) site (#793). Such a site has no inner pages or
 * bundle yet — its only real page is the watch page — so this is a registry-only, mostly-locked
 * bar: "The site" links to the overview (the watch page), while "The story" / "The record" are
 * locked markers (the watch page itself lists what will land there). Built purely from the registry
 * `NetworkSite`, never the bundle (a coming-soon site has none, and the page renders against the
 * Lima reference), so the menu names the *current* site without reading its non-existent data.
 */
export function comingSoonSiteTabs(site: NetworkSite): NavItem[] {
  const base = siteBase(site.slug);
  return [
    { kind: "link", label: "The site", section: "home", href: base },
    { kind: "link", label: "The story", section: "story", href: base, locked: true },
    { kind: "link", label: "The record", section: "site", href: base, locked: true },
  ];
}

/** The platform cluster (right of the bar), constant across tiers. Ask + Search and
 *  Submit are rendered separately as affordances; these two are the plain links.
 *  Connect has moved to the Research dropdown (#1017). */
export function platformLinks(): { label: string; section: SectionId; href: string }[] {
  const { base } = siteRoots();
  return [
    { label: "Docs", section: "reports", href: `${base}/docs/` },
    { label: "Wiki", section: "wiki", href: "/wiki/" },
  ];
}

/** Connect — the MCP connector + contribution entry point; lives in the Research dropdown (#1017). */
export const CONNECT_LINK: { label: string; section: SectionId; href: string } = {
  label: "Connect",
  section: "connect",
  href: "/network/connect",
};

/** Submit — a right-cluster affordance (a `+` pill), present on both tiers (design "Chrome").
 *  It's the network-tier `/submit` route; the per-record correction deep-links target the
 *  site-tier `<base>/submit` instead (both share <SubmitForm>). */
export const SUBMIT_LINK: { label: string; section: SectionId; href: string } = {
  label: "Submit",
  section: "submit",
  href: "/submit",
};

/** Whether `item` is the active header tab for the page's `active` section. A dropdown /
 *  mega parent lights when its section or any descendant section (its `match` list) is active. */
export function navItemActive(item: NavItem, active: SectionId): boolean {
  if (item.section === active) return true;
  return item.match?.includes(active) ?? false;
}

/** The flattened primary links a tab contributes to the footer row / mobile sheet. For the mega,
 *  that's just the two tiles — environment/economy are their own dropdown tabs now (#1307), each
 *  contributing its own children; the story spine's deep chapter links stay desktop-mega-only. */
export function navItemLinks(item: NavItem): { label: string; href: string }[] {
  if (item.kind === "link") return [{ label: item.label, href: item.href }];
  if (item.kind === "mega") return item.mega.tiles.map((t) => ({ label: t.label, href: t.href }));
  return item.children
    .filter((c): c is { label: string; href: string; blurb?: string } => !("divider" in c))
    .map((c) => ({ label: c.label, href: c.href }));
}

/** Flat primary-nav links for the footer row — both tiers + platform. A dropdown / mega tab
 *  contributes its children / tiles (so the footer still reaches Overview / Open leads / story). */
export function navLinks(): { label: string; href: string }[] {
  return [
    ...siteTabs().flatMap(navItemLinks),
    { label: "Directory", href: "/" },
    { label: "Research", href: "/research/hypotheses" },
    { label: CONNECT_LINK.label, href: CONNECT_LINK.href },
    ...platformLinks().map((t) => ({ label: t.label, href: t.href })),
  ];
}

export interface FooterGroup {
  heading: string;
  links: { label: string; href: string }[];
}

/** Structured footer nav groups — the three-column nav band. Raw paths; apply `withBase` in the template. */
export function footerGroups(): FooterGroup[] {
  const { base, storyRoot, story } = siteRoots();
  const plat = platformLinks();
  const docs = plat.find((p) => p.section === "reports")!;
  const wiki = plat.find((p) => p.section === "wiki")!;
  return [
    {
      heading: "The investigation",
      links: [
        { label: "Overview", href: base },
        { label: "Open leads", href: `${base}/leads` },
        { label: "The environment", href: `${base}/environment/` },
        { label: "The economy", href: `${base}/economy/` },
        // Only a site that surfaces a story gets a story link — a site without one (or Lima with
        // its walk hidden, #1256) shows none rather than leaking into Lima's story.
        ...(story ? [{ label: "The story", href: storyRoot }] : []),
        { label: "The record", href: `${base}/site/` },
      ],
    },
    {
      heading: "Resources",
      links: [
        { label: "Directory", href: "/" },
        { label: "Research", href: "/research/hypotheses" },
        { label: docs.label, href: docs.href },
        { label: wiki.label, href: wiki.href },
      ],
    },
    {
      heading: "Site",
      links: [
        { label: CONNECT_LINK.label, href: CONNECT_LINK.href },
        { label: "Methodology", href: "/methodology" },
        { label: "About", href: "/about" },
      ],
    },
  ];
}
