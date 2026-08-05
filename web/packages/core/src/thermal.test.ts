import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it, vi } from "vitest";
import type { ProvenancedValue, ThermalDischargeScreen, ThermalFlowScreen } from "./feeds";

// `buildThermal` reads the bundle at call time; point WATERMARK_BUNDLE_DIR at a fixture and
// re-import with a clean registry (the same harness dilution.test.ts / bundle.test.ts use).
const tmpDirs: string[] = [];

function pv(value: number | null, unit = "degC"): ProvenancedValue {
  return { value, unit, source: "connector", citation: "t", confidence: "high", asof: null };
}

/** A flow screen at one design low flow. `mixed` null models the zero-capacity case. */
function flow(
  label: string,
  cfs: number,
  mixed: number | null,
  capacityMw: number | null,
): ThermalFlowScreen {
  return {
    flow_label: label,
    design_flow: pv(cfs, "cfs"),
    thermal_capacity_mw: capacityMw,
    delta_t_c: mixed == null ? null : pv(mixed - 24),
    mixed_c: mixed == null ? null : pv(mixed),
    exceedance_factor: null,
    capacity_fraction: null,
    headroom_fraction: null,
    mixed_over_criterion: mixed == null ? null : mixed > 29.4,
    flag: mixed == null ? "no_capacity" : "exceedance",
    note: null,
  };
}

const META = {
  subject: "s",
  source: "src",
  site: "lima",
  receiving_water: "Ottawa River",
  zone_id: "lake_erie_basin_general",
  zone_rule: "OAC 3745-1-35 Table 35-11 (G)",
  design_period: "Jun 16-30",
  daily_max_c: 29.4,
  ambient_c: 24.0,
  ambient_source: "connector",
  reference_ambient_c: 27.8,
  facility_count: 3,
  modelled_count: 1,
  industrial_count: 2,
  critical_count: 2,
  monitor_only_permits: ["OH0002623"],
  permits_over_daily_max_criterion: ["OH0002623"],
  caveats: ["a caveat"],
};

function makeBundle(payload: object | null): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-thermal-"));
  tmpDirs.push(dir);
  const feeds =
    payload == null
      ? []
      : [
          {
            name: "thermal",
            path: "thermal.json",
            media_type: "application/json",
            schema: "s",
            kind: "object",
            count: 1,
          },
        ];
  writeFileSync(
    join(dir, "manifest.json"),
    JSON.stringify({
      bundle_version: "test",
      contract_version: "2.0.0",
      generated_at: "2026-01-01T00:00:00Z",
      feed_count: feeds.length,
      row_total: feeds.length,
      feeds,
    }),
  );
  if (payload != null) writeFileSync(join(dir, "thermal.json"), JSON.stringify(payload));
  return dir;
}

async function loadThermal(dir: string): Promise<typeof import("./thermal")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./thermal");
}

afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

const CAMPUS: ThermalDischargeScreen = {
  facility: "Project BOSC",
  facility_key: "project-bosc",
  kind: "data_center",
  npdes_id: null,
  method_disclosed: true,
  reject_heat_mw: pv(316.2, "MW"),
  flow_screens: [flow("1Q10", 0, null, 0), flow("7Q10", 0.2, 999.9, 0.128)],
  ris_checks: [],
  scenarios: [],
  flag: "critical",
  detail: "d",
};
const REFINERY: ThermalDischargeScreen = {
  facility: "LIMA REFINERY",
  facility_key: "OH0002623",
  kind: "permitted_discharger",
  npdes_id: "OH0002623",
  method_disclosed: false,
  flow_screens: [flow("7Q10", 0.2, 31.9, 0.128)],
  ris_checks: [],
  scenarios: [],
  dmr: { npdes_id: "OH0002623", window: "w", n_obs: 8, effluent_c: pv(32.22) },
  flag: "critical",
  detail: "d",
};
/** A permit ECHO carries but that reports no temperature — a cited ABSENCE, not a zero. */
const SILENT: ThermalDischargeScreen = {
  facility: "OHGC02549",
  facility_key: "OHGC02549",
  kind: "permitted_discharger",
  npdes_id: "OHGC02549",
  method_disclosed: false,
  flow_screens: [],
  ris_checks: [],
  scenarios: [],
  dmr: { npdes_id: "OHGC02549", window: "w", n_obs: 0, effluent_c: null },
  flag: "uncharacterized",
  detail: "d",
};

describe("buildThermal", () => {
  it("returns null for a site whose bundle carries no thermal screen", async () => {
    const { buildThermal } = await loadThermal(makeBundle(null));
    // The honest answer for every site but the one the screen was built for — never a fallback
    // to the reference site's river, zone criterion, or permittees.
    expect(buildThermal()).toBeNull();
  });

  it("reads the reach's criterion, ambient, headroom and capacity", async () => {
    const { buildThermal } = await loadThermal(makeBundle({ meta: META, screens: [CAMPUS, REFINERY] }));
    const t = buildThermal()!;
    expect(t.river).toBe("Ottawa River");
    expect(t.criterionC).toBe(29.4);
    expect(t.ambientC).toBe(24.0);
    expect(t.headroomC).toBe(5.4); // 29.4 − 24.0, free of float noise
    // The capacity is a property of the REACH, read off whichever row carries the chronic screen.
    expect(t.capacityMw).toBe(0.128);
    expect(t.designFlowCfs).toBe(0.2);
  });

  it("keeps modelled and observed heat loads in separate cohorts", async () => {
    const { buildThermal } = await loadThermal(
      makeBundle({ meta: META, screens: [CAMPUS, REFINERY, SILENT] }),
    );
    const t = buildThermal()!;
    // One is an inference about a facility that is not yet discharging; the other is a
    // measurement. Merging them into one ranked list is the mistake this guards.
    expect(t.modelled.map((s) => s.facility_key)).toEqual(["project-bosc"]);
    expect(t.observed.map((s) => s.facility_key)).toEqual(["OH0002623", "OHGC02549"]);
  });

  it("treats a permit that reports no temperature as a cited absence, not a row", async () => {
    const { buildThermal } = await loadThermal(makeBundle({ meta: META, screens: [REFINERY, SILENT] }));
    const t = buildThermal()!;
    // It stays in `observed` (it is part of the corridor's permit coverage) but out of
    // `reported`, so a comparison table never renders a blank cell that reads as "no heat".
    expect(t.observed).toHaveLength(2);
    expect(t.reported.map((s) => s.npdes_id)).toEqual(["OH0002623"]);
  });

  it("flattens only rows with a computable mixed temperature into the chart rows", async () => {
    const { buildThermal } = await loadThermal(
      makeBundle({ meta: META, screens: [CAMPUS, REFINERY, SILENT] }),
    );
    const t = buildThermal()!;
    // SILENT has no flow screens at all; CAMPUS and REFINERY both resolve at the 7Q10.
    expect(t.mixedRows.map((r) => r.npdesId)).toEqual([null, "OH0002623"]);
    expect(t.mixedRows[0]).toMatchObject({ modelled: true, overCriterion: true, mixedC: 999.9 });
    expect(t.mixedRows[1]).toMatchObject({ modelled: false, overCriterion: true, mixedC: 31.9 });
    expect(t.unbounded).toEqual([]);
    // SILENT contributes no bar and is recorded, so a surface can name the omission rather than
    // letting a filtered chart read as the whole corridor.
    expect(t.unresolved.map((s) => s.npdes_id)).toEqual(["OHGC02549"]);
  });

  it("records an unresolved OBSERVED row, not just an unbounded modelled one", async () => {
    // The gap this guards: `unbounded` covers data_center rows only, so a permitted discharger the
    // screen resolves no mixed temperature for would drop off the chart with nothing recording it.
    const { buildThermal } = await loadThermal(makeBundle({ meta: META, screens: [CAMPUS, SILENT] }));
    const t = buildThermal()!;
    expect(t.unbounded).toEqual([]);
    expect(t.unresolved.map((s) => s.facility_key)).toEqual(["OHGC02549"]);
  });

  it("refuses to pick a reach capacity when the rows disagree about it", async () => {
    // Every row screens the same water at the same cited design flows, so their chronic screens
    // must agree. Taking `screens[0]`'s would make the reach's capacity depend on row order and
    // render a real modeling inconsistency as a settled figure.
    const oddball: ThermalDischargeScreen = {
      ...REFINERY,
      flow_screens: [flow("7Q10", 0.9, 31.9, 4.2)],
    };
    const { buildThermal } = await loadThermal(makeBundle({ meta: META, screens: [CAMPUS, oddball] }));
    expect(() => buildThermal()).toThrow(/disagree on the reach's 7Q10 screen/);
  });

  it("falls back to a modelled row's partitions when its own rise is off the liquid-water scale", async () => {
    // Lima's real shape: the whole condenser rejection into a 0.2 cfs design flow has NO mixed
    // temperature (the screen refuses to print a rise of hundreds of degrees), so a chart keyed on
    // the row alone would silently drop the largest load on the page.
    const unboundedCampus: ThermalDischargeScreen = {
      ...CAMPUS,
      flow_screens: [flow("7Q10", 0.2, null, 0.128)],
      scenarios: [
        {
          scenario: "once_through",
          basis: "b",
          instream_fraction: 1.0,
          flow_screens: [flow("7Q10", 0.2, 34.0, 0.128)],
          flag: "context",
        },
        {
          scenario: "evaporative_blowdown",
          basis: "b",
          instream_fraction: 0.0119,
          flow_screens: [flow("7Q10", 0.2, 31.8, 0.128)],
          flag: "context",
        },
        // The conservative bound is unbounded too — it contributes no bar, and that is correct.
        {
          scenario: "conservative_bound",
          basis: "b",
          instream_fraction: 1.0,
          flow_screens: [flow("7Q10", 0.2, null, 0.128)],
          flag: "context",
        },
      ],
    };
    const { buildThermal } = await loadThermal(
      makeBundle({ meta: META, screens: [unboundedCampus, REFINERY] }),
    );
    const t = buildThermal()!;
    expect(t.mixedRows.map((r) => r.scenario)).toEqual(["once_through", "evaporative_blowdown", null]);
    expect(t.mixedRows.map((r) => r.mixedC)).toEqual([34.0, 31.8, 31.9]);
    // The row is reported as unbounded so the page can say WHY the whole-rejection bar is missing.
    expect(t.unbounded.map((s) => s.facility_key)).toEqual(["project-bosc"]);
  });

  it("marks a reference-table design ambient as ungrounded", async () => {
    // Without an in-stream station the screen falls back to the zone's seasonal-average criterion
    // standing in as a stated design ambient — a `[reference]` figure, not a measurement.
    const { buildThermal } = await loadThermal(
      makeBundle({
        meta: { ...META, ambient_source: "reference", ambient_c: 27.8 },
        screens: [CAMPUS],
      }),
    );
    const t = buildThermal()!;
    expect(t.ambientGrounded).toBe(false);
    expect(t.headroomC).toBe(1.6); // the reach carries far less capacity on this rung
  });
});

describe("warmestMixedC", () => {
  it("prefers the row's own chronic temperature and falls back to its hottest partition", async () => {
    const { warmestMixedC } = await loadThermal(makeBundle(null));
    expect(warmestMixedC(REFINERY)).toBe(31.9);
    const partitioned: ThermalDischargeScreen = {
      ...CAMPUS,
      flow_screens: [flow("7Q10", 0.2, null, 0.128)],
      scenarios: [
        {
          scenario: "once_through",
          basis: "b",
          flow_screens: [flow("7Q10", 0.2, 34.0, 0.128)],
          flag: "context",
        },
        {
          scenario: "evaporative_blowdown",
          basis: "b",
          flow_screens: [flow("7Q10", 0.2, 31.8, 0.128)],
          flag: "context",
        },
      ],
    };
    expect(warmestMixedC(partitioned)).toBe(34.0);
    // Nothing resolves ⇒ null, so a surface prints "—" rather than inventing a temperature.
    expect(warmestMixedC(SILENT)).toBeNull();
  });
});

describe("flowAt", () => {
  it("selects a row's screen at a named design flow and defaults to the chronic one", async () => {
    const { CHRONIC_FLOW_LABEL, flowAt } = await loadThermal(makeBundle(null));
    expect(CHRONIC_FLOW_LABEL).toBe("7Q10");
    expect(flowAt(CAMPUS)?.flow_label).toBe("7Q10");
    // The 1Q10 runs the reach dry: zero capacity, so there is no computable mixed temperature.
    expect(flowAt(CAMPUS, "1Q10")?.mixed_c).toBeNull();
    expect(flowAt(SILENT)).toBeNull();
  });
});
