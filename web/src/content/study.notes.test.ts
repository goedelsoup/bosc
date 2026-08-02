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
import type { EconomicBaseline, FacilityItem, GridProfile, ScenarioResult } from "@watermark/core/feeds";
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
  const fm = raw.split("---")[1] ?? "";
  return {
    id,
    site: parts[0],
    chapter: parts[parts.length - 1],
    frontmatterChapter: (fm.match(/^chapter:\s*(.+)$/m)?.[1] ?? "").trim(),
    body: raw,
  };
});

const note = (id: string): Note => {
  const found = notes.find((n) => n.id === id);
  if (!found) throw new Error(`No study note "${id}" — pinned claims must name a real note`);
  return found;
};

describe(`study notes — wiring (${notes.length} notes)`, () => {
  it("finds the authored cohort", () => {
    expect(notes.length).toBeGreaterThanOrEqual(13);
    expect(notes.map((n) => n.id)).toContain("lima/_cover");
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
    claim: "114",
    expected: () => String(lima<FacilityItem[]>("facility")[0].genset_count),
  },
  {
    note: "lima/_cover",
    claim: "250 to 300 megawatts",
    expected: () => {
      const f = lima<FacilityItem[]>("facility")[0];
      return `${f.it_load_low_mw} to ${f.it_load_high_mw} megawatts`;
    },
  },
  {
    note: "lima/project",
    claim: "asserted from the tower count, not disclosed by the operator",
    // The archetype must stay an ASSUMPTION; a disclosure would make this sentence false.
    expected: () =>
      lima<FacilityItem[]>("facility")[0].cooling_model_source === "assumption"
        ? "asserted from the tower count, not disclosed by the operator"
        : null,
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
      const min = Math.min(...checks.map((c) => c.dilution_ratio));
      return `${min.toFixed(2)}:1`;
    },
  },

  // --- air: the note says the peak column "reads as dashes"; true ONLY while uncomputed ---
  {
    note: "lima/air",
    claim: "The peak-concentration column above reads as dashes",
    expected: () =>
      lima<{ available: boolean }[]>("air-dispersion").every((r) => !r.available)
        ? "The peak-concentration column above reads as dashes"
        : null,
  },

  // --- groundwater: the note reads the ten impacted wells by consumed column, not by feet ---
  {
    note: "lima/groundwater",
    claim: "2,056 feet away",
    expected: () => {
      const dw = lima<{ impacted_wells: { distance_ft: number; column_consumed_frac: number }[] }>(
        "dewatering",
      );
      const nearest = [...dw.impacted_wells].sort((a, b) => a.distance_ft - b.distance_ft)[0];
      return `${nearest.distance_ft.toLocaleString("en-US")} feet away`;
    },
  },
  {
    note: "lima/groundwater",
    claim: "takes 47 % of it",
    expected: () => {
      const dw = lima<{ impacted_wells: { distance_ft: number; column_consumed_frac: number }[] }>(
        "dewatering",
      );
      const nearest = [...dw.impacted_wells].sort((a, b) => a.distance_ft - b.distance_ft)[0];
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
      `${lima<{ screens: { headroom_c: number }[] }>("thermal").screens[0].headroom_c} °C of headroom`,
  },

  // --- the annex counts its own asks ---
  {
    note: "lima/missing",
    claim: "the submit link on each row",
    expected: () => (rows("leads") > 0 ? "the submit link on each row" : null),
  },
];

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
