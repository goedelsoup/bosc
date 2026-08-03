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
 */
import { hasFeed, loadFeed, loadManifest } from "./bundle";
import type { DomainState, Readiness, SiteTier } from "./bundle";
import type { ScenarioResult } from "./feeds";
import { scopedLegal } from "./legal";
import { scopedReference } from "./reference";
import { LIMA_SLUG } from "./routes";
import { surfacedStories } from "./sites";

export type { DomainState, SiteTier } from "./bundle";

/** The five activation domains (`bosc.site.readiness.Domain`). */
export type Domain = "backdrop" | "facility" | "places" | "record" | "story";

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
  domains: { backdrop: "absent", facility: "absent", places: "absent", record: "absent", story: "absent" },
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
      // The guided walk needs a *surfaced* (readable) story — registered in the `sites.ts` overlay
      // and neither `hidden` (#1256) nor `comingSoon` (#1526). A leads-only story domain (Urbana)
      // has no walk to open; the editorial walks are `comingSoon`, so this facet locks and their
      // story tab/hub CTA render as a "— coming soon" marker + teaser instead of a readable door.
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
  return (Object.keys(SECTION_META) as ReadinessSection[]).filter((s) => sectionStatus(slug, s) === "locked");
}

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
  | "concepts"
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
  concepts: {
    route: "/site/concepts/",
    label: "Glossary",
    section: "record",
    domain: null,
    scope: "network-global",
    note:
      "DECLARED network-global (#1886, the concepts decision). The glossary is the network's SHARED " +
      "method vocabulary — 7Q10, consumptive cooling, NPDES mean the same thing at every watershed " +
      "point — plus whatever terms a site tags for itself (#1567), so peers legitimately serve an " +
      "identical core set. It renders INSIDE each site build (rather than once, network-global) " +
      "because the record's `[[wiki links]]` must resolve without leaving the site (`wikiScope.ts`); " +
      "it carries no domain gate for the same reason — the vocabulary is readable before a site has " +
      "a corpus. The residual duplication against the network-global `/wiki/concepts/` build is a " +
      "separate, known problem: one taxonomy per noun, tracked in #1892.",
  },
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
    case "concepts":
      return feedCount(slug, "concepts") > 0;
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
