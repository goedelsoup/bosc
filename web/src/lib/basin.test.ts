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
  phaseSplit,
  totalDesignFlow,
} from "./basin";
import type { WatershedNode } from "./feeds";
import type { NetworkSite } from "./sites";

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
