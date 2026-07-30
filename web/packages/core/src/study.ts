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
import type { EconomicBaseline, FacilityItem, ProvenancedValue, ScenarioResult } from "./feeds";
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

/** Reserved bundle feed name — when a future export ships per-chapter models, the frontend
 *  prefers it wholesale and the TS composers below become the fallback. */
export const IMPACT_STUDY_FEED = "impact-study";

/** One row of the future `impact-study` feed (`(chapter, facility_key)`-keyed). */
export interface ImpactStudyFeedRow {
  chapter: string;
  facility_key: string | null;
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
function coolingUndisclosed(slug: string, facility: FacilityItem | null): boolean {
  return coolingMethodUndisclosed(slug) || facility?.cooling_model === "unknown";
}

const NA_REASON = "No disclosed project — this chapter is computed the day one is on the record.";

/** The facility-less predicate for project-dependent chapters. */
const needsProject = (_slug: string, facility: FacilityItem | null): boolean => facility === null;

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
        "no project is disclosed at this site; the day one is, this chapter names it from the record.",
      producer: "the operator's own filings — a permit application, a rezoning, an interconnection request",
    },
    references: [
      { label: "The record", path: "/site/" },
      { label: "Timeline", path: "/timeline", requiresFeed: "timeline" },
      { label: "End use & workloads", path: "/reports/end-use-and-workloads" },
    ],
    probe: (slug) =>
      facilityState(slug) === "live"
        ? []
        : ["the IT load on the record is a screening bracket, not an instrument-grounded figure"],
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
    probe: (slug, facility) =>
      coolingUndisclosed(slug, facility)
        ? [
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
      missingRecord: "no discharge characterization for this project has been filed.",
      producer: "an NPDES permit application and its fact sheet",
    },
    references: [
      { label: "Hydrology", path: "/environment/hydrology" },
      { label: "RSEI / toxics", path: "/environment/rsei", requiresFeed: "rsei" },
    ],
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
      missingRecord: "no thermal characterization exists for this project.",
      producer: "the NPDES application's thermal load sheet, or the permit's §316(a) demonstration",
    },
    references: [{ label: "Thermal / §316(a)", path: "/environment/thermal", requiresFeed: "thermal" }],
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
      missingRecord: "no well survey or dewatering record has been produced.",
      producer: "state well logs, a dewatering permit, and the contractor's discharge records",
    },
    references: [{ label: "Groundwater", path: "/environment/groundwater" }],
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
      missingRecord: "no air-permit application for this project is on the record.",
      producer: "the state air permit application (PTI/Title V) and its emissions tables",
    },
    references: [
      { label: "Air dispersion", path: "/environment/air", requiresFeed: "air-dispersion" },
      { label: "Imagery", path: "/environment/imagery" },
    ],
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
      missingRecord: "the county employment baseline has not been assembled for this site yet.",
      producer: "BLS QCEW and Census ACS — public series; this gap closes on the next export",
    },
    references: [{ label: "Localized labor baseline", path: "/environment/economics-baseline" }],
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
      missingRecord: "the grid backdrop has not been assembled for this site yet.",
      producer: "EIA-861/930 — public series; this gap closes on the next export",
    },
    references: [
      { label: "The grid backdrop", path: "/economy/grid", requiresFeed: "grid" },
      { label: "The load & the grid", path: "/reports/the-load-and-the-grid" },
    ],
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
      missingRecord:
        "the abatement agreement, the school-board resolution, and the county auditor's abatement report — all public records — have not been produced into this record.",
      producer: "the county auditor, the school board, and the enterprise-zone/CRA agreement itself",
    },
    references: [],
    notApplicable: needsProject,
    // Curated-only, gap-first by design: no fiscal feed exists, and none is fabricated.
    derive: () => ({ status: "gap", reasons: ["no fiscal instrument is on the record"] }),
  },
  {
    id: "balance",
    part: "economy",
    title: "The public balance",
    dek: "What the community gives against what it is documented to get — a verdict over the chapters.",
    requiredFeeds: [],
    gap: {
      wouldScreen: "the whole trade on one sheet — headroom given against benefits documented.",
      missingRecord: "the balance synthesizes the other chapters; it has no record of its own to miss.",
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
    return { status: "gap", reasons: [def.gap.missingRecord] };
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
 * (the Python seam); falls back to the TS composers over today's feeds. Plain JSON out.
 */
export function studyChapterModel(id: string, slug: string, facilityKey?: string): StudyChapterModel {
  const def = studyChapter(id);
  const facility = resolveStudyFacility(slug, facilityKey);
  const key = facilityKey ?? facility?.key ?? null;

  if (hasFeed(IMPACT_STUDY_FEED, slug)) {
    const rows = loadFeed<ImpactStudyFeedRow[]>(IMPACT_STUDY_FEED, slug);
    const row = rows.find((r) => r.chapter === id && (key === null || r.facility_key === key));
    if (row) return row.model;
  }

  const { status, reasons } = chapterAvailability(def, slug, facilityKey);
  const composed =
    status === "na" ? EMPTY_COMPOSITION : (COMPOSERS[id]?.(slug, facility) ?? EMPTY_COMPOSITION);
  return {
    id,
    facilityKey: key,
    status,
    statusReasons: reasons,
    stats: composed.stats,
    // The chapter-level gap framing renders whenever the chapter IS the finding; probe-level
    // gaps (a bracketed cooling method inside a partial chapter) come from the composer.
    gaps: status === "gap" ? [def.gap, ...composed.gaps] : composed.gaps,
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

function pvStat(
  label: string,
  pv: ProvenancedValue | null | undefined,
  evidence: FigureStatData["evidence"],
  extra?: Partial<FigureStatData>,
): FigureStatData | null {
  if (pv == null || pv.value == null) return null;
  return {
    label,
    value: fmtRanged({ value: pv.value, low: pv.low, high: pv.high }, 1),
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
};

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
