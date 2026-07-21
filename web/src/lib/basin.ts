/**
 * The basin view (design "Basin — Maumee"; the /basin redesign, branch design/basin-view) —
 * pure view-model builders so the page's data shaping unit-tests offline (the
 * `directory.ts` pattern: no bundle import, the page loads the `network` feed and passes it in).
 *
 * Discipline: every figure is computed from the registry or the `network` feed, or it is a
 * dash — never invented. The design mock's placeholder projections (a cumulative-draw curve,
 * per-site draw bars, "~890 MW proj.") have no backing feed, so the honest on-record
 * equivalents render instead: the receiving WWTPs' NPDES design flows, the assembled dilution
 * screens, and the one estimated IT load. A site with nothing on file reads [open], not a number.
 */
import type { LinePoint, RankedBarDatum } from "@watermark/charts/charts";
import type { EvidenceKind, TagKind } from "@watermark/core/evidence";
import type { ReachRouting, RoutedHydrographNetwork, WatershedNode } from "@watermark/core/feeds";
import {
  type FacilityStatus,
  type NetworkSite,
  SITE_STATUS_META,
  siteBadge,
  type SiteStatus,
} from "@watermark/core/sites";

/** Build-phase ink (design "Basin — Maumee" legend; the peer of the directory home's
 *  PHASE_COLOR): live is the forest signal, building is ink, queued/tracking step down.
 *  Phase is NOT evidence — these never touch the `--ev-*` palette. */
export const PHASE_INK: Record<SiteStatus, string> = {
  live: "var(--forest)",
  building: "var(--ink)",
  queued: "var(--ink-muted)",
  tracking: "var(--ink-faint)",
};

/** Index the `network` feed's nodes by slug (empty when the feed is absent). */
export function nodeIndex(nodes: readonly WatershedNode[]): Map<string, WatershedNode> {
  return new Map(nodes.map((n) => [n.slug, n]));
}

/** The basin's HUC-8 span, derived from the nodes on file — "04100005 – 04100009", or a
 *  single code when they all agree. Null when no node carries one (the badge then hides
 *  rather than asserting a boundary the feed doesn't). */
export function hucRange(nodes: readonly WatershedNode[]): string | null {
  const hucs = [...new Set(nodes.map((n) => n.huc8).filter(Boolean))].sort();
  if (hucs.length === 0) return null;
  const [lo, hi] = [hucs[0], hucs[hucs.length - 1]];
  return lo === hi ? lo : `${lo} – ${hi}`;
}

/**
 * The "Draw record" evidence class for a site — what the record actually holds about a
 * data-center draw at this point (NOT the municipal WWTP's own permit):
 *  - verified: a disclosed facility AND an assembled dilution screen (Lima);
 *  - inference: a facility on the record but no screened water record yet (Fort Wayne —
 *    its load is read from other filings, so any draw figure is a labelled reading);
 *  - open: nothing filed — an open question, never a zero.
 */
export function drawRecordKind(node: WatershedNode | undefined, facility: FacilityStatus): TagKind {
  if (node?.activity.has_disclosed_facility && node.screen.status === "screened") return "verified";
  if (node?.activity.has_disclosed_facility || facility !== "investigation") return "inference";
  return "open";
}

export interface BasinSiteRow {
  slug: string;
  /** The badge — codename when the site has one (BOSC, GCP), else its 3-letter mono. */
  code: string;
  place: string;
  /** Receiving-water subline from the registry (finer than the basin). */
  subbasin: string;
  phase: SiteStatus;
  phaseLabel: string;
  phaseInk: string;
  evidence: TagKind;
  href: string;
}

/** One table row per basin site — registry joined with the feed's node (when present). */
export function basinSiteRows(
  sites: readonly NetworkSite[],
  nodes: Map<string, WatershedNode>,
): BasinSiteRow[] {
  return sites.map((s) => {
    const node = nodes.get(s.slug);
    return {
      slug: s.slug,
      code: siteBadge(s),
      place: s.place,
      subbasin: s.basin,
      phase: s.status,
      phaseLabel: SITE_STATUS_META[s.status].label,
      phaseInk: PHASE_INK[s.status],
      // Facility lifecycle now rides on the network feed's node activity (#1628) — read it off the
      // node this builder already receives, so basin.ts stays pure (no bundle import).
      evidence: drawRecordKind(node, node?.activity.facility_status ?? "investigation"),
      href: s.href,
    };
  });
}

/** Build-phase split for the proportion bar — real counts, phases with zero sites dropped. */
export function phaseSplit(
  sites: readonly NetworkSite[],
): { key: SiteStatus; label: string; count: number; ink: string }[] {
  const order: SiteStatus[] = ["live", "building", "queued", "tracking"];
  return order
    .map((k) => ({
      key: k,
      label: SITE_STATUS_META[k].label,
      count: sites.filter((s) => s.status === k).length,
      ink: PHASE_INK[k],
    }))
    .filter((p) => p.count > 0);
}

/**
 * Running total of the receiving WWTPs' NPDES design flows, in the feed's
 * upstream → downstream node order — the treatment capacity any new load lands on.
 * Labels are the sites' badges (codename else mono, matching the map and the table)
 * so eight points fit the plot. Nodes without a design flow on file are skipped
 * (and counted, so the caption can say so).
 */
export function cumulativeFlowSeries(
  nodes: readonly WatershedNode[],
  sites: readonly NetworkSite[],
): { points: LinePoint[]; totalMgd: number; skipped: number } {
  const bySlug = new Map(sites.map((s) => [s.slug, s]));
  const points: LinePoint[] = [];
  // Accumulate raw and round only at the point/total boundary, so the end label always
  // agrees with `totalDesignFlow` (which sums raw values and rounds once).
  let running = 0;
  let skipped = 0;
  for (const n of nodes) {
    const flow = n.screen.design_flow_mgd;
    if (flow == null) {
      skipped += 1;
      continue;
    }
    running += flow;
    const site = bySlug.get(n.slug);
    points.push({ label: site ? siteBadge(site) : n.place, value: Math.round(running * 100) / 100 });
  }
  return { points, totalMgd: Math.round(running * 10) / 10, skipped };
}

/** Per-site receiving design flow, largest first — the ranked-bar view of the same record. */
export function designFlowBars(nodes: readonly WatershedNode[]): RankedBarDatum[] {
  return nodes
    .filter((n) => n.screen.design_flow_mgd != null)
    .map((n) => ({ label: n.place, value: n.screen.design_flow_mgd as number }))
    .sort((a, b) => b.value - a.value);
}

/**
 * The estimated IT load across the basin — a sum of per-site `it_load_mw` over the sites that
 * carry a disclosed facility. The *facility* is on the record; each load figure is a labelled
 * derivation of mixed provenance (Lima/Fort-Wayne N+1 backup reads, Van Wert's announced "up to
 * 500 MW" ceiling, Findlay's contracted take, Urbana's floor-area screen), never a disclosed
 * meter reading — so the sum is "estimated", not "disclosed" (#1702).
 */
export function estimatedItLoad(nodes: readonly WatershedNode[]): { mw: number; count: number } {
  const withLoad = nodes.filter((n) => n.activity.has_disclosed_facility && n.activity.it_load_mw != null);
  return {
    mw: withLoad.reduce((a, n) => a + (n.activity.it_load_mw as number), 0),
    count: withLoad.length,
  };
}

/** Total receiving design flow on file (MGD) + how many nodes carry one. */
export function totalDesignFlow(nodes: readonly WatershedNode[]): { mgd: number; count: number } {
  const withFlow = nodes.filter((n) => n.screen.design_flow_mgd != null);
  return {
    mgd: Math.round(withFlow.reduce((a, n) => a + (n.screen.design_flow_mgd as number), 0) * 10) / 10,
    count: withFlow.length,
  };
}

// --- routed storm hydrograph (#1184) ------------------------------------------------------

/**
 * Downsample the routed outlet hydrograph to ~`target` evenly-spaced points for the SSR
 * LineChart — the raw feed is ~480 dt-steps, far too many dots/x-labels to render. Labels are
 * the whole hour; the final step is always kept so the recession tail closes the curve.
 */
export function outletHydrographSeries(rn: RoutedHydrographNetwork, target = 16): LinePoint[] {
  const t = rn.times_hr;
  const q = rn.outlet_hydrograph_cfs;
  const n = Math.min(t.length, q.length);
  if (n === 0) return [];
  const stride = Math.max(1, Math.ceil(n / target));
  const points: LinePoint[] = [];
  for (let i = 0; i < n; i += stride) {
    points.push({ label: `${Math.round(t[i])}h`, value: Math.round(q[i]) });
  }
  if ((n - 1) % stride !== 0) {
    points.push({ label: `${Math.round(t[n - 1])}h`, value: Math.round(q[n - 1]) });
  }
  return points;
}

export interface ReachAttenuationRow {
  reach: string;
  lengthFt: number;
  inflowPeakCfs: number;
  outflowPeakCfs: number;
  attenuationPct: number;
  lagHr: number;
}

/** Per-reach attenuation/lag rows, most-attenuating reach first — the screening detail behind
 *  the outlet headline (each reach is where a channel took a bite out of the peak). */
export function reachAttenuationRows(reaches: readonly ReachRouting[]): ReachAttenuationRow[] {
  return reaches
    .map((r) => ({
      reach: r.name,
      lengthFt: r.length_ft,
      inflowPeakCfs: r.inflow_peak_cfs,
      outflowPeakCfs: r.outflow_peak_cfs,
      attenuationPct: r.attenuation_pct,
      lagHr: r.lag_hr,
    }))
    .sort((a, b) => b.attenuationPct - a.attenuationPct);
}

// The screen-status gloss the old scorecard used — kept verbatim so the gap reads as a finding.
const SCREEN_TEXT: Record<string, string> = {
  no_receiving_water: "unscreened · no ECHO receiving water",
  no_7q10: "unscreened · ungaged tributary",
  no_design_flow: "unscreened · no design flow",
  not_in_inventory: "unscreened · not in ECHO",
};

export interface DischargeRow {
  slug: string;
  /** The permitted discharger, as ECHO names it. */
  title: string;
  /** place · receiving water · NPDES id · screen state. */
  meta: string;
  /** "12 MGD design" or "—". */
  flow: string;
  evidence: EvidenceKind;
  /** Dilution-screen flag when screened (ok | tight | violation) — drives the row accent. */
  flag: string | null;
  href: string;
}

/**
 * The basin's receiving outfalls, one row per node — screened records first (they carry an
 * assembled dilution read), then the unscreened rest in drainage order. Every NPDES id here
 * is a filed permit; the [open] tag marks a screen that isn't assembled, a gap — not a zero.
 */
export function dischargeRows(
  nodes: readonly WatershedNode[],
  sites: readonly NetworkSite[],
): DischargeRow[] {
  const bySlug = new Map(sites.map((s) => [s.slug, s]));
  const rows = nodes.map((n): DischargeRow => {
    const s = bySlug.get(n.slug);
    const screened = n.screen.status === "screened";
    const screenNote =
      screened && n.screen.dilution_ratio != null
        ? `screened · ${n.screen.flag} · ${n.screen.dilution_ratio.toFixed(2)}:1`
        : (SCREEN_TEXT[n.screen.status] ?? "unscreened");
    const water = n.screen.receiving_water ?? n.receiving_water;
    return {
      slug: n.slug,
      title: n.screen.discharger || "Outfall on file",
      meta: [n.place + (s?.codename ? ` (${s.codename})` : ""), water, `NPDES ${n.screen.npdes}`, screenNote]
        .filter(Boolean)
        .join(" · "),
      flow: n.screen.design_flow_mgd != null ? `${n.screen.design_flow_mgd} MGD design` : "—",
      evidence: screened ? "verified" : "open",
      flag: screened ? (n.screen.flag ?? null) : null,
      href: s?.href ?? `/network/${n.slug}`,
    };
  });
  return [...rows.filter((r) => r.evidence === "verified"), ...rows.filter((r) => r.evidence !== "verified")];
}
