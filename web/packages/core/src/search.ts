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
  type EntityNode,
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
import { getSection, networkTabs, platformLinks, sections, siteTabs, type NavItem } from "./nav";
import { NARRATIVE } from "./narrative";
import { facetAvailable, RECORD_FACETS, sectionStatus, type RecordFacet } from "./readiness";
import { scopedReference } from "./reference";
import { REPORT_PAGES } from "./reports";
import { groupLabel } from "./records";
import { LIMA_SLUG, siteBase } from "./routes";
import { SITES, siteBadge, siteState } from "./sites";
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

/** One selectable site's shard, as a page hands it to the client matcher. */
export interface SearchShardRef {
  slug: string;
  label: string;
  /** Root-absolute path to the shard, pre-deploy-base — the caller applies `withBase`. */
  path: string;
}

/**
 * Where each selectable site's shard lives. The chrome (`Header.astro`) and the full results page
 * both hand this to the client so the two can't disagree about what "the network" contains, and so
 * a site promoted to `selectable` becomes searchable with no edit here.
 */
export function searchShardRefs(): SearchShardRef[] {
  return SITES.filter((s) => s.selectable).map((s) => ({
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
 * A note on where the wiki rows come from. The canonical wiki build renders **Lima's** bundle —
 * `getStaticPaths` in `pages/wiki/**` runs outside `runWithSite`, so `activeSite()` is Lima — and
 * this index has to point at pages that exist. It therefore reads Lima's feeds *explicitly*, with
 * the coupling named rather than inherited from an ambient default. The consequence is real and
 * recorded in `searchCoverage.ts`: a peer's entity that never reaches Lima's feed has no wiki page
 * to be found on, so it is not indexed. That is a taxonomy gap (the edge `taxonomy.ts` documents),
 * not a search one — the fix is to widen the wiki build, and inventing a URL here would only
 * produce a 404 with a good snippet.
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
  // research lenses, Connect. Hand-authored pages with no feed behind them, and unreachable by
  // search until now.
  const seen = new Set(docs.map((d) => d.url));
  for (const dest of navDestinations([...networkTabs(), ...platformLinks().map(toNavLink)])) {
    if (dest.href.startsWith("/network/") || seen.has(dest.href)) continue;
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

/** The wiki nouns + the curated-entity pages, all of them network-global routes off Lima's bundle. */
function wikiRows(): SearchDoc[] {
  return runWithSite(LIMA_SLUG, () => {
    const docs: SearchDoc[] = [];
    const WIKI = "Wiki";

    if (hasFeed("entities")) {
      for (const e of loadFeed<EntityNode[]>("entities")) {
        docs.push({
          title: e.display,
          url: `/wiki/entities/${slugify(e.key)}/`,
          section: WIKI,
          text: blob(e.kind, e.classification, ...e.variants, ...Object.keys(e.roles ?? {})),
          kind: "Entity",
        });
      }
    }

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
 * One site's own searchable rows. Every URL is rooted at `siteBase(slug)`, every facet is gated by
 * `facetAvailable`, and every row carries `site: slug`.
 *
 * Run inside `runWithSite` so the feed reads and `sections()` resolve against this site's bundle
 * rather than the ambient default — the same discipline the per-site page renders use.
 */
export function buildSiteSearchIndex(slug: string): SearchDoc[] {
  return runWithSite(slug, () => {
    const base = siteBase(slug);
    const docs: SearchDoc[] = [];
    const at = (path: string): string => `${base}${path}`;
    const push = (d: Omit<SearchDoc, "site">): void => {
      docs.push({ ...d, site: slug });
    };

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
        url: at("/environment/economics-baseline"),
        // Economic ground, so it's filed under the economy section even though the route still
        // lives under /environment/ (#1323).
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

    // The impact study's chapters. Every selectable site builds all thirteen — a chapter with no
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

    // Everything else the site chrome navigates to: the environment and economy themes, the
    // reports' companion pages, the story's chapters. Hand-authored routes with no feed behind
    // them — see `navDestinations`. Read inside `runWithSite`, so `siteTabs()` is already this
    // site's, and already collapsed to a landing link wherever a section is locked.
    const seen = new Set(docs.map((d) => d.url));
    for (const dest of navDestinations(siteTabs())) {
      if (!dest.href.startsWith(`${base}/`) || seen.has(dest.href)) continue;
      seen.add(dest.href);
      push({
        title: dest.label,
        url: dest.href,
        section: getSection("site").label,
        text: blob(dest.blurb),
        kind: "Page",
      });
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
