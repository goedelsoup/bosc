// The basin view's data shaping (design "Basin — Maumee") — pure over an explicit node/site
// fixture, so the evidence mapping and the on-record aggregates test offline (the
// directory.ts pattern). The doctrine under test: a gap reads [open], never a number.
import { describe, expect, it } from "vitest";

import {
  basinSiteRows,
  cumulativeFlowSeries,
  designFlowBars,
  dischargeRows,
  disclosedLoad,
  drawRecordKind,
  hucRange,
  nodeIndex,
  outletHydrographSeries,
  phaseSplit,
  reachAttenuationRows,
  totalDesignFlow,
} from "./basin";
import type { ReachRouting, RoutedHydrographNetwork, WatershedNode } from "@watermark/core/feeds";
import type { NetworkSite } from "@watermark/core/sites";

const site = (slug: string, over: Partial<NetworkSite> = {}): NetworkSite => ({
  slug,
  codename: null,
  mono: slug.slice(0, 3).toUpperCase(),
  place: slug[0].toUpperCase() + slug.slice(1),
  basin: "Test River",
  status: "queued",
  selectable: false,
  href: `/network/${slug}`,
  ...over,
});

// Type-checked like site() — no cast, so the fixture can't drift from the feeds.ts contract.
const node = (slug: string, over: Partial<WatershedNode> = {}): WatershedNode => ({
  slug,
  place: slug[0].toUpperCase() + slug.slice(1),
  county: "Test",
  huc8: "04100005",
  receiving_water: "Test River",
  drainage_path: ["Test River"],
  subtree: "Test",
  downstream: "Lake Erie",
  regime: "tributary",
  screen: { npdes: `OH00${slug.length}`, discharger: `${slug.toUpperCase()} WWTP`, status: "no_7q10" },
  grid: {},
  economy: {},
  toxics: {},
  activity: { has_disclosed_facility: false },
  ...over,
});

const screened = (slug: string, flow: number, extra: Partial<WatershedNode> = {}): WatershedNode =>
  node(slug, {
    screen: {
      npdes: "OH0000001",
      discharger: `${slug.toUpperCase()} WWTP`,
      receiving_water: "Test River",
      design_flow_mgd: flow,
      dilution_ratio: 0.5,
      flag: "violation",
      status: "screened",
    },
    ...extra,
  });

describe("basin view model (design Basin — Maumee)", () => {
  it("drawRecordKind: verified needs a disclosed facility AND a screened record; a bare facility is inference; nothing is open", () => {
    const lima = screened("lima", 1.5, { activity: { has_disclosed_facility: true, it_load_mw: 275 } });
    expect(drawRecordKind(lima, "construction")).toBe("verified");
    // A facility on the record without a screened water record — a labelled reading.
    expect(drawRecordKind(node("fort-wayne"), "live")).toBe("inference");
    expect(
      drawRecordKind(node("fort-wayne", { activity: { has_disclosed_facility: true } }), "investigation"),
    ).toBe("inference");
    // No filing at all — an open question, never a zero. Missing node included.
    expect(drawRecordKind(node("bryan"), "investigation")).toBe("open");
    expect(drawRecordKind(undefined, "investigation")).toBe("open");
  });

  it("hucRange spans the nodes on file, collapses when they agree, and hides when absent", () => {
    expect(hucRange([node("a", { huc8: "04100009" }), node("b", { huc8: "04100005" })])).toBe(
      "04100005 – 04100009",
    );
    expect(hucRange([node("a"), node("b")])).toBe("04100005");
    expect(hucRange([])).toBeNull();
  });

  it("cumulativeFlowSeries accumulates in feed order, labels by site badge, and counts skipped nodes", () => {
    const sites = [site("a", { codename: "BOSC" }), site("b"), site("c")];
    const { points, totalMgd, skipped } = cumulativeFlowSeries(
      [screened("a", 1.5), node("b"), screened("c", 12)],
      sites,
    );
    expect(points).toEqual([
      { label: "BOSC", value: 1.5 }, // codename when the site has one (matches map + table)…
      { label: "C", value: 13.5 }, // …else the 3-letter mono
    ]);
    expect(totalMgd).toBe(13.5);
    expect(skipped).toBe(1); // no design flow on file → not stacked, and said so
  });

  it("designFlowBars ranks the on-file flows largest first and drops the rest", () => {
    expect(designFlowBars([screened("a", 1.5), node("b"), screened("c", 12)])).toEqual([
      { label: "C", value: 12 },
      { label: "A", value: 1.5 },
    ]);
  });

  it("disclosedLoad and totalDesignFlow sum only what the record carries", () => {
    const nodes = [
      screened("a", 1.5, { activity: { has_disclosed_facility: true, it_load_mw: 275 } }),
      node("b", { activity: { has_disclosed_facility: true } }), // disclosed but no load figure
      screened("c", 12),
    ];
    expect(disclosedLoad(nodes)).toEqual({ mw: 275, count: 1 });
    expect(totalDesignFlow(nodes)).toEqual({ mgd: 13.5, count: 2 });
    expect(disclosedLoad([])).toEqual({ mw: 0, count: 0 });
  });

  it("basinSiteRows joins registry order with the feed and keeps phase distinct from evidence", () => {
    const sites = [site("lima", { codename: "BOSC", status: "live", basin: "Ottawa River" }), site("bryan")];
    const nodes = nodeIndex([
      screened("lima", 1.5, { activity: { has_disclosed_facility: true, it_load_mw: 275 } }),
    ]);
    const rows = basinSiteRows(sites, nodes);
    expect(rows.map((r) => r.code)).toEqual(["BOSC", "BRY"]);
    expect(rows[0]).toMatchObject({ subbasin: "Ottawa River", phaseLabel: "Live", evidence: "verified" });
    // A site the feed doesn't know yet still renders — as an open question.
    expect(rows[1].evidence).toBe("open");
  });

  it("phaseSplit counts real phases and drops empty ones", () => {
    const split = phaseSplit([site("a", { status: "live" }), site("b"), site("c")]);
    expect(split.map((p) => [p.label, p.count])).toEqual([
      ["Live", 1],
      ["Queued", 2],
    ]);
  });

  it("dischargeRows puts screened outfalls first and tags the unscreened rest [open] with the gap named", () => {
    const sites = [site("a"), site("b", { codename: "GCP" })];
    const rows = dischargeRows([node("b"), screened("a", 1.5)], sites);
    expect(rows.map((r) => r.slug)).toEqual(["a", "b"]);
    expect(rows[0]).toMatchObject({ evidence: "verified", flag: "violation", flow: "1.5 MGD design" });
    expect(rows[0].meta).toContain("screened · violation · 0.50:1");
    expect(rows[1]).toMatchObject({ evidence: "open", flag: null, flow: "—" });
    expect(rows[1].meta).toContain("(GCP)");
    expect(rows[1].meta).toContain("unscreened · ungaged tributary");
  });
});

// --- routed storm hydrograph (#1184) ------------------------------------------------------

const reach = (name: string, atten: number, lag: number, over: Partial<ReachRouting> = {}): ReachRouting => ({
  node_id: name,
  name,
  length_ft: 10000,
  slope: 0.001,
  inflow_peak_cfs: 1000,
  inflow_time_to_peak_hr: 12,
  outflow_peak_cfs: 1000 * (1 - atten / 100),
  outflow_time_to_peak_hr: 12 + lag,
  attenuation_pct: atten,
  lag_hr: lag,
  ...over,
});

const routedNet = (over: Partial<RoutedHydrographNetwork> = {}): RoutedHydrographNetwork => ({
  tier: "tier0",
  scenario: "design-storm",
  site: "Lima",
  return_period_yr: 25,
  storm_depth_in: 4.25,
  dt_hr: 1,
  times_hr: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  outlet_hydrograph_cfs: [10.4, 20, 30, 40.6, 50, 60, 70.5, 80, 90, 100.4],
  summed_hydrograph_cfs: [12, 22, 33, 44, 55, 66, 77, 88, 99, 110],
  routed_peak_cfs: 100.4,
  summed_peak_cfs: 110,
  peak_attenuation_pct: 8.7,
  routed_time_to_peak_hr: 10,
  summed_time_to_peak_hr: 8,
  lag_hr: 2,
  reaches: [],
  warnings: [],
  ...over,
});

describe("routed storm hydrograph view model (#1184)", () => {
  it("outletHydrographSeries downsamples to ~target points, labels by whole hour, and keeps the tail", () => {
    const pts = outletHydrographSeries(routedNet(), 4);
    // stride = ceil(10/4) = 3 → indices 0,3,6,9; the last step (idx 9) lands on the stride so no extra append.
    expect(pts).toEqual([
      { label: "1h", value: 10 }, // values rounded to whole cfs
      { label: "4h", value: 41 },
      { label: "7h", value: 71 },
      { label: "10h", value: 100 },
    ]);
  });

  it("outletHydrographSeries always includes the final step even when it is off-stride", () => {
    const pts = outletHydrographSeries(routedNet(), 3); // stride = ceil(10/3) = 4 → 0,4,8, then append 9
    expect(pts.map((p) => p.label)).toEqual(["1h", "5h", "9h", "10h"]);
    expect(pts[pts.length - 1]).toEqual({ label: "10h", value: 100 });
  });

  it("outletHydrographSeries is empty when the series is absent", () => {
    expect(outletHydrographSeries(routedNet({ times_hr: [], outlet_hydrograph_cfs: [] }))).toEqual([]);
  });

  it("reachAttenuationRows orders reaches by attenuation (most first) and maps the fields", () => {
    const rows = reachAttenuationRows([reach("gentle", 2, 0.5), reach("steep", 9, 1.5), reach("mid", 5, 1)]);
    expect(rows.map((r) => r.reach)).toEqual(["steep", "mid", "gentle"]);
    expect(rows[0]).toMatchObject({ reach: "steep", attenuationPct: 9, lagHr: 1.5, inflowPeakCfs: 1000 });
    expect(rows[0].outflowPeakCfs).toBeCloseTo(910);
  });
});
