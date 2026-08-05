/**
 * Build-time assembly of the client search index over the content bundle.
 *
 * **Two shards, because the network has two kinds of content** (#1890, epic #1884 phase 6).
 *
 * The index used to be one file assembled with no site argument at all, which meant every read
 * fell through `activeSite()` to Lima and every URL came out of the Lima-pinned `siteUrl()`. The
 * result was a box present on every page of every site that could only ever find Lima — and, since
 * documents contributed one row per *collection*, could not find a source document at all. 531
 * entries against 4,078 routes.
 *
 * What replaces it mirrors the scope vocabulary the record facets already declare (`RECORD_FACETS`,
 * #1886) and the nouns already declare (`taxonomy.ts`, #1892), rather than inventing a third:
 *
 *  - {@link buildNetworkSearchIndex} — the **network-global** shard, emitted once at
 *    `/search-index.json`: the root sections, the site directory, the long-form `/docs/` prose,
 *    and the wiki nouns. Loaded on every page of every site.
 *  - {@link buildSiteSearchIndex} — **one site's own** rows, emitted at
 *    `/network/<id>/search-index.json`: its records, timeline, documents, meetings, places,
 *    people, exhibits, legal, and reference. Loaded alongside the network shard when the reader is
 *    standing on that site, and all of them together when they ask for network scope.
 *
 * Which sites get a shard is **route emission, not switchability** (#1907) — see
 * {@link searchShardRefs}. Sharding on `selectable` was the accident that left Findlay's held
 * `flagpole` walk unfindable from anywhere, including from Findlay.
 *
 * Two rules the split exists to enforce, both of them #1886's finding carried into a new surface:
 *
 *  1. **A site's shard is gated by `facetAvailable`.** A locked facet renders a lock page, so
 *     indexing its rows would deep-link a reader into an ask-for-a-source screen; worse, a facet
 *     that locks *because the content isn't this site's* is exactly the borrowed record the
 *     gate exists to stop. The index reads the gate rather than re-deciding.
 *  2. **No row in a site's shard may point outside that site's base.** `siteUrl()` — the
 *     Lima-pinned convenience — is deliberately not imported here; every per-site URL is built
 *     from `siteBase(slug)`. `search.test.ts` asserts both.
 *
 * The emitted JSON is consumed by the dependency-free client matcher in `scripts/searchEngine.ts`
 * — no lunr, no CDN. What each shard covers, and what is deliberately left out, is declared in
 * `searchCoverage.ts` and asserted against the built routes by `scripts/check-routes.mjs`.
 */
import { hasFeed, loadFeed, runWithSite } from "./bundle";
import { containerOf, folderPathOf, summarizeCollections } from "./docBrowse";
import { docPermalinkForRel, documentId } from "./documentId";
import { isRoutableDoc } from "./docRouting";
import {
  evidenceKind,
  slugify,
  type CandidateItem,
  type ConceptItem,
  type DefenseContractors,
  type DocumentCollectionItem,
  type EconomicBaseline,
  type ExhibitItem,
  type LeiInventory,
  type MeetingItem,
  type PersonItem,
  type PlaceItem,
  type RecordItem,
  type TimelineEntry,
} from "./feeds";
import { blob } from "./format";
import { scopedLegal } from "./legal";
import { DOMAINS } from "./methodology";
import { LENS_ORDER, LENSES } from "./lenses";
import {
  contextualLeaves,
  getSection,
  networkTabs,
  platformLinks,
  sections,
  siteTabs,
  type NavItem,
} from "./nav";
import { NARRATIVE } from "./narrative";
import { networkEntities } from "./networkEntities";
import { facetAvailable, facetOffered, RECORD_FACETS, sectionStatus, type RecordFacet } from "./readiness";
import { scopedReference } from "./reference";
import { REPORT_PAGES } from "./reports";
import { groupLabel } from "./records";
import { LIMA_SLUG, siteBase, walkBase } from "./routes";
import { comingSoonWalks, SITES, siteBadge, siteForSlug, siteState, type NetworkSite } from "./sites";
import { STUDY_CHAPTERS, studyHref } from "./study";
import { NETWORK_NOUNS } from "./taxonomy";
import type { TagKind } from "./teardown";

export interface SearchDoc {
  title: string;
  url: string;
  section: string;
  text: string;
  /** Short kind eyebrow for the result row (#307): Record, Entity, Concept, … */
  kind: string;
  /** A mono identifier shown on the row, when the thing carries a real one. */
  id?: string;
  /** Evidence dot — set only where the row carries a genuine evidence signal
   *  (records, via their citation). Absent rows show no dot — no fabricated tag. */
  tag?: TagKind;
  /**
   * The site whose record this row is drawn from. Set on every row of a per-site shard and on
   * NO row of the network shard, so a result rendered under network scope can say which
   * watershed point it came from and a merged index can be filtered back down (#1890).
   */
  site?: string;
}

/** One shard-shipping site's shard, as a page hands it to the client matcher. */
export interface SearchShardRef {
  slug: string;
  label: string;
  /** Root-absolute path to the shard, pre-deploy-base — the caller applies `withBase`. */
  path: string;
}

/**
 * Whether a site puts rows of its own on the network — the axis {@link searchShardRefs} shards on.
 *
 * **Route emission, not switchability** (#1907). `selectable` gates the site interior:
 * `selectableSitePaths` is the path source for every `network/[site]/…` route but the story's, so
 * a peer's record, timeline, documents and study genuinely do not exist and indexing them would
 * mint rows for pages the build never wrote. The story is the exception: its routes emit on story
 * REGISTRATION (#1466), so a peer can publish a walk it cannot yet be switched into — which
 * Findlay's `flagpole` does. Sharding on `selectable` made those routes reachable from the site's
 * own home and findable from nowhere; sharding on what a site actually publishes fixes it, and
 * keeps the list derived so promotion still costs no edit here.
 *
 * A **held** story is the only kind a peer can publish today, and `storyRows` is what it earns.
 * A peer that un-holds a walk without being promoted publishes real prose this predicate does not
 * claim; that is a deliberate loud failure, not a silent one — `check-routes.mjs` reports the
 * chapters as uncovered content routes and points at `searchCoverage.ts`, which is where the next
 * decision about what the network advertises belongs.
 */
function shipsOwnRows(site: NetworkSite): boolean {
  return site.selectable || comingSoonWalks(site.slug).length > 0;
}

/**
 * Where each shard-shipping site's shard lives. The chrome (`Header.astro`) and the full results
 * page both hand this to the client so the two can't disagree about what "the network" contains,
 * and so a site promoted to `selectable` becomes searchable with no edit here.
 */
export function searchShardRefs(): SearchShardRef[] {
  return SITES.filter(shipsOwnRows).map((s) => ({
    slug: s.slug,
    label: s.place,
    path: `${siteBase(s.slug)}/search-index.json`,
  }));
}

/**
 * Every destination a nav item leads to, label and blurb intact.
 *
 * The standing rule this implements: **if the chrome navigates a reader somewhere, search can find
 * it.** Those pages — the environment and economy themes, the story's chapters, the study's — are
 * hand-authored `.astro` routes with no feed behind them, so nothing else in this module would
 * reach them, and before #1890 none of them were indexed. Reading the nav model instead of listing
 * routes here means a new theme page becomes searchable when it becomes reachable, which is the
 * only version of this that stays true.
 *
 * `navItemLinks` (the footer's flattener) is deliberately not reused: it takes a mega menu's tiles
 * only, and the study and story spines — 13 and 12 chapters — live in the spine beneath them.
 */
function navDestinations(items: NavItem[]): { label: string; href: string; blurb?: string }[] {
  const out: { label: string; href: string; blurb?: string }[] = [];
  for (const item of items) {
    if (item.kind === "link") {
      out.push({ label: item.label, href: item.href });
    } else if (item.kind === "dropdown") {
      for (const c of item.children) if (!("divider" in c)) out.push(c);
    } else {
      out.push(...item.mega.tiles);
      out.push({ label: item.mega.spine.title, href: item.mega.spine.href, blurb: item.mega.spine.blurb });
      out.push({ label: "Contents", href: item.mega.spine.tocHref });
      out.push(...item.mega.spine.items);
    }
  }
  return out;
}

// --- The network-global shard ----------------------------------------------

/**
 * Content that exists **once** for the whole network: the root sections, the site directory, the
 * long-form prose, and the wiki nouns `taxonomy.ts` declares network-global.
 *
 * A note on where the wiki rows come from. This index has to point at pages that exist, so it reads
 * from the same place each page is minted from, explicitly — never from an ambient default.
 * **Entities** come from the network union (`networkEntities`, #1906), which is what closed the
 * gap this comment used to describe: the wiki once built from the reference bundle alone, so a
 * party carried only by a peer had no page to be found on and was deliberately left unindexed
 * rather than given a URL that would 404 with a good snippet. The **glossary** and the curated
 * inventories still read the canonical build, because those pages genuinely build once.
 */
export function buildNetworkSearchIndex(): SearchDoc[] {
  const docs: SearchDoc[] = [];

  // Section landings + their TOC areas. Only the network-global ones: a per-site section belongs
  // to that site's shard, where it is gated on that site's readiness (a locked section renders a
  // lock, which is not a search result). `sections()` marks the difference in the href it builds —
  // a site section is rooted at `siteBase(activeSite())`, a global one at `/`.
  for (const s of sections()) {
    if (s.href.startsWith("/network/")) continue;
    docs.push({ title: s.label, url: s.href, section: s.label, text: s.blurb, kind: "Section" });
    for (const t of s.toc) {
      docs.push({
        title: `${t.label} — ${s.label}`,
        url: `${s.href}#${t.anchor}`,
        section: s.label,
        text: `${t.label} ${s.blurb}`,
        kind: "Section",
      });
    }
  }

  // The network's own sites (#1888) — the canonical index, plus one entry per REGISTERED site.
  // Off the registry, not the bundle, so a site is findable the moment it's registered and a
  // reader searching a place name lands on that site instead of on whichever page happens to
  // mention it. This is the one place a non-selectable site appears in search: its `/network/<slug>`
  // watch page is real, and it is the honest destination for "is anyone looking at Defiance?".
  const network = getSection("directory").label;
  docs.push({
    title: "The network — every site",
    url: "/network",
    section: network,
    text: blob(
      "network index directory every registered watershed point site",
      `${SITES.length} sites`,
      ...SITES.map((s) => s.place),
    ),
    kind: "Section",
  });
  for (const site of SITES) {
    docs.push({
      title: site.place,
      url: site.href,
      section: network,
      text: blob(site.basin, site.county, site.codename, site.mono, siteState(site.slug)),
      kind: "Site",
      id: siteBadge(site),
    });
  }

  // Migrated narrative prose (#69) — by title + blurb. Network-global at the root (#1304), so a
  // plain `/docs/<slug>` path (like the `/wiki/...` entries), not a site-rooted one.
  for (const d of NARRATIVE) {
    docs.push({
      title: d.title,
      url: `/docs/${d.slug}`,
      section: getSection(d.section).label,
      text: d.blurb,
      kind: "Doc",
    });
  }

  // The canonical index page for each network-global noun (`/wiki/entities/`, `/wiki/concepts/`,
  // `/wiki/hypotheses/`) — declared once in the taxonomy (#1892), so search points at the same
  // canonical the nav and the hub pages do.
  for (const noun of NETWORK_NOUNS) {
    docs.push({
      title: noun.label,
      url: noun.index,
      section: getSection("wiki").label,
      text: blob(noun.note),
      kind: "Section",
    });
  }

  // The methodology's per-domain pages (#1130) — how each kind of evidence in the corpus is read.
  // A reader searching "SSURGO" or "parcel" wants the method as readily as the data.
  for (const domain of DOMAINS) {
    docs.push({
      title: `${domain.label} — Methodology`,
      url: `/methodology/${domain.slug}/`,
      section: getSection("about").label,
      text: blob(domain.method, ...domain.dataSources, ...domain.sections.map((s) => s.heading)),
      kind: "Method",
    });
  }

  // Every destination the network chrome navigates to: /about/*, /methodology, /basin, the
  // research hypotheses, Connect. Hand-authored pages with no feed behind them, and unreachable by
  // search until now.
  //
  // What "belongs to a site" means here is asked of the registry rather than of the string (#1908).
  // The old test was `startsWith("/network/")`, which is true of every site-rooted href AND of
  // `/network/connect` — the one network-global page that happens to live under that prefix. So
  // Connect was carried by the chrome (the Research dropdown, the footer) and dropped by this walk,
  // and the site shards skip it too because it isn't under any site's base. It was findable from
  // nowhere while being linked from two places, which no rule stated and nothing would have caught.
  const siteRoots = SITES.map((s) => `${siteBase(s.slug)}/`);
  const seen = new Set(docs.map((d) => d.url));
  for (const dest of navDestinations([...networkTabs(), ...platformLinks().map(toNavLink)])) {
    if (siteRoots.some((r) => dest.href.startsWith(r)) || seen.has(dest.href)) continue;
    seen.add(dest.href);
    docs.push({
      title: dest.label,
      url: dest.href,
      section: getSection("directory").label,
      text: blob(dest.blurb),
      kind: "Page",
    });
  }

  docs.push(...wikiRows());
  return docs;
}

/** A platform link as a nav item, so both feed one flattener. */
function toNavLink(l: { label: string; section: string; href: string }): NavItem {
  return { kind: "link", label: l.label, section: l.section as NavItem["section"], href: l.href };
}

/**
 * The wiki nouns + the curated-entity pages — network-global routes.
 *
 * The entity rows come from the **network union** (`networkEntities`, #1906), the same reader the
 * pages are minted from, so every party that has a page is findable and nothing is minted for one
 * that doesn't. The rest still read the canonical build explicitly: the glossary and the curated
 * inventories (`lei`, `candidates`, `defense-contractors`) are single-bundle pages by design.
 */
function wikiRows(): SearchDoc[] {
  const docs: SearchDoc[] = [];
  const WIKI = "Wiki";

  for (const e of networkEntities()) {
    docs.push({
      title: e.node.display,
      url: `/wiki/entities/${e.slug}/`,
      section: WIKI,
      // The places are in the row's text so "Fort Wayne Dana" finds the party the peer carries —
      // the cross-site view is the reason the graph is network-global.
      text: blob(
        e.node.kind,
        e.node.classification,
        ...e.node.variants,
        ...Object.keys(e.node.roles ?? {}),
        ...e.sites.map((s) => siteForSlug(s)?.place ?? s),
      ),
      kind: "Entity",
    });
  }

  return runWithSite(LIMA_SLUG, () => {
    if (hasFeed("concepts")) {
      for (const c of loadFeed<ConceptItem[]>("concepts")) {
        docs.push({
          title: c.title,
          url: `/wiki/concepts/${c.slug}/`,
          section: WIKI,
          text: blob(c.summary, ...c.aliases, ...c.tags, c.body),
          kind: "Concept",
        });
      }
    }

    // Curated-entity pages (Pages cutover #103) — one entry per page, not per row.
    if (hasFeed("candidates")) {
      const rows = loadFeed<CandidateItem[]>("candidates");
      docs.push({
        title: "Cloud-consumer candidates",
        url: "/wiki/candidates",
        section: WIKI,
        text: blob("cloud-consumer demand-fit candidates", ...rows.map((c) => c.name)),
        kind: "Wiki",
      });
    }
    if (hasFeed("defense-contractors")) {
      const dc = loadFeed<DefenseContractors>("defense-contractors");
      docs.push({
        title: "Defense contractors",
        url: "/wiki/defense-contractors",
        section: WIKI,
        text: blob("DoD prime contractor pattern matches", ...dc.contractors.map((c) => c.name)),
        kind: "Wiki",
      });
    }
    if (hasFeed("lei")) {
      const lei = loadFeed<LeiInventory>("lei");
      docs.push({
        title: "Entity LEIs (GLEIF)",
        url: "/wiki/lei",
        section: WIKI,
        text: blob("GLEIF legal entity identifiers", ...lei.records.map((r) => r.legal_name)),
        kind: "Wiki",
      });
    }
    return docs;
  });
}

// --- The per-site shard ----------------------------------------------------

/**
 * A site's **held** stories, one row each (#1907).
 *
 * A held story (`comingSoon`, #1526) is *advertised, not readable*: its site home renders a teaser
 * and every one of its routes — the on-ramp, the table of contents, each chapter — serves the same
 * `StoryComingSoon` interstitial. Title, dek, "nothing in the walk is readable yet."
 *
 * So it earns exactly **one** row, at the story's own root, titled the way the page titles itself.
 * Eight rows for eight copies of one notice would be eight near-identical results, each promising
 * chapter prose that is deliberately held; the contents and chapter routes are declared
 * `represented` by this row in `searchCoverage.ts`, which is the verdict for content a reader
 * reaches through a row that IS indexed.
 *
 * The other two story states need nothing here. A **readable** story's chapters are separate
 * destinations and the nav spine already reaches them (`navDestinations(siteTabs())`, below). A
 * **`hidden`** one (#1256) is "reachable by direct URL, just not advertised" — precisely what a
 * search row would undo.
 */
function storyRows(site: NetworkSite): SearchDoc[] {
  const held = comingSoonWalks(site.slug);
  if (held.length === 0) return [];
  const section = getSection("story").label;
  return held.map((ref) => ({
    title: `${ref.title} — coming soon`,
    url: `${walkBase(site.slug, ref.codename)}/`,
    section,
    text: blob("the story, a guided walk, coming soon — held while it is finished", ref.dek),
    kind: "Walk",
    site: site.slug,
  }));
}

/**
 * One site's own searchable rows. Every URL is rooted at `siteBase(slug)`, every facet is gated by
 * `facetAvailable`, and every row carries `site: slug`.
 *
 * Run inside `runWithSite` so the feed reads and `sections()` resolve against this site's bundle
 * rather than the ambient default — the same discipline the per-site page renders use.
 */
export function buildSiteSearchIndex(slug: string): SearchDoc[] {
  return runWithSite(slug, () => {
    const base = siteBase(slug);
    const site = siteForSlug(slug);
    const docs: SearchDoc[] = site ? storyRows(site) : [];
    const at = (path: string): string => `${base}${path}`;
    const push = (d: Omit<SearchDoc, "site">): void => {
      docs.push({ ...d, site: slug });
    };

    // A peer's shard stops at its stories, because that is all a peer publishes (#1907). Every
    // other `network/[site]/…` route — the record, the timeline, the documents, the study, the
    // reports — comes from `selectableSitePaths`, so for a non-selectable site none of it is
    // built. Everything below reads the site's BUNDLE, which a thin peer may well have; a bundle
    // is not a page, and a row for a page that doesn't exist is a search result that 404s.
    if (!site?.selectable) return docs;

    const RECORD = "The record";

    // This site's section landings, each gated on its own readiness. A locked section renders the
    // lock + the ask, so it is not a destination; `sections()` is read inside `runWithSite`, so the
    // hrefs are already this site's.
    //
    // Their URLs are remembered because a few record facets share a route with a section — the
    // `timeline` facet's route IS the timeline section's landing — and two rows for one destination
    // is a duplicate in the reader's result list, not two results.
    const sectionUrls = new Set<string>();
    for (const s of sections()) {
      if (!s.href.startsWith(`${base}/`) && s.href !== base) continue;
      if (sectionLocked(slug, s.id)) continue;
      sectionUrls.add(s.href);
      push({ title: s.label, url: s.href, section: s.label, text: s.blurb, kind: "Section" });
      for (const t of s.toc) {
        push({
          title: `${t.label} — ${s.label}`,
          url: `${s.href}#${t.anchor}`,
          section: s.label,
          text: `${t.label} ${s.blurb}`,
          kind: "Section",
        });
      }
    }

    if (facetAvailable(slug, "records")) {
      const records = loadFeed<RecordItem[]>("records");
      for (const r of records) {
        const instrument = r.fields?.instrument_no;
        push({
          title: r.title,
          // The record's OWN leaf (`/site/records/<group>/<id>`), not its group index. A result
          // that lands on a 23-row index and leaves the reader to spot the row is a near miss;
          // the leaf is where the record block and its citation actually are.
          url: at(`/site/records/${r.group}/${slugify(r.rel)}/`),
          section: RECORD,
          text: blob(r.group, r.confidence, ...r.warnings, String(instrument ?? "")),
          kind: "Record",
          // Records carry a real per-row evidence signal — its citation's verified flag.
          tag: evidenceKind(r.citation),
          id: instrument ? String(instrument) : undefined,
        });
      }
      // …and the group indexes themselves, which is where "all the deeds" wants to land.
      for (const group of [...new Set(records.map((r) => r.group))]) {
        push({
          title: groupLabel(group),
          url: at(`/site/records/${group}/`),
          section: RECORD,
          text: blob("record group", `${records.filter((r) => r.group === group).length} records`),
          kind: "Records",
        });
      }
    }

    if (facetAvailable(slug, "timeline")) {
      for (const e of loadFeed<TimelineEntry[]>("timeline")) {
        push({
          title: `${e.date} — ${e.title}`,
          url: at("/timeline"),
          section: RECORD,
          text: blob(e.category, e.detail, e.source, ...e.parties),
          kind: "Timeline",
        });
      }
    }

    if (facetAvailable(slug, "documents")) {
      docs.push(...documentRows(slug, loadFeed<DocumentCollectionItem[]>("documents")));
    }

    // Meeting summaries render as a section OF the legal-history index (`/site/legal#meetings`),
    // so they are reachable only while that facet is open. A site with meetings and no legal
    // documents of its own would have nowhere to send a reader — `searchCoverage.ts` records that
    // as a known unindexable, rather than this quietly emitting a link into a lock page.
    if (facetAvailable(slug, "legal") && hasFeed("meetings")) {
      for (const m of loadFeed<MeetingItem[]>("meetings")) {
        push({
          title: `${m.date} — ${m.kind}`,
          url: at("/site/legal#meetings"),
          section: RECORD,
          text: blob(m.summary),
          kind: "Meeting",
          id: m.slug,
        });
      }
    }

    if (facetAvailable(slug, "places")) {
      for (const p of loadFeed<PlaceItem[]>("places")) {
        push({
          title: p.name,
          url: at(`/site/places/${p.slug}/`),
          section: RECORD,
          text: blob(p.kind, ...p.aliases, ...p.tags, p.body),
          kind: "Place",
        });
      }
    }

    if (facetAvailable(slug, "people")) {
      for (const p of loadFeed<PersonItem[]>("people")) {
        push({
          title: p.name,
          url: at(`/site/people/${p.slug}/`),
          section: RECORD,
          text: blob(...p.aliases, ...p.roles, ...p.affiliations, p.summary),
          kind: "Person",
        });
      }
    }

    // Exhibits share one page, so each row deep-links to its own anchor on it.
    if (facetAvailable(slug, "exhibits")) {
      for (const e of loadFeed<ExhibitItem[]>("exhibits")) {
        push({
          title: e.title,
          url: at(`/site/exhibits#${e.slug}`),
          section: RECORD,
          text: blob(e.caption, e.source, e.pages),
          kind: "Exhibit",
        });
      }
    }

    // Legal-history docs (Pages cutover #105), scoped to this site's corpus (#1886) — by title +
    // group + blurb.
    if (facetAvailable(slug, "legal")) {
      for (const d of scopedLegal(slug)) {
        push({
          title: d.title,
          url: at(`/site/legal/${d.slug}`),
          section: RECORD,
          text: blob(d.group, d.blurb),
          kind: "Legal",
        });
      }
    }

    // Reference datasets (Pages cutover #104), scoped through the catalog seam (#1260).
    if (facetAvailable(slug, "reference")) {
      for (const d of scopedReference(slug)) {
        push({
          title: d.title,
          url: at(`/site/reference/${d.slug}`),
          section: RECORD,
          text: blob("reference data", d.blurb),
          kind: "Reference",
        });
      }
    }

    if (hasFeed("economics-baseline")) {
      const eb = loadFeed<EconomicBaseline>("economics-baseline");
      push({
        title: "Economics — localized baseline",
        url: at("/economy/economics-baseline"),
        // Economic ground, filed under the economy section — and since #1893 the route agrees
        // (it lived under /environment/ from #1323 until then).
        section: getSection("economy").label,
        text: blob("BLS QCEW Census employment population baseline", eb.area_name, eb.note),
        kind: "Dataset",
      });
    }

    // The record facets' own landings — the door to each leaf, gated the same way the leaf is.
    //
    // Skipped where the section walk above already claimed the route: `timeline`'s facet route is
    // the timeline section's landing, so emitting both listed one page twice in every result set
    // that matched it. The section row wins because it carries the section's blurb. (If the section
    // is locked but the facet is open, the section row was never pushed and the facet supplies the
    // destination — which is why this checks the URL rather than special-casing the facet.)
    for (const facet of Object.keys(RECORD_FACETS) as RecordFacet[]) {
      if (!facetAvailable(slug, facet)) continue;
      if (sectionUrls.has(at(RECORD_FACETS[facet].route))) continue;
      const d = RECORD_FACETS[facet];
      push({
        title: d.label,
        url: at(d.route),
        section: RECORD,
        text: blob(d.note),
        kind: "Section",
      });
    }

    // The impact study's chapters. Every selectable site builds all fifteen — a chapter with no
    // data is not a lock, it is the study *naming the gap*, which is the artifact's whole point
    // (`STUDY_CHAPTERS`, the missing-impact-study epic). So all of them are destinations.
    for (const c of STUDY_CHAPTERS) {
      push({
        title: c.title,
        url: studyHref(slug, c.id),
        section: getSection("study").label,
        text: blob(c.dek, c.part),
        kind: "Study",
      });
    }

    // The reports' companion pages. Off `REPORT_PAGES`, not `INTERACTIVE_REPORTS`: the latter is
    // the ESSAY registry, and the capstone (`public-balance-sheet`) and the cost scenario have no
    // essay behind them, so asking it for the route list silently drops two of the seven.
    if (sectionStatus(slug, "reports") !== "locked") {
      for (const r of REPORT_PAGES) {
        push({
          title: r.label,
          url: at(`/reports/${r.slug}`),
          section: getSection("reports").label,
          text: blob("report", r.label),
          kind: "Report",
        });
      }
    }

    // Everything else the site chrome navigates to: the five lens landings, the reports' companion
    // pages, the story's chapters. Hand-authored routes with no feed behind them — see
    // `navDestinations`. Read inside `runWithSite`, so `siteTabs()` is already this site's.
    const seen = new Set(docs.map((d) => d.url));
    const push_ = (label: string, href: string, text: string): void => {
      if (!href.startsWith(`${base}/`) || seen.has(href)) return;
      seen.add(href);
      push({ title: label, url: href, section: getSection("site").label, text: blob(text), kind: "Page" });
    };
    for (const dest of navDestinations(siteTabs())) push_(dest.label, dest.href, dest.blurb ?? "");

    // The lens FACETS (#1915). These twelve `/environment/*` and `/economy/*` leaves used to reach
    // the index through the Reference dropdown that listed them; the Lenses tab carries five
    // landings instead, and the leaves are reached from the landing bodies. The standing rule is
    // "if the chrome navigates a reader somewhere, search can find it" — a landing is chrome, so
    // reading the lens model here is the same move as reading the nav model above, not an
    // exception to it. Anchored facets (`…#consumer-energy`) resolve to their page, which is
    // already indexed under its own label, so `seen` drops them.
    //
    // Gated on `facetOffered` (#1908), which is the half this walk originally left out. The rule is
    // "whatever the chrome navigates to" — and a landing that withholds a door is not navigating
    // anywhere. Ungated, this indexed nineteen leaves no landing offered: `/environment/thermal` on
    // a site with no thermal feed, every `/environment/enclave`, and the record facets sitting
    // behind their own locks. A row for a lock is a search result that promises somewhere to land
    // and delivers the ask instead. The leaf ROUTES now carry the same gate (`offeredFacetPaths`),
    // so for the feed-gated ones there is no longer a page here to index either.
    for (const id of LENS_ORDER) {
      const lens = LENSES[id];
      for (const f of lens.facets) {
        if (f.route.includes("#") || !facetOffered(slug, f)) continue;
        push_(f.label, `${base}${f.route}`, `${f.blurb} ${lens.name} ${lens.question}`);
      }
    }

    // The site's declared contextual leaves (#1908) — real content the chrome deliberately doesn't
    // carry, reached from another page's body copy. Not being in the menu is a wayfinding decision;
    // it was never a reason to be unfindable, and before this the two were the same thing. A leaf
    // that declares itself `represented` is skipped: the row it names is already here.
    for (const leaf of contextualLeaves()) {
      if (leaf.represented) continue;
      push_(leaf.label, leaf.href, `${leaf.blurb} ${leaf.via}`);
    }

    return docs;
  });
}

/**
 * The document layer (#1890, over #1887's addressing) — the 87% of the build that was unsearchable.
 *
 * One row per **routable** source document, addressed by its stable handle rather than its
 * as-received path: `/network/<id>/doc/<handle>/`. Two things follow from using the handle.
 *
 *  - The row is ~200 bytes instead of the ~1 KB a 16-segment path cost, which is why all 3,247 of
 *    Lima's documents fit in a shard that compresses to ~32 KB on the wire. The as-received folder
 *    trail is not discarded — it goes into the searchable `text`, where a reader looking for
 *    "Shawnee force main" finds the file even though no segment of the URL says so.
 *  - Non-routable entries (Windows thumbnail caches, the sidecars Office writes beside a
 *    save-as-web-page) are excluded, because `docRouting` gives them no page. They stay in the
 *    corpus and stay listed in their production's manifest; a search result is a promise that
 *    there is somewhere to land.
 *
 * Collection landings are indexed too — a reader searching "sanitary" wants the production's front
 * door as readily as one file inside it.
 */
function documentRows(slug: string, collections: DocumentCollectionItem[]): SearchDoc[] {
  const base = siteBase(slug);
  const rows: SearchDoc[] = [];
  const summaries = new Map(summarizeCollections(collections).map((s) => [s.slug, s]));
  for (const c of collections) {
    rows.push({
      title: c.title,
      url: `${base}/site/documents/${c.slug}/`,
      section: "The record",
      text: blob(c.description, `${c.entries.length} documents`),
      kind: "Collection",
      site: slug,
    });
    // Each production's own front door (`<collection>/<container>`) — the level #1887 cut the
    // routes at, and the one a reader means by "the mandamus production". Its paginated pages are
    // deliberately not indexed: `page-2` holds no content its landing doesn't reach.
    for (const container of summaries.get(c.slug)?.containers ?? []) {
      rows.push({
        title: `${container.slug} — ${c.title}`,
        url: `${base}/site/documents/${c.slug}/${container.slug}/`,
        section: "The record",
        text: blob(
          c.title,
          container.slug,
          `${container.count} documents`,
          container.folders > 0 ? `${container.folders} folders` : null,
        ),
        kind: "Production",
        site: slug,
      });
    }
    for (const entry of c.entries) {
      if (!isRoutableDoc(entry)) continue;
      rows.push({
        title: entry.name,
        url: `${base}${docPermalinkForRel(entry.rel)}`,
        section: "The record",
        // The provenance the permalink no longer carries: which production it came out of, and
        // the custodian's own folder trail beneath it. This is what makes a document findable by
        // where it sat rather than only by what it was named.
        text: blob(c.title, containerOf(entry.rel), ...folderPathOf(entry.rel), entry.suffix),
        kind: "Document",
        id: documentId(entry.rel),
        site: slug,
      });
    }
  }
  return rows;
}

/**
 * Whether a nav section is locked for a site. The two vocabularies differ by design — `nav.ts`
 * names content areas, `readiness.ts` names gateable domains — so the overlap is stated here
 * rather than assumed. A section with no readiness peer (`home`, `study`) is never locked: it
 * renders from the site's own bundle whatever the domains say.
 */
function sectionLocked(slug: string, id: string): boolean {
  const gated: Record<string, Parameters<typeof sectionStatus>[1]> = {
    leads: "leads",
    contacts: "contacts",
    story: "story",
    timeline: "timeline",
    reports: "reports",
    site: "record",
    environment: "environment",
    economy: "economy",
  };
  const section = gated[id];
  return section !== undefined && sectionStatus(slug, section) === "locked";
}
