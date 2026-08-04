/**
 * The network-tier lens scorecard — the whole network read on one lens (#1914, epic #1911 phase 2).
 *
 * `/lens/<id>` is the peer of `/research/hypotheses`, over the other axis: same registry, same
 * table grammar (`./scorecard`), a different dimension. What it may say is narrower, and that
 * narrowness is the whole design.
 *
 * ## What a lens column is allowed to be
 *
 * A lens carries **no verdict**, so nothing here may score, rank, or rate a site. Every column is
 * therefore a **measurement of the record** — how many rows the site's own export committed on the
 * feeds the lens declares — never a reading of the place. "Findlay has 2 hydrology scenarios"
 * is a fact about the corpus; "Findlay is at moderate environmental risk" is a verdict, and there
 * is deliberately no shape in this module that could express it.
 *
 * Two column kinds, because the bundle has two kinds of feed:
 *
 *  - `count` — a `collection`/`geojson` feed, summed across the metric's feeds. A real `0` renders
 *    as `0` (a measurement); `null` renders as a dash (nothing measured — no committed bundle).
 *  - `presence` — an `object` feed, whose manifest count is always 1 and therefore says nothing.
 *    The honest column is whether the site committed one at all, rendered as plain muted text
 *    ("on file" / "—"), **never a pill**: a pill in the evidence grammar's shape would read as a
 *    tag, and a lens has no evidentiary weight of its own to declare (#1913).
 *
 * ## Three states per site, kept apart
 *
 * The standing `null`-vs-`0` discipline (#1861), applied at the row level:
 *
 *  1. **rows** — a bundle is committed and `lensStatus` is `available`: the figures render.
 *  2. **chips, `unrecorded`** — a bundle is committed and the lens is locked. "Not on the record
 *     here" is a statement about the corpus, never about the site, and never "not yet assessed"
 *     (which is a hypothesis's evidentiary position — see `TAIL_META`).
 *  3. **chips, `unmeasured`** — no bundle at all. Nothing has been measured, which is not a zero.
 *
 * Collapsing 2 into 3 would claim an export ran that never did; collapsing 3 into 2 would claim we
 * looked and found nothing.
 *
 * ## Grouping
 *
 * Rows nest under the site's **readiness tier**, deepest first. The tier is the standing property
 * `watermark export` recomputes every run — how much record the site's own export has assembled —
 * so it answers the question a lens page actually raises ("where is this dimension worked?")
 * without inventing a per-lens depth score, which would be a verdict.
 *
 * Pure (no bundle read): the page threads the three bundle-backed lookups in as resolvers, exactly
 * as `/research/hypotheses` threads `siteRollup` / `facilityStatus`.
 */
import type { SiteTier } from "./bundle";
import { type Lens, LENSES, type LensId } from "./lenses";
import type { SectionStatus } from "./readiness";
import {
  type AxisGroup,
  type Cell,
  columnHeads,
  type ColumnSpec,
  figure,
  type Group,
  numCell,
  PHASE_PILL,
  type Row,
  type ScorecardView,
  siteCell,
  TAIL_META,
  type TailClaim,
  textCell,
  TIER_ABBR,
  TIER_DEPTH_ORDER,
  TIER_PILL,
} from "./scorecard";
import type { NetworkSite } from "./sites";

/** One measured column on a lens scorecard. */
export interface LensMetric {
  label: string;
  /**
   * The feeds this column measures. Every one must be declared by the lens (`lensView.test.ts`
   * pins it) — a column may not reach for data the lens does not say it reads.
   */
  feeds: readonly string[];
  /** `count` sums the feeds' manifest row counts; `presence` reports whether any was committed. */
  kind: "count" | "presence";
  /** What the figure is, for the table's footer. */
  gloss: string;
}

/**
 * Each lens's columns, drawn from the feeds it declares.
 *
 * This lives here rather than on the {@link Lens} because it is a **projection**: the network table
 * is one way to show a lens, the site tier (#1915) will be another, and the model should not carry
 * either one's column widths. `lenses.ts` says what a lens reads; this says how the network table
 * reports it.
 */
export const LENS_METRICS: Record<LensId, readonly LensMetric[]> = {
  land: [
    {
      label: "Places",
      feeds: ["places"],
      kind: "count",
      gloss: "profiled parcels and sites in the site's own `places` feed",
    },
    {
      label: "Enclave",
      feeds: ["enclave"],
      kind: "presence",
      gloss: "a DoD MIRTA federal-enclave record, where the land is off the county tax rolls",
    },
  ],
  power: [
    {
      label: "Grid backdrop",
      feeds: ["grid"],
      kind: "presence",
      gloss: "a cited balancing-authority / fuel-mix read for the grid the load lands on",
    },
    {
      label: "Consumer energy",
      feeds: ["consumer-energy", "energy-burden"],
      kind: "presence",
      gloss: "what households on the same grid already pay, and the burden that represents",
    },
  ],
  environment: [
    {
      label: "Scenarios",
      feeds: ["hydrology-scenarios"],
      kind: "count",
      gloss: "modelled water-balance scenarios screened against the receiving reach",
    },
    {
      label: "Air fields",
      feeds: ["air-dispersion-field"],
      kind: "count",
      gloss: "AERMOD screening fields",
    },
    {
      label: "Toxics",
      feeds: ["rsei"],
      kind: "presence",
      gloss: "an EPA RSEI toxic-release read for the site's reporting county",
    },
  ],
  economy: [
    {
      label: "Labor baseline",
      feeds: ["economics-baseline"],
      kind: "presence",
      gloss: "the localized BLS QCEW / Census employment baseline a jobs claim is measured against",
    },
    {
      label: "Carbon & water use",
      feeds: ["greenops"],
      kind: "presence",
      gloss: "the GreenOps sustainability read",
    },
  ],
  disclosure: [
    {
      label: "Documents",
      feeds: ["documents"],
      kind: "count",
      gloss: "source-document collections in the site's own corpus",
    },
    {
      label: "Records",
      feeds: ["records"],
      kind: "count",
      gloss: "structured extractions reviewed out of those documents",
    },
    {
      label: "Meetings",
      feeds: ["meetings"],
      kind: "count",
      gloss: "public-body meeting records the corpus carries",
    },
  ],
};

/** The bundle-backed lookups a lens view needs, threaded in so the builder stays pure. */
export interface LensResolvers {
  /** The site's readiness tier, or `null` when it has no committed bundle (`siteRollup`). */
  tierOf: (slug: string) => SiteTier | null;
  /** The lens's status for the site. Only ever called where `tierOf` returned a tier. */
  statusOf: (slug: string) => SectionStatus;
  /** A feed's manifest row count — `0` for a bundle without it, `null` for no bundle at all. */
  countOf: (slug: string, feed: string) => number | null;
}

/** Which of the three states a site is in under a lens. */
export type LensSiteState = "on-record" | "unrecorded" | "unmeasured";

/** Resolve a site's state — the one decision every part of the view is derived from. */
export function lensSiteState(slug: string, r: LensResolvers): LensSiteState {
  if (r.tierOf(slug) === null) return "unmeasured";
  return r.statusOf(slug) === "available" ? "on-record" : "unrecorded";
}

/** A metric's cell for one site. Never fabricates: an unmeasured site gets a dash, not a zero. */
function metricCell(slug: string, metric: LensMetric, r: LensResolvers): Cell {
  const counts = metric.feeds.map((f) => r.countOf(slug, f));
  // A single `null` among them means the whole site is unmeasured (no bundle), not that one feed
  // is missing — `countOf` reports 0 for a committed bundle that simply lacks the feed.
  if (counts.some((c) => c === null)) return metric.kind === "count" ? numCell("—") : textCell("—", true);
  const total = counts.reduce<number>((n, c) => n + (c ?? 0), 0);
  if (metric.kind === "count") return numCell(figure(total));
  // Presence is plain muted text, never a pill: a lens declares no evidentiary weight (#1913).
  return total > 0 ? textCell("on file") : textCell("—", true);
}

/** One lens metric read for a single site — the site-tier peer of a scorecard column (#1915). */
export interface LensMetricReading {
  label: string;
  gloss: string;
  kind: LensMetric["kind"];
  /** The rendered figure: a count, "on file", or "—" where nothing was measured. */
  text: string;
  /** Whether the site actually committed anything here — what a lede leads with, or declines to. */
  present: boolean;
}

/**
 * What this lens's record consists of on one site — the same measurement the network scorecard
 * makes, for a single row.
 *
 * The site-tier lens landings lead with this because it is the only thing a lens can honestly say
 * about a site before its own reading exists: *how much of this dimension the record carries here*.
 * It is a statement about the corpus, cited by construction (manifest row counts), and it reaches
 * no verdict — which is the whole constraint (#1911).
 */
export function lensMetricReadings(
  id: LensId,
  slug: string,
  countOf: LensResolvers["countOf"],
): LensMetricReading[] {
  const r: LensResolvers = { tierOf: () => null, statusOf: () => "locked", countOf };
  return LENS_METRICS[id].map((m) => {
    const cell = metricCell(slug, m, r);
    const text = cell.text ?? "—";
    return { label: m.label, gloss: m.gloss, kind: m.kind, text, present: text !== "—" && text !== "0" };
  });
}

/** The lens table's columns: the site, its build phase, then one column per declared metric. */
function lensColumns(metrics: readonly LensMetric[]): { cols: readonly ColumnSpec[]; fr: string[] } {
  return {
    cols: [
      { label: "Site" },
      { label: "Watershed point" },
      { label: "Build phase" },
      ...metrics.map((m): ColumnSpec => ({ label: m.label, align: "right" as const })),
    ],
    fr: ["1.35fr", "1.2fr", "0.9fr", ...metrics.map(() => "0.85fr")],
  };
}

/** The footer note: what each column counts, plus the standing dash-vs-zero rule. */
export function lensFootNote(id: LensId): string {
  const parts = LENS_METRICS[id].map((m) => `${m.label} — ${m.gloss}`);
  return `${parts.join(". ")}. Every figure is read from the site's own exported bundle at build time. A dash means no bundle is committed yet — nothing measured; a zero means the export ran and the site carries none. A lens reaches no verdict, so none of these columns ranks a site.`;
}

/** How many sites sit in each state — the framing panel's axis chips and the card count line. */
export function lensNetworkCounts(
  sites: readonly NetworkSite[],
  r: LensResolvers,
): Record<LensSiteState, number> {
  const out: Record<LensSiteState, number> = { "on-record": 0, unrecorded: 0, unmeasured: 0 };
  for (const s of sites) out[lensSiteState(s.slug, r)] += 1;
  return out;
}

/** The lens card's count line — how much of the network this reading actually reaches. */
export function lensCount(sites: readonly NetworkSite[], r: LensResolvers): string {
  const n = lensNetworkCounts(sites, r);
  return `${n["on-record"]} on the record · ${sites.length - n["on-record"]} to assemble`;
}

/** A lens view is the shared scorecard shape plus the id of the reading it renders. */
export interface LensView extends ScorecardView {
  key: LensId;
  lens: Lens;
}

/** Build a lens's whole-network view: tier-grouped rows, then the two chip tails. */
export function buildLensView(id: LensId, sites: readonly NetworkSite[], r: LensResolvers): LensView {
  const lens = LENSES[id];
  const metrics = LENS_METRICS[id];
  const { cols, fr } = lensColumns(metrics);

  const state = new Map(sites.map((s) => [s.slug, lensSiteState(s.slug, r)]));
  const groups: Group[] = [];

  // --- rows, grouped by the site's readiness tier, deepest first ---
  for (const tier of TIER_DEPTH_ORDER) {
    const inTier = sites.filter((s) => state.get(s.slug) === "on-record" && r.tierOf(s.slug) === tier);
    if (!inTier.length) continue;
    groups.push({
      kind: "rows",
      abbr: TIER_ABBR[tier],
      label: `${TIER_PILL[tier].label} sites`,
      count: inTier.length,
      rows: inTier.map(
        (s): Row => ({
          slug: s.slug,
          href: s.href,
          live: s.status === "live",
          cells: [
            siteCell(s),
            textCell(s.basin),
            { kind: "pill", pill: PHASE_PILL[s.status] },
            ...metrics.map((m) => metricCell(s.slug, m, r)),
          ],
        }),
      ),
      chips: [],
    });
  }

  // --- the two tails, in that order: looked-and-found-nothing, then never-looked ---
  const tail = (claim: TailClaim, want: LensSiteState): void => {
    const inState = sites.filter((s) => state.get(s.slug) === want);
    if (!inState.length) return;
    groups.push({
      kind: "chips",
      abbr: "—",
      label: TAIL_META[claim].label,
      claim,
      count: inState.length,
      rows: [],
      chips: inState.map((s) => ({ place: s.place, dot: PHASE_PILL[s.status].dot, href: s.href })),
    });
  };
  tail("unrecorded", "unrecorded");
  tail("unmeasured", "unmeasured");

  const counts = lensNetworkCounts(sites, r);
  const axisGroups: AxisGroup[] = [
    {
      chips: [
        { name: "On the record", count: counts["on-record"] },
        { name: TAIL_META.unrecorded.label, count: counts.unrecorded },
        { name: TAIL_META.unmeasured.label, count: counts.unmeasured },
      ],
    },
  ];

  return {
    key: id,
    lens,
    axisTitle: "Across the network",
    axisGroups,
    cols: columnHeads(cols),
    gridCols: fr.join(" "),
    groups,
  };
}
