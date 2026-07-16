import { describe, expect, it } from "vitest";
import type { ReachNetwork, RoutedHydrographNetwork, ScenarioResult } from "@watermark/core/feeds";
import { buildFlowReaches, deficitReceivingWaters, worstScenario } from "./flowModel";

const network: ReachNetwork = {
  site: "lima",
  crs: "WGS84 (EPSG:4326)",
  note: "",
  caveats: [],
  reaches: [
    {
      node_id: "ottawa-head",
      name: "Ottawa River upstream of Lima",
      receiving_water: "Ottawa River",
      downstream: "lima-abstraction",
      length_km: 22,
      coordinates: [
        [-84.1, 40.75],
        [-84.12, 40.74],
      ],
    },
    {
      node_id: "dug-run-head",
      name: "Dug Run (headwater)",
      receiving_water: "Dug Run",
      downstream: "dug-run-confluence",
      length_km: 9,
      coordinates: [
        [-84.2, 40.8],
        [-84.19, 40.79],
      ],
    },
    {
      node_id: "no-geom",
      name: "degenerate",
      receiving_water: "Ottawa River",
      downstream: null,
      length_km: 0,
      coordinates: [[-84.1, 40.75]],
    },
  ],
};

const routed: RoutedHydrographNetwork = {
  tier: "tier0",
  scenario: "s",
  site: "Lima",
  return_period_yr: 100,
  storm_depth_in: 4,
  dt_hr: 0.1,
  times_hr: [],
  outlet_hydrograph_cfs: [],
  summed_hydrograph_cfs: [],
  routed_peak_cfs: 0,
  summed_peak_cfs: 0,
  peak_attenuation_pct: 0,
  routed_time_to_peak_hr: 0,
  summed_time_to_peak_hr: 0,
  lag_hr: 0,
  warnings: [],
  reaches: [
    {
      node_id: "ottawa-head",
      name: "Ottawa",
      length_ft: 82000,
      slope: 0.001,
      inflow_peak_cfs: 12800,
      inflow_time_to_peak_hr: 17,
      outflow_peak_cfs: 12000,
      outflow_time_to_peak_hr: 19,
      attenuation_pct: 3,
      lag_hr: 2,
    },
    {
      node_id: "dug-run-head",
      name: "Dug Run",
      length_ft: 21000,
      slope: 0.002,
      inflow_peak_cfs: 3000,
      inflow_time_to_peak_hr: 10,
      outflow_peak_cfs: 3000,
      outflow_time_to_peak_hr: 11,
      attenuation_pct: 0,
      lag_hr: 1,
    },
  ],
};

const pv = (value: number) => ({
  value,
  unit: "cfs",
  source: "derived" as const,
  citation: "",
  confidence: "medium" as const,
  asof: null,
});

const scenario = (over: Partial<ScenarioResult> = {}): ScenarioResult =>
  ({
    scenario: {
      name: "worst",
      cooling_demand: pv(10),
      consumptive_fraction: pv(0.8),
    },
    consumptive_loss: pv(5),
    receiving_7q10: pv(0.2),
    receiving_water_name: "Ottawa River",
    balance: { nodes: [], tier: "tier0", warnings: [] },
    assimilative: [
      {
        receiving_water: "Dug Run",
        discharger: "American II",
        design_low_flow: pv(0.78),
        discharge: pv(1.86),
        dilution_ratio: 0.42,
        flag: "violation",
        detail: "",
      },
    ],
    ...over,
  }) as ScenarioResult;

describe("worstScenario", () => {
  it("picks the largest consumptive loss", () => {
    const a = scenario({ consumptive_loss: pv(1) });
    const b = scenario({ consumptive_loss: pv(9) });
    expect(worstScenario([a, b])).toBe(b);
  });
  it("is null for no scenarios", () => {
    expect(worstScenario([])).toBeNull();
  });
});

describe("deficitReceivingWaters", () => {
  it("collects assimilative violations and the consumptive-draw mainstem", () => {
    const s = deficitReceivingWaters([scenario()]);
    expect(s.has("Dug Run")).toBe(true); // assimilative violation
    expect(s.has("Ottawa River")).toBe(true); // draw 5 > 7Q10 0.2
  });
  it("omits the mainstem when draw is under the low flow", () => {
    const s = deficitReceivingWaters([scenario({ consumptive_loss: pv(0.1) })]);
    expect(s.has("Ottawa River")).toBe(false);
    expect(s.has("Dug Run")).toBe(true);
  });
});

describe("buildFlowReaches", () => {
  it("joins geometry + magnitude + deficit and drops degenerate reaches", () => {
    const reaches = buildFlowReaches(network, routed, [scenario()]);
    expect(reaches.map((r) => r.id)).toEqual(["ottawa-head", "dug-run-head"]); // no-geom dropped
    const ottawa = reaches[0];
    expect(ottawa.speed).toBe(1); // 12000 is the network max peak
    expect(ottawa.deficit).toBe(true); // Ottawa River draw > 7Q10
    expect(ottawa.magnitudeCfs).toBe(12000);
    const dug = reaches[1];
    expect(dug.speed).toBeCloseTo(0.25); // 3000 / 12000
    expect(dug.deficit).toBe(true); // Dug Run assimilative violation
  });
  it("returns [] without a network", () => {
    expect(buildFlowReaches(null, routed, [])).toEqual([]);
  });
  it("keeps a faint baseline magnitude for reaches absent from the hydrograph", () => {
    const reaches = buildFlowReaches(network, { ...routed, reaches: [] }, []);
    expect(reaches[0].speed).toBeGreaterThan(0);
    expect(reaches[0].magnitudeCfs).toBeNull();
    expect(reaches[0].deficit).toBe(false);
  });
});
