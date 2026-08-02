import { describe, expect, it } from "vitest";
import {
  buildLens,
  featuredSites,
  indexAssessments,
  LENS_ORDER,
  lensConfig,
  lensCount,
  lensDatum,
  TIER_DEPTH_ORDER,
  TIER_PILL,
} from "./directory";
import type { FacilityStatus, HypothesisAssessmentItem, HypothesisItem } from "./feeds";
import { SITE_BASE } from "./routes";
import { SITES, type SiteRollup } from "./sites";

// Pure stubs for buildLens's two bundle-backed lookups — the real page passes `facilityStatus`
// (#1628) and `siteRollup` (#1861); these keep the unit test offline (no bundle). The rollup stub
// covers the four cases the renderer must distinguish: the reference build, a worked `case`, a
// built-but-empty site (real zeros), and a registered site with no bundle at all (nulls).
const FAC_STATUS = (slug: string): FacilityStatus => (slug === "lima" ? "construction" : "investigation");

const ROLLUPS: Record<string, SiteRollup> = {
  lima: { documents: 3247, records: 56, tier: "reference" },
  "bowling-green": { documents: 8, records: 5, tier: "case" },
  sandusky: { documents: 0, records: 0, tier: "stub" },
};
// Every other slug is registered but unbuilt — nothing measured.
const NO_BUNDLE: SiteRollup = { documents: null, records: null, tier: null };
const ROLLUP = (slug: string): SiteRollup => ROLLUPS[slug] ?? NO_BUNDLE;

// The committed (site x hypothesis) cells, as they arrive from the `hypothesis-assessments`
// feed. Mirrors data/hypotheses/**; the Python port-parity test guards these against LENS_DATA.
const CELLS: HypothesisAssessmentItem[] = [
  {
    site: "lima",
    hypothesis: "defense",
    signal: "anchor",
    tag: "verified",
    group: "arsenal",
    fields: { nexus: "Lima Army Tank Plant (JSMC)", linkage: "Co-located · Allen Co." },
    citations: [],
  },
  {
    site: "springfield",
    hypothesis: "defense",
    signal: "moderate",
    tag: "verified",
    group: "arsenal",
    fields: { nexus: "Springfield-Beckley ANGB", linkage: "Adjacent · NASIC nearby" },
    citations: [],
  },
  {
    site: "wpafb",
    hypothesis: "defense",
    signal: "strong",
    tag: "verified",
    group: "arsenal",
    fields: { nexus: "Wright-Patterson AFB", linkage: "Adjacent · Mad R. terminus" },
    citations: [],
  },
  {
    site: "new-albany",
    hypothesis: "defense",
    signal: "moderate",
    tag: "verified",
    group: "federal",
    fields: { nexus: "CHIPS semiconductor megasite", linkage: "Federal program" },
    citations: [],
  },
  {
    site: "columbus",
    hypothesis: "defense",
    signal: "moderate",
    tag: "verified",
    group: "federal",
    fields: { nexus: "DLA Land & Maritime", linkage: "Supply chain" },
    citations: [],
  },
  {
    site: "lordstown",
    hypothesis: "defense",
    signal: "watch",
    tag: "inference",
    group: "supply",
    fields: { nexus: "Defense-battery corridor", linkage: "Supply chain (signal)" },
    citations: [],
  },
  {
    site: "lima",
    hypothesis: "surveillance",
    signal: "anchor",
    tag: "verified",
    group: "onrecord",
    fields: { operator: "Project BOSC", capital: "CRA #548-25 · 15 yr / 75%" },
    citations: [],
  },
  {
    site: "hamilton-middletown",
    hypothesis: "surveillance",
    signal: "watch",
    tag: "open",
    group: "subsidy",
    fields: { operator: "—", capital: "Municipal power + CRA (signal)" },
    citations: [],
  },
  {
    site: "new-albany",
    hypothesis: "surveillance",
    signal: "moderate",
    tag: "inference",
    group: "onrecord",
    fields: { operator: "Hyperscaler cluster (inferred)", capital: "JobsOhio · TIF (inference)" },
    citations: [],
  },
  {
    site: "columbus",
    hypothesis: "surveillance",
    signal: "watch",
    tag: "open",
    group: "subsidy",
    fields: { operator: "—", capital: "Enterprise-zone abatement (signal)" },
    citations: [],
  },
];
const DATA = indexAssessments(CELLS);

describe("directory lenses — one network, read three ways (#308)", () => {
  it("orders the lenses water → defense → surveillance (water is the live default)", () => {
    expect(LENS_ORDER).toEqual(["water", "defense", "surveillance"]);
  });

  it("water lens groups all sites by basin, nested under the two divides", () => {
    const v = buildLens("water", ROLLUP, DATA, FAC_STATUS);
    expect(v.groups).toHaveLength(11); // eleven basins
    const total = v.groups.reduce((n, g) => n + g.rows.length, 0);
    expect(total).toBe(SITES.length);
    // Exactly two groups open a divide banner (Lake Erie, Ohio River), in drainage order.
    const divides = v.groups.filter((g) => g.divide).map((g) => g.divide?.label);
    expect(divides).toEqual(["Lake Erie drainage", "Ohio River drainage"]);
    // Lake Erie drains first: Maumee leads, the Ohio-River basins follow.
    expect(v.groups.map((g) => g.label)).toEqual([
      "Maumee",
      "Portage",
      "Sandusky",
      "Cuyahoga",
      "Great Miami",
      "Little Miami",
      "Scioto",
      "Muskingum",
      "Mahoning",
      "Hocking",
      "Ohio Brush Creek",
    ]);
  });

  it("water lens rolls each site's OWN bundle counts up per row, not Lima's alone (#1861)", () => {
    const v = buildLens("water", ROLLUP, DATA, FAC_STATUS);
    const rows = v.groups.flatMap((g) => g.rows);
    const row = (slug: string) => rows.find((r) => r.slug === slug);
    // cols: site, watershed, phase, tier, documents, records, facility
    expect(v.cols.map((c) => c.label)).toEqual([
      "Site",
      "Watershed point",
      "Build phase",
      "Tier",
      "Documents",
      "Records",
      "Facility status",
    ]);
    expect(v.gridCols.split(" ")).toHaveLength(v.cols.length); // one width per column
    expect([row("lima")?.cells[4].text, row("lima")?.cells[5].text]).toEqual(["3,247", "56"]);
    // The symptom this fixes: a worked peer used to read "—/—" beside a rolled-up facility pill.
    expect([row("bowling-green")?.cells[4].text, row("bowling-green")?.cells[5].text]).toEqual(["8", "5"]);
  });

  it("distinguishes a measured zero from an unmeasured dash — the two are different claims", () => {
    const v = buildLens("water", ROLLUP, DATA, FAC_STATUS);
    const rows = v.groups.flatMap((g) => g.rows);
    // Built, but its export carries nothing: a real 0, rendered un-muted — a measurement.
    const sandusky = rows.find((r) => r.slug === "sandusky");
    expect(sandusky?.cells[4].text).toBe("0");
    expect(sandusky?.cells[4].muted).toBe(false);
    // No committed bundle: a muted dash, never a fabricated zero.
    for (const r of rows) {
      if (["lima", "bowling-green", "sandusky"].includes(r.slug)) continue;
      expect(r.cells[4].text).toBe("—");
      expect(r.cells[5].text).toBe("—");
      expect(r.cells[4].muted).toBe(true);
    }
  });

  it("surfaces readiness.tier as its own pill — and withholds it where no export produced one", () => {
    const v = buildLens("water", ROLLUP, DATA, FAC_STATUS);
    const rows = v.groups.flatMap((g) => g.rows);
    const tier = (slug: string) => rows.find((r) => r.slug === slug)?.cells[3];
    expect(tier("lima")?.pill).toEqual(TIER_PILL.reference);
    expect(tier("bowling-green")?.pill).toEqual(TIER_PILL.case);
    // An empty stub and a worked case are no longer visually identical (the #1861 complaint).
    expect(tier("sandusky")?.pill).toEqual(TIER_PILL.stub);
    expect(tier("sandusky")?.pill).not.toEqual(tier("bowling-green")?.pill);
    // An unbuilt site gets a dash, not a `stub` pill — that would assert a tier nothing computed.
    const unbuilt = rows.find((r) => !["lima", "bowling-green", "sandusky"].includes(r.slug));
    expect(unbuilt?.cells[3].pill).toBeUndefined();
    expect(unbuilt?.cells[3].text).toBe("—");
  });

  it("routes every row to the site it names — the directory's click-through (#1862)", () => {
    const v = buildLens("water", ROLLUP, DATA, FAC_STATUS);
    const rows = v.groups.flatMap((g) => g.rows);
    const href = (slug: string) => rows.find((r) => r.slug === slug)?.href;
    // Lima is the one site whose URL id isn't its slug — it must land on the re-rooted base,
    // never a fabricated /network/lima (which no route serves).
    expect(href("lima")).toBe(SITE_BASE);
    expect(href("lima")).not.toBe("/network/lima");
    // Every other site routes to its own /network/<slug> page, including the unbuilt ones:
    // a queued/tracking row lands on its watch page rather than a dead end.
    expect(href("bowling-green")).toBe("/network/bowling-green");
    expect(href("toledo")).toBe("/network/toledo");
    // No row is stranded, and none carries the deploy base — the page applies that at render.
    expect(rows).toHaveLength(SITES.length);
    for (const r of rows) {
      expect(r.href).toBe(SITES.find((s) => s.slug === r.slug)?.href);
      expect(r.href.startsWith("/network/")).toBe(true);
    }
  });

  it("routes the not-yet-assessed chips too — H2/H3 leave no site unreachable (#1862)", () => {
    for (const lens of ["defense", "surveillance"] as const) {
      const v = buildLens(lens, ROLLUP, DATA, FAC_STATUS);
      const dests = [
        ...v.groups.flatMap((g) => g.rows).map((r) => r.href),
        ...v.groups.flatMap((g) => g.chips).map((c) => c.href),
      ];
      // Rows + chips cover the whole network, and every one of them goes somewhere real.
      expect(dests).toHaveLength(SITES.length);
      expect(new Set(dests)).toEqual(new Set(SITES.map((s) => s.href)));
    }
  });

  it("defense lens groups assessed sites and sweeps the rest into a 'not yet assessed' chip tail", () => {
    const v = buildLens("defense", ROLLUP, DATA, FAC_STATUS);
    const rowGroups = v.groups.filter((g) => g.kind === "rows");
    const chipGroups = v.groups.filter((g) => g.kind === "chips");
    expect(rowGroups.map((g) => [g.abbr, g.count])).toEqual([
      ["MIL", 3], // Lima, Springfield, WPAFB
      ["FED", 2], // New Albany, Columbus
      ["SUP", 1], // Lordstown
    ]);
    expect(chipGroups).toHaveLength(1);
    expect(chipGroups[0].count).toBe(SITES.length - 6);
    // No site is dropped: rows + chips cover the whole network.
    const covered = rowGroups.reduce((n, g) => n + g.rows.length, 0) + chipGroups[0].chips.length;
    expect(covered).toBe(SITES.length);
  });

  it("surveillance lens splits on-record from signal-only, with the rest in the chip tail", () => {
    const v = buildLens("surveillance", ROLLUP, DATA, FAC_STATUS);
    const rowGroups = v.groups.filter((g) => g.kind === "rows");
    expect(rowGroups.map((g) => [g.abbr, g.count])).toEqual([
      ["OPR", 2], // Lima, New Albany
      ["SUB", 2], // Hamilton·Middletown, Columbus
    ]);
    const chips = v.groups.find((g) => g.kind === "chips");
    expect(chips?.count).toBe(SITES.length - 4);
  });

  it("counts assessment progress in the lens-card line, and the network in the water line", () => {
    expect(lensCount("water", DATA)).toBe(`${SITES.length} sites · 11 basins`);
    expect(lensCount("defense", DATA)).toBe(`6 assessed · ${SITES.length - 6} to review`);
    expect(lensCount("surveillance", DATA)).toBe(`4 assessed · ${SITES.length - 4} to review`);
  });

  it("defaults an unassessed site to 'watch' under both theses — a dash, not a verdict", () => {
    const d = lensDatum("toledo", DATA);
    expect(d.def.group).toBe("watch");
    expect(d.def.nexus).toBe("—");
    expect(d.surv.group).toBe("watch");
    // Lima is the worked anchor under both.
    expect(lensDatum("lima", DATA).def.signal).toBe("anchor");
    expect(lensDatum("lima", DATA).surv.group).toBe("onrecord");
  });

  it("an empty feed leaves every site unassessed (graceful, no crash)", () => {
    const empty = indexAssessments([]);
    expect(lensDatum("lima", empty).def.group).toBe("watch");
    expect(lensCount("defense", empty)).toBe(`0 assessed · ${SITES.length} to review`);
  });

  it("sub_thesis flows through indexAssessments and renders as a bracketed suffix (#905)", () => {
    const cellsWithTag: HypothesisAssessmentItem[] = [
      ...CELLS,
      {
        site: "lima",
        hypothesis: "surveillance",
        signal: "anchor",
        tag: "verified",
        sub_thesis: "capture",
        group: "onrecord",
        fields: { operator: "Project BOSC", capital: "CRA #548-25 · 15 yr / 75%" },
        citations: [],
      },
    ];
    const data = indexAssessments(cellsWithTag);
    expect(lensDatum("lima", data).surv.sub_thesis).toBe("capture");
    // The scorecard row appends · [capture] to the operator cell.
    const v = buildLens("surveillance", ROLLUP, data, FAC_STATUS);
    const limaRow = v.groups.flatMap((g) => g.rows).find((r) => r.slug === "lima");
    expect(limaRow?.cells[1].text).toBe("Project BOSC · [capture]");
  });

  it("lensConfig sources name/claim/blurb/status from the hypotheses feed (not hardcoded)", () => {
    const hyp: HypothesisItem = {
      id: "defense",
      number: "H2",
      name: "FEED NAME",
      claim: "FEED CLAIM",
      thesis: "FEED THESIS",
      status: "emerging",
      signals: [],
      groups: [],
      fields: [],
      related_docs: [],
      predicted_evidence: [],
    };
    const cfg = lensConfig("defense", hyp);
    expect(cfg.name).toBe("FEED NAME");
    expect(cfg.claim).toBe("FEED CLAIM");
    expect(cfg.blurb).toBe("FEED THESIS");
    expect(cfg.status).toBe("Emerging hypothesis");
    expect(cfg.statusKind).toBe("new");
    // Presentation (accent, columns) stays local to the frontend.
    expect(cfg.accent).toBe("#16201a");
    // Falls back to the built-in config when the feed lacks the hypothesis.
    expect(lensConfig("defense").name).toBe("Defense & Federal Enclave");
  });
});

describe("featured slice — ranked by assembled record, not registry order (#1864)", () => {
  it("ranks on the readiness tier first, deepest tier leading", () => {
    const slugs = featuredSites(ROLLUP, 8).map((s) => s.slug);
    // The three measured sites lead, in tier depth order — reference, case, stub.
    expect(slugs.slice(0, 3)).toEqual(["lima", "bowling-green", "sandusky"]);
    // The bug this fixes: `SITES.slice(0, 8)` ranked by nothing, so five registered-but-unbuilt
    // sites outranked the worked `case` at registry position 6 and the built site at 23 never
    // surfaced at all.
    expect(SITES.slice(0, 8).map((s) => s.slug)).not.toContain("sandusky");
    for (const unbuilt of ["fort-wayne", "urbana", "defiance"]) {
      expect(slugs.indexOf(unbuilt)).toBeGreaterThan(slugs.indexOf("bowling-green"));
    }
  });

  it("sorts an unmeasured site BELOW a measured one, never scoring it as a stub", () => {
    // `tier: null` (no committed bundle) is not the shallowest tier — it is no measurement at all,
    // and it must not outrank a site whose export genuinely produced zeros.
    const slugs = featuredSites(ROLLUP, SITES.length).map((s) => s.slug);
    const measured = ["lima", "bowling-green", "sandusky"];
    const lastMeasured = Math.max(...measured.map((s) => slugs.indexOf(s)));
    expect(lastMeasured).toBe(measured.length - 1);
    // …and the unbuilt tail keeps registry order, so the slice is stable between builds.
    expect(slugs.slice(measured.length)).toEqual(
      SITES.filter((s) => !measured.includes(s.slug)).map((s) => s.slug),
    );
  });

  it("breaks a tier tie on the site's own records, then documents", () => {
    // Three registry slugs stood up as same-tier peers; every other site stays unbuilt.
    const PEERS: Record<string, SiteRollup> = {
      toledo: { documents: 900, records: 2, tier: "case" },
      "van-wert": { documents: 4, records: 40, tier: "case" },
      bryan: { documents: 90, records: 2, tier: "case" },
    };
    const slugs = featuredSites((slug) => PEERS[slug] ?? NO_BUNDLE, 3).map((s) => s.slug);
    // Records lead (40 > 2), then documents break the remaining tie (900 > 90) — a big pile of
    // unreviewed source files never outranks a reviewed record.
    expect(slugs).toEqual(["van-wert", "toledo", "bryan"]);
  });

  it("returns at most `limit` sites, and the whole registry when asked for more", () => {
    expect(featuredSites(ROLLUP, 8)).toHaveLength(8);
    expect(featuredSites(ROLLUP, SITES.length + 10)).toHaveLength(SITES.length);
    expect(featuredSites(ROLLUP, 0)).toEqual([]);
  });

  it("orders the tiers deepest-first, the one place that order is written down", () => {
    expect(TIER_DEPTH_ORDER).toEqual(["reference", "case", "backdrop", "stub"]);
    // Every tier the pill map knows is ranked — a new tier can't silently sort as unmeasured.
    expect([...TIER_DEPTH_ORDER].sort()).toEqual(Object.keys(TIER_PILL).sort());
  });
});
