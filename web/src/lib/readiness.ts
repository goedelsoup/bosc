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
 * Two sections are network-global rather than per-site: `reports` (the `docs/` long-form the
 * reference build hosts) stays reference-only (`isReferenceSite`, the surviving network-global-host
 * role, #1220); `environment` also locks when the facility's cooling method is undisclosed (#1057).
 */
import { hasFeed, loadFeed, loadManifest } from "./bundle";
import type { DomainState, Readiness, SiteTier } from "./bundle";
import type { ScenarioResult } from "./feeds";
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
function domainPresent(slug: string, domain: Domain): boolean {
  return siteDomainStates(slug)[domain] !== "absent";
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
    case "story":
      // The guided walk needs a *surfaced* story (registered in the `sites.ts` overlay and not
      // hidden) — a leads-only story domain (Urbana) has no walk to open, and Lima's hidden Project
      // BOSC walk (#1256) locks here too, so its story tab/hub CTA drop in the early build state.
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
