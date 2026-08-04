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
 * `navItemActive` (so the Environment sub-area lights the The record tab, etc.).
 *
 * **Per-site (#724/#740):** these are now functions, not constants — every site-rooted href is
 * built from the **active** site (`siteBase(activeSite())` / the active site's default story), so
 * a second site's chrome points at its own pages. They're evaluated per render (inside the
 * middleware's `runWithSite` scope); nav.ts is build-only, so reading the ambient site is safe.
 * Network-global hrefs (`/about`, `/wiki/`, `/`, …) are unchanged.
 */

import { activeSite } from "./bundle";
import type { HypothesisItem } from "./feeds";
import { LENS_ORDER, LENSES } from "./lenses";
import { lensStatus, sectionStatus } from "./readiness";
import { siteBase, storyBase } from "./routes";
import type { NetworkSite } from "./sites";
import { STUDY_CHAPTERS, STUDY_PARTS } from "./study";
import { NETWORK_NOUNS } from "./taxonomy";
import { type Story, activeStory, chapterHref, storyContentsHref } from "./walk";

export type SectionId =
  | "home"
  | "leads"
  | "contacts"
  | "story"
  | "study"
  | "timeline"
  | "reports"
  | "docs"
  | "about"
  | "site"
  | "environment"
  | "economy"
  | "wiki"
  | "ask"
  | "search"
  | "directory"
  | "lens"
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
 *  surfaces no *readable* story (a thin peer, or a site whose walk is `hidden`/#1256 or
 *  `comingSoon`/#1526), `storyRoot` falls back to the site's OWN home, never Lima's story: a
 *  non-story site must not leak into Lima's walk. */
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
      // Site-level contacts — the people and bodies to reach on this site (officials, organizers,
      // community groups the record names). A tile in the "The site" mega-menu; the spine the
      // petition-connect + bulletin surfaces build on.
      id: "contacts",
      label: "Contacts",
      tab: "Contacts",
      href: `${base}/contacts`,
      blurb: "The people and bodies to reach on this site — each one drawn from the record that names it.",
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
      // The impact study — the site's primary artifact: the environmental + economic study the
      // community never received, assembled from the public record. Every chapter renders the
      // screen the record supports or the gap AS a finding; the study never locks. The toc
      // anchors are the cover page's chapter cards (`id={def.id}`), which feeds the search index.
      id: "study",
      label: "The impact study",
      tab: "Study",
      href: `${base}/study/`,
      blurb:
        "The environmental and economic impact study this community never received — data where the record provides it, and the gap named where it doesn't.",
      toc: STUDY_CHAPTERS.map((c) => ({ label: c.title, anchor: c.id })),
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
      label: "The record",
      tab: "Record",
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
      // The section survives as the GATE (`ReadinessSection`) and as the `section=` 15 leaf pages
      // declare; its landing is the Environment lens now (#1915), and `/environment/` 301s there.
      href: `${base}/lens/environment`,
      blurb: "Hydrology dashboards, the watershed map, imagery before/during/after, and RSEI toxics.",
      toc: [
        { label: "Hydrology", anchor: "hydrology" },
        { label: "Watershed map", anchor: "map" },
        { label: "Imagery", anchor: "imagery" },
        { label: "RSEI / toxics", anchor: "rsei" },
        { label: "Air dispersion", anchor: "air" },
        { label: "Seasonal withdrawal", anchor: "seasonal" },
        { label: "Thermal / §316(a)", anchor: "thermal" },
      ],
    },
    {
      // The economy section (design "Chrome", 5-tab site bar) — the economic ground the
      // data-center deal sits on: the localized labor baseline, the grid/load backdrop, the
      // end-use & workloads read, and the cost-of-opacity narrative.
      id: "economy",
      label: "The economy",
      tab: "Economy",
      // Same as `environment` above: the gate stays, the landing is the Economy lens (#1915).
      href: `${base}/lens/economy`,
      blurb:
        "The local economic ground — labor baseline, the grid/load backdrop, end-use & workloads, and the cost of opacity.",
      toc: [],
    },
    {
      // The long-form prose collection (`lib/narrative.ts`) is network-global-host content — the
      // investigation's method and analysis, not per-watershed-site data (#1304) — so it lives at a
      // single root `/docs/` build, with its own section id (untangled from `reports`, which is the
      // per-site long-form landing). Global href, like the other network-global sections below.
      id: "docs",
      label: "Docs",
      tab: "Docs",
      href: "/docs/",
      blurb:
        "The investigation's long-form prose — the dossier, the water and economics reads, the legal analyses, and the framing essays.",
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
        // The network-global nouns, straight from the taxonomy (#1892): the nav model states the
        // canonical view per noun. People are per-site (each site's record hub), so not listed.
        ...NETWORK_NOUNS.map((n) => ({ label: n.label, anchor: n.anchor })),
        { label: "Open questions", anchor: "open-questions" },
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
      // The lens axis (#1914, epic #1911) — the network read five standing ways. The peer of
      // `research` and deliberately NOT a child of it: the hypotheses ask *why* the buildout is
      // happening and reach for a verdict; a lens asks *what it does* to a place and reaches for
      // none. Filing one under the other would blur exactly the distinction the epic opens by
      // drawing. Its TOC is the five lenses, which is also what makes each `/lens/<id>` page
      // searchable (`search.ts` walks the nav model).
      id: "lens",
      label: "Lenses",
      tab: "Lenses",
      href: "/lens/",
      blurb:
        "Five standing ways to read a buildout — the land it takes, the power it pulls, what it draws from the ground and air, what it costs the public, and how the decision was made.",
      toc: LENS_ORDER.map((id) => ({ label: LENSES[id].name, anchor: id })),
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
/** The "The site" mega-menu: the destination tiles (Overview · Open leads · Contacts · Reports —
 *  Reports re-homed here from the network Research ▾ dropdown, reverting #1305) and the story spine.
 *  The environment + economy themes it crosses are now first-class site-tier dropdown tabs (#1307),
 *  not a column here. The spine carries `locked` when the story is locked for the active (peer)
 *  site (#781). */
export interface MegaMenu {
  tiles: { label: string; href: string; blurb: string; icon: "home" | "leads" | "contacts" | "reports" }[];
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
  const researchChildren: NavChild[] = [
    // `?h=` is the canonical deep-link param (#1912). The page still honors the pre-#1912
    // `?lens=` spelling for links already shared, but nothing emits it any more.
    ...hypotheses.map((h) => ({ label: h.name, href: `/research/hypotheses?h=${h.id}` })),
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
      // Lenses ride BEFORE Research (#1914): "what does this buildout do to my county" is the
      // first question most readers actually arrive with, and the hypotheses — a causal thesis to
      // adjudicate — are the second. This is the network tier's only lens surface, so `/lens/*`
      // sits well inside the nav-diet ceiling; #1916 gives the home page the other one.
      kind: "dropdown",
      label: "Lenses",
      section: "lens",
      children: [
        { label: "All five lenses", href: "/lens/", blurb: "The network, read five standing ways" },
        { divider: true as const },
        ...LENS_ORDER.map((id) => ({
          label: `${LENSES[id].number} · ${LENSES[id].name}`,
          href: `/lens/${id}`,
          blurb: LENSES[id].question,
        })),
      ],
    },
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
        { label: "Mission", href: "/about/mission", blurb: "Why this project exists" },
        { label: "My research", href: "/about-me", blurb: "The method, the record's gaps, and who keeps it" },
        { divider: true as const },
        // The two framing essays (research course + the bigger picture) are the author's
        // investigation overview, re-homed out of the site-scoped `home` section into this
        // network-global About area (#1308); their docs live at the `/docs/` build (#1304).
        {
          label: "Research course",
          href: "/docs/course",
          blurb: "What we're investigating — the open threads",
        },
        {
          label: "The bigger picture",
          href: "/docs/bigger-picture",
          blurb: "Placed against the national data-center build-out",
        },
        { divider: true as const },
        { label: "Data catalog", href: "/about/catalog", blurb: "Every dataset: source, license, freshness" },
        { divider: true as const },
        { label: "Contributing", href: "/about/contributing" },
        { label: "Privacy", href: "/privacy", blurb: "What we do and don't collect" },
      ],
    },
  ];
}

/**
 * Site-tier left tabs — shown inside a site. A 4-tab bar (the nav diet, #1893, retained):
 * The site · **The impact study** · **Lenses** · The record.
 *
 * ## Why lenses are a primary tab beside the study (#1915)
 *
 * #1884 deliberately DEMOTED environment/economy into "Reference — the data behind the study's
 * chapters", because the impact study is the site's declared primary artifact. Promoting lenses
 * back to a primary tab partly reverses that reasoning, so the resolution is written down here
 * rather than left in a commit message:
 *
 * > The **study** is the *read* door — narrative, linear, verdict-bearing.
 * > The **lenses** are the *explore* door — dimensional, cross-site, never verdict-bearing.
 * > Different audiences; both first-class.
 *
 * A reader who wants the argument takes the study. A reader who arrived asking "what does this do
 * to my county's water" takes a lens, and can then carry that same question across every other
 * site in the network (`/lens/<id>`, #1914) — which the study, being one site's argument, cannot
 * do. Neither is the other's table of contents.
 *
 * The dropdown carries **five landings and nothing else**. That is what satisfies the criterion
 * this issue inherited from #1893 — "route prefix and menu section agree for every leaf reachable
 * from the tab" — which the old Reference dropdown could not, because it listed `/environment/map`
 * and `/environment/imagery` under a menu section that no longer named them. Those leaves are
 * reached from the Land landing instead: an in-page cross-link is not a nav surface (#1893), so
 * the prefix/section agreement holds and no URL had to move.
 *
 * The study — the site's primary artifact — still rides second, right after the mega. The
 * standalone "The story" tab is gone: the mega's spine IS the story — its head links the story
 * root and it lists every chapter — so the tab beside it was the same destination twice in one
 * bar. Story routes still light "The site" (see the mega's `match`).
 */
export function siteTabs(): NavItem[] {
  const { base, storyRoot, story } = siteRoots();
  const chapters = story?.chapters ?? [];
  // Per-site readiness (#781/#1220): on a thinner peer some of these destinations aren't on the
  // record yet. `lensStatus` composes the same domain-activation block `sectionStatus` reads, so
  // Lima's menu is unchanged (every domain live) without any reference-site special-case. A locked
  // lens still LINKS — its landing renders the coherent lock and the ask, which is a real
  // destination — but the dropdown marks it, so available vs awaiting-a-source is legible in the
  // menu itself rather than only after a click. The study tab has NO locked variant: an absent
  // record is a chapter's own content, never a lock.
  const slug = activeSite();
  const storyLocked = sectionStatus(slug, "story") === "locked";

  // Five landings and nothing else — see the docstring on why no facet leaf appears here.
  const lensChildren: NavChild[] = LENS_ORDER.map((id) => {
    const lens = LENSES[id];
    const locked = lensStatus(slug, id) === "locked";
    return {
      label: `${lens.number} · ${lens.name}`,
      href: `${base}/lens/${id}`,
      blurb: locked ? "Awaiting a source on this site" : lens.question,
    };
  });

  return [
    {
      kind: "mega",
      label: "The site",
      // Reports re-homed into this mega (reverting #1305), so the tab also lights on a report route.
      section: "home",
      match: ["leads", "contacts", "story", "reports"],
      mega: {
        tiles: [
          { label: "Overview", href: base, blurb: "The site at a glance — the front door", icon: "home" },
          {
            label: "Open leads",
            href: `${base}/leads`,
            blurb: "Every gap we're chasing, in the open",
            icon: "leads",
          },
          {
            label: "Contacts",
            href: `${base}/contacts`,
            blurb: "The people and bodies to reach on this site",
            icon: "contacts",
          },
          {
            // Reports — the long-form analysis over the record — is the site-tier capstone, re-homed
            // here from the network Research ▾ dropdown (reverting #1305). Like the leads/contacts
            // tiles it always links; a peer whose corpus can't support the read shows the lock on the
            // reports index itself (the readiness `reports` gate), not a nav marker.
            label: "Reports",
            href: `${base}/reports`,
            blurb: "Long-form analysis over the record",
            icon: "reports",
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
    {
      // The impact study — the site's primary artifact. Never a locked variant: the study
      // renders for every selectable site, and an absent record is a chapter's own content
      // (the gap-as-finding register), not a lock.
      kind: "dropdown",
      label: "The impact study",
      section: "study",
      children: [
        {
          label: "The impact study",
          href: `${base}/study/`,
          blurb: "Cover — the verdict strip over every chapter",
        },
        ...STUDY_PARTS.flatMap((p): NavChild[] => [
          { divider: true },
          ...STUDY_CHAPTERS.filter((c) => c.part === p.id).map((c) => ({
            label: c.title,
            href: `${base}/study/${c.id}`,
          })),
        ]),
      ],
    },
    {
      // Lenses — the explore door. Never collapses to a locked marker the way the old Reference
      // tab did on a stub peer: each landing is a real page even when locked, and its own lock
      // states what would open it, which is more useful than a non-navigable tab. `match` keeps
      // the surviving `/environment/*` and `/economy/*` LEAF routes lighting this tab, since the
      // sections those pages still declare are the ones their lenses gather.
      kind: "dropdown",
      label: "Lenses",
      section: "lens",
      match: ["environment", "economy"],
      children: lensChildren,
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
  return [
    // Docs are network-global-host (#1304): a single root `/docs/` build, not per-site.
    { label: "Docs", section: "docs", href: "/docs/" },
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

/** The flattened primary links a tab contributes to the mobile sheet. For the mega that's its
 *  tiles PLUS the story spine's head — the spine replaced the standalone "The story" tab (#1893),
 *  and a phone reader gets no mega, so without the head the story would be reachable from the
 *  desktop bar and the footer but not from the sheet. The spine's per-chapter links stay
 *  desktop-mega-only; the Lenses dropdown contributes its five landings. */
export function navItemLinks(item: NavItem): { label: string; href: string }[] {
  if (item.kind === "link") return [{ label: item.label, href: item.href }];
  if (item.kind === "mega") {
    return [
      ...item.mega.tiles.map((t) => ({ label: t.label, href: t.href })),
      { label: item.mega.spine.title, href: item.mega.spine.href },
    ];
  }
  return item.children
    .filter((c): c is { label: string; href: string; blurb?: string } => !("divider" in c))
    .map((c) => ({ label: c.label, href: c.href }));
}

export interface FooterGroup {
  heading: string;
  links: { label: string; href: string }[];
}

/** Structured footer nav groups — the three-column nav band. Raw paths; apply `withBase` in the template. */
export function footerGroups(): FooterGroup[] {
  const { base, storyRoot, story } = siteRoots();
  const plat = platformLinks();
  const docs = plat.find((p) => p.section === "docs")!;
  const wiki = plat.find((p) => p.section === "wiki")!;
  return [
    {
      heading: "The investigation",
      links: [
        { label: "Overview", href: base },
        // NOT the impact study (#1893). It reached readers from four places at once — the home's
        // full-width promotion, its own tab, that tab's chapter dropdown, and here — and a thing
        // linked from everywhere is emphasized nowhere. Its two surfaces are the ones that say
        // "primary artifact": the home band and the tab. See `navSurfaces`.
        { label: "Open leads", href: `${base}/leads` },
        { label: "The environment", href: `${base}/lens/environment` },
        { label: "The economy", href: `${base}/lens/economy` },
        // Only a site that surfaces a *readable* story gets a story link — a site without one (or
        // whose walk is hidden/#1256 or coming-soon/#1526) shows none rather than leaking into
        // Lima's story.
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
        { label: "Mission", href: "/about/mission" },
        { label: "Privacy", href: "/privacy" },
      ],
    },
  ];
}

// --- The navigation surfaces, and the ceiling on them (#1893) ---------------
//
// The nav diet's standing rule: **no destination appears in more than two navigation surfaces.**
// Before it, the impact study was reachable from four at once and Reports from four; neither was
// wrong on its own, and together they meant the nav had no hierarchy — everything one click from
// everywhere, which emphasizes nothing. `navSurfaces.test.ts` is the enforcement.
//
// A SURFACE is a distinct standing affordance a reader can use from a page, not a rendering of
// one. The desktop tab bar and the phone sheet render the SAME models (`siteTabs`,
// `networkTabs`, `platformLinks`), so they are one surface each, and a tab and its own dropdown
// are one surface — the dropdown is how that tab is opened, not a second route to the thing.
// Deliberately NOT counted: the `Watermark.` wordmark (the logo, a constant escape hatch, not a
// nav item), and in-page contextual cross-links (a hub tile, a chapter's annex footer, a "see
// also"). Those are the demotion this rule pushes work INTO — a destination that loses a nav
// surface keeps its contextual links.

/** One standing navigation affordance and every destination it offers. */
export interface NavSurface {
  id: "site-home" | "header-site" | "header-network" | "platform" | "footer";
  label: string;
  links: { label: string; href: string }[];
}

/** EVERY destination a tab offers, which is not the same set as `navItemLinks`. That one answers
 *  "what does the phone sheet show", and the sheet deliberately stops short of the mega's
 *  per-chapter links. A surface has to be counted by what a reader can actually reach from it, so
 *  the mega contributes its tiles, its spine head AND the spine's chapters — otherwise a chapter
 *  that later picked up a footer link and a home tile would sit on three surfaces with the ceiling
 *  test reporting two. */
export function navItemDestinations(item: NavItem): { label: string; href: string }[] {
  if (item.kind !== "mega") return navItemLinks(item);
  return [
    ...item.mega.tiles.map((t) => ({ label: t.label, href: t.href })),
    { label: item.mega.spine.title, href: item.mega.spine.href },
    ...item.mega.spine.items.map((i) => ({ label: i.label, href: i.href })),
  ];
}

/** The site home's promoted door — the impact study, the site's primary artifact (#1795). The
 *  home template renders this band; it's declared here so it is counted with the chrome rather
 *  than being invisible to the rule that governs the chrome. */
export function siteHomePromotions(): { label: string; href: string }[] {
  const { base } = siteRoots();
  return [{ label: "Read the impact study", href: `${base}/study/` }];
}

/** Every navigation surface for the active site, flattened. The ceiling is asserted over this. */
export function navSurfaces(hypotheses: HypothesisItem[] = []): NavSurface[] {
  return [
    { id: "site-home", label: "The site home's promoted door", links: siteHomePromotions() },
    {
      id: "header-site",
      label: "Header — site tier",
      links: siteTabs().flatMap(navItemDestinations),
    },
    {
      id: "header-network",
      label: "Header — network tier",
      links: networkTabs(hypotheses).flatMap(navItemDestinations),
    },
    {
      id: "platform",
      label: "Header — platform cluster",
      links: [
        ...platformLinks().map((p) => ({ label: p.label, href: p.href })),
        { label: SUBMIT_LINK.label, href: SUBMIT_LINK.href },
        { label: "Ask the corpus", href: "/ask" },
        { label: "Search", href: "/search" },
      ],
    },
    { id: "footer", label: "Footer", links: footerGroups().flatMap((g) => g.links) },
  ];
}
