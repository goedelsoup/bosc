/**
 * The directory's three-lens model (#308 "Directory" dictate) — one network, read three ways.
 *
 * The /research/hypotheses index reorganizes the SAME 32 sites around one of three hypotheses:
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
 */
import type { SiteTier } from "./bundle";
import type { FacilityStatus, HypothesisAssessmentItem, HypothesisItem } from "./feeds";
import {
  FACILITY_STATUS_META,
  groupSites,
  type NetworkSite,
  SITES,
  siteBadge,
  type SiteRollup,
  type SiteStatus,
} from "./sites";

export type DirLens = "water" | "defense" | "surveillance";

/** Display order of the lens cards / panes (water is the default, live thesis). */
export const LENS_ORDER: readonly DirLens[] = ["water", "defense", "surveillance"];

/** The strength of a per-site signal under H2/H3 — inference until a nexus is documented. */
export type Signal = "anchor" | "strong" | "moderate" | "watch";

interface Swatch {
  label: string;
  color: string;
  bg: string;
  dot: string;
}

export const SIGNAL_META: Record<Signal, Swatch> = {
  anchor: { label: "Anchor case", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  strong: { label: "Strong signal", color: "#1f6f4a", bg: "#e4ece4", dot: "#3f8a63" },
  moderate: { label: "Moderate", color: "#566159", bg: "#e8e4d8", dot: "#8c9389" },
  watch: { label: "Under investigation", color: "#8c9389", bg: "#faf8f1", dot: "#cdc8b8" },
};

/** Build-phase pill swatches (the hex peer of `SITE_STATUS_META`'s CSS classes — the directory
 *  renders pills inline, like the facility pill, rather than through the switcher's class set). */
export const PHASE_PILL: Record<SiteStatus, Swatch> = {
  live: { label: "Live", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  building: { label: "Building", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  queued: { label: "Queued", color: "#9a6a14", bg: "#efe6d0", dot: "#9a6a14" },
  tracking: { label: "Tracking", color: "#566159", bg: "#e8e4d8", dot: "#8c9389" },
};

/** Readiness-tier pill swatches (#1861) — the manifest `readiness.tier`, a THIRD clock beside the
 *  build phase (our progress on the website) and the facility status (the plant in the ground).
 *  This one is neither: it is how much record the site's own export has actually assembled, and
 *  unlike the other two it is computed at every export rather than hand-maintained. */
export const TIER_PILL: Record<SiteTier, Swatch> = {
  reference: { label: "Reference", color: "#1f6f4a", bg: "#e4ece4", dot: "#1f6f4a" },
  case: { label: "Case", color: "#1f6f4a", bg: "#e4ece4", dot: "#3f8a63" },
  backdrop: { label: "Backdrop", color: "#566159", bg: "#e8e4d8", dot: "#8c9389" },
  stub: { label: "Stub", color: "#8c9389", bg: "#faf8f1", dot: "#cdc8b8" },
};

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
 * inference, and now carries a Citation in the feed (the provenance LENS_DATA lacked).
 */
export type LensData = Record<string, { def?: DefFact; surv?: SurvFact }>;

const asSignal = (s: string | null | undefined): Signal =>
  s === "anchor" || s === "strong" || s === "moderate" ? s : "watch";

// Narrow the feed's free `group` string to its union (an out-of-union value falls back
// to "watch" rather than passing silently through a bare cast) (#585).
const asDefGroup = (g: string | null | undefined): DefGroup =>
  g === "arsenal" || g === "federal" || g === "supply" || g === "capture" ? g : "watch";
const asSurvGroup = (g: string | null | undefined): SurvGroup =>
  g === "onrecord" || g === "subsidy" ? g : "watch";

/** Fold the `hypothesis-assessments` feed into the per-site def/surv index the lenses read. */
export function indexAssessments(cells: readonly HypothesisAssessmentItem[]): LensData {
  const data: LensData = {};
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
export function lensDatum(slug: string, data: LensData): { def: DefFact; surv: SurvFact } {
  const d = data[slug];
  return { def: d?.def ?? DEF0, surv: d?.surv ?? SURV0 };
}

// --- The two continental divides (water lens grouping) ------------------------------------------
// Basins nest under the divide they drain to — the water thesis's organizing fact. Labels match
// `PLACEMENT`'s basin names so `groupSites("basin")` keys line up.
const DIVIDES: readonly { label: string; note: string; basins: readonly string[] }[] = [
  {
    label: "Lake Erie drainage",
    note: "north — into Lake Erie",
    basins: ["Maumee", "Portage", "Sandusky", "Cuyahoga"],
  },
  {
    label: "Ohio River drainage",
    note: "south — into the Ohio & Mississippi",
    basins: ["Great Miami", "Little Miami", "Scioto", "Muskingum", "Mahoning", "Hocking", "Ohio Brush Creek"],
  },
];

// --- Lens configuration (cards, framing, columns) ----------------------------------------------
export interface LensConfig {
  key: DirLens;
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
  cols: readonly { label: string; align?: "right" }[];
  fr: readonly string[];
}

export const LENSES: Record<DirLens, LensConfig> = {
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

/** The lens-card count line: the water lens counts the network; H2/H3 count assessment progress. */
export function lensCount(lens: DirLens, data: LensData): string {
  if (lens === "water") return `${SITES.length} sites · ${groupSites("basin").length} basins`;
  const assessed = SITES.filter((s) =>
    lens === "defense"
      ? lensDatum(s.slug, data).def.group !== "watch"
      : lensDatum(s.slug, data).surv.group !== "watch",
  ).length;
  return `${assessed} assessed · ${SITES.length - assessed} to review`;
}

/** Merge a lens's static presentation config with its content from the `hypotheses` feed (#308):
 *  name/claim/blurb/status now come from bosc.hypotheses, not hardcoded. The LENSES content is the
 *  offline fallback for a bundle that predates the hypotheses feed. */
export function lensConfig(lens: DirLens, hyp?: HypothesisItem): LensConfig {
  if (!hyp) return LENSES[lens];
  const reference = hyp.status === "reference";
  return {
    ...LENSES[lens],
    name: hyp.name,
    claim: hyp.claim,
    blurb: hyp.thesis,
    status: reference ? "Reference build" : "Emerging hypothesis",
    statusKind: reference ? "live" : "new",
  };
}

// --- The rendered view model -------------------------------------------------------------------
export interface AxisGroup {
  label?: string;
  chips: { name: string; count: number }[];
}
export type CellKind = "site" | "text" | "num" | "pill";
export interface Cell {
  kind: CellKind;
  // site
  badge?: string;
  place?: string;
  badgeBg?: string;
  badgeColor?: string;
  // text / num
  text?: string;
  muted?: boolean;
  // pill
  pill?: Swatch;
}
export interface Row {
  slug: string;
  /**
   * Where the row goes: the site's OWN page (#1862). The registry href — Lima → `SITE_BASE`,
   * every other site → `/network/<slug>` — carried through **without** the deploy base, which
   * the page applies at render with `withBase`, exactly as the switcher does. Every registered
   * site has a real destination (`[site].astro` renders the non-selectable ones), so a `queued`
   * or `tracking` row lands on its watch page rather than a dead end.
   */
  href: string;
  live: boolean;
  cells: Cell[];
}
export interface Group {
  kind: "rows" | "chips";
  abbr: string;
  label: string;
  count: number;
  /** Set on the first basin group of a divide (water lens) — the divide banner above it. */
  divide?: { label: string; note: string };
  rows: Row[];
  /** A not-yet-assessed site under H2/H3. It routes like a row (#1862) — "not assessed under
   *  this thesis" is a statement about the thesis, not a reason to strand the site. */
  chips: { place: string; dot: string; href: string }[];
}
export interface LensView {
  key: DirLens;
  axisTitle: string;
  axisGroups: AxisGroup[];
  cols: { label: string; align: "left" | "right" }[];
  gridCols: string;
  groups: Group[];
}

const siteCell = (s: NetworkSite): Cell => {
  const live = s.status === "live";
  const codename = Boolean(s.codename);
  return {
    kind: "site",
    badge: siteBadge(s),
    place: s.place,
    badgeBg: live ? "#1f6f4a" : codename ? "#ece8dc" : "#e8e4d8",
    badgeColor: live ? "#f5f2ea" : codename ? "#1f6f4a" : "#566159",
  };
};
const textCell = (t: string, muted = false): Cell => {
  const empty = !t || t === "—";
  return { kind: "text", text: t || "—", muted: muted || empty };
};
const numCell = (t: string): Cell => ({ kind: "num", text: t, muted: t === "—" });
/** A rolled-up figure for the scorecard: thousands-separated, or "—" when nothing was measured
 *  (`null` = no committed bundle). A real 0 renders as "0" — it is a measurement, not a gap. */
const figure = (n: number | null): string => (n === null ? "—" : n.toLocaleString("en-US"));
const pillCell = (s: Swatch): Cell => ({ kind: "pill", pill: s });

const facPill = (status: FacilityStatus): Cell => pillCell(FACILITY_STATUS_META[status]);

/**
 * Build a lens's full view model: the scorecard column spec, the grouped rows (or chip groups),
 * and the framing-panel axis chips.
 *
 * Two bundle-backed lookups are threaded in as resolvers so this builder stays pure (no bundle
 * read) and a unit test can stub both: `facilityStatusOf` resolves the facility lifecycle stage
 * (#1628), and `rollupOf` resolves the site's own documents/records/tier (#1861 — it replaces the
 * Lima-only hardcoded counts this used to take). The page passes `facilityStatus` / `siteRollup`.
 */
export function buildLens(
  lens: DirLens,
  rollupOf: (slug: string) => SiteRollup,
  data: LensData,
  facilityStatusOf: (slug: string) => FacilityStatus,
): LensView {
  const cfg = LENSES[lens];
  const cols = cfg.cols.map((c) => ({ label: c.label, align: c.align ?? ("left" as const) }));
  const gridCols = cfg.fr.join(" ");

  const groups: Group[] = [];
  const axisGroups: AxisGroup[] = [];

  if (lens === "water") {
    const byBasin = new Map(groupSites("basin").map((g) => [g.label, g]));
    for (const d of DIVIDES) {
      d.basins.forEach((basinLabel, i) => {
        const grp = byBasin.get(basinLabel);
        if (!grp?.sites.length) return;
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
        if (i === 0) g.divide = { label: d.label, note: d.note };
        groups.push(g);
      });
    }
    axisGroups.push(
      ...DIVIDES.map((d) => ({
        label: d.label,
        chips: d.basins
          .map((b) => ({ name: b, count: byBasin.get(b)?.sites.length ?? 0 }))
          .filter((c) => c.count > 0),
      })),
    );
    return { key: lens, axisTitle: cfg.axisTitle, axisGroups, cols, gridCols, groups };
  }

  // Defense / surveillance: group by thesis category, with a "not yet assessed" chip tail.
  const isDef = lens === "defense";
  const grpKey = (s: NetworkSite): string =>
    isDef ? lensDatum(s.slug, data).def.group : lensDatum(s.slug, data).surv.group;
  const rowFor = (s: NetworkSite): Row => {
    const dat = lensDatum(s.slug, data);
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
      label: "Not yet assessed under this thesis",
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

  return { key: lens, axisTitle: cfg.axisTitle, axisGroups, cols, gridCols, groups };
}
