/**
 * The impact study — each site's primary artifact (epic: the missing impact study).
 *
 * Communities facing a data-center (or similar industrial-water-user) project never receive
 * the environmental + economic impact study that should precede abatements and rezonings. The
 * platform already computes the ingredients; this module assembles them into that study's
 * **data spine**: a fixed, site-generic chapter registry whose every chapter renders either
 * the screen the record supports or the gap **as a finding** — "a real impact study would
 * report X; the record needed to compute it has not been produced."
 *
 * Three disciplines govern this module:
 *
 *  - **The study never locks.** An absent feed is *content* (the absence register), so status
 *    derivation composes the same primitives readiness reads (`hasFeed` row counts,
 *    `coolingMethodUndisclosed`, `facilityState`) into a per-chapter *verdict*
 *    (`data | partial | gap | na`) — never into a `SectionLocked`. A facility-less site still
 *    has a study: its baseline chapters are real reported content and its project-dependent
 *    chapters read `na` (watch state), not `gap` — "no project ⇒ nothing to say" is exactly
 *    the framing this artifact exists to refute.
 *  - **Verdicts measure the record, not the lifecycle.** Row counts + content probes decide
 *    status; a facility's `investigation → live` clock changes framing copy only.
 *  - **Multi-project forward-compat, no compute change.** Every function threads an optional
 *    `facilityKey` (nothing passes one today) and the model carries it, so a second campus
 *    later gets its own study rows without rearchitecting. Facility-scoped routes are
 *    reserved under `/study/f/<facility-key>/…` — the `f/` prefix means a chapter id and a
 *    facility key can never collide (and no chapter may ever take the id `f`). No "the
 *    campus" singletons live here: copy reads the resolved facility's own name.
 *
 * **The Python seam.** `StudyChapterModel` is plain JSON keyed by `(chapter, facility_key)` —
 * deliberately the shape of a future `impact-study` bundle feed. `studyChapterModel` prefers
 * that feed wholesale when a bundle ships it; today's TS composers (each a thin read over the
 * existing builders) are the fallback that the feed will replace row-for-row. Everything the
 * study's surfaces render (cover strip, chapter header, annex rollup) reads ONLY
 * `chapterAvailability` / `studyChapterModel`, never raw feeds — that is the seam.
 *
 * NOT client-safe (imports the node bundle loader) — pages render these plain objects.
 */
import { hasFeed, loadFeed, loadManifest } from "./bundle";
import {
  citeDataset,
  citedSourcesIn,
  citedSourcesInNote,
  citeGroups,
  type CitedGroup,
  type CitedSource,
} from "./cite";
import type {
  CoolingModel,
  EconomicBaseline,
  FacilityItem,
  ProvenancedValue,
  RecordItem,
  ScenarioResult,
} from "./feeds";
import { fmtMult, fmtRanged, round } from "./format";
import { buildDemandPressure, buildGridBackdrop } from "./gridBackdrop";
import { coolingMethodUndisclosed, facilityLoadAvailable, facilityState } from "./readiness";
import { siteBase } from "./routes";
import { buildThermal } from "./thermal";
import type { FigureStatData } from "./viz";

// --- the study's shape -------------------------------------------------------------------

/** The study's four parts, in reading order. */
export type StudyPartId = "project" | "environment" | "economy" | "annex";

export interface StudyPart {
  id: StudyPartId;
  /** Front-matter numbering for the wayfinding line ("Part II · The environment"). */
  num: string;
  title: string;
  dek: string;
}

export const STUDY_PARTS: readonly StudyPart[] = [
  {
    id: "project",
    num: "I",
    title: "The project",
    dek: "What this study is, how it reads evidence, and the project on the record.",
  },
  {
    id: "environment",
    num: "II",
    title: "The environment",
    dek: "Water, heat, groundwater, runoff, and air — each screened where the record allows.",
  },
  {
    id: "economy",
    num: "III",
    title: "The economy",
    dek: "The labor baseline, the grid and its ratepayers, the fiscal trade, and the balance.",
  },
  {
    id: "annex",
    num: "IV",
    title: "What's missing",
    dek: "Every gap this study names, as one inventory — each with the record that would close it.",
  },
];

/**
 * A chapter's verdict — the study's status vocabulary (display labels live with the chip):
 *  - `data`    — every required ingredient is on the record; the screen renders.
 *  - `partial` — ingredients present but a probe brackets or withholds part of the read
 *                (undisclosed cooling, a screening-only load, a baseline-only context).
 *  - `gap`     — the record needed for the chapter's central question has not been produced:
 *                the chapter renders AS the finding, never as a lock.
 *  - `na`      — the chapter is project-dependent and no project is disclosed here yet
 *                (watch state — distinct from `gap` so the verdict strip doesn't scold a
 *                site with nothing to study).
 */
export type ChapterStatus = "data" | "partial" | "gap" | "na";

/** The cooling-archetype display labels (epic #1060) — the enum is keyed on mechanism, and
 *  "open loop / closed loop" are the industry's ambiguous names, shown only as parenthetical
 *  aliases. ONE copy, shared by the hydrology annex page and the study's water chapter. */
export const COOLING_MODEL_LABELS: Record<CoolingModel, string> = {
  off: "no cooling-water load",
  evaporative_tower: "evaporative cooling tower (“open loop”)",
  once_through: "once-through surface water (“open once-through”)",
  closed_loop_dry: "closed-loop dry / air-cooled (“closed loop”)",
  hybrid_adiabatic: "hybrid dry + seasonal adiabatic assist",
  unknown: "undisclosed cooling method",
};

/** Display copy for each verdict — the status chip and the cover's verdict strip read this
 *  (one vocabulary, so the strip and the chapter header can never disagree). The chip colors
 *  live with the component; these are the words. */
export const STUDY_STATUS_META: Record<ChapterStatus, { label: string; gloss: string }> = {
  data: { label: "On the record", gloss: "every required ingredient is committed and cited" },
  partial: {
    label: "Partial",
    gloss: "on the record in part — a probe brackets or withholds the rest",
  },
  gap: { label: "Gap", gloss: "the record needed to compute this chapter has not been produced" },
  na: { label: "Watch", gloss: "computed the day a project is on the record here" },
};

/** A gap rendered as a FINDING (the absence register) — the fixed three-line grammar the
 *  gap panel renders: the requirement, the absence, the ask. Always `[open]`; never counted,
 *  summed, or ranked into a score (a "gap index" would be a fabricated metric over absences). */
export interface StudyGapFinding {
  /** Line 1 — "A real impact study would report ___." About the study, never an accusation. */
  wouldScreen: string;
  /** Line 2 — the specific record that has not been produced. */
  missingRecord: string;
  /** Line 3 — who could produce it (a public body, the operator, a filing). */
  producer?: string;
  /** Curated `LeadItem.id`s this gap corresponds to (PR5) — the SAME ask as the leads board,
   *  never a fuzzy keyword match (misattributing a gap is an evidentiary-discipline violation). */
  leadIds?: string[];
}

/** A cross-link into the existing environment/economy/reports tree — "the data behind this
 *  chapter". Site-relative path (prefix with the site root at render). */
export interface StudyReference {
  label: string;
  path: string;
  /** Only offer the link when the site's bundle carries this feed (no doors onto locks). */
  requiresFeed?: string;
}

export interface StudyChapterDef {
  /** URL slug under `/study/` — a closed namespace (`f` is reserved, see the header). */
  id: string;
  part: StudyPartId;
  title: string;
  dek: string;
  /** Feeds whose presence (>0 manifest rows) makes the chapter renderable as data. */
  requiredFeeds: readonly string[];
  /** When true, the required feeds are alternatives — any ONE lifts the chapter out of gap
   *  (groundwater's two screens), instead of all being co-required. */
  anyRequired?: boolean;
  /** Feeds that enrich, or stand in as baseline context when the required set is absent
   *  (present optional + absent required ⇒ `partial`, the baseline register). */
  optionalFeeds?: readonly string[];
  /** The chapter-level gap framing when the record is absent. */
  gap: StudyGapFinding;
  /** Reference-annex links (rendered in the chapter footer, feed-guarded). */
  references: readonly StudyReference[];
  /**
   * The record groups this chapter's screen reads (#1885) — the "the record behind this chapter"
   * band. Declared as the contractor-agnostic group ids (`RECORD_GROUP_LABELS`), which are
   * site-generic: `citeGroups` resolves each against the site's OWN records feed and drops the
   * ones it has no rows in, so a chapter offers a peer the groups that peer actually holds and
   * never a door onto an empty index. Never a per-site rel — those are derived (below) or
   * authored in the site's own MDX note.
   */
  recordGroups?: readonly string[];
  /**
   * Published reference datasets the chapter's screen rests on (#1885) — slugs in `REFERENCE`,
   * guarded per site by `scopedReference`. This is where a connector-grounded `[verified]` figure
   * gets its destination: the labor baseline is BLS QCEW, the grid backdrop is EIA-861/930, and
   * before this each of those rendered a `[verified]` tag with nothing behind it.
   */
  datasets?: readonly string[];
  /** Content probe run when the required feeds ARE present — returns the partial-status
   *  reasons (empty ⇒ `data`). Reads the same primitives readiness reads. */
  probe?: (slug: string, facility: FacilityItem | null) => string[];
  /** Project-dependent chapters return `na` (watch state) for a facility-less site. */
  notApplicable?: (slug: string, facility: FacilityItem | null) => boolean;
  /** Full status override for the chapters whose verdict is not feed-shaped: `method`
   *  (front matter, never gaps), `fiscal` (curated-only, gap-first by design), `balance`
   *  (an aggregate over the screened chapters), `missing` (the annex, always renders). */
  derive?: (slug: string, facility: FacilityItem | null) => { status: ChapterStatus; reasons: string[] };
}

/** The plain-JSON model every study surface reads — **deliberately the shape of the future
 *  `impact-study` feed row** (see the module header). Keep it serializable. */
export interface StudyChapterModel {
  id: string;
  facilityKey: string | null;
  status: ChapterStatus;
  /** Human-readable status qualifiers ("cooling method undisclosed — bracketed range"). */
  statusReasons: string[];
  /** The chapter's headline findings strip (each figure wears its evidence tag). */
  stats: FigureStatData[];
  /** Gap findings to render as panels (chapter-level and probe-produced). */
  gaps: StudyGapFinding[];
  /** MUST-render caveats (the `gridBackdrop.ts` discipline: callers render, never drop). */
  caveats: string[];
}

/** The bundle feed the Python export ships (#1804) — the frontend prefers its rows
 *  wholesale, and the TS composers below survive as the fallback for a bundle predating it
 *  (plus the parity harness's reference derivation — see `study.parity.test.ts`). */
export const IMPACT_STUDY_FEED = "impact-study";

/** One row of the `impact-study` feed (`(chapter, facility_key)`-keyed). `lead_ids` are the
 *  chapter-level curated gap → lead joins, whose ONE owner is now the Python projector
 *  (`watermark.site.impact_study.STUDY_GAP_LEADS`) — the export refuses a join that stops
 *  reconciling against the site's own leads feed. */
export interface ImpactStudyFeedRow {
  chapter: string;
  facility_key: string | null;
  lead_ids?: string[];
  model: StudyChapterModel;
}

// --- small shared reads ------------------------------------------------------------------

/** A feed's manifest row count for a site (0 when absent) — object feeds count 1, so a
 *  single `> 0` test covers both kinds. Never `hasFeed` alone: a present-but-empty
 *  collection (fort-wayne's zero-row `hydrology-scenarios`) is NOT on the record. */
function feedRows(slug: string, name: string): number {
  return loadManifest(slug).feeds.find((f) => f.name === name)?.count ?? 0;
}

/**
 * The facility a study reads — defaulted to the primary campus (the same idiom every
 * existing page uses), resolvable by `key` the day a site hosts more than one project.
 */
export function resolveStudyFacility(slug: string, facilityKey?: string): FacilityItem | null {
  const rows = hasFeed("facility", slug) ? loadFeed<FacilityItem[]>("facility", slug) : [];
  if (facilityKey) return rows.find((f) => f.key === facilityKey) ?? null;
  return rows.find((f) => f.is_primary) ?? rows[0] ?? null;
}

/** Whether the resolved facility's cooling method is on the record. Reads BOTH the scenario
 *  rows (#1057's probe) and the facility row itself, so a site with a facility but no
 *  scenarios yet (fort-wayne) still names the disclosure as its water chapter's ask. */
/**
 * A chapter's gap framing, narrowed to what is ACTUALLY missing for this site (#1983).
 *
 * `StudyChapterDef.gap` is written for the common case, which for `water-supply` is a facility
 * that discloses neither its cooling method nor a water quantity. A facility that DOES disclose
 * the method (West Union / Buck Canyon: hybrid/adiabatic, ~97% air, from Amazon's own brochure)
 * would otherwise be told the method is missing — asserting an absence the record contradicts.
 * The gap is narrowed to the quantity, which is the half genuinely `[open]`.
 *
 * `off` is deliberately NOT a disclosed method here: it means there is no cooling-water load to
 * quantify at all (a federal enclave — WPAFB), so narrowing the gap to "no quantity" would assert
 * a missing figure that the archetype says cannot exist.
 *
 * Mirrors `watermark.site.impact_study._chapter_gap` — change the two together or not at all.
 */
function chapterGap(def: StudyChapterDef, slug: string, facility: FacilityItem | null): StudyGapFinding {
  // Same rule on the air axis (#1998): the chapter's gap says "an air-permit application for this
  // project — none is on the record", which stops being true the moment one is FILED. An
  // application is not a permit and the chapter rightly stays `gap` — the dispersion screen needs
  // the emission-unit inventory only the draft carries — but telling a reader nothing has been
  // filed, on a site whose own record holds the agency's acknowledgment letter, asserts an
  // absence the corpus contradicts.
  if (def.id === "air" && airApplicationFiled(slug)) {
    return {
      ...def.gap,
      missingRecord:
        "a DRAFT permit or public notice — an air-permit application is on the record here, but the document that names the generator fleet has not issued.",
      // The producer moves with the gap. Naming "the air permit application" as what would close
      // this reads as a document nobody has requested, on a site where it was filed weeks ago —
      // it sends a reader to the wrong instrument.
      producer:
        "the Ohio EPA draft permit or public notice for the pending application, and its emission-unit inventory",
    };
  }
  if (
    def.id === "water-supply" &&
    facility &&
    facility.cooling_model != null &&
    facility.cooling_model !== "off" &&
    !coolingUndisclosed(slug, facility)
  ) {
    return {
      ...def.gap,
      missingRecord:
        "a metered, contracted or permit-grounded water quantity — the cooling method is disclosed here, but no quantity is.",
    };
  }
  return def.gap;
}

function coolingUndisclosed(slug: string, facility: FacilityItem | null): boolean {
  return coolingMethodUndisclosed(slug) || facility?.cooling_model === "unknown";
}

/**
 * A shipped scenario whose intake the RECORD states — the peer of `_contracted_demand` in
 * `watermark/site/impact_study.py`, and it must stay identical to it (parity suite).
 *
 * An undisclosed cooling method usually means the water figures are a bracketed range across
 * candidate archetypes, and the probe says so. Sidney inverts that: the method is undisclosed but
 * the gallons are in an executed service agreement, so its intake ships `source: "document"`.
 * Telling a reader those figures are a bracket would be false — the bracket is the cross-check
 * sitting beside them, not the headline (#1995).
 */
/**
 * The site's own record holds an air-program filing — the peer of `_air_application_filed` in
 * `watermark/site/impact_study.py`, and it must stay identical to it (parity suite).
 *
 * Read off the `permits-epa` group and keyed on the agency naming its AIR division, which is how
 * the corpus separates an air action from the surface-water and 401 actions sharing that group.
 * Deliberately narrow: it answers "has anything been FILED", never "has a permit issued" (#1998).
 */
function airApplicationFiled(slug: string): boolean {
  if (feedRows(slug, "records") === 0) return false;
  return loadFeed<RecordItem[]>("records", slug).some(
    (r) =>
      r.group === "permits-epa" &&
      String((r.fields as Record<string, unknown> | undefined)?.agency ?? "")
        .toLowerCase()
        .includes("air pollution control"),
  );
}

function contractedDemand(slug: string): boolean {
  if (feedRows(slug, "hydrology-scenarios") === 0) return false;
  return loadFeed<ScenarioResult[]>("hydrology-scenarios", slug).some(
    (r) => r.scenario?.cooling_demand?.source === "document" && (r.scenario?.cooling_demand?.value ?? 0) > 0,
  );
}

const NA_REASON = "No disclosed project — this chapter is computed the day one is on the record.";

/** The facility-less predicate for project-dependent chapters. */
const needsProject = (_slug: string, facility: FacilityItem | null): boolean => facility === null;

/**
 * Rows in the site's OWN records feed carrying any of `groups` — the corpus-keyed primitive the
 * `assembly` / `governance` chapters screen on (#1969).
 *
 * A **raw** feed read on purpose. `citeGroups` is readiness-gated and would be the tempting reuse,
 * but a status derivation that runs through a gate the Python projector cannot see would break
 * parity (`study.parity.test.ts`) the first time a site's record facet locked with rows on disk.
 * Gating belongs to the evidence band; the verdict reads the record.
 */
const recordGroupRows = (slug: string, groups: readonly string[]): number =>
  feedRows(slug, "records") === 0
    ? 0
    : loadFeed<RecordItem[]>("records", slug).filter((r) => groups.includes(r.group)).length;

/** The conveyance vocabulary `assembly` screens on. */
const ASSEMBLY_GROUPS = ["land-assembly", "deeds"] as const;
/** The decision-path vocabulary `governance` screens on. */
const GOVERNANCE_GROUPS = ["local-legislation", "litigation"] as const;
/** Mirrors `impact_study._FISCAL_GROUPS` (#1993). */
const FISCAL_GROUPS = ["incentive-package"] as const;

// --- the chapter registry ----------------------------------------------------------------

/** The chapters whose screens the balance chapter aggregates (feed-shaped verdicts only —
 *  never `fiscal`, whose designed gap would otherwise cap the balance forever, and never
 *  `balance` itself). */
const SCREEN_CHAPTER_IDS = [
  "water-supply",
  "discharge",
  "heat",
  "groundwater",
  "stormwater",
  "air",
  "labor",
  "power",
] as const;

export const STUDY_CHAPTERS: readonly StudyChapterDef[] = [
  // --- Part I · The project (front matter) ---
  {
    id: "method",
    part: "project",
    title: "Scope & method",
    dek: "What a real impact study is, who normally commissions one, and how this one reads evidence.",
    requiredFeeds: [],
    gap: {
      wouldScreen: "—",
      missingRecord: "—",
    },
    references: [{ label: "Methodology", path: "/methodology" }],
    // Front matter about the study itself — it screens nothing, so it cites nothing.
    derive: () => ({ status: "data", reasons: [] }),
  },
  {
    id: "project",
    part: "project",
    title: "The project on the record",
    dek: "Operator, lifecycle, load, cooling, and footprint — every undisclosed field a named blank.",
    requiredFeeds: ["facility"],
    gap: {
      wouldScreen: "the project this study screens — its operator, scale, load, and cooling design.",
      missingRecord:
        "a disclosed project — none is on the record at this site yet; the day one is, this chapter names it.",
      producer: "the operator's own filings — a permit application, a rezoning, an interconnection request",
    },
    references: [
      { label: "The record", path: "/site/" },
      { label: "Timeline", path: "/timeline", requiresFeed: "timeline" },
      { label: "End use & workloads", path: "/reports/end-use-and-workloads" },
    ],
    // The project's own instruments: what it applied for, who applied, and what it bought.
    // `local-legislation` (#1438) is the fourth kind and was missing until Bowling Green's record
    // arrived almost entirely in that form — a rezoning roll call IS "what it applied for", and at
    // a township-scale site it is often the only instrument that names the applicant at all.
    recordGroups: [
      "permits-epa",
      "permits-idem",
      "permits-sos",
      "deeds",
      "land-assembly",
      "local-legislation",
      "plans",
    ],
    datasets: ["gleif"],
    probe: (slug) => {
      if (facilityState(slug) === "live") return [];
      // A facility whose load is entirely `[open]` has no bracket to describe (#1983): saying
      // "a screening bracket" would assert a figure the record does not carry. West Union /
      // Buck Canyon is the first — the campus is disclosed, but the only MW on the record is
      // filed for an unnamed customer, so `SiteFacility.it_load_mw` is None.
      const facility = resolveStudyFacility(slug);
      if (facility && facility.it_load_mw == null) {
        return [
          "the facility is disclosed but its IT load is not instrument-grounded — no instrument on the record states it",
        ];
      }
      return ["the IT load on the record is a screening bracket, not an instrument-grounded figure"];
    },
  },
  {
    id: "assembly",
    part: "project",
    title: "Land assembly & the deal",
    dek: "How the land was put together, by whom, and what the paper trail says about when.",
    // Corpus-keyed, not facility-keyed (#1969): assembly is screened against the site's OWN
    // extracted record, and it takes no `notApplicable` — speculative assembly PRECEDES the
    // announcement, which is the whole shape of the Lima story. A chapter that went `na` for a
    // facility-less site could never report the assembly that happened before one was disclosed.
    requiredFeeds: ["records"],
    gap: {
      wouldScreen:
        "how the project's land was assembled — the conveyance chain, the buyers of record, and the dates.",
      missingRecord:
        "the recorded deeds and the option or purchase instruments for the campus parcels — none produced into this record.",
      producer: "the county recorder and auditor — recorded instruments are public records",
    },
    references: [
      { label: "Places & parcels", path: "/site/places", requiresFeed: "geo/campus" },
      { label: "Timeline", path: "/timeline", requiresFeed: "timeline" },
    ],
    recordGroups: [...ASSEMBLY_GROUPS],
    probe: (slug) =>
      recordGroupRows(slug, ASSEMBLY_GROUPS) > 0
        ? []
        : [
            "the record carries no conveyance instrument — the land history has not been produced for this site",
          ],
  },
  // --- Part II · The environment ---
  {
    id: "water-supply",
    part: "environment",
    title: "Water supply & consumptive use",
    dek: "How much water the project consumes, against the receiving water's own cited low flows.",
    requiredFeeds: ["hydrology-scenarios"],
    optionalFeeds: ["water-seasonal-field"],
    gap: {
      wouldScreen:
        "how much water this project consumes at buildout — monthly, against the receiving water's cited design low flows.",
      missingRecord:
        "a disclosed cooling method and a metered or contracted water quantity; neither is on the record here.",
      producer:
        "the water utility's contract, a wastewater permit application, or the operator's cooling-plant spec",
    },
    references: [
      { label: "Hydrology", path: "/environment/hydrology" },
      { label: "Seasonal withdrawal", path: "/environment/seasonal", requiresFeed: "water-seasonal-field" },
    ],
    // The design low flows this chapter screens against are read off the receiving water's own
    // permit fact sheets — the NPDES file IS the citation for the floor.
    recordGroups: ["permits-npdes"],
    probe: (slug, facility) =>
      coolingUndisclosed(slug, facility)
        ? contractedDemand(slug)
          ? [
              "cooling method undisclosed — but the water quantity is CONTRACTED, so the figures are a stated account rather than a bracketed range; what stays open is how the heat is rejected, not how much water it takes",
            ]
          : [
              "cooling method undisclosed — the water figures are a bracketed range across candidate archetypes, not an estimate",
            ]
        : [],
    notApplicable: needsProject,
  },
  {
    id: "discharge",
    part: "environment",
    title: "The discharge & the receiving water",
    dek: "Dilution at the design low flows, and the burden the receiving water already carries.",
    requiredFeeds: ["hydrology-scenarios"],
    optionalFeeds: ["rsei"],
    gap: {
      wouldScreen:
        "the discharge screened against the receiving stream's assimilative capacity at its cited design low flows.",
      missingRecord: "a discharge characterization for this project — none has been filed.",
      producer: "an NPDES permit application and its fact sheet",
    },
    references: [
      { label: "Hydrology", path: "/environment/hydrology" },
      { label: "RSEI / toxics", path: "/environment/rsei", requiresFeed: "rsei" },
    ],
    // The corridor's other dischargers (ECHO's basin inventory + their own permits and orders),
    // and the county release record the chapter reads the arrival against.
    recordGroups: ["permits-npdes", "enforcement"],
    datasets: ["echo", "rsei"],
  },
  {
    id: "heat",
    part: "environment",
    title: "Heat",
    dek: "The discharge's heat against the reach's temperature criterion at design low flow.",
    requiredFeeds: ["thermal"],
    gap: {
      wouldScreen:
        "how much heat the discharge adds to a reach screened against Ohio's numeric temperature criterion at its design low flows.",
      missingRecord: "a thermal characterization for this project — none exists on the record.",
      producer: "the NPDES application's thermal load sheet, or the permit's §316(a) demonstration",
    },
    references: [{ label: "Thermal / §316(a)", path: "/environment/thermal", requiresFeed: "thermal" }],
    // The corridor's reported effluent temperatures come off the permits themselves, and the set
    // of dischargers screened on the reach is the ECHO basin inventory's.
    recordGroups: ["permits-npdes"],
    datasets: ["echo"],
    notApplicable: needsProject,
  },
  {
    id: "groundwater",
    part: "environment",
    title: "Groundwater & dewatering",
    dek: "The wells within reach of the site's pumping, and where the pumped water went.",
    requiredFeeds: ["drawdown", "dewatering"],
    anyRequired: true,
    gap: {
      wouldScreen:
        "the wells within the drawdown radius, and whether construction dewatering was permitted and where the water went.",
      missingRecord: "a well survey and any dewatering record — neither has been produced.",
      producer: "state well logs, a dewatering permit, and the contractor's discharge records",
    },
    references: [{ label: "Groundwater", path: "/environment/groundwater" }],
    // Both screens stand on the DNR well logs — the county census and the campus dewatering
    // wellfield are two datasets of one published README.
    datasets: ["ohio-waterwells"],
    notApplicable: needsProject,
  },
  {
    id: "stormwater",
    part: "environment",
    title: "Stormwater & the built surface",
    dek: "The runoff a campus-scale impervious surface adds to the design storm.",
    requiredFeeds: ["reach-network"],
    optionalFeeds: ["routed-hydrograph"],
    gap: {
      wouldScreen:
        "the runoff a campus-scale impervious surface adds to the design storm, routed down the reach.",
      missingRecord: "the site grading and drainage plan — requested, not produced.",
      producer: "the site plan's grading/drainage sheets and the construction stormwater permit (NOI)",
    },
    references: [
      { label: "Water flow", path: "/environment/flow", requiresFeed: "reach-network" },
      { label: "Watershed map", path: "/environment/map" },
    ],
    // The impervious acreage and the outfall come from the construction stormwater coverage and
    // the site plan set.
    recordGroups: ["permits-npdes", "plans"],
    notApplicable: needsProject,
  },
  {
    id: "air",
    part: "environment",
    title: "Air",
    dek: "The dispersion footprint of the campus's permitted generator fleet.",
    requiredFeeds: ["air-dispersion"],
    optionalFeeds: ["air-dispersion-field", "air-scenarios"],
    gap: {
      wouldScreen: "the dispersion footprint of the campus's permitted backup-generator fleet.",
      missingRecord: "an air-permit application for this project — none is on the record.",
      producer: "the state air permit application (PTI/Title V) and its emissions tables",
    },
    references: [
      { label: "Air dispersion", path: "/environment/air", requiresFeed: "air-dispersion" },
      { label: "Imagery", path: "/environment/imagery" },
    ],
    // The emission caps, the engine count, and every runtime band come off the air permit file.
    recordGroups: ["permits-epa", "permits-idem"],
    notApplicable: needsProject,
  },
  // --- Part III · The economy ---
  {
    id: "labor",
    part: "economy",
    title: "Labor & the local baseline",
    dek: "What this economy is before the project — the denominator every jobs claim divides by.",
    requiredFeeds: ["economics-baseline"],
    gap: {
      wouldScreen: "the local labor baseline every jobs claim should be read against.",
      missingRecord: "the county employment baseline — not yet assembled for this site.",
      producer: "BLS QCEW and Census ACS — public series; this gap closes on the next export",
    },
    references: [{ label: "Localized labor baseline", path: "/economy/economics-baseline" }],
    // The baseline is entirely public federal series; the dataset page IS its provenance. A site
    // with WARN closure/layoff notices on its own record shows those beside it.
    recordGroups: ["labor"],
    datasets: ["economics"],
  },
  {
    id: "power",
    part: "economy",
    title: "Power & ratepayers",
    dek: "Whose grid this load lands on, and what it does to the households on the same wires.",
    requiredFeeds: ["grid"],
    optionalFeeds: ["economics-demand-pressure", "energy-burden", "consumer-energy"],
    gap: {
      wouldScreen:
        "the campus's load against the serving utility's, balancing authority's, and state's annual load.",
      missingRecord: "the site's grid backdrop — not yet assembled.",
      producer: "EIA-861/930 — public series; this gap closes on the next export",
    },
    references: [
      { label: "The grid backdrop", path: "/economy/grid", requiresFeed: "grid" },
      { label: "The load & the grid", path: "/reports/the-load-and-the-grid" },
    ],
    // The serving utility, the balancing authority, and all three denominators are EIA-861/930.
    datasets: ["eia"],
    probe: (slug, facility) => {
      if (facility === null)
        return ["no disclosed campus load to size against the grid — the backdrop stands on its own"];
      return facilityLoadAvailable(slug)
        ? []
        : [
            "the campus load is a screening bracket — the demand-pressure read is withheld until an instrument grounds it",
          ];
    },
  },
  {
    id: "fiscal",
    part: "economy",
    title: "The fiscal trade",
    dek: "What tax revenue is being traded away, for how long, and what the paper trail says.",
    requiredFeeds: [],
    gap: {
      wouldScreen: "what tax revenue is being traded away and for how long, before the trade is approved.",
      // Reworded at #1993, in the same change that made it false — see `impact_study.py`.
      missingRecord:
        "the county auditor's abatement report and the year-by-year exemption ledger — public records, none produced into this record. Where the agreement itself is on the record it states the TERMS of the trade, never its cost to the taxing bodies.",
      producer: "the county auditor, the school board, and the enterprise-zone/CRA agreement itself",
    },
    references: [],
    // The public money that IS on the record — the loans and awards, plus (#1438) the legislative
    // ACT that granted the trade where one has been read: Wood County's Resolution 23-01249
    // authorizing a 75%/15-year CRA exemption is exactly this chapter's subject. Note what that
    // does and does not close — the resolution AUTHORIZES an agreement it does not contain, so the
    // executed agreement, the school compensation agreements and the auditor's abatement report
    // stay this chapter's named gap and are never scaffolded from the authorization.
    recordGroups: ["finance", "local-legislation"],
    notApplicable: needsProject,
    // Gap-first by design — no fiscal FEED exists and none is fabricated — but not blind to the
    // record any more (#1993). `incentive-package` is the one group whose definition is sufficient
    // on its own; `agreements` deliberately does not gate here, because it also holds an NDA and an
    // intergovernmental treatment agreement.
    derive: (slug) =>
      recordGroupRows(slug, FISCAL_GROUPS) > 0
        ? {
            status: "partial",
            reasons: [
              "the incentive instruments are on the record, but the accounting is not — no auditor's abatement report and no exemption ledger says what the trade cost",
            ],
          }
        : { status: "gap", reasons: ["no fiscal accounting and no incentive instrument is on the record"] },
  },
  {
    id: "governance",
    part: "economy",
    title: "Governance & the local record",
    dek: "The ordinances, resolutions, votes, and minutes that approved — or refused — the project.",
    // Corpus-keyed and deliberately NOT project-dependent (#1969). Mansfield is the corpus's
    // first documented data-center REFUSAL: it carries a governance record and no facility at
    // all, and a `needsProject` gate would read that refusal as "nothing to say here" — the
    // exact framing this study exists to refute.
    requiredFeeds: ["records"],
    optionalFeeds: ["meetings"],
    gap: {
      wouldScreen:
        "the public decisions that approved or refused the project — the ordinances, resolutions, roll-call votes, and the minutes that carry them.",
      missingRecord:
        "the legislative instruments and meeting minutes of the deciding bodies — none produced into this record.",
      producer:
        "the municipal clerk, the township trustees, and the county commissioners — R.C. 149.43 records",
    },
    references: [
      { label: "Timeline", path: "/timeline", requiresFeed: "timeline" },
      { label: "Open leads", path: "/leads", requiresFeed: "leads" },
    ],
    recordGroups: [...GOVERNANCE_GROUPS],
    probe: (slug) =>
      recordGroupRows(slug, GOVERNANCE_GROUPS) > 0 || feedRows(slug, "meetings") > 0
        ? []
        : [
            "the record carries no legislative instrument and no minutes — the decision path has not been produced for this site",
          ],
  },
  {
    id: "balance",
    part: "economy",
    title: "The public balance",
    dek: "What the community gives against what it is documented to get — a verdict over the chapters.",
    requiredFeeds: [],
    gap: {
      wouldScreen: "the whole trade on one sheet — headroom given against benefits documented.",
      missingRecord:
        "no record of its own — it synthesizes the other chapters, and none of them has a record to draw on yet.",
    },
    references: [
      { label: "Public balance sheet", path: "/reports/public-balance-sheet" },
      { label: "The economic ledger", path: "/reports/the-economic-ledger" },
    ],
    notApplicable: needsProject,
    derive: (slug, facility) => {
      // An aggregate verdict over the screened chapters (never fiscal's designed gap, never
      // itself): all data ⇒ data; anything on the record ⇒ partial; nothing ⇒ gap.
      const statuses = SCREEN_CHAPTER_IDS.map(
        (id) => chapterAvailability(studyChapter(id), slug, facility?.key).status,
      ).filter((s) => s !== "na");
      const data = statuses.filter((s) => s === "data").length;
      const partial = statuses.filter((s) => s === "partial").length;
      if (statuses.length > 0 && data === statuses.length) return { status: "data", reasons: [] };
      if (data + partial > 0) {
        return {
          status: "partial",
          reasons: [
            `synthesizes the screened chapters — ${data} on the record, ${partial} partial, ${statuses.length - data - partial} gap`,
          ],
        };
      }
      return { status: "gap", reasons: ["none of the screened chapters has a record to balance yet"] };
    },
  },
  // --- Part IV · What's missing (annex) ---
  {
    id: "missing",
    part: "annex",
    title: "The gap inventory",
    dek: "Every gap this study names, with the record that would close it and where to send it.",
    requiredFeeds: [],
    gap: { wouldScreen: "—", missingRecord: "—" },
    references: [
      { label: "Open leads", path: "/leads", requiresFeed: "leads" },
      { label: "Open questions", path: "/wiki/open-questions" },
    ],
    derive: () => ({ status: "data", reasons: [] }),
  },
];

/**
 * The curated lead ids tracking a chapter's asks on a site ([] when none are joined) — the
 * annex wiring. Each join says "this chapter's asks are ALREADY TRACKED as these leads":
 * the study's gap panels deep-link the board's own anchors, and the annex inventory lists
 * them under the chapter, so the study and the leads board present ONE set of asks.
 *
 * The curation itself moved home to the Python projector at the feed cutover (#1804 —
 * `watermark.site.impact_study.STUDY_GAP_LEADS`, strictly curated, never a fuzzy keyword
 * match, and validated against the site's own leads feed at export). This is now a thin
 * reader of the shipped row's `lead_ids`; a bundle predating the feed simply has no joins,
 * and its gap panels degrade to the submit CTA alone.
 */
export function studyGapLeads(slug: string, chapterId: string, facilityKey?: string): readonly string[] {
  if (!hasFeed(IMPACT_STUDY_FEED, slug)) return [];
  const key = facilityKey ?? resolveStudyFacility(slug, facilityKey)?.key ?? null;
  const rows = loadFeed<ImpactStudyFeedRow[]>(IMPACT_STUDY_FEED, slug);
  return rows.find((r) => r.chapter === chapterId && r.facility_key === key)?.lead_ids ?? [];
}

/** Look up a chapter def by id (throws on an unknown id — a registry typo, not a data state). */
export function studyChapter(id: string): StudyChapterDef {
  const def = STUDY_CHAPTERS.find((c) => c.id === id);
  if (!def) throw new Error(`Unknown study chapter "${id}"`);
  return def;
}

/** A chapter's 1-based number in the continuous study order (the wayfinding line). */
export function chapterNumber(id: string): number {
  const i = STUDY_CHAPTERS.findIndex((c) => c.id === id);
  if (i < 0) throw new Error(`Unknown study chapter "${id}"`);
  return i + 1;
}

// --- status derivation ---------------------------------------------------------------------

/**
 * A chapter's verdict for a site — feed presence + **row counts** + content probes, never
 * `hasFeed` alone. Reads the same primitives readiness reads, but composes them into a
 * *status*, not a lock (`hasEnough` is deliberately never consulted — the study never locks).
 */
export function chapterAvailability(
  def: StudyChapterDef,
  slug: string,
  facilityKey?: string,
): { status: ChapterStatus; reasons: string[] } {
  const facility = resolveStudyFacility(slug, facilityKey);
  if (def.notApplicable?.(slug, facility)) return { status: "na", reasons: [NA_REASON] };
  if (def.derive) return def.derive(slug, facility);

  const present = def.requiredFeeds.filter((f) => feedRows(slug, f) > 0);
  const optionalPresent = (def.optionalFeeds ?? []).filter((f) => feedRows(slug, f) > 0);
  if (present.length === 0 && optionalPresent.length === 0) {
    return { status: "gap", reasons: [chapterGap(def, slug, facility).missingRecord] };
  }
  if (present.length < def.requiredFeeds.length) {
    // `anyRequired` feeds are alternatives (either groundwater screen suffices).
    if (def.anyRequired && present.length > 0) return probeOrData(def, slug, facility);
    const missing = def.requiredFeeds.filter((f) => !present.includes(f));
    return {
      status: "partial",
      reasons:
        present.length === 0
          ? ["baseline context only — the project-side record has not been produced"]
          : missing.map((f) => `no ${f} on the record for this site`),
    };
  }
  return probeOrData(def, slug, facility);
}

function probeOrData(
  def: StudyChapterDef,
  slug: string,
  facility: FacilityItem | null,
): { status: ChapterStatus; reasons: string[] } {
  const flags = def.probe?.(slug, facility) ?? [];
  return flags.length > 0 ? { status: "partial", reasons: flags } : { status: "data", reasons: [] };
}

// --- the chapter model (the feed seam) ------------------------------------------------------

/**
 * The chapter model every study surface renders. Prefers a shipped `impact-study` feed row
 * (the Python seam, now live — #1804); falls back to `composeStudyChapterModel` for a
 * bundle predating the feed. Plain JSON out.
 */
export function studyChapterModel(id: string, slug: string, facilityKey?: string): StudyChapterModel {
  studyChapter(id); // the registry-typo guard throws on an unknown id even on the feed path
  const facility = resolveStudyFacility(slug, facilityKey);
  const key = facilityKey ?? facility?.key ?? null;

  if (hasFeed(IMPACT_STUDY_FEED, slug)) {
    const rows = loadFeed<ImpactStudyFeedRow[]>(IMPACT_STUDY_FEED, slug);
    // Exact (chapter, facility_key) pair — a null key matches only site-level rows
    // (facility_key null), never some other facility's study, and vice versa.
    const row = rows.find((r) => r.chapter === id && r.facility_key === key);
    if (row) return row.model;
  }
  return composeStudyChapterModel(id, slug, facilityKey);
}

/**
 * The TS-composed chapter model — the pre-feed derivation, kept as (a) the fallback for a
 * bundle that ships no `impact-study` feed and (b) the reference derivation the parity gate
 * compares every shipped row against (`study.parity.test.ts`): the Python projector mirrors
 * this path line-for-line, and a divergence is a defect there, not a display choice.
 */
export function composeStudyChapterModel(id: string, slug: string, facilityKey?: string): StudyChapterModel {
  const def = studyChapter(id);
  const facility = resolveStudyFacility(slug, facilityKey);
  const key = facilityKey ?? facility?.key ?? null;
  const { status, reasons } = chapterAvailability(def, slug, facilityKey);
  const composed =
    status === "na" ? EMPTY_COMPOSITION : (COMPOSERS[id]?.(slug, facility) ?? EMPTY_COMPOSITION);
  // The chapter-level gap framing renders whenever the chapter IS the finding; probe-level
  // gaps (a bracketed cooling method inside a partial chapter) come from the composer. The
  // curated per-site lead joins ride every gap the chapter renders (one board, one ask) —
  // the same attachment rule the Python projector applies, so a partially-shipped feed
  // (a row missing for one chapter) still composes consistently with its siblings.
  const leadIds = studyGapLeads(slug, id, facilityKey);
  const gaps = (status === "gap" ? [chapterGap(def, slug, facility), ...composed.gaps] : composed.gaps).map(
    (g) => (leadIds.length > 0 && (g.leadIds?.length ?? 0) === 0 ? { ...g, leadIds: [...leadIds] } : g),
  );
  return {
    id,
    facilityKey: key,
    status,
    statusReasons: reasons,
    stats: composed.stats,
    gaps,
    caveats: composed.caveats,
  };
}

type Composition = Pick<StudyChapterModel, "stats" | "gaps" | "caveats">;
const EMPTY_COMPOSITION: Composition = { stats: [], gaps: [], caveats: [] };

/** The cooling-disclosure ask, shared by the water chapter's partial (bracketed) state. */
const COOLING_GAP: StudyGapFinding = {
  wouldScreen: "a single consumptive-draw figure against the receiving water's low-flow floor.",
  missingRecord:
    "any record of how the facility rejects heat — a water contract, a wastewater permit, or a cooling-plant spec; until one surfaces, the water figures stay a bracketed range across candidate archetypes.",
  producer: "the water utility, the wastewater permit file, or the operator's own engineering disclosure",
};

/** The load-instrument ask, shared by the power chapter's screening-bracket state. */
const LOAD_INSTRUMENT_GAP: StudyGapFinding = {
  wouldScreen:
    "the campus's share of the serving utility's, balancing authority's, and state's annual load, from a grounded load figure.",
  missingRecord:
    "an instrument that grounds the IT load — an air permit or an interconnection filing; the load on the record is a screening bracket.",
  producer: "the state air-permit file or the RTO interconnection queue",
};

/**
 * One decimal, unless that would render a real figure as 0 — the peer of `_stat_decimals` in
 * `watermark/site/impact_study.py`, and it must stay identical to it (the parity suite pins the
 * two derivations equal).
 *
 * Every headline stat rounds to one decimal, which suits the magnitudes this study was built on.
 * Sidney's contracted cooling draw is 0.0146 cfs (3.44M gal/yr, `[verified]` in an executed
 * service agreement) and renders as **"0 cfs"** — a reader takes that as *no draw*, which is a
 * different claim from *a very small one* and the wrong one (#1995). A value that would vanish
 * keeps two significant figures instead. Nothing at the old scale moves.
 */
export function statDecimals(value: number | null | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 1;
  if (value === 0 || Math.round(Math.abs(value) * 10) / 10 !== 0) return 1;
  return 1 - Math.floor(Math.log10(Math.abs(value)));
}

function pvStat(
  label: string,
  pv: ProvenancedValue | null | undefined,
  evidence: FigureStatData["evidence"],
  extra?: Partial<FigureStatData>,
): FigureStatData | null {
  if (pv == null || pv.value == null) return null;
  return {
    label,
    value: fmtRanged({ value: pv.value, low: pv.low, high: pv.high }, statDecimals(pv.value)),
    unit: pv.unit ?? undefined,
    evidence,
    source: pv.source ?? undefined,
    ...extra,
  };
}

/**
 * The per-chapter composers — each a thin read over the existing builders/feeds, producing
 * only headline stats + probe-level gaps + must-render caveats. Bespoke chapter sections
 * (landing in later PRs) render the full screens; the future `impact-study` feed replaces
 * these row-for-row. Chapters without a composer render their status + gap panels alone.
 */
const COMPOSERS: Record<string, (slug: string, facility: FacilityItem | null) => Composition> = {
  project(slug, facility) {
    if (!facility) return EMPTY_COMPOSITION;
    const stats: FigureStatData[] = [];
    if (facility.it_load_low_mw != null || facility.it_load_mw != null) {
      const low = facility.it_load_low_mw;
      const high = facility.it_load_high_mw;
      const grounded = facilityState(slug) === "live";
      stats.push({
        label: "IT load",
        value:
          low != null && high != null
            ? `${round(low)}–${round(high)}`
            : String(round(facility.it_load_mw ?? low ?? 0)),
        unit: "MW",
        evidence: "inference",
        basis: "modeled",
        sub: grounded
          ? "bracket grounded by an instrument on the record"
          : "screening bracket — no instrument grounds it yet",
        source: facility.air_permit_citation ? "air permit (committed)" : "screening estimate",
      });
    }
    stats.push({
      label: "Cooling",
      value:
        facility.cooling_model === "unknown" ? "not disclosed" : facility.cooling_model.replace(/_/g, " "),
      evidence:
        facility.cooling_model === "unknown"
          ? "open"
          : facility.cooling_model_source === "document" || facility.cooling_model_source === "connector"
            ? "verified"
            : "inference",
      sub:
        facility.cooling_model_source === "reference"
          ? "an operator claim — a claim is not an instrument"
          : undefined,
    });
    const caveats: string[] = [];
    if (facility.status === "investigation") {
      caveats.push(
        "Reported, not confirmed: every project-dependent figure in this study is conditional on the project proceeding.",
      );
    }
    return { stats, gaps: [], caveats };
  },

  "water-supply"(slug, facility) {
    if (feedRows(slug, "hydrology-scenarios") === 0) return EMPTY_COMPOSITION;
    const rows = loadFeed<ScenarioResult[]>("hydrology-scenarios", slug);
    const stats: FigureStatData[] = [];
    const worst = rows.reduce<ScenarioResult | null>(
      (a, b) => (a === null || (b.consumptive_loss.value ?? 0) > (a.consumptive_loss.value ?? 0) ? b : a),
      null,
    );
    if (worst) {
      const s = pvStat("Worst-case consumptive draw", worst.consumptive_loss, "inference", {
        basis: "modeled",
        sub: `scenario: ${worst.scenario.name}`,
      });
      if (s) stats.push(s);
      const floor = pvStat("Receiving low flow (7Q10)", worst.receiving_7q10, "verified", {
        basis: "grounded",
        sub: worst.receiving_water_name ?? undefined,
      });
      if (floor) stats.push(floor);
    }
    const gaps = coolingUndisclosed(slug, facility) ? [COOLING_GAP] : [];
    return {
      stats,
      gaps,
      caveats: [
        "The draw is set against the receiving water's cited design low flow as a worst-case, basin-scale bound — a screening comparison, not a withdrawal claim.",
      ],
    };
  },

  discharge(slug) {
    if (feedRows(slug, "hydrology-scenarios") === 0) {
      return {
        stats: [],
        gaps: [],
        caveats: [
          "Only the receiving water's existing burden is on the record here — the project-side discharge screen renders the day a characterization is filed.",
        ],
      };
    }
    const rows = loadFeed<ScenarioResult[]>("hydrology-scenarios", slug);
    const checks = rows.flatMap((r) => r.assimilative);
    if (checks.length === 0) return EMPTY_COMPOSITION;
    const worst = checks.reduce((a, b) => (b.dilution_ratio < a.dilution_ratio ? b : a));
    return {
      stats: [
        {
          label: "Tightest chronic dilution",
          value: fmtMult(worst.dilution_ratio),
          evidence: "verified",
          basis: "grounded",
          sub: `${worst.discharger} → ${worst.receiving_water}`,
          warn: worst.flag === "violation",
        },
      ],
      gaps: [],
      caveats: [],
    };
  },

  heat(slug) {
    const model = buildThermal(slug);
    if (!model) return EMPTY_COMPOSITION;
    const stats: FigureStatData[] = [];
    if (model.headroomC != null) {
      stats.push({
        label: "Thermal headroom at design low flow",
        value: String(round(model.headroomC, 1)),
        unit: "°C",
        evidence: "inference",
        basis: "modeled",
        sub: model.river,
        warn: model.headroomC <= 0,
      });
    }
    if (model.capacityMw != null) {
      stats.push({
        label: "Reach thermal capacity",
        value: String(round(model.capacityMw, 1)),
        unit: "MW",
        evidence: "inference",
        basis: "modeled",
      });
    }
    return {
      stats,
      gaps: [],
      caveats: model.ambientGrounded
        ? []
        : [
            "The design ambient is the zone's seasonal criterion standing in, not a measured in-stream temperature — the capacity moves with that choice.",
          ],
    };
  },

  labor(slug) {
    if (feedRows(slug, "economics-baseline") === 0) return EMPTY_COMPOSITION;
    const eb = loadFeed<EconomicBaseline>("economics-baseline", slug);
    const stats: FigureStatData[] = [];
    const emp = pvStat("County employment", eb.latest.total_employment ?? null, "verified", {
      basis: "grounded",
      sub: `${eb.area_name} · ${eb.latest.year}`,
      source: "BLS QCEW",
    });
    if (emp) stats.push(emp);
    return {
      stats,
      gaps: [],
      caveats: [
        "Any jobs claim reads against this baseline as claim vs. denominator — the study never computes a jobs multiplier.",
      ],
    };
  },

  power(slug, facility) {
    const backdrop = buildGridBackdrop(slug);
    if (!backdrop) return EMPTY_COMPOSITION;
    const stats: FigureStatData[] = [
      {
        label: "Serving utility",
        value: backdrop.utilityName,
        evidence: "verified",
        basis: "grounded",
        sub: backdrop.baName,
      },
    ];
    const utilityShare = backdrop.denominators.find((d) => d.key === "utility")?.sharePct;
    if (backdrop.campus && utilityShare != null) {
      stats.push({
        label: "Campus share of utility load",
        value: `${utilityShare.toFixed(2)}%`,
        evidence: "inference",
        basis: "modeled",
        sub: `~${round(backdrop.campus.loadMw)} MW disclosed campus draw`,
      });
    }
    const gaps: StudyGapFinding[] = [];
    if (facility !== null && !facilityLoadAvailable(slug)) gaps.push(LOAD_INSTRUMENT_GAP);
    const caveats: string[] = [];
    if (facilityLoadAvailable(slug)) {
      const pressure = buildDemandPressure(slug);
      if (pressure?.caveats) caveats.push(...pressure.caveats);
    }
    if (backdrop.note) caveats.push(backdrop.note);
    return { stats, gaps, caveats };
  },

  fiscal(_slug, facility) {
    const caveats: string[] = [];
    if (facility?.disclosed_investment_usd != null) {
      caveats.push(
        `Disclosed investment: $${(facility.disclosed_investment_usd / 1e9).toFixed(1)}B — the operator's own announcement, not an instrument; the abatement agreement that would price the trade is not on the record.`,
      );
    }
    return { stats: [], gaps: [], caveats };
  },

  // The two corpus-keyed composers (#1969). Each counts ONLY rows in the groups its chapter
  // declares, so a `[verified]` stat exists exactly where `citeGroups` can resolve a destination
  // for it — the citation invariant (`study.evidence.test.ts`) holds by construction rather than
  // by a listed exemption.
  assembly(slug) {
    const rows = recordGroupRows(slug, ASSEMBLY_GROUPS);
    if (rows === 0) return EMPTY_COMPOSITION;
    return {
      stats: [
        {
          label: "Conveyance instruments",
          value: String(rows),
          evidence: "verified",
          basis: "grounded",
          sub: "recorded deeds and assembly instruments on this site's record",
        },
      ],
      gaps: [],
      caveats: [
        "A conveyance chain on the record is what was produced, not what exists — an assembly can run through options, nominees, and unrecorded agreements that no recorder's index will show.",
      ],
    };
  },

  // `meetings` is a STATUS signal for this chapter, never a stat. A minutes count has no
  // destination in the evidence annex's three bands, so asserting one as `[verified]` would be a
  // provenance claim the page can't honour — the precise thing `study.evidence.test.ts` forbids.
  // The site's own meetings surface already carries that count, cited.
  governance(slug) {
    const instruments = recordGroupRows(slug, GOVERNANCE_GROUPS);
    if (instruments === 0) return EMPTY_COMPOSITION;
    return {
      stats: [
        {
          label: "Legislative instruments",
          value: String(instruments),
          evidence: "verified",
          basis: "grounded",
          sub: "resolutions, ordinances, zoning applications as docketed, and filed court instruments on this site's record",
        },
      ],
      gaps: [],
      caveats: [
        "An instrument on the record says what was moved, not what was decided — some are pending or proposed, and the deliberation that produced any of them lives in minutes and audio that are separate records.",
      ],
    };
  },
};

// --- the record behind a chapter (#1885) -----------------------------------------------------

/**
 * The evidence a chapter can actually hand a reader — "the record behind this chapter".
 *
 * Three bands, in the order the annex renders them. Every entry is a destination this site
 * really builds; `cite.ts` drops anything it can't resolve, so an empty band means the record
 * genuinely isn't here, not that the link broke.
 */
export interface StudyChapterEvidence {
  /** Record-group indexes with rows on this site (the declared `recordGroups`). */
  groups: CitedGroup[];
  /** Leaf records/documents the chapter's own feeds name in their citations — derived, not
   *  curated, so a peer's chapter cites the peer's sources with no per-site list to maintain. */
  sources: CitedSource[];
  /** Published reference datasets the site owns (the declared `datasets`). */
  datasets: CitedSource[];
}

/** Whether a chapter offers a reader any resolving evidence link at all. */
export function hasChapterEvidence(evidence: StudyChapterEvidence): boolean {
  return evidence.groups.length + evidence.sources.length + evidence.datasets.length > 0;
}

/**
 * Resolve a chapter's evidence for a site (#1885).
 *
 * **Why this is not on `StudyChapterModel`.** The model is byte-locked to the Python projector
 * by the parity gate (`study.parity.test.ts` — the shipped `impact-study` row must equal the TS
 * derivation exactly), so adding a field here would silently invalidate every committed bundle
 * until all 26 are re-exported. Evidence is also a different axis from a verdict: it is a join
 * over feeds the chapter sections already read raw, at render, in the same `runWithSite` scope.
 * Folding it into the feed is a clean follow-up — mirror it in `watermark.site.impact_study`,
 * bump the contract, re-export — and this function is deliberately shaped as that future row.
 *
 * The `na` chapters (project-dependent, no project disclosed) resolve to nothing: there is no
 * screen, so there is no record behind it, and offering the site's record groups anyway would
 * dress an empty chapter in someone else's evidence.
 */
export function studyChapterEvidence(
  chapterId: string,
  slug: string,
  opts: {
    facilityKey?: string;
    /** The site's MDX note for this chapter, raw. Its authored `<Cite>`s join the annex so
     *  the block lists everything the page links, not just the machine-derived half. */
    noteBody?: string;
  } = {},
): StudyChapterEvidence {
  const { facilityKey, noteBody } = opts;
  const def = studyChapter(chapterId);
  const empty: StudyChapterEvidence = { groups: [], sources: [], datasets: [] };
  if (chapterAvailability(def, slug, facilityKey).status === "na") return empty;

  // Two source axes, deduped into one list. AUTHORED first (a human named it in the prose, so
  // it is the most specific thing the chapter cites), then DERIVED: the citations of exactly
  // the feeds this chapter declares it reads — never the whole bundle, so an air permit can't
  // surface under the labor baseline. A feed absent from the bundle contributes nothing.
  const sources = new Map<string, CitedSource>();
  // Declared datasets first; an authored `<Cite dataset>` joins this band rather than the leaf
  // list, so the annex's three bands stay one kind each however the citation was written.
  const datasets = new Map<string, CitedSource>();
  const add = (source: CitedSource): void => {
    const bucket = source.kind === "reference" ? datasets : sources;
    bucket.set(`${source.kind}:${source.key}`, source);
  };
  for (const declared of def.datasets ?? []) {
    const dataset = citeDataset(declared, slug);
    if (dataset) add(dataset);
  }
  for (const source of noteBody ? citedSourcesInNote(noteBody, slug) : []) add(source);
  for (const feed of [...def.requiredFeeds, ...(def.optionalFeeds ?? [])]) {
    if (!hasFeed(feed, slug)) continue;
    for (const source of citedSourcesIn(loadFeed<unknown>(feed, slug), slug)) add(source);
  }
  return {
    groups: citeGroups(def.recordGroups ?? [], slug),
    sources: [...sources.values()],
    datasets: [...datasets.values()],
  };
}

// --- TOC / hrefs / rollups -------------------------------------------------------------------

/** A study URL, pre-deploy-base (the `siteBase` convention): the cover, or a chapter. */
export function studyHref(slug: string, chapterId?: string): string {
  const root = `${siteBase(slug)}/study/`;
  return chapterId ? `${root}${chapterId}` : root;
}

export interface StudyTocChapter {
  def: StudyChapterDef;
  num: number;
  status: ChapterStatus;
  reasons: string[];
  href: string;
}

export interface StudyTocPart {
  part: StudyPart;
  chapters: StudyTocChapter[];
}

/** The whole study's table of contents for a site — parts, chapters, verdicts, hrefs. The
 *  cover's verdict strip and the annex rollup read this (never raw feeds). */
export function studyToc(slug: string, facilityKey?: string): StudyTocPart[] {
  return STUDY_PARTS.map((part) => ({
    part,
    chapters: STUDY_CHAPTERS.filter((c) => c.part === part.id).map((def) => {
      const { status, reasons } = chapterAvailability(def, slug, facilityKey);
      return { def, num: chapterNumber(def.id), status, reasons, href: studyHref(slug, def.id) };
    }),
  }));
}

/** The verdict rollup for home cards: "N on the record · n partial · n gaps named". */
export function studyStatusSummary(
  slug: string,
  facilityKey?: string,
): { data: number; partial: number; gap: number; na: number; total: number } {
  const out = { data: 0, partial: 0, gap: 0, na: 0, total: STUDY_CHAPTERS.length };
  for (const def of STUDY_CHAPTERS) {
    out[chapterAvailability(def, slug, facilityKey).status] += 1;
  }
  return out;
}
