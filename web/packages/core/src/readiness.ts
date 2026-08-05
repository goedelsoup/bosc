/**
 * Per-site readiness — the gating engine for a network site, driven by **domain activation**
 * (#1220 / #1223).
 *
 * The network is *additive*: a site is defined by the **domains that actually have a story
 * there**, not by its deficits against Lima's full section taxonomy. Readiness is computed **in
 * Python at export** (`bosc.site.readiness`) and written into the bundle `manifest.json` as a
 * `readiness` block (five domains × `absent|seeded|live`, plus a derived `tier`). This module reads
 * that block — it is the SSOT for the site-level gating and the chrome tier, and there is no
 * "reference site ⇒ everything available" shortcut: Lima renders as available because its manifest
 * says every domain is `live`, not because it is special-cased.
 *
 * Sections gate in two bands:
 *   - **Primary sections** (`record` / `places` / `environment` / `economy`) read their parent
 *     **domain** state from the manifest block — a domain with any evidence (`seeded` or `live`)
 *     opens them. This is what lets a Backdrop-tier peer (floor data only) render a real environment +
 *     economy page instead of a wall of locks.
 *   - **Leaf facets** (`timeline` / `people` / `exhibits` / `story` / `leads`) additionally require
 *     their own feed/registry signal, so an active domain never opens an *empty* facet page (a
 *     timeline with no events reads as a lock + needs-board ask, not a barren page).
 * `reports` is a site-tier section (its nav home is the "The site" mega-menu, #1305 reverted), but
 * the analysis it hosts exists only on the reference build for now, so it stays reference-only
 * (`isReferenceSite`, the surviving network-global-host role, #1220) — a peer's Reports index shows
 * the lock until its corpus supports the read; `environment` also locks when the facility's cooling
 * method is undisclosed (#1057).
 *
 * Below the sections sits a third band, the **record facets** (`RECORD_FACETS` / `facetStatus`,
 * #1886): the leaf pages under The Record, each declaring what its content is scoped to
 * (`per-site` vs `network-global`) and what must be true of this site before it opens. That
 * declaration is the module's record of the `concepts` decision, and the property `facets.test.ts`
 * enforces — no two sites may serve identical non-empty content at the same facet route unless the
 * facet says outright that it is network-global.
 *
 * Above all three sits a fourth, purely *derived* band: `lensStatus` (#1913), which composes the
 * two gates for the five Lenses declared in `lenses.ts`. It reads them; it does not change them.
 */
import { hasFeed, loadFeed, loadManifest } from "./bundle";
import type { DomainState, Readiness, SiteTier } from "./bundle";
import type { ScenarioResult } from "./feeds";
import { LENSES, type LensFacet, type LensId } from "./lenses";
import { scopedLegal } from "./legal";
import { scopedReference } from "./reference";
import { LIMA_SLUG } from "./routes";
import { selectableSitePaths, surfacedStories } from "./sites";

export type { DomainState, SiteTier } from "./bundle";

/** The five activation domains (`bosc.site.readiness.Domain`). */
/** The five readiness domains. `inquiry` was `story` until #1971 (epic #1968): its predicate was
 *  a registered MDX walk plus a leads feed — the only domain whose signal was authored prose — and
 *  it now reads the site's own `impact-study` verdicts. It is REPORTED, never a tier gate. */
export type Domain = "backdrop" | "facility" | "places" | "record" | "inquiry";

/**
 * The live reference build (Lima) hosts the network-global content — the `docs/` narrative that
 * the `reports` section reads, the cross-site hypothesis matrix, the whole-data-tier catalog. This
 * is the **network-global-host role** (the peer of `bosc.sites.is_reference_site`), NOT a readiness
 * backdoor: it no longer forces every section available (#1220). Only `reports` still keys off it.
 */
export function isReferenceSite(slug: string): boolean {
  return slug === LIMA_SLUG;
}

export type SectionStatus = "available" | "locked";

/** A gateable site section — a top-level destination under `/network/<site>`. */
export type ReadinessSection =
  | "record"
  | "timeline"
  | "people"
  | "places"
  | "exhibits"
  | "legal"
  | "environment"
  | "economy"
  | "reports"
  | "story"
  | "leads"
  | "contacts";

/** Display + lock copy for each section. `holds` answers "what lands here once we have sources"
 *  — shown on the lock so an empty section reads as *awaiting a source*, not broken or barren. */
export const SECTION_META: Record<ReadinessSection, { label: string; holds: string }> = {
  record: {
    label: "The record",
    holds: "the source documents, structured records, and the entities drawn from them",
  },
  timeline: {
    label: "Timeline",
    holds: "the dated events reconstructed from the record — permits, filings, meetings",
  },
  people: {
    label: "People",
    holds: "the actors named in the record, each tied back to the documents that name them",
  },
  places: {
    label: "Places",
    holds: "the parcels, facilities, and waters the record locates",
  },
  exhibits: {
    label: "Exhibits",
    holds: "the curated source exhibits — the documents that carry the keystone figures",
  },
  legal: {
    label: "Legal history",
    holds:
      "a governance and litigation record of its own — the filings, hearing transcripts, records-access analyses, and audits its corpus carries",
  },
  environment: {
    label: "The environment",
    holds:
      "the hydrology, imagery, air-dispersion, and toxics-release picture for the receiving water and air",
  },
  economy: {
    label: "Economy",
    holds: "the load, grid, and economic-baseline reads for the site",
  },
  reports: {
    label: "Reports",
    holds: "the long-form analysis built over the corpus, once the corpus supports it",
  },
  story: {
    label: "The story",
    holds: "the guided walk that teaches the record one document at a time",
  },
  leads: {
    label: "Open leads",
    holds: "the open questions and the source data we're seeking for this site",
  },
  contacts: {
    label: "Contacts",
    holds:
      "the people and bodies to reach on this site — the officials, organizers, and groups the record names",
  },
};

/** All-absent readiness — the safe fallback when a bundle predates the `readiness` block (contract
 *  < 1.17.0) or a synthetic fixture omits it: sections lock (degrade), nothing crashes. */
const ABSENT_READINESS: Readiness = {
  tier: "stub",
  domains: { backdrop: "absent", facility: "absent", places: "absent", record: "absent", inquiry: "absent" },
};

/** The site's computed readiness block, read straight from its bundle manifest (#1220). */
export function siteReadinessBlock(slug: string): Readiness {
  return loadManifest(slug).readiness ?? ABSENT_READINESS;
}

/** The five domains' `absent|seeded|live` states for a site (the manifest block, domain axis). */
export function siteDomainStates(slug: string): Record<Domain, DomainState> {
  return siteReadinessBlock(slug).domains;
}

/** A site's readiness tier (`stub|backdrop|case|reference`) — the chrome/tab tier reads this. */
export function siteTier(slug: string): SiteTier {
  return siteReadinessBlock(slug).tier;
}

/** Count a feed's rows from the manifest (0 when the feed is absent). */
function feedCount(slug: string, name: string): number {
  return loadManifest(slug).feeds.find((f) => f.name === name)?.count ?? 0;
}

/**
 * Whether the site's water math rests on an **undisclosed cooling method** (#1057).
 *
 * A `hydrology-scenarios` row whose `cooling_model` is `unknown` (equivalently, whose basis
 * says `method_disclosed: false`) carries a bracketed range across candidate archetypes, not
 * an estimate — the facility exists but no record says how it rejects heat. Rendering its
 * single consumptive/7Q10-multiple headline as if confirmed would fabricate the site's most
 * load-bearing number, so the environment section locks and the needs board asks for the
 * disclosure instead. Content-based (reads feed rows), so it stands apart from the domain block.
 */
export function coolingMethodUndisclosed(slug: string): boolean {
  if (!hasFeed("hydrology-scenarios", slug)) return false;
  const rows = loadFeed<ScenarioResult[]>("hydrology-scenarios", slug);
  return rows.some(
    (r) =>
      (r.cooling_model ?? r.scenario.cooling_model) === "unknown" ||
      r.scenario.basis?.method_disclosed === false,
  );
}

/** A domain carries evidence (is worth opening its sections for) when it is `seeded` or `live`. */
export function domainPresent(slug: string, domain: Domain): boolean {
  return siteDomainStates(slug)[domain] !== "absent";
}

/** The facility domain's state (`absent | seeded | live`) for a site — the facility-output gate reads
 *  this directly so a `live → seeded` regression (a permit-grounded load decaying to a screening
 *  lead) is visible to users, not swallowed into the chrome tier alone (#1630). */
export function facilityState(slug: string): DomainState {
  return siteDomainStates(slug).facility;
}

/**
 * Whether the site's facility-load read (the campus load / demand-pressure content on the economy
 * hub) may render as grounded output — the facility domain is `live`, i.e. its IT load is
 * **instrument-grounded** (an air permit or a filed disclosure), not a screening [inference] or a
 * [reference] announcement (#1630). A `seeded` (screening-only) or `absent` facility fails this, so
 * the load door is withheld rather than presenting a screening bracket as a settled load. This is
 * the facility axis's peer of the domain gates above — the facility domain, not one economics feed,
 * drives it.
 */
export function facilityLoadAvailable(slug: string): boolean {
  return facilityState(slug) === "live";
}

/**
 * Whether a section has enough of *this site's* own data to stand on its own — the additive gate.
 * Primary sections read the manifest `readiness` block (their parent domain); leaf facets add a
 * feed/registry check so an active domain never opens an empty page. Deterministic per bundle.
 */
function hasEnough(section: ReadinessSection, slug: string): boolean {
  switch (section) {
    // --- primary sections: gated by their parent domain's activation state (the manifest block) ---
    case "record":
      return domainPresent(slug, "record");
    case "places":
      return domainPresent(slug, "places");
    case "economy":
      return domainPresent(slug, "backdrop");
    case "environment":
      // The floor's environment read (hydrology + toxics) opens with the backdrop domain — but an
      // undisclosed cooling method locks it outright (#1057): its scenario rows are bracketed
      // ranges, and no fabricated single-figure headline may stand in.
      return domainPresent(slug, "backdrop") && !coolingMethodUndisclosed(slug);
    // --- leaf facets: the domain plus the facet's own feed/registry signal (no empty pages) ---
    case "timeline":
      return domainPresent(slug, "record") && feedCount(slug, "timeline") > 0;
    case "people":
      return domainPresent(slug, "record") && feedCount(slug, "people") > 0;
    case "exhibits":
      return domainPresent(slug, "record") && feedCount(slug, "exhibits") > 0;
    case "legal":
      // The legal-history set has no bundle feed — it renders committed markdown out of
      // `data/extracted/` — so its "own signal" is the corpus-scope read (#1886): the site opens
      // the section only for the filings its OWN corpus carries, never the reference build's.
      return domainPresent(slug, "record") && scopedLegal(slug).length > 0;
    case "story":
      // The guided walk needs a *surfaced* (readable) walk — registered in the `sites.ts` overlay
      // and neither `hidden` (#1256) nor `comingSoon` (#1526). Since #1971 only Lima registers one
      // (the network's method demo; the other three were absorbed into their impact studies by
      // #1970), so this facet opens there and locks everywhere else — and a peer's narrative now
      // lives in its study, which never locks. Note this is the SECTION `story`, not the readiness
      // domain of that name: that domain is `inquiry` now, and nothing here reads it.
      return surfacedStories(slug).length > 0;
    case "leads":
      // The leads board is feed-driven per site (#796); the reference build also hosts the
      // network-global curated board.
      return feedCount(slug, "leads") > 0 || isReferenceSite(slug);
    case "contacts":
      // The contacts directory is purely feed-driven: a site opens it only once it ships its own
      // committed `contacts` feed — never borrowing another site's contacts.
      return feedCount(slug, "contacts") > 0;
    // --- network-global: the reference build hosts the long-form `docs/` narrative ---
    case "reports":
      return isReferenceSite(slug);
  }
}

/** A section's status for a site: `available` (render its real data) or `locked` (show the lock). */
export function sectionStatus(slug: string, section: ReadinessSection): SectionStatus {
  return hasEnough(section, slug) ? "available" : "locked";
}

/** Convenience: is this section ready to render for the site? */
export function isAvailable(slug: string, section: ReadinessSection): boolean {
  return sectionStatus(slug, section) === "available";
}

/** Every section's status for a site — the full readiness map (the model the pages + nav read). */
export function siteReadiness(slug: string): Record<ReadinessSection, SectionStatus> {
  const out = {} as Record<ReadinessSection, SectionStatus>;
  for (const section of Object.keys(SECTION_META) as ReadinessSection[]) {
    out[section] = sectionStatus(slug, section);
  }
  return out;
}

/** The sections currently locked for a site (empty for a site whose domains are all lit). */
export function lockedSections(slug: string): ReadinessSection[] {
  return (Object.keys(SECTION_META) as ReadinessSection[]).filter(
    (s) => sectionStatus(slug, s) === "locked" && !NEVER_A_NEED.has(s),
  );
}

/**
 * Sections that lock without being a **need** (#1971).
 *
 * The needs board asks a site for the source that would open a locked section. `story` stopped
 * being that kind of lock when epic #1968 retired the walk as a per-site obligation: only Lima
 * registers one now, as the network's method demo, and a peer's narrative lives in its impact
 * study, which never locks at all. Listing it here would have every peer's board ask for a guided
 * walk nobody owes — the precise expectation the epic removed, re-entering through the needs UI.
 *
 * It is deliberately NOT dropped from `SECTION_META` or `ReadinessSection`: Lima still has the
 * section, the nav still resolves it, and `sectionStatus` still answers for it honestly.
 */
const NEVER_A_NEED: ReadonlySet<ReadinessSection> = new Set<ReadinessSection>(["story"]);

// --- the record facets: declared scope, enforced gating (#1886) ---------------------------
//
// A *section* is a destination the nav and the needs board reason about; a **facet** is one leaf
// page under The Record. The two are not the same gate, and conflating them is what let the legal
// facet leak: `record` was live on Fort Wayne and Urbana, so any facet that merely rode the domain
// was "available" — and legal, alone among them, reads NETWORK-GLOBAL content (the curated
// `data/extracted/` set) rather than a per-site feed, so it served Lima's fifteen pages verbatim.
//
// Every other facet was correct only by accident: it happened to read a feed the exporter had
// already scoped, and would have leaked the same way the moment it didn't. The declaration below
// makes each facet state (a) what its content is scoped to and (b) what has to be true of THIS
// site before the page opens — so the property is asserted, not inferred from which lib a page
// happened to import (`facets.test.ts`).

/** A leaf page under The Record whose availability is declared here. */
export type RecordFacet =
  | "documents"
  | "records"
  | "timeline"
  | "exhibits"
  | "people"
  | "places"
  | "legal"
  | "reference";

/**
 * How a facet's *content* is scoped across the network.
 *
 * - `per-site` — the page renders this site's own corpus. Two sites serving byte-identical
 *   non-empty content at the route is a **bug** (one is borrowing the other's record).
 * - `network-global` — the page deliberately renders shared, network-wide content, so the
 *   duplication is intended and must be justified in `note`.
 */
export type FacetScope = "per-site" | "network-global";

export interface FacetDeclaration {
  /** Route under `/network/<site>`, for the declaration to be checkable against the build. */
  route: string;
  /** Heading shown on the facet's lock — the leaf's own name, not its parent section's. */
  label: string;
  /** Whose lock copy (`SECTION_META`) the facet borrows when it isn't on this site's record. */
  section: ReadinessSection;
  /** The activation domain that must carry evidence before the facet can open (`null` = none). */
  domain: Domain | null;
  scope: FacetScope;
  /** Why the facet is scoped the way it is — REQUIRED reasoning for a `network-global` one. */
  note: string;
}

export const RECORD_FACETS: Record<RecordFacet, FacetDeclaration> = {
  documents: {
    route: "/site/documents/",
    label: "Documents",
    section: "record",
    domain: "record",
    scope: "per-site",
    note: "The source-document catalog, from the site's own scoped `documents` feed.",
  },
  records: {
    route: "/site/records/",
    label: "Records",
    section: "record",
    domain: "record",
    scope: "per-site",
    note: "Structured extractions from the site's own corpus subtree (`records` feed).",
  },
  timeline: {
    route: "/timeline",
    label: "Timeline",
    section: "timeline",
    domain: "record",
    scope: "per-site",
    note: "Events reconstructed from the site's own record (`timeline` feed).",
  },
  exhibits: {
    route: "/site/exhibits",
    label: "Exhibits",
    section: "exhibits",
    domain: "record",
    scope: "per-site",
    note: "Curated slices of the site's own source documents (`exhibits` feed).",
  },
  people: {
    route: "/site/people/",
    label: "People",
    section: "people",
    domain: "record",
    scope: "per-site",
    note: "Actors named in the site's own record (`people` feed).",
  },
  places: {
    route: "/site/places/",
    label: "Places & parcels",
    section: "places",
    domain: "places",
    scope: "per-site",
    note:
      "Per-place profiles from the site's own `places` feed. NOTE the facet is narrower than the " +
      "`places` DOMAIN, which also lights on committed geometry alone (Urbana's parcel assemblage) " +
      "— that geometry is the map's, not a profile page's, so the facet locks while the section stays open.",
  },
  legal: {
    route: "/site/legal/",
    label: "Legal history",
    section: "legal",
    domain: "record",
    scope: "per-site",
    note:
      "The one facet with no feed between it and the corpus: it renders `data/extracted/` markdown " +
      "through a content collection, so `scopedLegal` supplies the corpus-scope read the exporter " +
      "does for everything else (#1886).",
  },
  // The glossary is deliberately NOT a facet anymore (#1892, closing the residual half of the
  // #1886 concepts decision): it was the one `network-global` entry — the shared method vocabulary,
  // rendered inside every site build so `[[wiki links]]` resolved without leaving the site — and
  // that render was the duplication. The glossary now builds ONCE at `/wiki/concepts/` (the noun's
  // canonical page, `taxonomy.ts`); a record's `[[wiki links]]` resolve there, the retired
  // `/site/concepts/*` routes 301 there, and the record hub's Glossary door is a plain
  // cross-reference, not a gated facet.
  reference: {
    route: "/site/reference/",
    label: "Reference data",
    section: "record",
    domain: "record",
    scope: "per-site",
    note: "External datasets the site OWNS, via the catalog `site_scope` seam (#1260).",
  },
};

/** Whether this site's own corpus puts anything behind the facet (the content half of the gate). */
function facetHasContent(slug: string, facet: RecordFacet): boolean {
  switch (facet) {
    case "documents":
      return feedCount(slug, "documents") > 0;
    case "records":
      return feedCount(slug, "records") > 0;
    case "timeline":
      return feedCount(slug, "timeline") > 0;
    case "exhibits":
      return feedCount(slug, "exhibits") > 0;
    case "people":
      return feedCount(slug, "people") > 0;
    case "places":
      return feedCount(slug, "places") > 0;
    case "legal":
      return scopedLegal(slug).length > 0;
    case "reference":
      return scopedReference(slug).length > 0;
  }
}

/**
 * A record facet's status for a site: `available` (render its real content) or `locked` (render
 * the lock + the ask). The declared domain must carry evidence AND the facet must have content of
 * this site's own — an active domain never opens an empty leaf, and no leaf ever fills itself
 * from another site's record.
 */
export function facetStatus(slug: string, facet: RecordFacet): SectionStatus {
  const { domain } = RECORD_FACETS[facet];
  const domainOpen = domain === null || domainPresent(slug, domain);
  return domainOpen && facetHasContent(slug, facet) ? "available" : "locked";
}

/** Convenience: is this record facet ready to render for the site? */
export function facetAvailable(slug: string, facet: RecordFacet): boolean {
  return facetStatus(slug, facet) === "available";
}

/**
 * `getStaticPaths` for a record facet: the selectable sites where the facet actually opens.
 *
 * #1908 gave the lens facets this treatment and deliberately stopped short of the record facets,
 * on the reasoning that "their locks are real destinations with a real ask on them". Measured
 * against the build (#1894), they were not destinations at all. `site/index.astro` drops a locked
 * facet's door (#1886) and `search.ts` skips its row (#1908) — so the page it left standing was
 * reachable from no link and findable by no query, on every peer, forever. A lock nobody can arrive
 * at makes no ask; it is a 404 with a nicer body.
 *
 * The ask itself is not lost, which is what makes this safe: the record index renders the locked
 * facets as its needs board, in place, beside the doors that did open. That is a better ask than a
 * separate page anyway — it is where the reader already is.
 *
 * Same three-consumer shape as {@link facetOffered}, one band down: the door, the row and now the
 * route all read `facetAvailable`, so a facet cannot open in one and stay shut in the others.
 */
export function availableFacetPaths(
  facet: RecordFacet,
): Array<{ params: { site: string }; props: { slug: string } }> {
  return selectableSitePaths().filter((p) => facetAvailable(p.props.slug, facet));
}

/**
 * `getStaticPaths` for a page inside a gated section — today the seven `/reports/<slug>` companions.
 *
 * The reports were the same defect as the record facets above, one band up and louder: seven routes
 * per site, each rendering the IDENTICAL lock, because `ReportShell` swapped its Lima-authored
 * title, eyebrow and body for generic "Reports" copy whenever the section was locked. Twenty-eight
 * built pages across the four selectable sites said one thing, and twelve of them were reachable
 * from nowhere. The section's own index still builds on every site and still carries the lock and
 * the contribute CTA — it is in the site bar, so a reader can actually get to it.
 */
export function openSectionPaths(
  section: ReadinessSection,
): Array<{ params: { site: string }; props: { slug: string } }> {
  return selectableSitePaths().filter((p) => isAvailable(p.props.slug, section));
}

/**
 * Does this site actually BUILD the site-relative route `path`? The link-side peer of the three
 * `getStaticPaths` gates above (#1894).
 *
 * {@link facetOfferedAt} answered this for the lens leaves and is subsumed here. Once a route stops
 * building everywhere, every hand-written cross-link into it becomes a potential 404 — the study's
 * reference annex, the grid page's "the load report walks the chain", the economy hub's tiles. They
 * were all correct while the page existed on every site and rendered a lock, which is exactly why
 * the lock pages were load-bearing, and exactly what made them unfindable orphans.
 *
 * Defaults OPEN for any route no gate claims, so a caller can ask this of an arbitrary path (a
 * study reference may point at `/methodology`) without special-casing. Three families are claimed:
 * a `/reports/<slug>` companion, a record facet, and a lens facet.
 */
export function siteRouteOffered(slug: string, path: string): boolean {
  const bare = path.split("#")[0].split("?")[0];
  if (/^\/reports\/[^/]+\/?$/.test(bare)) return isAvailable(slug, "reports");
  const facet = (Object.keys(RECORD_FACETS) as RecordFacet[]).find(
    (f) => RECORD_FACETS[f].route.replace(/\/$/, "") === bare.replace(/\/$/, ""),
  );
  if (facet) return facetAvailable(slug, facet);
  return facetOfferedAt(slug, bare);
}

// --- the lens band: a composition over the two gates above (#1913, epic #1911) -------------
//
// **Lens is a nav/landing concept; section stays the gating concept**, and the two are allowed to
// be different granularities. Nothing above this line moves: `environment` and `economy` remain
// the gated `ReadinessSection`s that map to manifest domains, and a lens simply declares which of
// those sections and which activation domains its reading stands on (`lenses.ts`). This function
// is the composition — the model is pure and lives there, the bundle read lives here.
//
// So the five lenses cut across the bands rather than replacing them: `land` and `disclosure` are
// pure domain reads (`places` / `record`), `environment` and `economy` inherit their same-named
// section's gate verbatim (including the #1057 cooling lock, which a lens must never route
// around), and `power` — the one genuine split out of `economy` — takes the economy section AND
// the `facility` domain, because "whose grid carries it" presupposes an *it* on the record.
//
// There is no `isReferenceSite` path here: Lima's five lenses open because its manifest says every
// domain is live, and a `stub`-tier peer locks all five for the same reason, in reverse.

/**
 * A lens's status for a site: `available` (open its landing) or `locked` (show the lock + the ask).
 *
 * Every declared section must be available AND every declared domain must carry evidence — a lens
 * is a *view over* those gates, so it can never be more open than the narrowest thing it gathers.
 */
export function lensStatus(slug: string, lens: LensId): SectionStatus {
  const { sections, domains } = LENSES[lens];
  const open = sections.every((s) => isAvailable(slug, s)) && domains.every((d) => domainPresent(slug, d));
  return open ? "available" : "locked";
}

/** Convenience: is this lens ready to open for the site? */
export function lensAvailable(slug: string, lens: LensId): boolean {
  return lensStatus(slug, lens) === "available";
}

/**
 * Whether this site puts anything behind one of a lens's doors (#1908, over #1915's declaration).
 *
 * A record facet carries its own declared gate; the rest name the feeds that open them. The rule
 * itself is #1915's and unchanged — what moved is *where it lives*. It was written inline in
 * `lens/[lens].astro`, which made it the landing's private opinion, and the landing was the only
 * surface that held it: `getStaticPaths` built the leaf for every selectable site and `search.ts`
 * indexed every facet the model declares, so nineteen leaves were built and findable on sites whose
 * landing correctly refused to offer them. A search result is a promise that there is somewhere to
 * land, and "no thermal-discharge screen has been modeled for this site yet" is not that.
 *
 * So the gate is one function with three consumers — the landing that draws the door, the route
 * that emits the leaf, and the walk that indexes it. They cannot disagree, which is the only
 * arrangement in which "every built page is reachable" stays true after the next facet is added.
 *
 * NOT a page gate in the other direction: a leaf that IS offered still renders its own honest empty
 * state, and the record facets keep building on every selectable site because their locks are real
 * destinations with a real ask on them.
 */
export function facetOffered(slug: string, facet: LensFacet): boolean {
  if (facet.facet) return facetAvailable(slug, facet.facet);
  if (facet.requires) return facet.requires.some((feed) => hasFeed(feed, slug));
  return true;
}

/**
 * The same gate, keyed by route — for the in-page cross-links that point at a lens leaf.
 *
 * Once the route stopped building everywhere, every hand-written link into it became a potential
 * 404: the study's annex footers, the watershed map's "see the imagery slider", the network lens
 * page's facet list. They were all correct while the leaf existed unconditionally and rendered
 * "nothing modeled here yet" — which is exactly why the stub pages were load-bearing, and why
 * `check-links` found them the moment they weren't.
 *
 * `true` for any route no lens declares, so a caller can ask this of an arbitrary path (a study
 * reference may point at `/methodology`) without special-casing. This is the ONE place that
 * defaults open; the three gates above default to the declaration.
 */
export function facetOfferedAt(slug: string, route: string): boolean {
  const bare = route.split("#")[0];
  const facet = Object.values(LENSES)
    .flatMap((l) => l.facets)
    .find((f) => f.route.split("#")[0] === bare);
  return facet ? facetOffered(slug, facet) : true;
}

/**
 * `getStaticPaths` for a lens leaf: the selectable sites whose lens landing actually offers it.
 *
 * The second of {@link facetOffered}'s three consumers. A leaf page reads its OWN route here rather
 * than restating the condition, so the route it emits and the door that links it are decided by one
 * line of `lenses.ts` — the same discipline `how-to-read` uses to stay Lima-only, generalized.
 *
 * Throws on a route no lens declares. That is the tripwire worth having: a leaf that quietly failed
 * this lookup would fall back to building everywhere, which is the state this is here to end.
 */
export function offeredFacetPaths(
  route: string,
): Array<{ params: { site: string }; props: { slug: string } }> {
  const facet = Object.values(LENSES)
    .flatMap((l) => l.facets)
    .find((f) => f.route === route);
  if (!facet) throw new Error(`no lens declares the facet route "${route}" — see lenses.ts`);
  return selectableSitePaths().filter((p) => facetOffered(p.props.slug, facet));
}
