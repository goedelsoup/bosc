/**
 * Build-time model for the **thermal discharge / CWA §316(a)** page (#1719, epic #1715 Phase 4) —
 * the reader for the `thermal` object feed.
 *
 * The **third cooling axis**. `dilution.ts` carries the cooling load's *volume* and the toxics
 * screen carries the discharge's *chemistry*; this carries its **heat**: a heat load read against
 * the receiving reach's Ohio numeric temperature criterion at the cited design low flows.
 *
 * The one discipline every consumer must keep is the `kind` split, which is why this module never
 * merges the two cohorts into a single ranked list:
 *
 *   - `data_center` — the heat load is **modelled** from the disclosed IT load. An `[inference]`
 *     about a facility that is not yet discharging, carrying its three heat-partition scenarios
 *     and a calibration that grades the model against the corridor's record.
 *   - `permitted_discharger` — the heat load is **observed**: the permittee's own ECHO-DMR
 *     reported effluent temperature × reported flow. A `[verified]` measurement.
 *
 * They are screened identically from there on — same reach, same design flows, same criterion —
 * and must never be conflated. `modelled` / `observed` are separate fields for that reason.
 *
 * Discipline, in the shape `dilution.ts` and `gridBackdrop.ts` established: **no reference-site
 * fallback**. A site whose bundle carries no `thermal` feed returns `null` and its page degrades —
 * it never borrows another site's river, zone criterion, or permittees. (The export gates the feed
 * on the screen artifact's own `meta.site` for the same reason.)
 *
 * NOT client-safe (imports the node bundle loader) — the page renders these plain objects.
 */
import { hasFeed, loadFeed } from "./bundle";
import type {
  ThermalDischargeScreen,
  ThermalFlowScreen,
  ThermalScreenMeta,
  ThermalScreenReport,
} from "./feeds";
import { round } from "./format";

/** The chronic design flow Ohio's aquatic-life criteria are written at, and the reach's least
 *  degenerate binding case — the 1Q10 is often 0 cfs, which carries no computable mixed
 *  temperature at all (zero assimilative capacity, exceeded by construction). */
export const CHRONIC_FLOW_LABEL = "7Q10";

/** One row's fully-mixed temperature at a design low flow, flattened for the comparison chart. */
export interface ThermalMixedRow {
  label: string;
  facility: string;
  npdesId: string | null;
  /**
   * The heat-partition scenario this temperature belongs to, when the row came from one.
   *
   * A modelled facility's *whole* condenser rejection has no plottable temperature on this reach —
   * see `unbounded` below — so its bars are its partitions, which is the more honest comparison
   * anyway: each names how much of the rejection it assumes reaches the water.
   */
  scenario: string | null;
  /** Fully-mixed temperature, °C — rounded for display. */
  mixedC: number;
  /** `true` when the heat load is modelled from a disclosed IT load rather than reported. */
  modelled: boolean;
  overCriterion: boolean;
}

export interface ThermalScreenModel {
  meta: ThermalScreenMeta;
  /** Receiving water name, or a generic stand-in — never another site's river. */
  river: string;
  /** Ohio's daily-maximum criterion for this zone + season, °C (`[reference]`, the rule text). */
  criterionC: number | null;
  /** The design ambient the screen actually used, °C. */
  ambientC: number | null;
  /**
   * `true` when the ambient is a MEASURED in-stream temperature (the corridor's own permit-required
   * upstream/downstream station) rather than the zone's seasonal-average criterion standing in as a
   * stated design ambient. Which rung the ladder landed on changes how much capacity the reach has,
   * so it changes the evidence register the page prints beside the number.
   */
  ambientGrounded: boolean;
  /** criterion − ambient, °C. ≤ 0 ⇒ the reach is already at/over the standard: no headroom. */
  headroomC: number | null;
  /** ρ·cp·Q·headroom at the chronic design flow, MW — the reach's thermal loading capacity. */
  capacityMw: number | null;
  /** The chronic design flow itself, cfs. */
  designFlowCfs: number | null;
  /** Rows whose heat load is modelled from a disclosed IT load (`[inference]`). */
  modelled: ThermalDischargeScreen[];
  /** Rows whose heat load is the permittee's own reported record (`[verified]`). */
  observed: ThermalDischargeScreen[];
  /**
   * The observed rows that actually report a temperature. A permit that monitors nothing is a
   * *cited absence* — it belongs in the coverage count, not in a comparison table where a blank
   * cell would read as "no heat".
   */
  reported: ThermalDischargeScreen[];
  /** Every row with a computable mixed temperature, for the criterion-marker chart. */
  mixedRows: ThermalMixedRow[];
  /**
   * Modelled rows whose fully-mixed rise is **unbounded** at the chronic design flow: the screen
   * reports `null` rather than a literal ΔT of hundreds of degrees, because the reach cannot
   * physically carry that load as sensible heat in liquid water.
   *
   * These have no bar on the criterion chart, and a page that shows the chart without saying so
   * would read as if the biggest load were simply absent. The magnitude lives in the row's
   * `exceedance_factor` / `detail` instead.
   */
  unbounded: ThermalDischargeScreen[];
  caveats: string[];
}

/** A row's screen at one design low flow (`null` when the reach carries no such cited flow). */
export function flowAt(
  row: { flow_screens: ThermalFlowScreen[] },
  label: string = CHRONIC_FLOW_LABEL,
): ThermalFlowScreen | null {
  return row.flow_screens.find((f) => f.flow_label === label) ?? null;
}

/**
 * The warmest fully-mixed temperature a row actually resolves at the chronic design flow — its
 * own where it has one, else the warmest of its heat-partition scenarios. `null` when none
 * resolve.
 *
 * Why this exists: the feed's own `RisThresholdCheck.exceeded` is evaluated at the row's
 * **binding** (lowest) design flow, which on a reach whose 1Q10 is 0 cfs is a dry channel — so
 * every biological limit there is crossed by construction and the screen honestly reports `null`
 * rather than `true` off a fabricated temperature. That is correct, and it is also a table of
 * nothing but dashes. This gives a surface a temperature it can name and compare against.
 */
export function warmestMixedC(row: ThermalDischargeScreen): number | null {
  const own = flowAt(row)?.mixed_c?.value;
  if (own != null) return round(own, 1);
  const scenario = row.scenarios
    .map((sc) => flowAt(sc)?.mixed_c?.value)
    .filter((v): v is number => v != null);
  return scenario.length > 0 ? round(Math.max(...scenario), 1) : null;
}

/**
 * The thermal screen for a site, or `null` when its bundle carries none.
 *
 * `null` is the honest answer for every site but the one the screen was built for: the page then
 * says no screen has been modelled rather than rendering a river the site does not sit on.
 */
export function buildThermal(slug?: string): ThermalScreenModel | null {
  if (!hasFeed("thermal", slug)) return null;
  const report = loadFeed<ThermalScreenReport>("thermal", slug);
  const meta = report.meta;
  const screens = report.screens ?? [];

  const criterionC = meta.daily_max_c ?? null;
  const ambientC = meta.ambient_c ?? null;
  const headroomC = criterionC != null && ambientC != null ? round(criterionC - ambientC, 1) : null;
  // `connector` (a live gage or a reported DMR station) and `document` are measurements; the
  // `reference` rung is the criteria table's own seasonal average standing in for one.
  const ambientGrounded = meta.ambient_source === "connector" || meta.ambient_source === "document";

  const modelled = screens.filter((s) => s.kind === "data_center");
  const observed = screens.filter((s) => s.kind === "permitted_discharger");
  const reported = observed.filter((s) => s.dmr?.effluent_c?.value != null);

  // The reach's capacity is a property of the REACH, not of any one row, so read it off whichever
  // row carries the chronic flow screen — they all screen the same water.
  const chronic = screens.map((s) => flowAt(s)).find((f) => f != null) ?? null;

  const mixedRows: ThermalMixedRow[] = [];
  const unbounded: ThermalDischargeScreen[] = [];
  for (const s of screens) {
    const f = flowAt(s);
    const mixed = f?.mixed_c?.value;
    const base = {
      facility: s.facility,
      npdesId: s.npdes_id ?? null,
      modelled: s.kind === "data_center",
    };
    if (f != null && mixed != null) {
      mixedRows.push({
        ...base,
        label: `${s.facility}${s.npdes_id ? ` · ${s.npdes_id}` : ""}`,
        scenario: null,
        mixedC: round(mixed, 1),
        overCriterion: f.mixed_over_criterion === true,
      });
      continue;
    }
    // No plottable temperature for the row as a whole. For a modelled facility that is the
    // *conservative bound* being off the liquid-water scale, not an absence of heat — so fall
    // through to its partitions, each of which does resolve, and record the row as unbounded so
    // the page can say why the whole-rejection bar is missing rather than quietly dropping it.
    if (s.kind !== "data_center" || s.scenarios.length === 0) continue;
    unbounded.push(s);
    for (const sc of s.scenarios) {
      const sf = flowAt(sc);
      const scMixed = sf?.mixed_c?.value;
      if (sf == null || scMixed == null) continue;
      mixedRows.push({
        ...base,
        label: `${s.facility} · ${sc.scenario.replace(/_/g, " ")}`,
        scenario: sc.scenario,
        mixedC: round(scMixed, 1),
        overCriterion: sf.mixed_over_criterion === true,
      });
    }
  }

  return {
    meta,
    river: meta.receiving_water ?? "the receiving water",
    criterionC,
    ambientC,
    ambientGrounded,
    headroomC,
    capacityMw: chronic?.thermal_capacity_mw ?? null,
    designFlowCfs: chronic?.design_flow.value ?? null,
    modelled,
    observed,
    reported,
    mixedRows,
    unbounded,
    caveats: meta.caveats ?? [],
  };
}
