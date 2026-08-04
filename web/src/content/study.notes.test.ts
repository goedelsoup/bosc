/**
 * The study-note drift guard (the missing-impact-study prose layer).
 *
 * A per-site note under `src/content/study/**` is hand-written prose that quotes figures
 * rendered by the chapter section directly above it. Those figures come from regenerable
 * feeds — a QCEW annual pull, an EIA-861 re-pull, a hydrology re-run — so the prose can
 * silently stop matching the table it sits under, with no CI signal: `study.guardrails` and
 * `study.parity` both check the MODEL and never read the notes.
 *
 * This closes that hole in two ways:
 *
 *  1. **Wiring** — every note's file-path id resolves to a real chapter (or the reserved
 *     `_cover`), and its `chapter:` frontmatter agrees with that id. Nothing in the shells
 *     reads `data.chapter` and neither shell errors on a typo'd FILENAME, so this is the
 *     only place either mistake surfaces.
 *  2. **Figures** — each pinned claim states the exact string the prose uses and derives the
 *     expected string from the bundle. A regen that moves a figure fails HERE, naming the
 *     file and the sentence to rewrite, instead of publishing a page whose prose and whose
 *     table disagree.
 *
 * Adding a figure to a note? Pin it. An unpinned figure is one nobody will notice going stale.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { loadFeed, loadManifest } from "@watermark/core/bundle";
import { citeSpecsInNote, resolveCiteSpec } from "@watermark/core/cite";
import type {
  EconomicBaseline,
  EconomicScenarios,
  EnergyBurden,
  FacilityItem,
  GridProfile,
  ScenarioResult,
} from "@watermark/core/feeds";
import { STUDY_CHAPTERS, studyStatusSummary } from "@watermark/core/study";

const ROOT = join(process.cwd(), "src/content/study");
const CHAPTER_IDS = new Set(STUDY_CHAPTERS.map((c) => c.id));
/** The cover's abstract — routed by `study/index.astro`, never by `[chapter].astro`. */
const RESERVED = new Set(["_cover"]);

interface Note {
  /** `<site>/<chapter>` or `<site>/<facility-key>/<chapter>` — the content-collection id. */
  id: string;
  site: string;
  chapter: string;
  frontmatterChapter: string;
  body: string;
  /** The body with its line breaks intact — what the `<Cite>` scanner reads. */
  raw: string;
}

function walk(dir: string, rel = ""): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const abs = join(dir, entry);
    const next = rel ? `${rel}/${entry}` : entry;
    if (statSync(abs).isDirectory()) return walk(abs, next);
    return entry.endsWith(".mdx") || entry.endsWith(".md") ? [next] : [];
  });
}

const notes: Note[] = walk(ROOT).map((rel) => {
  const id = rel.replace(/\.mdx?$/, "");
  const parts = id.split("/");
  const raw = readFileSync(join(ROOT, rel), "utf-8");
  const [, fm = "", ...rest] = raw.split("---");
  return {
    id,
    site: parts[0],
    chapter: parts[parts.length - 1],
    frontmatterChapter: (fm.match(/^chapter:\s*(.+)$/m)?.[1] ?? "").trim(),
    // Frontmatter STRIPPED, and whitespace collapsed: a containment assertion must be able
    // to match a claim that the source happens to line-wrap, and must never be satisfied by
    // a date or a slug in the frontmatter block.
    body: rest.join("---").replace(/\s+/g, " ").trim(),
    raw: rest.join("---"),
  };
});

/** Every note Lima's study is expected to carry — its 13 chapters plus the cover abstract.
 *  Asserted as a SET, not a count: deleting a chapter note must fail here, and a count of
 *  ">= 13" would happily pass with a peer site's notes making up the difference. */
const LIMA_NOTES = [
  "_cover",
  ...["method", "project"],
  ...["water-supply", "discharge", "heat", "groundwater", "stormwater", "air"],
  ...["labor", "power", "fiscal", "balance", "missing"],
].map((c) => `lima/${c}`);

const note = (id: string): Note => {
  const found = notes.find((n) => n.id === id);
  if (!found) throw new Error(`No study note "${id}" — pinned claims must name a real note`);
  return found;
};

describe(`study notes — wiring (${notes.length} notes)`, () => {
  it("carries Lima's complete authored set — 13 chapters plus the cover", () => {
    const ids = new Set(notes.map((n) => n.id));
    expect(LIMA_NOTES.filter((id) => !ids.has(id))).toEqual([]);
    expect(LIMA_NOTES).toHaveLength(14);
  });

  it.each(notes.map((n) => n.id))("%s — id resolves to a chapter, frontmatter agrees", (id) => {
    const n = note(id);
    // A typo'd filename is silently dead content in both shells; this is where it dies loudly.
    expect(CHAPTER_IDS.has(n.chapter) || RESERVED.has(n.chapter)).toBe(true);
    // `data.chapter` is declarative — nothing reads it — so it can only drift. Pin it.
    expect(n.frontmatterChapter).toBe(n.chapter);
  });
});

/**
 * The authored-citation gate (#1885).
 *
 * A `<Cite>` that names a source the site doesn't hold already fails the Astro build, but it
 * fails deep in a page render with no clue which note wrote it. This runs the same resolution
 * over every note's source and names the file, the site, and the identifier — and it runs in
 * the unit suite, so a bad citation is caught before anyone waits on a build.
 *
 * The second assertion is the regression pin on the finding itself, and it is deliberately
 * demanded of the reference build rather than of every site: all thirteen of Lima's chapters
 * had zero outbound links into the record, and Lima is the one site whose corpus is deep
 * enough that "this chapter cites nothing" is always a defect rather than a gap. A peer's
 * thinner note is covered by the resolution gate above and by `study.evidence.test.ts`.
 */
describe("study notes — authored citations resolve", () => {
  it.each(notes.map((n) => n.id))("%s — every <Cite> names a source this site holds", (id) => {
    const n = note(id);
    const unresolved = citeSpecsInNote(n.raw)
      .filter((spec) => resolveCiteSpec(spec, n.site) === null)
      .map((spec) => `${spec.kind}="${spec.key}"`);
    expect(unresolved, `${id}: <Cite> targets absent from site "${n.site}"`).toEqual([]);
  });

  it("all thirteen Lima chapters link into the record", () => {
    const bare = LIMA_NOTES.filter((id) => id !== "lima/_cover").filter(
      (id) => citeSpecsInNote(note(id).raw).length === 0,
    );
    expect(bare, "Lima study chapters citing nothing").toEqual([]);
  });
});

/**
 * A pinned figure: the literal string the prose uses, and the same figure derived from the
 * bundle. `expected` returning `null` means "the note asserts a condition, not a number" —
 * the claim still fails if the condition stops holding.
 */
interface Pin {
  note: string;
  claim: string;
  expected: () => string | null;
}

const lima = <T>(name: string): T => loadFeed<T>(name, "lima");
const rows = (name: string): number => loadManifest("lima").feeds.find((f) => f.name === name)?.count ?? 0;

/**
 * Read a ProvenancedValue that the prose depends on. Most of these fields are optional on
 * the feed interface, and a regen that DROPS one is exactly the drift this file exists to
 * catch — so an absent value fails the pin by name rather than crashing or type-erroring.
 */
const pv = (v: { value: number | null } | null | undefined, what: string): number => {
  if (v?.value == null) throw new Error(`Pinned figure "${what}" is no longer on the feed`);
  return v.value;
};

/**
 * The same guard for a row the prose depends on. Every feed read below indexes something —
 * `facility[0]`, `screens[0]`, the nearest well after a sort, the minimum over a set of
 * dilution checks. An emptied feed must fail this pin BY NAME; it must not throw a
 * TypeError, and it must never quietly produce `undefined` or `Infinity` that then compares
 * unequal for the wrong reason.
 */
const one = <T>(xs: readonly T[] | null | undefined, what: string): T => {
  if (!xs || xs.length === 0) throw new Error(`Pinned figure "${what}" has no rows on the feed`);
  return xs[0];
};
const num = (n: number): string => n.toLocaleString("en-US");

const PINS: Pin[] = [
  // --- the cover + balance quote the verdict summary the SAME page renders in its header ---
  {
    note: "lima/_cover",
    claim: "Twelve of its thirteen chapters",
    expected: () =>
      studyStatusSummary("lima").data === 12 && studyStatusSummary("lima").total === 13
        ? "Twelve of its thirteen chapters"
        : null,
  },
  {
    note: "lima/balance",
    claim: "Twelve of Lima's thirteen chapters",
    expected: () =>
      studyStatusSummary("lima").data === 12 && studyStatusSummary("lima").total === 13
        ? "Twelve of Lima's thirteen chapters"
        : null,
  },
  {
    note: "lima/balance",
    claim: "the only gap on this sheet",
    expected: () => (studyStatusSummary("lima").gap === 1 ? "the only gap on this sheet" : null),
  },

  // --- project / cover: the facility's own disclosed + inferred fields ---
  {
    note: "lima/project",
    // The full phrase, NOT the bare "114" — a two-or-three digit substring matches a date,
    // a parcel fragment, or another figure, so a bare number can pass for the wrong reason.
    claim: "114 backup generators",
    expected: () => `${one(lima<FacilityItem[]>("facility"), "facility").genset_count} backup generators`,
  },
  {
    note: "lima/_cover",
    claim: "250 to 300 megawatts",
    expected: () => {
      const f = one(lima<FacilityItem[]>("facility"), "facility");
      return `${f.it_load_low_mw} to ${f.it_load_high_mw} megawatts`;
    },
  },
  {
    note: "lima/project",
    claim: "asserted from the tower count, not disclosed by the operator",
    // The archetype must stay an ASSUMPTION; a disclosure would make this sentence false.
    expected: () =>
      one(lima<FacilityItem[]>("facility"), "facility").cooling_model_source === "assumption"
        ? "asserted from the tower count, not disclosed by the operator"
        : null,
  },
  {
    // The abatement terms the method note states, from the site's own CRA instrument.
    note: "lima/method",
    claim: "abated 75 % of the real property tax for 15 years",
    expected: () => {
      const c = lima<EconomicScenarios>("economics-scenarios").constants ?? [];
      const pct = pv(c.find((x) => x.key === "abatement_percent")?.value, "abatement_percent");
      const yrs = pv(c.find((x) => x.key === "term_years")?.value, "term_years");
      return `abated ${pct * 100} % of the real property tax for ${yrs} years`;
    },
  },

  // --- labor: a QCEW annual pull moves all of these at once ---
  {
    note: "lima/labor",
    claim: "49,690 jobs",
    expected: () =>
      `${num(pv(lima<EconomicBaseline>("economics-baseline").latest.total_employment, "total_employment"))} jobs`,
  },
  {
    note: "lima/labor",
    claim: "2,586 establishments",
    expected: () =>
      `${num(pv(lima<EconomicBaseline>("economics-baseline").latest.establishments, "establishments"))} establishments`,
  },
  {
    note: "lima/labor",
    claim: "$58,790",
    expected: () =>
      `$${num(pv(lima<EconomicBaseline>("economics-baseline").latest.avg_annual_pay, "avg_annual_pay"))}`,
  },
  {
    note: "lima/labor",
    claim: "$62,001",
    expected: () =>
      `$${num(pv(lima<EconomicBaseline>("economics-baseline").median_household_income, "median_household_income"))}`,
  },

  // --- power: an EIA-861 / EIA-930 re-pull moves the denominators ---
  {
    note: "lima/power",
    claim: "48,653 gigawatt-hours",
    expected: () =>
      `${num(Math.round(pv(lima<GridProfile>("grid").utility_profile.retail_sales_gwh, "retail_sales_gwh")))} gigawatt-hours`,
  },
  {
    note: "lima/power",
    claim: "1,533,265",
    expected: () => num(pv(lima<GridProfile>("grid").utility_profile.customers, "customers")),
  },
  {
    note: "lima/power",
    claim: "5.64 %",
    expected: () =>
      `${pv(lima<GridProfile>("grid").load_share?.share_of_utility_pct, "share_of_utility_pct")} %`,
  },
  {
    note: "lima/power",
    claim: "1.69 %",
    expected: () => `${pv(lima<GridProfile>("grid").load_share?.share_of_state_pct, "share_of_state_pct")} %`,
  },
  {
    // The note must quote what the TABLE renders (Power.astro formats with toFixed(2)),
    // not the raw feed value (0.337) — a reader scans the table for the number they read.
    note: "lima/power",
    claim: "0.34 %",
    expected: () =>
      `${pv(lima<GridProfile>("grid").load_share?.share_of_ba_pct, "share_of_ba_pct").toFixed(2)} %`,
  },
  {
    // The consumer-side reference price. The note is explicit that the campus does NOT buy at
    // it, so the figure has to stay the one the energy-burden read is actually built on.
    note: "lima/power",
    claim: "16.96 cents per kilowatt-hour",
    expected: () =>
      `${pv(lima<EnergyBurden>("energy-burden").residential_electricity_price, "residential_electricity_price")} cents per kilowatt-hour`,
  },
  {
    note: "lima/power",
    claim: "about $1,781 a year on electricity",
    expected: () =>
      `about $${num(Math.round(pv(lima<EnergyBurden>("energy-burden").electricity_annual_cost, "electricity_annual_cost")))} a year on electricity`,
  },
  {
    note: "lima/power",
    claim: "$970 on natural gas",
    expected: () =>
      `$${num(Math.round(pv(lima<EnergyBurden>("energy-burden").gas_annual_cost, "gas_annual_cost")))} on natural gas`,
  },
  {
    // Derived from the two costs above over the same income the labor note pins — so all four
    // must move together or this fails, which is the point of pinning the derived figure too.
    note: "lima/power",
    claim: "4.44 % of that income",
    expected: () =>
      `${pv(lima<EnergyBurden>("energy-burden").combined_burden_pct, "combined_burden_pct")} % of that income`,
  },
  {
    note: "lima/power",
    claim: "median household income of $62,001",
    expected: () =>
      `median household income of $${num(pv(lima<EnergyBurden>("energy-burden").median_household_income, "median_household_income"))}`,
  },

  // --- discharge: the note quotes the table's own 2-decimal formatting (Discharge.astro) ---
  {
    note: "lima/discharge",
    claim: "0.42:1",
    expected: () => {
      const checks = lima<ScenarioResult[]>("hydrology-scenarios").flatMap((s) => s.assimilative ?? []);
      const dug = checks.find((c) => c.receiving_water === "Dug Run");
      return dug ? `${dug.dilution_ratio.toFixed(2)}:1` : null;
    },
  },
  {
    note: "lima/discharge",
    claim: "0.01:1",
    expected: () => {
      const checks = lima<ScenarioResult[]>("hydrology-scenarios").flatMap((s) => s.assimilative ?? []);
      // Guarded: Math.min() over an emptied feed is Infinity, which would render "Infinity:1"
      // and fail for a reason that hides the real one.
      const min = Math.min(...checks.map((c) => one([c.dilution_ratio], "dilution_ratio")));
      return checks.length > 0 ? `${min.toFixed(2)}:1` : null;
    },
  },

  // --- air: the note says the peak column "reads as dashes"; true ONLY while uncomputed ---
  {
    note: "lima/air",
    claim: "The peak-concentration column above reads as dashes",
    expected: () => {
      // `.every()` on an emptied feed is vacuously true — the claim would keep passing after
      // the rows it describes had gone. Require rows first.
      const disp = lima<{ available: boolean }[]>("air-dispersion");
      return disp.length > 0 && disp.every((r) => !r.available)
        ? "The peak-concentration column above reads as dashes"
        : null;
    },
  },

  // --- groundwater: the note reads the ten impacted wells by consumed column, not by feet ---
  {
    note: "lima/groundwater",
    claim: "2,056 feet away",
    expected: () => {
      const dw = lima<{ impacted_wells: { distance_ft: number; column_consumed_frac: number }[] }>(
        "dewatering",
      );
      const nearest = one(
        [...dw.impacted_wells].sort((a, b) => a.distance_ft - b.distance_ft),
        "impacted_wells",
      );
      return `${num(nearest.distance_ft)} feet away`;
    },
  },
  {
    note: "lima/groundwater",
    claim: "takes 47 % of it",
    expected: () => {
      const dw = lima<{ impacted_wells: { distance_ft: number; column_consumed_frac: number }[] }>(
        "dewatering",
      );
      const nearest = one(
        [...dw.impacted_wells].sort((a, b) => a.distance_ft - b.distance_ft),
        "impacted_wells",
      );
      return `takes ${Math.round(nearest.column_consumed_frac * 100)} % of it`;
    },
  },
  {
    note: "lima/groundwater",
    claim: "44 dewatering wells",
    expected: () => `${lima<{ well_count: number }>("dewatering").well_count} dewatering wells`,
  },
  {
    note: "lima/groundwater",
    claim: "None of the ten goes dry",
    expected: () => {
      const dw = lima<{ impacted_wells: { goes_dry: boolean }[] }>("dewatering");
      return dw.impacted_wells.length === 10 && dw.impacted_wells.every((w) => !w.goes_dry)
        ? "None of the ten goes dry"
        : null;
    },
  },

  // --- stormwater: a hydrology re-run moves every one of these ---
  {
    note: "lima/stormwater",
    claim: "14,283 cfs",
    expected: () =>
      `${Math.round(lima<{ routed_peak_cfs: number }>("routed-hydrograph").routed_peak_cfs).toLocaleString("en-US")} cfs`,
  },
  {
    note: "lima/stormwater",
    claim: "2.66 %",
    expected: () => `${lima<{ peak_attenuation_pct: number }>("routed-hydrograph").peak_attenuation_pct} %`,
  },
  {
    note: "lima/stormwater",
    claim: "4.25 inches",
    expected: () => `${lima<{ storm_depth_in: number }>("routed-hydrograph").storm_depth_in} inches`,
  },
  {
    // The attenuation the note describes is the DELAY as well as the shaved peak; both come
    // off the same re-run, so pinning one without the other lets half the sentence go stale.
    note: "lima/stormwater",
    claim: "20.2 hours instead of 17.4",
    expected: () => {
      const r = lima<{ routed_time_to_peak_hr: number; summed_time_to_peak_hr: number }>("routed-hydrograph");
      return `${r.routed_time_to_peak_hr} hours instead of ${r.summed_time_to_peak_hr}`;
    },
  },

  // --- heat: the criterion, the ambient, and the headroom between them ---
  {
    note: "lima/heat",
    claim: "29.4 °C",
    expected: () => `${lima<{ meta: { daily_max_c: number } }>("thermal").meta.daily_max_c} °C`,
  },
  {
    note: "lima/heat",
    claim: "5.4 °C of headroom",
    expected: () =>
      `${one(lima<{ screens: { headroom_c: number }[] }>("thermal").screens, "thermal screens").headroom_c} °C of headroom`,
  },

  // --- the annex counts its own asks ---
  {
    note: "lima/missing",
    claim: "the submit link on each row",
    expected: () => (rows("leads") > 0 ? "the submit link on each row" : null),
  },
];

/**
 * Figures the notes quote that this file deliberately does NOT pin, and why. Recorded so the
 * absence reads as a decision rather than an oversight — both are legitimately un-pinnable
 * from `web/`, not merely unwritten:
 *
 *  - **The reservoir + drought-reserve set** (water-supply: 14.4 BG, 3.92 MGD, 20.7 %,
 *    960.9 → 761.8 days). Not in the content bundle at all. Its regenerable source is
 *    `docs/HYDROLOGY.md`, at the repo root — reaching it would make this test depend on a
 *    tree outside `web/`, breaking the standalone/offline contract the frontend keeps.
 *  - **The declared acreages** (project + stormwater: 335 / 195 / 115 acres). Same reason:
 *    they live in the committed extraction `data/extracted/plans/bosc-site-footprint.yaml`,
 *    which the export does not project into a feed.
 *
 * The cross-note check below is what those two get instead: it cannot catch the SOURCE
 * moving, but it does catch the two notes drifting apart from each other.
 */
const CROSS_NOTE_CLAIMS: { claim: string; notes: string[] }[] = [
  { claim: "115 acres", notes: ["lima/project", "lima/stormwater"] },
  { claim: "335 acres", notes: ["lima/_cover", "lima/project", "lima/stormwater"] },
  { claim: "960.9", notes: ["lima/water-supply", "lima/balance"] },
  { claim: "761.8", notes: ["lima/water-supply", "lima/balance"] },
];

describe(`study notes — cross-note agreement (${CROSS_NOTE_CLAIMS.length} figures)`, () => {
  it.each(
    CROSS_NOTE_CLAIMS.map((c) => [c.claim, c] as const),
  )("%s — every note that states it states the same value", (_claim, c) => {
    expect(c.notes.filter((id) => !note(id).body.includes(c.claim))).toEqual([]);
  });
});

describe(`study notes — pinned figures (${PINS.length} claims)`, () => {
  it.each(PINS.map((p, i) => [`${p.note} · ${p.claim}`, i] as const))("%s", (_label, i) => {
    const pin = PINS[i];
    const body = note(pin.note).body;
    // The claim must still be DERIVABLE (the feed still says what the prose says)…
    expect(pin.expected()).toBe(pin.claim);
    // …and the prose must still CONTAIN it (nobody quietly reworded around the pin).
    expect(body.toLowerCase()).toContain(pin.claim.toLowerCase());
  });
});
