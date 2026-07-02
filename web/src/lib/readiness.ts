/**
 * Per-site section readiness (#781) — the gating engine for a partial network site.
 *
 * A new watershed-point site rarely has the whole record on day one (Fort Wayne today: the
 * Project Zodiac campus + rsei/econ/network slices, but no timeline / people / exhibits). The
 * site must still be navigable and useful, and actively solicit sources — so each section is
 * classified `available` or `locked` from what *that site's* bundle actually carries, never from
 * Lima's. Pages read this to either render their real partial data or show a coherent "not on the
 * record yet" lock with a contribute CTA: degrade, don't break; lock what isn't ready; and — the
 * repo's spine — never fabricate Lima's record onto a thinner peer.
 *
 * The reference build (Lima) is the deliberate exception: it hosts the network-global narrative
 * and leads (the root `/reports`, `/leads` read it), so its sections are always `available`
 * regardless of counts. Mirrors the backend reference-host asymmetry (`bosc.sites`).
 *
 * Gating is read off the bundle `manifest.json` feed counts (+ the site registry for the story),
 * so it's pure and testable: the committed `sample-bundle/{lima,fort-wayne}` fixtures are a real
 * full-vs-partial pair the unit tests pin against.
 */
import { hasFeed, loadFeed, loadManifest } from "./bundle";
import type { ScenarioResult } from "./feeds";
import { LIMA_SLUG } from "./routes";
import { siteForSlug } from "./sites";

/**
 * The live reference build hosts the network-global content (the `docs/` narrative, the Lima
 * leads board); its sections never lock. The frontend peer of `bosc.sites.is_reference_site`.
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
  | "watershed"
  | "economy"
  | "reports"
  | "story"
  | "leads";

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
  watershed: {
    label: "Watershed",
    holds: "the hydrology, imagery, and toxics-release picture for the receiving water",
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
};

/** Count a feed's rows from the manifest (0 when the feed is absent). */
function feedCount(slug: string, name: string): number {
  return loadManifest(slug).feeds.find((f) => f.name === name)?.count ?? 0;
}

/** Sum a set of feeds' row counts. */
function feedSum(slug: string, names: readonly string[]): number {
  return names.reduce((n, name) => n + feedCount(slug, name), 0);
}

/**
 * Whether the site's water math rests on an **undisclosed cooling method** (#1057).
 *
 * A `hydrology-scenarios` row whose `cooling_model` is `unknown` (equivalently, whose basis
 * says `method_disclosed: false`) carries a bracketed range across candidate archetypes, not
 * an estimate — the facility exists but no record says how it rejects heat. Rendering its
 * single consumptive/7Q10-multiple headline as if confirmed would fabricate the site's most
 * load-bearing number, so the watershed section locks and the needs board asks for the
 * disclosure instead. Content-based (reads feed rows), unlike the count-based predicates.
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

/**
 * Whether a section has enough of *this site's* own data to stand on its own. The reference site
 * short-circuits to `available` everywhere (it carries the network-global content). Each predicate
 * reads only feed counts (+ the registry for the story), so it's deterministic per bundle.
 */
function hasEnough(section: ReadinessSection, slug: string): boolean {
  switch (section) {
    case "record":
      // The library spine — any of the document/record/entity feeds is enough to open the door.
      return feedSum(slug, ["records", "documents", "entities"]) > 0;
    case "timeline":
      return feedCount(slug, "timeline") > 0;
    case "people":
      return feedCount(slug, "people") > 0;
    case "places":
      return feedCount(slug, "places") > 0;
    case "exhibits":
      return feedCount(slug, "exhibits") > 0;
    case "watershed":
      // An undisclosed cooling method locks the section outright (#1057): its scenario rows
      // are bracketed ranges, and no fabricated single-figure headline may stand in.
      if (coolingMethodUndisclosed(slug)) return false;
      return feedSum(slug, ["geo/campus", "geo/watershed", "geo/imagery", "hydrology-scenarios", "rsei"]) > 0;
    case "economy":
      return feedSum(slug, ["economics-baseline", "network"]) > 0;
    case "reports":
      // The reports are the network-global `docs/` narrative — Lima's only, today. A peer locks it
      // until it grows its own long-form (no per-site narrative feed exists yet).
      return false;
    case "story":
      return (siteForSlug(slug)?.stories?.length ?? 0) > 0;
    case "leads":
      // The leads board is the Lima corpus-audit, network-global today — reference-only until a
      // per-site leads feed lands (#781 follow-up).
      return false;
  }
}

/** A section's status for a site: `available` (render its real data) or `locked` (show the lock). */
export function sectionStatus(slug: string, section: ReadinessSection): SectionStatus {
  if (isReferenceSite(slug)) return "available";
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

/** The sections currently locked for a site (empty for the reference build). */
export function lockedSections(slug: string): ReadinessSection[] {
  return (Object.keys(SECTION_META) as ReadinessSection[]).filter((s) => sectionStatus(slug, s) === "locked");
}
