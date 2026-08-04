/**
 * The directory's three-hypothesis model (#308 "Directory" dictate) — one network, read three ways.
 *
 * The /research/hypotheses index reorganizes the SAME registry (`SITES`, every site) around one
 * of three hypotheses — never a subset, and never a count written out in prose, which goes stale
 * the moment a site is registered:
 *   H1 water — where compute meets the watershed (the live reference thesis; Lima is worked).
 *   H2 defense — where the build-out meets federal land and the defense base (emerging).
 *   H3 surveillance — who owns it, who's watching, where the money moves (emerging).
 *
 * Discipline (the spine, mirrored from `defenseNexus.ts` and the evidentiary-method skills):
 * H2/H3 are hypotheses UNDER TEST, not findings. A site carries a defense/surveillance entry
 * only when there's a real, public, on-the-record fact behind it; inference is labeled as such;
 * everything else is "—" and lands in a "Not yet assessed under this thesis" chip group — never
 * a zero, which would read as a cleared verdict. We never fabricate a nexus, an operator, or a
 * count: the doc/record/tier figures are each site's OWN exported bundle (#1861), rolled up per
 * row, and "—" only where no bundle is committed yet.
 *
 * Pure (no bundle read) so it unit-tests offline: the page loads the `hypotheses` +
 * `hypothesis-assessments` feeds and passes the folded assessment data in, and threads the
 * bundle-backed `siteRollup` / `facilityStatus` lookups as resolvers.
 *
 * The scorecard's row/cell/group **grammar** lives in `./scorecard` (#1914) — this module and the
 * lens pages render the same network two ways and must look like the same table. What stays here
 * is what is specific to a thesis: the three hypotheses' framing, their column specs, the basin
 * pivot, and {@link SIGNAL_META}. That last one is deliberate: a signal is a **verdict**, so
 * keeping it out of the shared primitive is what stops a lens surface from reaching for it.
 */
import type { SiteTier } from "./bundle";
import type { FacilityStatus, HypothesisAssessmentItem, HypothesisItem } from "./feeds";
import { basinsOfDivide, DIVIDES } from "./placement";
import {
  type AxisGroup,
  type Cell,
  columnHeads,
  type ColumnSpec,
  figure,
  type Group,
  numCell,
  PHASE_PILL,
  pillCell,
  type Row,
  type ScorecardView,
  siteCell,
  type Swatch,
  TAIL_META,
  TIER_DEPTH_ORDER,
  textCell,
  TIER_PILL,
} from "./scorecard";
import { FACILITY_STATUS_META, groupSites, type NetworkSite, SITES, type SiteRollup } from "./sites";

// The shared scorecard grammar, re-exported from the module its consumers already import — the
// hypotheses page and the network index reach for these by way of `directory`, and the lift is an
// internal reorganization, not a change to what this module offers.
export type { AxisGroup, Cell, CellKind, ColumnSpec, Group, Row, ScorecardView, Swatch } from "./scorecard";
export { PHASE_PILL, TIER_ABBR, TIER_DEPTH_ORDER, TIER_PILL } from "./scorecard";

export type HypothesisId = "water" | "defense" | "surveillance";

/** Display order of the hypothesis cards / panes (water is the default, live thesis). */
export const HYPOTHESIS_ORDER: readonly HypothesisId[] = ["water", "defense", "surveillance"];

/** The strength of a per-site signal under H2/H3 — inference until a nexus is documented.
 *
 *  A **verdict** vocabulary, and the reason it stays in this module rather than moving to the
 *  shared `./scorecard` grammar with the rest of the pill swatches: a lens never carries one. */
export type Signal = "anchor" | "strong" | "moderate" | "watch";

export const SIGNAL_META: Record<Signal, Swatch> = {
  anchor: { label: "Anchor case", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  strong: { label: "Strong signal", color: "#1f6f4a", bg: "#e4ece4", dot: "#3f8a63" },
  moderate: { label: "Moderate", color: "#566159", bg: "#e8e4d8", dot: "#8c9389" },
  watch: { label: "Under investigation", color: "#8c9389", bg: "#faf8f1", dot: "#cdc8b8" },
};

/**
 * The home page's "Across the network" slice: the `limit` sites whose OWN export has assembled
 * the most record, deepest first (#1864). It replaces `SITES.slice(0, limit)`, which ranked by
 * nothing — an empty `stub` that happened to sit in the first eight was "featured" while a
 * worked `case` at position 9 fell below the fold, and the selection reshuffled silently
 * whenever registry order changed.
 *
 * Ranked on the readiness tier first (the standing property `watermark export` recomputes every
 * run), then the site's own records, then its documents, then registry order as a stable final
 * tiebreak. So this moves on its own with the record: a site rises into the slice when a source
 * lands and falls out when one dries up — the same two-clock discipline the ledger reads by.
 *
 * A registered site with no committed bundle (`tier: null`) sorts LAST rather than being scored
 * as a `stub`: nothing has been measured there, and an unmeasured site must never outrank a
 * measured one on a figure we'd have had to invent for it.
 *
 * Pure, like the rest of this module — the page threads `siteRollup` in as the resolver.
 */
export function featuredSites(rollupOf: (slug: string) => SiteRollup, limit: number): NetworkSite[] {
  // Deepest tier = highest rank; no bundle = -1, below every measured tier including `stub`.
  const rank = (tier: SiteTier | null): number =>
    tier === null ? -1 : TIER_DEPTH_ORDER.length - 1 - TIER_DEPTH_ORDER.indexOf(tier);
  return SITES.map((site, order) => ({ site, order, roll: rollupOf(site.slug) }))
    .sort(
      (a, b) =>
        rank(b.roll.tier) - rank(a.roll.tier) ||
        (b.roll.records ?? 0) - (a.roll.records ?? 0) ||
        (b.roll.documents ?? 0) - (a.roll.documents ?? 0) ||
        a.order - b.order,
    )
    .slice(0, limit)
    .map((e) => e.site);
}

// --- The defense (H2) and surveillance (H3) reading of each site --------------------------------
// A site appears in a thesis group ONLY with a real, public, on-the-record fact; `group: "watch"`
// (the default) means "not yet assessed under this thesis" — it lands in the chip group, not a row.
export type DefGroup = "arsenal" | "federal" | "supply" | "capture" | "watch";
export type SurvGroup = "onrecord" | "subsidy" | "watch";

export interface DefFact {
  /** The federal / defense nexus, or "—". */
  nexus: string;
  /** How the site relates to it (adjacency, supply chain, …), or "—". */
  linkage: string;
  /** The economic-capture reading (#1663) — what the federal money does here, or "—". Distinct
   *  from H3's `capital`, which is about private operators and public subsidy. */
  capture: string;
  /** The dollars or jobs the capture reading rests on, or "—". */
  federal_flow: string;
  signal: Signal;
  group: DefGroup;
  /** Investigative-frame tag (#905): what kind of claim the cell is making. */
  sub_thesis?: string | null;
}
export interface SurvFact {
  /** Operator behind the LLC (inferred), or "—". */
  operator: string;
  /** Capital & public-subsidy note, or "—". */
  capital: string;
  signal: Signal;
  group: SurvGroup;
  /** Investigative-frame tag (#905): what kind of claim the cell is making. */
  sub_thesis?: string | null;
}

const DEF0: DefFact = {
  nexus: "—",
  linkage: "—",
  capture: "—",
  federal_flow: "—",
  signal: "watch",
  group: "watch",
};
const SURV0: SurvFact = { operator: "—", capital: "—", signal: "watch", group: "watch" };

/**
 * The per-site H2/H3 reading, indexed by slug — now built from the `hypothesis-assessments`
 * bundle feed (#308), no longer hardcoded here. Absent slugs inherit DEF0/SURV0 ("not yet
 * assessed"). Every committed cell is a real, on-the-record fact or an explicitly-tagged
 * inference, and now carries a Citation in the feed (the provenance the hardcoded table lacked).
 */
export type AssessmentIndex = Record<string, { def?: DefFact; surv?: SurvFact }>;

const asSignal = (s: string | null | undefined): Signal =>
  s === "anchor" || s === "strong" || s === "moderate" ? s : "watch";

// Narrow the feed's free `group` string to its union (an out-of-union value falls back
// to "watch" rather than passing silently through a bare cast) (#585).
const asDefGroup = (g: string | null | undefined): DefGroup =>
  g === "arsenal" || g === "federal" || g === "supply" || g === "capture" ? g : "watch";
const asSurvGroup = (g: string | null | undefined): SurvGroup =>
  g === "onrecord" || g === "subsidy" ? g : "watch";

/** Fold the `hypothesis-assessments` feed into the per-site def/surv index the hypotheses read. */
export function indexAssessments(cells: readonly HypothesisAssessmentItem[]): AssessmentIndex {
  const data: AssessmentIndex = {};
  for (const c of cells) {
    const entry = data[c.site] ?? {};
    data[c.site] = entry;
    if (c.hypothesis === "defense") {
      entry.def = {
        nexus: c.fields.nexus ?? "—",
        linkage: c.fields.linkage ?? "—",
        capture: c.fields.capture ?? "—",
        federal_flow: c.fields.federal_flow ?? "—",
        signal: asSignal(c.signal),
        group: asDefGroup(c.group),
        sub_thesis: c.sub_thesis,
      };
    } else if (c.hypothesis === "surveillance") {
      entry.surv = {
        operator: c.fields.operator ?? "—",
        capital: c.fields.capital ?? "—",
        signal: asSignal(c.signal),
        group: asSurvGroup(c.group),
        sub_thesis: c.sub_thesis,
      };
    }
  }
  return data;
}

/** A site's defense + surveillance reading, defaulting to "not yet assessed". */
export function assessmentFor(slug: string, data: AssessmentIndex): { def: DefFact; surv: SurvFact } {
  const d = data[slug];
  return { def: d?.def ?? DEF0, surv: d?.surv ?? SURV0 };
}

// --- The two continental divides (H1 grouping) --------------------------------------------------
// Basins nest under the divide they drain to — the water thesis's organizing fact. Both the
// divides and their basin membership now come from the one `./placement` table each basin is a row
// in (#1863), so adding a basin can't leave it grouped in the selector but missing from H1.

// --- Hypothesis configuration (cards, framing, columns) -----------------------------------------
export interface HypothesisConfig {
  key: HypothesisId;
  /** Hypothesis tag, H1/H2/H3. */
  n: string;
  name: string;
  accent: string;
  accentBg: string;
  accentBd: string;
  /** "Reference build" (live) or "Emerging hypothesis" (new). */
  status: string;
  statusKind: "live" | "new";
  claim: string;
  blurb: string;
  axisTitle: string;
  scoreTitle: string;
  scoreNote: string;
  footNote: string;
  /** The scorecard's column headers, in the shared `ColumnSpec` shape. */
  cols: readonly ColumnSpec[];
  /** The matching CSS grid track list, one entry per column. */
  fr: readonly string[];
}

export const HYPOTHESIS_VIEW: Record<HypothesisId, HypothesisConfig> = {
  water: {
    key: "water",
    n: "H1",
    name: "Water & Coercion",
    accent: "#1f6f4a",
    accentBg: "#e4ece4",
    accentBd: "#bcd2c4",
    status: "Reference build",
    statusKind: "live",
    claim: "Where discharge becomes leverage.",
    blurb:
      "The original thesis: hyperscale compute lands where it can pull power and water, and a data center's intake, discharge, and downstream effects are basin facts. Sites nest by drainage — two divides, eleven basins. Lima is the live, fully-assembled reference. A coercion sub-thesis (#903): in municipalities with declining populations, the receiving WWTP may be running lean on influent — below the biological-treatment minimum that keeps it in NPDES compliance. A datacenter's high-volume, consistent discharge provides the flow buffer the plant needs, structurally compelling municipal acceptance. The Clean Water Act is the backstop that makes the need non-negotiable.",
    axisTitle: "Two divides · eleven basins",
    scoreTitle: "Every point, by drainage",
    scoreNote:
      "Build phase, readiness tier, and facility status are three clocks — our progress on the site, the record it has assembled, and the plant in the ground — kept distinct.",
    footNote:
      "Tier and counts are read from each site's own exported bundle at build time. A dash means no bundle is committed yet — nothing measured; a zero means the export ran and the site carries none.",
    cols: [
      { label: "Site" },
      { label: "Watershed point" },
      { label: "Build phase" },
      { label: "Tier" },
      { label: "Documents", align: "right" },
      { label: "Records", align: "right" },
      { label: "Facility status" },
    ],
    fr: ["1.35fr", "1.2fr", "0.9fr", "0.9fr", "0.7fr", "0.66fr", "1.15fr"],
  },
  defense: {
    key: "defense",
    n: "H2",
    name: "Defense & Federal Enclave",
    accent: "#16201a",
    accentBg: "#ece8dc",
    accentBd: "#cdc8b8",
    status: "Emerging hypothesis",
    statusKind: "new",
    claim: "Where the build-out meets federal land and the defense base.",
    blurb:
      "A second reading: the same map tracks arsenals, air bases, federal research and the CHIPS build — enclaves where federal jurisdiction, clearance, and defense supply chains concentrate. Newly opened; most sites are not yet assessed, and a federal nexus is a signal, not a verdict. A capture sub-thesis (#1663): the enclave is not only geography, it is an economic structure — federal payroll and prime-award obligations concentrated in one county, land held by the United States and off the local tax rolls, and the abatement / PILOT instruments layered around it. Whether the defense base distorts the local economy the datacenter lands in, or merely sits beside it.",
    axisTitle: "Assessment so far",
    scoreTitle: "Every site, by federal nexus",
    scoreNote: "Signal is inference until a federal nexus is documented.",
    footNote:
      "Sites without an entry are not yet assessed under this thesis — that is not the same as cleared.",
    cols: [
      { label: "Site" },
      { label: "Federal / defense nexus" },
      { label: "Linkage" },
      { label: "Economic capture" },
      { label: "Signal" },
      { label: "Facility status" },
    ],
    fr: ["1.3fr", "1.6fr", "0.95fr", "1.5fr", "1.0fr", "1.1fr"],
  },
  surveillance: {
    key: "surveillance",
    n: "H3",
    name: "Consumer Surveillance",
    accent: "#566159",
    accentBg: "#e8e4d8",
    accentBd: "#cdc8b8",
    status: "Emerging hypothesis",
    statusKind: "new",
    claim: "What the compute is for, who it watches, and who's paying.",
    blurb:
      "A third reading: the operators behind shell LLCs, the public-subsidy stack that pulls them in, and the capital and data flows the facilities sit on. The consumer-surveillance thesis — opening now, mostly under investigation, with Lima's abatement on record. An end-use sub-thesis (#904): these facilities are infrastructure nodes in a consumer surveillance apparatus — behavioral tracking, financial-transaction processing, or similar mass-scale surveillance of individual consumer activity, financed in part by the public subsidies the same communities provide.",
    axisTitle: "Assessment so far",
    scoreTitle: "Every site, by operator & end-use",
    scoreNote: "Operator identity constrains the end-use inference; public subsidy is on record.",
    footNote:
      "Sites without an entry are not yet assessed under this thesis — that is not the same as cleared.",
    cols: [
      { label: "Site" },
      { label: "Operator (inferred)" },
      { label: "Capital & public subsidy" },
      { label: "Signal" },
      { label: "Facility status" },
    ],
    fr: ["1.4fr", "1.5fr", "1.6fr", "1.05fr", "1.15fr"],
  },
};

/** The hypothesis-card count line: H1 counts the network; H2/H3 count assessment progress. */
export function hypothesisCount(id: HypothesisId, data: AssessmentIndex): string {
  if (id === "water") return `${SITES.length} sites · ${groupSites("basin").length} basins`;
  const assessed = SITES.filter((s) =>
    id === "defense"
      ? assessmentFor(s.slug, data).def.group !== "watch"
      : assessmentFor(s.slug, data).surv.group !== "watch",
  ).length;
  return `${assessed} assessed · ${SITES.length - assessed} to review`;
}

/** Merge a hypothesis's static presentation config with its content from the `hypotheses` feed
 *  (#308): name/claim/blurb/status now come from bosc.hypotheses, not hardcoded. The
 *  HYPOTHESIS_VIEW content is the offline fallback for a bundle predating the hypotheses feed. */
export function hypothesisConfig(id: HypothesisId, hyp?: HypothesisItem): HypothesisConfig {
  if (!hyp) return HYPOTHESIS_VIEW[id];
  const reference = hyp.status === "reference";
  return {
    ...HYPOTHESIS_VIEW[id],
    name: hyp.name,
    claim: hyp.claim,
    blurb: hyp.thesis,
    status: reference ? "Reference build" : "Emerging hypothesis",
    statusKind: reference ? "live" : "new",
  };
}

// --- The rendered view model -------------------------------------------------------------------
// The grammar (Cell / Row / Group / AxisGroup and the cell constructors) is `./scorecard`'s, shared
// with the lens pages. A hypothesis view is that shape plus the key of the thesis it reads.
export interface HypothesisView extends ScorecardView {
  key: HypothesisId;
}

const facPill = (status: FacilityStatus): Cell => pillCell(FACILITY_STATUS_META[status]);

/**
 * Build a hypothesis's full view model: the scorecard column spec, the grouped rows (or chip
 * groups), and the framing-panel axis chips.
 *
 * Two bundle-backed lookups are threaded in as resolvers so this builder stays pure (no bundle
 * read) and a unit test can stub both: `facilityStatusOf` resolves the facility lifecycle stage
 * (#1628), and `rollupOf` resolves the site's own documents/records/tier (#1861 — it replaces the
 * Lima-only hardcoded counts this used to take). The page passes `facilityStatus` / `siteRollup`.
 */
export function buildHypothesisView(
  id: HypothesisId,
  rollupOf: (slug: string) => SiteRollup,
  data: AssessmentIndex,
  facilityStatusOf: (slug: string) => FacilityStatus,
): HypothesisView {
  const cfg = HYPOTHESIS_VIEW[id];
  const cols = columnHeads(cfg.cols);
  const gridCols = cfg.fr.join(" ");

  const groups: Group[] = [];
  const axisGroups: AxisGroup[] = [];

  if (id === "water") {
    const byBasin = new Map(groupSites("basin").map((g) => [g.label, g]));
    for (const d of DIVIDES) {
      // The banner opens the first basin of the divide that actually RENDERS, not the first one
      // in the table — a divide whose leading basin holds no sites yet still gets its heading.
      let openBanner = true;
      for (const basin of basinsOfDivide(d.key)) {
        const grp = byBasin.get(basin.label);
        if (!grp?.sites.length) continue;
        const rows: Row[] = grp.sites.map((s) => {
          const roll = rollupOf(s.slug);
          return {
            slug: s.slug,
            href: s.href,
            live: s.status === "live",
            cells: [
              siteCell(s),
              textCell(s.basin),
              pillCell(PHASE_PILL[s.status]),
              // No bundle ⇒ no computed tier: a muted dash, not a `stub` pill we'd be asserting.
              roll.tier ? pillCell(TIER_PILL[roll.tier]) : textCell("—", true),
              numCell(figure(roll.documents)),
              numCell(figure(roll.records)),
              facPill(facilityStatusOf(s.slug)),
            ],
          };
        });
        const g: Group = {
          kind: "rows",
          abbr: grp.tag,
          label: grp.label,
          count: grp.sites.length,
          rows,
          chips: [],
        };
        if (openBanner) {
          g.banner = { label: d.label, note: d.note };
          openBanner = false;
        }
        groups.push(g);
      }
    }
    axisGroups.push(
      ...DIVIDES.map((d) => ({
        label: d.label,
        chips: basinsOfDivide(d.key)
          .map((b) => ({ name: b.label, count: byBasin.get(b.label)?.sites.length ?? 0 }))
          .filter((c) => c.count > 0),
      })),
    );
    return { key: id, axisTitle: cfg.axisTitle, axisGroups, cols, gridCols, groups };
  }

  // Defense / surveillance: group by thesis category, with a "not yet assessed" chip tail.
  const isDef = id === "defense";
  const grpKey = (s: NetworkSite): string =>
    isDef ? assessmentFor(s.slug, data).def.group : assessmentFor(s.slug, data).surv.group;
  const rowFor = (s: NetworkSite): Row => {
    const dat = assessmentFor(s.slug, data);
    const defTag = dat.def.sub_thesis ? ` · [${dat.def.sub_thesis}]` : "";
    const survTag = dat.surv.sub_thesis ? ` · [${dat.surv.sub_thesis}]` : "";
    // The capture cell reads as "<what the money does> · <the figure it rests on>" so the
    // reading and its grounding never separate; "—" stays a single dash, never a fabricated pair.
    const cap =
      dat.def.capture === "—"
        ? "—"
        : dat.def.federal_flow === "—"
          ? dat.def.capture
          : `${dat.def.capture} · ${dat.def.federal_flow}`;
    const cells = isDef
      ? [
          siteCell(s),
          textCell(dat.def.nexus + defTag),
          textCell(dat.def.linkage, true),
          textCell(cap, true),
          pillCell(SIGNAL_META[dat.def.signal]),
          facPill(facilityStatusOf(s.slug)),
        ]
      : [
          siteCell(s),
          textCell(dat.surv.operator + survTag),
          textCell(dat.surv.capital),
          pillCell(SIGNAL_META[dat.surv.signal]),
          facPill(facilityStatusOf(s.slug)),
        ];
    return { slug: s.slug, href: s.href, live: s.status === "live", cells };
  };

  // [key, abbr, full label, short axis label] — the short label is explicit, not derived
  // by splitting the full label on " &" at the call site (#585).
  const cats: [string, string, string, string][] = isDef
    ? [
        ["arsenal", "MIL", "Arsenals & air bases", "Arsenals"],
        ["federal", "FED", "Federal semiconductor & research", "Federal semiconductor"],
        ["supply", "SUP", "Defense supply corridors", "Defense supply corridors"],
        ["capture", "CAP", "Federal economic capture", "Economic capture"],
      ]
    : [
        ["onrecord", "OPR", "Operator & subsidy on record", "Operator"],
        ["subsidy", "SUB", "Public-subsidy signal only", "Public-subsidy signal only"],
      ];

  for (const [key, abbr, label] of cats) {
    const sites = SITES.filter((s) => grpKey(s) === key);
    if (!sites.length) continue;
    groups.push({ kind: "rows", abbr, label, count: sites.length, rows: sites.map(rowFor), chips: [] });
  }
  const watch = SITES.filter((s) => grpKey(s) === "watch");
  if (watch.length) {
    groups.push({
      kind: "chips",
      abbr: "—",
      // `unassessed` is the claim only a HYPOTHESIS may make — the thesis has a verdict to reach
      // here and has not reached it. The lens surfaces get `unrecorded` instead (`./scorecard`).
      label: TAIL_META.unassessed.label,
      claim: "unassessed",
      count: watch.length,
      rows: [],
      chips: watch.map((s) => ({ place: s.place, dot: PHASE_PILL[s.status].dot, href: s.href })),
    });
  }
  axisGroups.push({
    chips: [
      ...cats.map(([key, , , short]) => ({
        name: short,
        count: SITES.filter((s) => grpKey(s) === key).length,
      })),
      { name: "Not yet assessed", count: watch.length },
    ],
  });

  return { key: id, axisTitle: cfg.axisTitle, axisGroups, cols, gridCols, groups };
}
