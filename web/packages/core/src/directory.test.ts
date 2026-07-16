import { describe, expect, it } from "vitest";
import { buildLens, indexAssessments, LENS_ORDER, lensConfig, lensCount, lensDatum } from "./directory";
import type { HypothesisAssessmentItem, HypothesisItem } from "./feeds";
import { SITES } from "./sites";

const LIMA_COUNTS = { docs: "2,140", records: "318" };

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
    fields: { operator: "Shawnee Energy Campus", capital: "CRA #548-25 · 15 yr / 75%" },
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
    const v = buildLens("water", LIMA_COUNTS, DATA);
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

  it("water lens shows Lima's real counts and a dash everywhere else — never a fabricated number", () => {
    const v = buildLens("water", LIMA_COUNTS, DATA);
    const rows = v.groups.flatMap((g) => g.rows);
    const lima = rows.find((r) => r.slug === "lima");
    // cols: site, watershed, phase, documents, records, facility
    expect(lima?.cells[3].text).toBe("2,140");
    expect(lima?.cells[4].text).toBe("318");
    for (const r of rows) {
      if (r.slug === "lima") continue;
      expect(r.cells[3].text).toBe("—");
      expect(r.cells[4].text).toBe("—");
      expect(r.cells[3].muted).toBe(true);
    }
  });

  it("defense lens groups assessed sites and sweeps the rest into a 'not yet assessed' chip tail", () => {
    const v = buildLens("defense", LIMA_COUNTS, DATA);
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
    const v = buildLens("surveillance", LIMA_COUNTS, DATA);
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
        fields: { operator: "Shawnee Energy Campus", capital: "CRA #548-25 · 15 yr / 75%" },
        citations: [],
      },
    ];
    const data = indexAssessments(cellsWithTag);
    expect(lensDatum("lima", data).surv.sub_thesis).toBe("capture");
    // The scorecard row appends · [capture] to the operator cell.
    const v = buildLens("surveillance", LIMA_COUNTS, data);
    const limaRow = v.groups.flatMap((g) => g.rows).find((r) => r.slug === "lima");
    expect(limaRow?.cells[1].text).toBe("Shawnee Energy Campus · [capture]");
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
